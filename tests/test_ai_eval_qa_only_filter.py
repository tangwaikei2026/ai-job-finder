from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

import pytest

import src.analysis.ai_eval_regression as regression
from src.analysis.ai_eval_jobs import (
    AI_RELATIONS,
    CAREER_POOLS,
    CLASSIFICATION_INPUT_FIELDS,
    ROLE_FAMILIES,
    SENIORITY_LEVELS,
    classify_body_primary_ai_evaluation,
    job_content_sha256,
    normalize_content_text,
    normalized_job_content,
    run_analysis,
)
from src.analysis.ai_eval_regression import (
    RegressionDataIntegrityError,
    load_frozen_regression_cases,
    run_frozen_regression,
    validate_frozen_regression_cases,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPO_ROOT / "tests/fixtures/ai_eval_regression_set_v1_117_frozen.yaml"
)
CONFIG_PATH = REPO_ROOT / "config.yaml"


@pytest.fixture(scope="module")
def frozen_cases() -> list[dict[str, object]]:
    return load_frozen_regression_cases(FIXTURE_PATH)


def test_content_normalization_contract_and_hash() -> None:
    job = {
        "title": "  ＡＩ\t测试  ",
        "description": "第一行\r\n\r第二\t  行\n   \n",
        "requirements": " Python  ",
    }

    assert normalize_content_text(job["description"]) == "第一行\n第二 行"
    assert normalized_job_content(job) == (
        "ai 测试",
        "第一行\n第二 行",
        "python",
    )
    assert job_content_sha256(job) == (
        "698f54d594bee9646621ad40a3ce073696c24f05ae4bc2947bf69bf50e9b261f"
    )


def test_frozen_yaml_structure_enums_uniqueness_hash_and_evidence(
    frozen_cases: list[dict[str, object]],
) -> None:
    assert len(frozen_cases) == 117
    assert len({row["case_id"] for row in frozen_cases}) == 117
    assert len({row["job_id"] for row in frozen_cases}) == 117
    assert len({row["content_sha256"] for row in frozen_cases}) == 117
    assert len({normalized_job_content(row) for row in frozen_cases}) == 117
    assert Counter(row["expected_career_pool"] for row in frozen_cases) == {
        "P1": 66,
        "P2": 18,
        "REF": 12,
        "X": 21,
    }

    for row in frozen_cases:
        assert row["expected_role_family"] in ROLE_FAMILIES
        assert row["expected_ai_relation"] in AI_RELATIONS
        assert row["expected_seniority_level"] in SENIORITY_LEVELS
        assert row["expected_career_pool"] in CAREER_POOLS
        assert job_content_sha256(row) == row["content_sha256"]
        evidence = row["evidence"]
        assert isinstance(evidence, dict)
        for field, snippets in evidence.items():
            assert field in CLASSIFICATION_INPUT_FIELDS
            assert all(snippet in row[field] for snippet in snippets)
        if row["expected_career_pool"] == "X":
            assert row["expected_reason_codes"]
        if "ai_context_not_primary" in row["boundary_tags"]:
            assert row["expected_ai_relation"] == "ai_context_only"


