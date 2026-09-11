"""Offline diagnostic evaluator. Does not change classifier, rules or Oracle.

Usage: python tools/market_oracle_baseline.py --output-dir <new directory>
Missing classifier fields remain unavailable; they are never inferred from JD.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.analysis.ai_eval_jobs import classify_market, job_content_sha256

FIELDS = ('in_scope', 'market_relevance', 'role_family', 'secondary_role_families', 'ai_relation')
ROLES = {'qa_test','quality_engineering','evaluation_engineering','algorithm_research','development','product','operations','domain_expert'}
RELATIONS = {'core_ai_evaluation','ai_product_quality','ai_for_testing'}
BOUNDARIES = ('N-03','N-04','N-11','N-13','N-14','B-03','B-05','B-09','X-20','P-12')
PRECEDENCE = ('SCOPE_FN','SCOPE_FP','RELEVANCE_WRONG','PRIMARY_ROLE_WRONG','AI_RELATION_WRONG',
              'SECONDARY_ROLE_MISSING','SECONDARY_ROLE_EXTRA','SECONDARY_FIELD_UNAVAILABLE','SECONDARY_OUTPUT_INVALID')

class IntegrityError(ValueError):
    pass

class UniqueLoader(yaml.SafeLoader):
    pass

def unique_mapping(loader, node, deep=False):
    result={}
    for key,value in node.value:
        k=loader.construct_object(key,deep=deep)
        if k in result:
            raise IntegrityError('DUPLICATE_YAML_KEY: '+str(k))
        result[k]=loader.construct_object(value,deep=deep)
    return result

UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,unique_mapping)

def read_yaml(path):
    return yaml.load(Path(path).read_text(),Loader=UniqueLoader)

def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def expected(case):
    return {f:case['expected_'+f] for f in FIELDS}

def validate_oracle(doc, expected_count=60, root=ROOT):
    cases=doc['cases']
    if len(cases)!=expected_count or len({r['case_id'] for r in cases})!=expected_count:
        raise IntegrityError('ORACLE_CASE_COUNT_OR_DUPLICATE')
    if len({(r['platform'],r['job_id']) for r in cases})!=expected_count:
        raise IntegrityError('ORACLE_IDENTITY_DUPLICATE')
    contract=doc['metadata']['contract']
    if sha_file(root/contract['file'])!=contract['file_sha256']:
        raise IntegrityError('FROZEN_CONTRACT_HASH_CHANGED')
    for r in cases:
        for f in ['case_id','platform','job_id','content_sha256']:
            if not isinstance(r.get(f),str) or not r[f]:
                raise IntegrityError('ORACLE_CONTENT_BINDING_FAIL: '+f)
        if not re.fullmatch('[0-9a-f]{64}',r['content_sha256']) or job_content_sha256(r)!=r['content_sha256']:
            raise IntegrityError('ORACLE_CONTENT_BINDING_FAIL: '+r['case_id'])
        o=expected(r)
        if type(o['in_scope']) is not bool:
            raise IntegrityError('INCOMPLETE_ORACLE: '+r['case_id'])
        if o['in_scope']:
            if o['market_relevance'] not in {'core','adjacent'} or o['role_family'] not in ROLES or o['ai_relation'] not in RELATIONS:
                raise IntegrityError('INVALID_ORACLE_ENUM')
            s=o['secondary_role_families']
            if not isinstance(s,list) or len(s)>2 or len(s)!=len(set(s)) or not set(s)<=ROLES or o['role_family'] in s:
                raise IntegrityError('INVALID_ORACLE_SECONDARY')
        elif o!=dict(in_scope=False,market_relevance=None,role_family=None,secondary_role_families=[],ai_relation=None):
            raise IntegrityError('ORACLE_STOP_SEMANTICS_FAIL')
        if r['provenance']['decision_status']!='accepted':
            raise IntegrityError('INCOMPLETE_HUMAN_DECISION')
        if set(r['evidence'])!={'title','description','requirements'}:
            raise IntegrityError('INVALID_EVIDENCE_FIELDS')
        for f,quotes in r['evidence'].items():
            if not isinstance(quotes,list) or any(not q or q not in r[f] for q in quotes):
                raise IntegrityError('EVIDENCE_NOT_IN_BOUND_JD: '+r['case_id'])
    return cases

def ratio(numerator,denominator):
    return numerator/denominator if denominator else None

def prf(tp,fp,fn):
    return dict(precision=ratio(tp,tp+fp),recall=ratio(tp,tp+fn),F1=ratio(2*tp,2*tp+fp+fn))

def score_case(case,raw):
    if type(raw.get('in_scope')) is not bool:
        raise IntegrityError('CLASSIFIER_SCOPE_OUTPUT_INVALID')
    exp=expected(case)
    pred={f:raw.get(f) for f in FIELDS}
    unavailable=[f for f in FIELDS if f not in raw or raw[f] is None]
    codes=[];wrong=[]
    match={'in_scope':exp['in_scope']==pred['in_scope']}
    if not match['in_scope']:
        codes.append('SCOPE_FN' if exp['in_scope'] else 'SCOPE_FP');wrong.append('in_scope')
    secondary_counts=None
    if exp['in_scope']:
        for field,code in [('market_relevance','RELEVANCE_WRONG'),('role_family','PRIMARY_ROLE_WRONG'),('ai_relation','AI_RELATION_WRONG')]:
            match[field]=field not in unavailable and pred[field]==exp[field]
            if not match[field]:codes.append(code);wrong.append(field)
        valid=isinstance(pred['secondary_role_families'],list) and all(isinstance(s,str) for s in pred['secondary_role_families'])
        predicted_set=set(pred['secondary_role_families']) if valid else set()
        expected_set=set(exp['secondary_role_families'])
        missing=sorted(expected_set-predicted_set);extra=sorted(predicted_set-expected_set)
        match['secondary_role_families']=valid and len(predicted_set)==len(pred['secondary_role_families']) and predicted_set==expected_set
        if not match['secondary_role_families']:
            wrong.append('secondary_role_families')
            if missing:codes.append('SECONDARY_ROLE_MISSING')
            if extra:codes.append('SECONDARY_ROLE_EXTRA')
            if 'secondary_role_families' in unavailable:codes.append('SECONDARY_FIELD_UNAVAILABLE')
            elif not valid or len(predicted_set)!=len(pred['secondary_role_families']):codes.append('SECONDARY_OUTPUT_INVALID')
        secondary_counts=dict(tp=len(expected_set&predicted_set),fp=len(extra),fn=len(missing),missing=missing,extra=extra)
    if len(wrong)>1:codes.append('MULTI_FIELD_WRONG')
    primary=next((c for c in PRECEDENCE if c in codes),None)
    return dict(case_id=case['case_id'],platform=case['platform'],job_id=case['job_id'],content_sha256=case['content_sha256'],
                expected=exp,predicted=pred,raw_prediction=raw,unavailable_fields=unavailable,
                evaluated_fields=list(match),field_matches=match,full_oracle_exact_match=all(match.values()),
                failure_fields=wrong,failure_codes=codes,primary_failure=primary,secondary_counts=secondary_counts,
                boundary_tags=case['boundary_tags'])

def evaluate(cases,classifier=classify_market):
    # Only the immutable JD's three text fields enter the unmodified classifier.
    records=[score_case(c,classifier({f:c[f] for f in ['title','description','requirements']})) for c in cases]
    tp=sum(r['expected']['in_scope'] and r['predicted']['in_scope'] for r in records)
    fp=sum(not r['expected']['in_scope'] and r['predicted']['in_scope'] for r in records)
    tn=sum(not r['expected']['in_scope'] and not r['predicted']['in_scope'] for r in records)
    fn=sum(r['expected']['in_scope'] and not r['predicted']['in_scope'] for r in records)
    positive=[r for r in records if r['expected']['in_scope']]
    n=len(positive)
    fields={f:dict(correct=sum(r['field_matches'][f] for r in positive),denominator=n,
                   accuracy=ratio(sum(r['field_matches'][f] for r in positive),n),
                   unavailable_count=sum(f in r['unavailable_fields'] for r in positive)) for f in FIELDS[1:]}
    stp=sum(r['secondary_counts']['tp'] for r in positive)
    sfp=sum(r['secondary_counts']['fp'] for r in positive)
    sfn=sum(r['secondary_counts']['fn'] for r in positive)
    full=sum(r['full_oracle_exact_match'] for r in records)
    failures=[r for r in records if not r['full_oracle_exact_match']]
    metrics=dict(case_count=len(records),expected_positive_count=n,
                 scope=dict(TP=tp,FP=fp,TN=tn,FN=fn,**prf(tp,fp,fn),accuracy=ratio(tp+tn,len(records))),
                 conditional_fields=fields,
                 secondary=dict(exact_set_match=fields['secondary_role_families'],micro=dict(TP=stp,FP=sfp,FN=sfn,**prf(stp,sfp,sfn))),
                 full_oracle_exact_match=dict(correct=full,denominator=len(records),accuracy=ratio(full,len(records))),
                 failure_case_count=len(failures),primary_failure_counts=dict(collections.Counter(r['primary_failure'] for r in failures)),
                 detailed_failure_counts=dict(collections.Counter(c for r in failures for c in r['failure_codes'])))
    assert sum(metrics['primary_failure_counts'].values())==len(failures)
    return dict(metrics=metrics,records=records,boundary_slice=[r for cid in BOUNDARIES for r in records if r['case_id']==cid])

def pct(value):
    return 'N/A（分母为0）' if value is None else f'{value:.2%}'

def render_report(result):
    m=result['metrics'];s=m['scope'];f=m['conditional_fields'];sec=m['secondary']['micro'];full=m['full_oracle_exact_match']
    lines=['# Market frozen 60-case baseline v1','',
           '这是purposefully sampled diagnostic/regression set；以下指标只描述本60条诊断集，不代表生产总体或真实市场准确率。', '',
           f"冻结60/60：delta 23 ACCEPT + 2 CHANGE，既有35 accepted不变。Scope TP={s['TP']}、FP={s['FP']}、TN={s['TN']}、FN={s['FN']}；precision={pct(s['precision'])}、recall={pct(s['recall'])}、F1={pct(s['F1'])}。",'',
           f"完整Oracle匹配 {full['correct']}/{full['denominator']}（{pct(full['accuracy'])}）；失败case {m['failure_case_count']}。分类器未修改，未做repair。", '',
           '| 字段/指标 | 正确数 / 分母 | 结果 |', '| --- | --- | --- |']
    for field in ['market_relevance','role_family','ai_relation','secondary_role_families']:
        a=f[field];lines.append(f"| {field} exact | {a['correct']} / {a['denominator']} | {pct(a['accuracy'])} |")
    lines += ['', f"Secondary集合micro：TP={sec['TP']}、FP={sec['FP']}、FN={sec['FN']}；precision={pct(sec['precision'])}、recall={pct(sec['recall'])}、F1={pct(sec['F1'])}。",'',
              '所有条件字段仅在expected_in_scope=true的case上评价，包括scope FN；不会用负例的null提高准确率。负例full match只看scope=false。每条相同权重。', '',
              '当前classifier不输出market_relevance或secondary_role_families。原始输出完整保存；投影null表示未输出，不能当成预测NONE。缺失字段exact不计正确（即使expected secondary=[]）；集合micro中缺失输出产生零个预测成员，precision分母为0时显示N/A，F1按2TP/(2TP+FP+FN)直接计算。', '',
              '因此完整匹配及这两项字段指标包含输出契约未实现的影响；它们不是阈值问题的证据。failure records保留unavailable_fields供Diagnosis区分。没有推断或补造core/secondary预测。', '',
              '| primary_failure（互斥） | case数 |','| --- | --- |']
    lines += [f'| {k} | {v} |' for k,v in m['primary_failure_counts'].items()]
    lines += ['', '详细failure code可多选；MULTI_FIELD_WRONG按不同字段数>1判定，不因同一secondary缺失/多出而重复计算字段。primary precedence为scope→relevance→primary→relation→secondary，仅用于汇总。', '',
              'Boundary slice（无额外权重）：', '', '| Case | Expected | Predicted | Failure fields |','| --- | --- | --- | --- |']
    for r in result['boundary_slice']:
        enc=lambda v:json.dumps(v,ensure_ascii=False,separators=(',',':'))
        lines.append(f"| {r['case_id']} | `{enc(r['expected'])}` | `{enc(r['predicted'])}` | {', '.join(r['failure_fields']) or 'NONE'} |")
    lines += ['', '机器输入：[完整baseline](market_baseline_v1.json) · [逐case failures CSV](market_baseline_failures_v1.csv)。CSV每失败case一行；expected/predicted、failure codes/fields及secondary集合差使用JSON单元格保存。', '',
              'Source/contract/classifier SHA、git commit及评估政策见baseline JSON metadata；冻结来源与人工原文见fixture provenance及market_batch_1_7_sources。', '',
              'READY_FOR_DIAGNOSIS: YES；READY_FOR_CLASSIFIER_REPAIR: NO。']
    return '\n'.join(lines)+'\n'

def write_new(path,content):
    data=content.encode() if isinstance(content,str) else content
    if path.exists():
        if path.read_bytes()!=data:raise IntegrityError('REFUSE_OVERWRITE: '+str(path))
    else:path.write_bytes(data)

def save_result(result,output_dir):
    output_dir.mkdir(parents=True,exist_ok=True)
    write_new(output_dir/'market_baseline_v1.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    buf=io.StringIO(newline='')
    cols=['case_id','platform','job_id','content_sha256','primary_failure','failure_codes','failure_fields','expected','predicted','unavailable_fields','secondary_counts','boundary_tags']
    writer=csv.DictWriter(buf,fieldnames=cols);writer.writeheader()
    for r in result['records']:
        if r['full_oracle_exact_match']:continue
        writer.writerow({k:json.dumps(r[k],ensure_ascii=False,separators=(',',':')) if isinstance(r[k],(dict,list)) or r[k] is None else r[k] for k in cols})
    write_new(output_dir/'market_baseline_failures_v1.csv',buf.getvalue())
    write_new(output_dir/'market_baseline_report_v1.md',render_report(result))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oracle',type=Path,default=ROOT/'tests/fixtures/market_oracle_v1.yaml')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    doc=read_yaml(args.oracle);cases=validate_oracle(doc)
    result=evaluate(cases)
    result['metadata']=dict(kind='BASELINE_NOT_REPAIR',oracle_file=str(args.oracle),oracle_sha256=sha_file(args.oracle),
        contract=doc['metadata']['contract'],classifier_file='src/analysis/ai_eval_jobs.py',
        classifier_source_sha256=sha_file(ROOT/'src/analysis/ai_eval_jobs.py'),
        classifier_config_sha256=sha_file(ROOT/'configs/analysis/versions.yaml'),
        classifier_git_commit=doc['metadata']['git_commit_sha'],
        current_predictions_sha256=digest([r['raw_prediction'] for r in result['records']]),
        conditional_population='expected_in_scope=true including scope FN',
        unavailable_secondary_policy='exact=false; zero predicted set members for micro; missing preserved as null',
        zero_denominator_policy='null; F1=2TP/(2TP+FP+FN)',sample_kind='purposefully sampled diagnostic/regression set',
        primary_failure_precedence=list(PRECEDENCE))
    save_result(result,args.output_dir)
    print(json.dumps(result['metrics'],ensure_ascii=False,indent=2))

if __name__=='__main__':main()
