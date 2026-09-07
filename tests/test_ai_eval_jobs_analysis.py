from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.analysis.ai_eval_jobs import load_jobs, resolve_input_path, run_analysis


def _write_config(path: Path) -> Path:
    path.write_text(
        """platforms:
  tencent:
    enabled: true
    name: 腾讯
  feishu:
    enabled: true
    name: 飞书招聘
    companies:
      - name: MiniMax
  disabled:
    enabled: false
    name: 未启用公司
""",
        encoding="utf-8",
    )
    return path


def _write_jobs(path: Path, jobs: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
    return path


def test_run_analysis_selects_extracts_and_respects_company_scope(
    tmp_path: Path,
) -> None:
    config_path = _write_config(tmp_path / "config.yaml")
    input_path = _write_jobs(
        tmp_path / "2026-07-08.json",
        [
            {
                "job_id": "1",
                "platform": "tencent",
                "company": "腾讯",
                "title": "大模型测试工程师",
                "description": "负责大模型产品质量保障、评测体系和Benchmark建设，使用Python处理数据。\u2028第二段。",
                "requirements": "本科及以上学历，计算机相关专业，三年以上评测经验，有大模型项目经验，沟通协作能力强。",
                "city_norm": ["北京"],
                "education": "本科",
                "experience": "3年以上",
                "url": "https://example.test/1",
            },
            {
                "job_id": "2",
                "platform": "feishu",
                "company": "MiniMax",
                "title": "Agent测试开发工程师",
                "description": "负责Agent产品质量保障和评测体系搭建。",
                "requirements": "有AI产品经验，具备跨团队沟通能力。",
                "city_norm": ["上海", "深圳"],
                "education": "硕士",
                "experience": "5年以上",
                "url": "https://example.test/2",
            },
            {
                "job_id": "3",
                "platform": "feishu",
                "company": "未配置公司",
                "title": "Agent评测工程师",
                "description": "负责Agent评测。",
                "requirements": "本科。",
            },
            {
                "job_id": "4",
                "platform": "disabled",
                "company": "未启用公司",
                "title": "AI评测工程师",
                "description": "负责模型评测。",
                "requirements": "本科。",
            },
            {
                "job_id": "5",
                "platform": "tencent",
                "company": "腾讯",
                "title": "硬件测试工程师",
                "description": "负责芯片测试。",
                "requirements": "三年以上经验。",
                "city_norm": ["北京"],
                "education": "本科",
                "experience": "3年以上",
            },
        ],
    )

    json_path, report_path, analysis = run_analysis(
        input_path,
        config_path=config_path,
        output_dir=tmp_path / "output",
        generated_at="2026-08-20T10:00:00+08:00",
    )

    assert json_path.exists()
    assert report_path.exists()
    assert analysis["manifest"]["eligible_job_count"] == 3
    assert analysis["manifest"]["selected_raw_count"] == 2
    assert analysis["manifest"]["selected_job_count"] == 2
    assert analysis["data_quality"]["configured_companies_without_matches"] == []
    assert {row["cohort"] for row in analysis["matched_jobs"]} == {
        "ai_product_quality"
    }
    skill_counts = {row["name"]: row["count"] for row in analysis["skills"]}
    assert skill_counts["评测体系与指标设计"] == 2
    assert skill_counts["Agent/智能体"] == 1
    assert skill_counts["Python"] == 1
    requirement_counts = {
        row["name"]: row["count"] for row in analysis["requirements"]
    }
    assert requirement_counts["沟通协作能力"] == 2
    assert requirement_counts["本科及以上学历"] == 1
    raw_matches = analysis["raw_matches"]
    assert len(raw_matches) == 2
    assert raw_matches[0]["job_id"] == "1"
    assert raw_matches[0]["company"] == "腾讯"
    assert raw_matches[0]["url"] == "https://example.test/1"
    assert raw_matches[0]["description"].startswith("负责大模型产品质量保障")
    assert raw_matches[0]["requirements"].startswith("本科及以上")
    assert raw_matches[0]["city_norm"] == ["北京"]
    assert raw_matches[0]["education"] == "本科"
    assert raw_matches[0]["experience"] == "3年以上"
    assert raw_matches[0]["selection_rule_id"] == (
        "qa_test_ai_product_quality_p1"
    )
    assert "进入 P1 池" in raw_matches[0]["selection_reason"]
    assert raw_matches[0]["body_primary_ai_evaluation"] == {
        "role_family": "qa_test",
        "ai_relation": "ai_product_quality",
        "seniority_level": "regular",
        "career_pool": "P1",
    }
    assert raw_matches[0]["selection_evidence"]["role"]["field"] == "title"
    assert raw_matches[0]["selection_evidence"]["ai_primary_duty"][
        "field"
    ] == "description"
    details_jsonl = Path(analysis["manifest"]["raw_matches_jsonl_file"])
    details_report = Path(analysis["manifest"]["raw_matches_report_file"])
    exclusions_jsonl = Path(
        analysis["manifest"]["excluded_jobs_jsonl_file"]
    )
    exclusion_report = Path(
        analysis["manifest"]["exclusion_report_file"]
    )
    assert details_jsonl.exists()
    assert details_report.exists()
    assert exclusions_jsonl.exists()
    assert exclusion_report.exists()
    detail_lines = details_jsonl.read_text(encoding="utf-8").splitlines()
    assert len(detail_lines) == 2
    assert [json.loads(line)["job_id"] for line in detail_lines] == ["1", "2"]
    details_text = details_report.read_text(encoding="utf-8")
    assert "## 1. 大模型测试工程师" in details_text
    assert "- city_norm: 北京" in details_text
    assert "- education: 本科" in details_text
    assert "- experience: 3年以上" in details_text
    report_text = report_path.read_text(encoding="utf-8")
    assert "输入为" in report_text
    assert "## 城市分布" in report_text
    assert "## 学历门槛" in report_text
    assert "## 专业背景" in report_text
    assert "## 项目经验" in report_text
    assert "占全部岗位" in report_text
    city_rows = {row["name"]: row for row in analysis["cities"]}
    assert city_rows["北京"] == {
        "name": "北京",
        "count": 1,
        "share": 0.5,
        "example_titles": ["大模型测试工程师"],
    }
    assert {row["name"] for row in analysis["education"]} == {"本科", "硕士"}
    assert analysis["majors"][0]["name"] == "计算机/软件工程"
    assert analysis["project_experience"][0]["name"] == "AI/大模型落地经验"
    companies = {row["name"]: row for row in analysis["companies"]}
    assert companies["腾讯"]["all_job_count"] == 2
    assert companies["腾讯"]["all_job_share"] == 0.6667
    assert len(exclusions_jsonl.read_text(encoding="utf-8").splitlines()) == 3
    assert "排除原因分布" in exclusion_report.read_text(encoding="utf-8")
    assert json.loads(json_path.read_text(encoding="utf-8")) == analysis


def test_run_analysis_deduplicates_by_content(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path / "config.yaml")
    base_job = {
        "platform": "tencent",
        "company": "腾讯",
        "title": "AI测试开发工程师",
        "description": "负责大模型产品质量保障和评测平台建设。",
        "requirements": "有Python和测试经验。",
    }
    input_path = _write_jobs(
        tmp_path / "jobs.json",
        [
            {**base_job, "job_id": "first"},
            {**base_job, "job_id": "second"},
        ],
    )

    _, _, analysis = run_analysis(
        input_path,
        config_path=config_path,
        output_dir=tmp_path / "output",
    )

    assert analysis["manifest"]["selected_raw_count"] == 2
    assert analysis["manifest"]["selected_job_count"] == 1
    assert analysis["manifest"]["duplicates_removed"] == 1
    assert analysis["data_quality"]["content_duplicates_in_eligible_jobs"] == 1
    assert analysis["matched_jobs"][0]["job_id"] == "first"
    assert analysis["raw_matches"][0][
        "included_after_content_deduplication"
    ] is True
    assert analysis["raw_matches"][1][
        "included_after_content_deduplication"
    ] is False
    assert analysis["raw_matches"][1]["duplicate_of_match_number"] == 1
    assert analysis["raw_matches"][1]["duplicate_of_job_id"] == "first"


def test_run_analysis_records_missing_source_fields(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path / "config.yaml")
    input_path = _write_jobs(
        tmp_path / "jobs.json",
        [
            {
                "job_id": "1",
                "platform": "tencent",
                "company": "腾讯",
                "title": "大模型测试开发工程师",
                "description": "负责大模型产品质量保障。",
                "requirements": "",
            }
        ],
    )

    _, _, analysis = run_analysis(
        input_path,
        config_path=config_path,
        output_dir=tmp_path / "output",
    )

    assert analysis["manifest"]["selected_job_count"] == 1
    assert analysis["data_quality"]["missing_fields_in_selected_jobs"] == {
        "title": 0,
        "description": 0,
        "requirements": 1,
    }
    assert analysis["skills"][0]["name"] == "大语言模型/LLM"
    assert analysis["requirements"] == []


def test_education_prefers_structured_value_then_falls_back_to_text(
    tmp_path: Path,
) -> None:
    config_path = _write_config(tmp_path / "config.yaml")
    input_path = _write_jobs(
        tmp_path / "jobs.json",
        [
            {
                "job_id": "structured",
                "platform": "tencent",
                "company": "腾讯",
                "title": "AI测试开发工程师",
                "description": "负责大模型产品质量保障和评测",
                "requirements": "本科及以上学历",
                "education": "硕士",
                "experience": "三年以上工作经验",
            },
            {
                "job_id": "fallback",
                "platform": "tencent",
                "company": "腾讯",
                "title": "Agent测试开发工程师",
                "description": "负责Agent产品质量保障和评测",
                "requirements": "本科及以上学历",
                "education": "",
                "experience": "",
            },
        ],
    )

    _, _, analysis = run_analysis(
        input_path,
        config_path=config_path,
        output_dir=tmp_path / "output",
    )

    education_counts = {
        row["name"]: row["count"] for row in analysis["education"]
    }
    experience_counts = {
        row["name"]: row["count"] for row in analysis["experience"]
    }
    assert education_counts == {"本科及以上": 1, "硕士": 1}
    assert experience_counts == {"3年以上": 1}
    assert analysis["data_quality"][
        "missing_threshold_fields_in_selected_jobs"
    ] == {
        "city_norm": 2,
        "education_structured": 1,
        "education_after_fallback": 0,
        "experience": 1,
    }


def test_load_jobs_rejects_structural_changes(tmp_path: Path) -> None:
    input_path = tmp_path / "jobs.json"
    input_path.write_text('{"jobs": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON array"):
        load_jobs(input_path)

    input_path.write_text('[{"title": "ok"}, "not-an-object"]', encoding="utf-8")
    with pytest.raises(ValueError, match="row 2 must be a JSON object"):
        load_jobs(input_path)


def test_resolve_input_path_uses_beijing_date_and_accepts_explicit_date() -> None:
    utc_time = datetime(2026, 8, 31, 16, 30, tzinfo=timezone.utc)

    assert resolve_input_path(now=utc_time) == Path(
        "data/clean/2026-09-01.json"
    )
    assert resolve_input_path(analysis_date="2026-07-08") == Path(
        "data/clean/2026-07-08.json"
    )
    with pytest.raises(ValueError, match="mutually exclusive"):
        resolve_input_path(Path("jobs.json"), analysis_date="2026-07-08")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        resolve_input_path(analysis_date="2026/07/08")


def test_run_analysis_accounts_for_each_exclusion_reason(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path / "config.yaml")
    input_path = _write_jobs(
        tmp_path / "jobs.json",
        [
            {
                "job_id": "outside",
                "platform": "feishu",
                "company": "未配置公司",
                "title": "Agent测试开发工程师",
                "description": "负责Agent产品质量保障和评测",
                "requirements": "本科",
            },
            {
                "job_id": "missing-title",
                "platform": "tencent",
                "company": "腾讯",
                "title": "",
                "description": "负责大模型",
                "requirements": "",
            },
            {
                "job_id": "eval-no-ai",
                "platform": "tencent",
                "company": "腾讯",
                "title": "产品评估专员",
                "description": "负责用户调研",
                "requirements": "沟通能力强",
            },
            {
                "job_id": "hardware",
                "platform": "tencent",
                "company": "腾讯",
                "title": "AI芯片测试工程师",
                "description": "负责AI芯片测试",
                "requirements": "三年经验",
            },
            {
                "job_id": "ai-title",
                "platform": "tencent",
                "company": "腾讯",
                "title": "AI算法工程师",
                "description": "开发大模型",
                "requirements": "Python",
            },
            {
                "job_id": "quality-body-ai",
                "platform": "tencent",
                "company": "腾讯",
                "title": "软件测试工程师",
                "description": "负责大模型产品",
                "requirements": "测试经验",
            },
            {
                "job_id": "body-ai",
                "platform": "tencent",
                "company": "腾讯",
                "title": "产品经理",
                "description": "负责Agent产品",
                "requirements": "产品经验",
            },
            {
                "job_id": "no-ai",
                "platform": "tencent",
                "company": "腾讯",
                "title": "财务经理",
                "description": "负责预算",
                "requirements": "本科",
            },
        ],
    )

    _, _, analysis = run_analysis(
        input_path,
        config_path=config_path,
        output_dir=tmp_path / "output",
    )

    assert analysis["manifest"]["selected_raw_count"] == 0
    assert analysis["manifest"]["excluded_job_count"] == 8
    assert len(analysis["excluded_jobs"]) == 8
    reasons_by_id = {
        row["job_id"]: row["exclusion_reason_codes"]
        for row in analysis["excluded_jobs"]
    }
    assert reasons_by_id == {
        "outside": ["outside_config_scope"],
        "missing-title": ["role_general_rnd"],
        "eval-no-ai": ["ai_not_primary_duty"],
        "hardware": ["domain_hardware"],
        "ai-title": ["role_algorithm_or_research"],
        "quality-body-ai": ["ai_not_primary_duty"],
        "body-ai": ["role_product"],
        "no-ai": ["role_general_rnd"],
    }