def test_hash_failure_aborts_before_classification(
    frozen_cases: list[dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    damaged = copy.deepcopy(frozen_cases)
    damaged[0]["title"] = str(damaged[0]["title"]) + "（被篡改）"

    def must_not_classify(_: object) -> object:
        raise AssertionError("classification must not run after integrity failure")

    monkeypatch.setattr(regression, "classify_body_primary_ai_evaluation", must_not_classify)
    with pytest.raises(RegressionDataIntegrityError, match="hash failure"):
        validate_frozen_regression_cases(damaged)


def test_classifier_receives_only_three_content_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = regression.classify_body_primary_ai_evaluation
    seen_keys: list[set[str]] = []

    def recording_classifier(job: object) -> dict[str, object]:
        assert isinstance(job, dict)
        seen_keys.append(set(job))
        return original(job)

    monkeypatch.setattr(
        regression,
        "classify_body_primary_ai_evaluation",
        recording_classifier,
    )
    report = run_frozen_regression(FIXTURE_PATH)

    assert report["passed"] == 117
    assert len(seen_keys) == 117
    assert all(keys == set(CLASSIFICATION_INPUT_FIELDS) for keys in seen_keys)


def test_production_entrypoint_runs_all_117_frozen_cases() -> None:
    report = run_frozen_regression(FIXTURE_PATH)

    assert report["production_entrypoint"] == (
        "src.analysis.ai_eval_jobs.classify_body_primary_ai_evaluation"
    )
    assert report["classification_input_fields"] == [
        "title",
        "description",
        "requirements",
    ]
    assert report["total"] == report["passed"] == 117
    assert report["failed"] == 0
    assert report["field_errors"] == {
        "role_family": 0,
        "ai_relation": 0,
        "seniority_level": 0,
        "career_pool": 0,
        "reason_codes": 0,
    }
    assert report["career_pool_confusion"] == {
        "P1": {"P1": 66, "P2": 0, "REF": 0, "X": 0},
        "P2": {"P1": 0, "P2": 18, "REF": 0, "X": 0},
        "REF": {"P1": 0, "P2": 0, "REF": 12, "X": 0},
        "X": {"P1": 0, "P2": 0, "REF": 0, "X": 21},
    }
    assert report["positive_negative_confusion"] == {
        "positive": {"positive": 96, "negative": 0},
        "negative": {"positive": 0, "negative": 21},
    }
    assert report["failures"] == []
    assert all(
        row["passed"] == row["total"]
        for row in report["boundary_tag_results"]
    )


def test_security_experience_preference_is_not_a_hard_exclusion() -> None:
    result = classify_body_primary_ai_evaluation(
        {
            "title": "测试开发工程师",
            "description": "负责Agent产品功能、稳定性和端到端质量保障。",
            "requirements": "有安全测试经验者优先。",
        }
    )

    assert result["body_primary_ai_evaluation"]["career_pool"] == "P1"
    assert "domain_security" not in result["reason_codes"]


def test_project_owner_is_not_people_management() -> None:
    result = classify_body_primary_ai_evaluation(
        {
            "title": "高级测试开发工程师",
            "description": "担任项目Owner，推动跨团队协作并对项目质量负责。负责大模型产品质量保障。",
            "requirements": "本科及以上。",
        }
    )

    classification = result["body_primary_ai_evaluation"]
    assert classification["seniority_level"] == "senior"
    assert classification["career_pool"] == "P1"


def test_jobs_deduplicate_only_by_normalized_three_field_content(
    tmp_path: Path,
) -> None:
    jobs = [
        {
            "job_id": "same-id",
            "platform": "tencent",
            "company": "腾讯",
            "title": "AI测试开发工程师",
            "description": "负责大模型产品质量保障。",
            "requirements": "Python",
        },
        {
            "job_id": "same-id",
            "platform": "tencent",
            "company": "腾讯",
            "title": "AI测试开发工程师",
            "description": "负责Agent产品质量保障。",
            "requirements": "Python",
        },
        {
            "job_id": "different-id",
            "platform": "tencent",
            "company": "另一公司",
            "title": "ＡＩ测试开发工程师",
            "description": "  负责Agent产品质量保障。  ",
            "requirements": "PYTHON",
        },
    ]
    input_path = tmp_path / "jobs.json"
    input_path.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")

    _, _, analysis = run_analysis(
        input_path,
        config_path=CONFIG_PATH,
        output_dir=tmp_path / "output",
    )

    assert analysis["manifest"]["selected_raw_count"] == 3
    assert analysis["manifest"]["selected_job_count"] == 2
    assert analysis["manifest"]["duplicates_removed"] == 1
    assert analysis["raw_matches"][0]["included_after_content_deduplication"] is True
    assert analysis["raw_matches"][1]["included_after_content_deduplication"] is True
    assert analysis["raw_matches"][2]["included_after_content_deduplication"] is False
    assert analysis["raw_matches"][2]["duplicate_of_job_id"] == "same-id"
    assert analysis["methodology"]["deduplication_key"] == [
        "title",
        "description",
        "requirements",
    ]
