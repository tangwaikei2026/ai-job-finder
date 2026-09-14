"""Contract and metamorphic checks; no fixture expectation is rewritten."""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from src.analysis.ai_eval_jobs import classify_market, classify_personal_fit, job_content_sha256
from src.analysis.classification import classify_record
from src.analysis.market_rules import MARKET_FIELDS, validate_market_output
from src.analysis.pipeline import load_settings
from src.analysis.source_health import Health
from tools.market_oracle_baseline import evaluate, read_yaml, validate_oracle


@pytest.fixture(scope='module')
def oracle():
    return validate_oracle(read_yaml('tests/fixtures/market_oracle_v1.yaml'))


def text_job(title, description, requirements='熟悉软件工程。'):
    return dict(title=title, description=description, requirements=requirements,
                platform='synthetic', job_id='example', company='Example')


def test_frozen_sixty_exact_and_evidence(oracle):
    result = evaluate(oracle)
    assert result['metrics']['full_oracle_exact_match']['correct'] == 60
    for case in oracle:
        market = classify_market(case)
        validate_market_output(market)
        for field, quotes in market['evidence'].items():
            assert all(quote in case[field] for quote in quotes)


def test_identity_and_expected_labels_do_not_influence_predictions(oracle):
    for case in oracle:
        original = classify_market(case)
        changed = dict(case, case_id='unseen', job_id='unseen', company='unseen',
                       platform='unseen', content_sha256='0'*64, expected_in_scope=not original['in_scope'])
        assert classify_market(changed) == original
        only_content = {key: case[key] for key in ('title', 'description', 'requirements')}
        assert classify_market(only_content) == original


def test_responsibility_order_is_not_a_semantic_weight(oracle):
    for case in oracle:
        original = classify_market(case)
        shuffled = dict(case, description='。'.join(reversed(case['description'].split('。'))))
        actual = classify_market(shuffled)
        assert {f: original[f] for f in MARKET_FIELDS} == {f: actual[f] for f in MARKET_FIELDS}


@pytest.mark.parametrize('job,relation', [
    (text_job('评测平台开发工程师', '负责建设LLM Evaluation Infra，支撑模型评测执行和结果产出。'), 'core_ai_evaluation'),
    (text_job('测试开发工程师', '负责AI软件产品的测试执行、用例设计及质量保障。'), 'ai_product_quality'),
    (text_job('测试开发工程师', '负责Prompt/Agent/Chain等相关模块的质量保障工作。'), 'ai_product_quality'),
    (text_job('测试开发工程师', '负责传统软件测试执行，使用LLM生成测试用例，提升测试效率。'), 'ai_for_testing'),
    (text_job('测试开发工程师', '负责AI产品质量保障。使用LLM生成测试用例，提升测试效率。'), 'ai_product_quality'),
])
def test_protected_object_precedence(job, relation):
    result = classify_market(job)
    assert result['in_scope']
    assert result['ai_relation'] == relation
    validate_market_output(result)


@pytest.mark.parametrize('description', [
    '负责Agent应用开发，了解Benchmark工具。',
    '负责服务端研发，协助开展一次模型评测。',
    '负责AI应用研发，使用AI工具编程并进行单元测试。',
])
def test_weak_evidence_stops(description):
    result = classify_market(text_job('开发工程师', description))
    assert {key: result[key] for key in MARKET_FIELDS} == dict(in_scope=False,
        market_relevance=None, role_family=None, secondary_role_families=[], ai_relation=None)
    with pytest.raises(ValueError):
        classify_personal_fit(text_job('开发工程师', description), result)


def test_secondary_requires_accountable_deliverable():
    base = text_job('AI产品测试工程师', '负责AI产品功能测试与质量保障。了解Benchmark和Judge。')
    assert classify_market(base)['secondary_role_families'] == []
    base['description'] += '负责建设模型Benchmark、设计评分标准和评测数据集。'
    assert classify_market(base)['secondary_role_families'] == ['evaluation_engineering']


@pytest.mark.parametrize('changes', [
    {'secondary_role_families':['qa_test']},
    {'secondary_role_families':['development']*2},
    {'secondary_role_families':['development','operations','product']},
    {'secondary_role_families':['hybrid']},
    {'ai_relation':'ai_context_only'},
    {'in_scope':False},
])
def test_invalid_output_rejected(changes):
    result = classify_market(text_job('AI产品测试工程师','负责AI产品质量保障。'))
    result.update(changes)
    with pytest.raises(ValueError):
        validate_market_output(result)


def test_serialization_and_schema_safe_carry(oracle):
    versions = load_settings()[1]
    for case in oracle:
        row, market = classify_record('2026-09-11', case, Health(True,True), versions)
        if not market['in_scope']:
            assert row is None
            continue
        row = json.loads(json.dumps(row))
        validate_market_output(row)
        assert (row['platform'],row['job_id'],row['content_sha256']) == (
            case['platform'],case['job_id'],job_content_sha256(case))
        assert all(row[key] == market[key] for key in MARKET_FIELDS)
        broken = dict(case, description='',requirements='')
        health = Health(True,False,('DETAIL_FAILED_JOB_ID',))
        carried,_ = classify_record('2026-09-12',broken,health,versions,row)
        assert carried['content_sha256'] == row['content_sha256']
        assert carried['classification_status'] == 'carried_forward'
        legacy = deepcopy(row)
        del legacy['secondary_role_families']
        new,_ = classify_record('2026-09-12',broken,health,versions,legacy)
        assert new is None or new['classification_status'] != 'carried_forward'


def test_special_case_scan():
    from tools.market_v1_regression import special_case_scan
    assert special_case_scan()['status'] == 'PASS'


def test_conflicts_are_proved_from_unchanged_expectations(oracle):
    from src.analysis.ai_eval_regression import load_frozen_regression_cases
    from tools.market_v1_regression import LEGACY, proven_legacy_conflicts
    conflicts = proven_legacy_conflicts(oracle, load_frozen_regression_cases(LEGACY))
    identical = [c for c in conflicts if c['proof']=='IDENTICAL_FULL_CONTENT_SHA256']
    assert identical
    for conflict in identical:
        source = next(c for c in oracle if c['case_id']==conflict['oracle_case_id'])
        assert len(conflict['content_sha256']) == 64
        assert source['content_sha256'] == conflict['content_sha256']
        assert conflict['legacy'] != conflict['required']
    assert any(c['proof']=='FROZEN_CONTRACT_STOP_SEMANTICS' for c in conflicts)
