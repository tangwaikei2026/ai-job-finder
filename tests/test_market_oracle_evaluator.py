"""Tests for scoring and binding, never assertions that classifier must fit Oracle."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('market_oracle_baseline',ROOT/'tools/market_oracle_baseline.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def case(cid,scope=True,secondary=None):
    oracle=dict(in_scope=scope,market_relevance='core' if scope else None,
        role_family='quality_engineering' if scope else None,
        secondary_role_families=(secondary or []) if scope else [],ai_relation='ai_product_quality' if scope else None)
    return dict(case_id=cid,platform='test',job_id=cid,content_sha256='a'*64,
                title=cid,description='JD',requirements='requirements',boundary_tags=[],
                **{'expected_'+f:v for f,v in oracle.items()})

def prediction(row,**overrides):
    return {**m.expected(row),**overrides}

def test_scope_and_conditional_denominators_hand_calculated():
    cases=[case('tp'),case('fn'),case('fp',False),case('tn',False)]
    predictions={c['case_id']:prediction(c) for c in cases}
    predictions['fn']['in_scope']=False;predictions['fp']['in_scope']=True
    seen=[]
    def classifier(jd):
        seen.append(jd)
        return predictions[jd['title']]
    result=m.evaluate(cases,classifier);metric=result['metrics']
    assert metric['scope']==dict(TP=1,FP=1,TN=1,FN=1,precision=.5,recall=.5,F1=.5,accuracy=.5)
    assert metric['conditional_fields']['role_family']['denominator']==2
    assert metric['conditional_fields']['role_family']['correct']==2 # Includes scope FN.
    assert metric['full_oracle_exact_match']['correct']==2
    assert metric['primary_failure_counts']=={'SCOPE_FN':1,'SCOPE_FP':1}
    assert all(set(jd)=={'title','description','requirements'} for jd in seen)

def test_negative_full_match_ignores_non_scope_fields():
    row=case('out',False)
    result=m.score_case(row,dict(in_scope=False,role_family='development',ai_relation='none'))
    assert result['evaluated_fields']==['in_scope']
    assert result['full_oracle_exact_match'] is True and result['failure_codes']==[]
    metrics=m.evaluate([row],lambda _:dict(in_scope=False))['metrics']
    assert metrics['conditional_fields']['role_family']['denominator']==0
    assert metrics['conditional_fields']['role_family']['accuracy'] is None

def test_secondary_exact_set_and_micro_are_distinct():
    a=case('a',secondary=['evaluation_engineering'])
    b=case('b',secondary=['development'])
    p={'a':prediction(a,secondary_role_families=['evaluation_engineering','development']),
       'b':prediction(b,secondary_role_families=[])}
    result=m.evaluate([a,b],lambda jd:p[jd['title']])
    sec=result['metrics']['secondary']
    assert sec['exact_set_match']['correct']==0
    assert sec['micro']==dict(TP=1,FP=1,FN=1,precision=.5,recall=.5,F1=.5)
    assert result['records'][0]['secondary_counts']['extra']==['development']
    assert 'SECONDARY_ROLE_EXTRA' in result['records'][0]['failure_codes']
    assert 'SECONDARY_ROLE_MISSING' in result['records'][1]['failure_codes']

def test_secondary_order_does_not_change_set_match():
    row=case('x',secondary=['evaluation_engineering','development'])
    scored=m.score_case(row,prediction(row,secondary_role_families=['development','evaluation_engineering']))
    assert scored['full_oracle_exact_match'] is True

def test_missing_secondary_not_forged_into_explicit_none():
    row=case('x');raw=prediction(row);raw.pop('secondary_role_families')
    result=m.score_case(row,raw)
    assert result['predicted']['secondary_role_families'] is None
    assert result['field_matches']['secondary_role_families'] is False
    assert result['primary_failure']=='SECONDARY_FIELD_UNAVAILABLE'
    metrics=m.evaluate([row],lambda _:raw)['metrics']['secondary']['micro']
    assert metrics['precision'] is metrics['recall'] is metrics['F1'] is None

def test_missing_relevance_and_secondary_keep_scope_independent():
    row=case('x',secondary=['evaluation_engineering']);raw=prediction(row)
    raw.pop('market_relevance');raw.pop('secondary_role_families')
    scored=m.score_case(row,raw)
    assert scored['failure_fields']==['market_relevance','secondary_role_families']
    assert scored['primary_failure']=='RELEVANCE_WRONG'
    assert set(scored['failure_codes'])=={'RELEVANCE_WRONG','SECONDARY_ROLE_MISSING','SECONDARY_FIELD_UNAVAILABLE','MULTI_FIELD_WRONG'}
    metrics=m.evaluate([row],lambda _:raw)['metrics']
    assert metrics['scope']['F1']==1
    assert metrics['secondary']['micro']==dict(TP=0,FP=0,FN=1,precision=None,recall=0,F1=0)

def test_secondary_missing_and_extra_is_one_wrong_field():
    row=case('x',secondary=['evaluation_engineering'])
    scored=m.score_case(row,prediction(row,secondary_role_families=['development']))
    assert scored['failure_fields']==['secondary_role_families']
    assert set(scored['failure_codes'])=={'SECONDARY_ROLE_MISSING','SECONDARY_ROLE_EXTRA'}
    assert scored['primary_failure']=='SECONDARY_ROLE_MISSING'

def test_primary_failure_precedence_does_not_erase_details():
    row=case('x',secondary=['evaluation_engineering'])
    scored=m.score_case(row,dict(in_scope=False,market_relevance='adjacent',role_family='development',
                                secondary_role_families=['algorithm_research'],ai_relation='ai_for_testing'))
    assert scored['primary_failure']=='SCOPE_FN'
    assert set(scored['failure_fields'])==set(m.FIELDS)
    assert set(scored['failure_codes'])=={'SCOPE_FN','RELEVANCE_WRONG','PRIMARY_ROLE_WRONG','AI_RELATION_WRONG',
                                        'SECONDARY_ROLE_MISSING','SECONDARY_ROLE_EXTRA','MULTI_FIELD_WRONG'}

def test_invalid_scope_fail_closed():
    with pytest.raises(m.IntegrityError,match='CLASSIFIER_SCOPE_OUTPUT_INVALID'):
        m.score_case(case('x'),dict(in_scope='false'))

def frozen():
    return m.read_yaml(ROOT/'tests/fixtures/market_oracle_v1.yaml')

def test_frozen_complete_unique_and_content_bound():
    doc=frozen();rows=m.validate_oracle(doc)
    assert doc['metadata']['complete']==60 and doc['metadata']['status']=='FROZEN'
    assert doc['metadata']['delta_decisions']=={'ACCEPT':23,'CHANGE':2,'KEEP_OPEN':0}
    by_id={r['case_id']:r for r in rows}
    for cid in ['N-04','B-03']:
        row=by_id[cid]
        assert row['expected_market_relevance']=='adjacent'
        codes={e['code'] for e in row['provenance']['normalization_history']}
        assert {'HUMAN_SEMANTIC_CHANGE','MECHANICAL_HUMAN_INPUT_NORMALIZATION'}<=codes
    assert by_id['B-01']['expected_ai_relation']=='core_ai_evaluation'
    assert by_id['X-20']['expected_role_family']=='development'
    assert by_id['P-12']['expected_secondary_role_families']==[]

@pytest.mark.parametrize('mutation',['body','hash_prefix','identity','duplicate_case','out_scope_fields'])
def test_frozen_validator_rejects_broken_binding_or_oracle(mutation):
    doc=frozen()
    if mutation=='body':doc['cases'][0]['description']+=' changed'
    elif mutation=='hash_prefix':doc['cases'][0]['content_sha256']=doc['cases'][0]['content_sha256'][:12]
    elif mutation=='identity':doc['cases'][0]['job_id']=''
    elif mutation=='duplicate_case':doc['cases'][1]['case_id']=doc['cases'][0]['case_id']
    else:doc['cases'][0]['expected_role_family']='qa_test'
    with pytest.raises(m.IntegrityError):m.validate_oracle(doc)

def test_duplicate_yaml_keys_rejected(tmp_path):
    path=tmp_path/'bad.yaml';path.write_text('expected_in_scope: true\nexpected_in_scope: false\n')
    with pytest.raises(m.IntegrityError,match='DUPLICATE_YAML_KEY'):m.read_yaml(path)

def test_output_refuses_overwriting_different_results(tmp_path):
    path=tmp_path/'result';m.write_new(path,'original')
    with pytest.raises(m.IntegrityError,match='REFUSE_OVERWRITE'):m.write_new(path,'changed')
    assert path.read_text()=='original'
