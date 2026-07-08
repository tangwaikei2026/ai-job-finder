from __future__ import annotations

from src.audit.missing_evidence import EDUCATION_EVIDENCE_FIELDS, extract_missing_evidence


FORBIDDEN_SPLIT_FIELDS = {
    "degree_pattern_name",
    "major_pattern_name",
    "degree_suggested_value",
    "major_suggested_value",
    "degree_barrier",
    "major_barrier",
    "degree_preferred",
    "major_preferred",
    "degree_confidence",
    "major_confidence",
    "degree_evidence_start",
    "major_evidence_start",
    "degree_reason",
    "major_reason",
}


def _job(**overrides: object) -> dict[str, object]:
    job: dict[str, object] = {
        "job_id": "job-1",
        "platform": "example",
        "title": "AI Product Manager",
        "company": "Example",
        "education": "<missing>",
        "experience": "3-5年",
        "description": "",
        "requirements": "",
        "url": "https://example.com/jobs/1",
    }
    job.update(overrides)
    return job


def _education_rows(job: dict[str, object]) -> list[dict[str, object]]:
    result = extract_missing_evidence(
        [job],
        input_file="data/clean/2026-07-08.json",
        generated_at="2026-07-08 12:00:00",
    )
    return result["education_rows"]


def test_bachelor_plus_degree_evidence() -> None:
    rows = _education_rows(_job(requirements="本科及以上学历"))

    assert rows[0]["pattern_name"] == "bachelor_plus"
    assert rows[0]["suggested_value"] == "bachelor_plus;unknown"
    assert rows[0]["barrier"] == "bachelor_plus"


def test_bachelor_plus_with_major_required() -> None:
    rows = _education_rows(_job(requirements="本科及以上学历，计算机相关专业"))

    assert rows[0]["pattern_name"] == "bachelor_plus;major_required"
    assert rows[0]["suggested_value"] == "bachelor_plus;计算机相关专业"
    assert rows[0]["barrier"] == "bachelor_plus;计算机相关专业"


def test_bachelor_plus_with_multi_major_required() -> None:
    rows = _education_rows(
        _job(requirements="本科及以上学历，计算机、软件工程、人工智能等相关专业")
    )

    assert rows[0]["suggested_value"] == "bachelor_plus;计算机、软件工程、人工智能相关专业"
    assert rows[0]["reason"] == "hard_degree_requirement_found;hard_major_requirement_found"


def test_bachelor_plus_with_major_preferred() -> None:
    rows = _education_rows(
        _job(requirements="本科及以上学历，计算机科学、信息技术、通信工程等相关专业优先")
    )

    assert rows[0]["pattern_name"] == "bachelor_plus;major_preferred_only"
    assert rows[0]["barrier"] == "bachelor_plus"
    assert rows[0]["preferred"] == "计算机科学、信息技术、通信工程相关专业"
    assert rows[0]["confidence"] == "medium"


def test_bachelor_plus_with_master_preferred_is_not_master_plus() -> None:
    rows = _education_rows(_job(requirements="本科及以上，硕士优先"))

    assert rows[0]["pattern_name"] == "bachelor_plus;preferred_only"
    assert rows[0]["suggested_value"] == "bachelor_plus;unknown"
    assert rows[0]["barrier"] == "bachelor_plus"
    assert rows[0]["preferred"] == "硕士"
    assert rows[0]["confidence"] == "medium"


def test_master_plus_degree_evidence() -> None:
    rows = _education_rows(_job(requirements="硕士及以上"))

    assert rows[0]["suggested_value"] == "master_plus;unknown"


def test_phd_degree_evidence() -> None:
    rows = _education_rows(_job(requirements="博士学历"))

    assert rows[0]["suggested_value"] == "phd;unknown"


def test_no_degree_requirement() -> None:
    rows = _education_rows(_job(requirements="学历不限"))
    rows_2 = _education_rows(_job(requirements="不限学历"))

    assert rows[0]["suggested_value"] == "no_requirement;unknown"
    assert rows_2[0]["suggested_value"] == "no_requirement;unknown"


def test_master_preferred_without_hard_requirement() -> None:
    rows = _education_rows(_job(requirements="硕士优先"))

    assert rows[0]["pattern_name"] == "preferred_only"
    assert rows[0]["suggested_value"] == "preferred_only;unknown"
    assert rows[0]["barrier"] == "unknown"
    assert rows[0]["preferred"] == "硕士"
    assert rows[0]["confidence"] == "low"


def test_major_preferred_without_hard_degree() -> None:
    rows = _education_rows(_job(requirements="人工智能专业优先"))

    assert rows[0]["pattern_name"] == "major_preferred_only"
    assert rows[0]["suggested_value"] == "unknown;人工智能专业"
    assert rows[0]["barrier"] == "unknown"
    assert rows[0]["preferred"] == "人工智能专业"
    assert rows[0]["confidence"] == "low"


def test_major_preferred_is_not_degree() -> None:
    rows = _education_rows(_job(requirements="计算机相关专业优先"))

    assert rows[0]["pattern_name"] == "major_preferred_only"
    assert rows[0]["suggested_value"] == "unknown;计算机相关专业"
    assert rows[0]["barrier"] == "unknown"


def test_major_before_degree_is_extracted() -> None:
    rows = _education_rows(_job(requirements="计算机相关专业本科及以上学历"))

    assert rows[0]["pattern_name"] == "bachelor_plus;major_required"
    assert rows[0]["suggested_value"] == "bachelor_plus;计算机相关专业"
    assert rows[0]["barrier"] == "bachelor_plus;计算机相关专业"


def test_major_required_with_degree_preferred_only() -> None:
    rows = _education_rows(
        _job(requirements="计算语言学、语言学、汉语言文学、翻译、小语种等相关专业，硕士或博士学位优先")
    )

    assert rows[0]["pattern_name"] == "preferred_only;major_required"
    assert rows[0]["suggested_value"] == "preferred_only;计算语言学、语言学、汉语言文学、翻译、小语种相关专业"
    assert rows[0]["barrier"] == "计算语言学、语言学、汉语言文学、翻译、小语种相关专业"
    assert rows[0]["preferred"] == "硕士或博士"
    assert rows[0]["confidence"] == "medium"


def test_product_background_is_not_major_preferred() -> None:
    rows = _education_rows(_job(requirements="AI工具类或内容/知识管理类产品背景优先"))

    assert rows == []


def test_existing_api_education_is_skipped() -> None:
    rows = _education_rows(_job(education="本科", requirements="本科及以上学历，计算机相关专业"))

    assert rows == []


def test_education_csv_has_no_split_degree_or_major_fields() -> None:
    assert tuple(EDUCATION_EVIDENCE_FIELDS) == (
        "platform",
        "job_id",
        "title",
        "company",
        "source_section",
        "sentence",
        "pattern_name",
        "suggested_value",
        "barrier",
        "preferred",
        "confidence",
        "evidence_start",
        "evidence_end",
        "reason",
        "description",
        "requirements",
        "url",
    )
    assert not (set(EDUCATION_EVIDENCE_FIELDS) & FORBIDDEN_SPLIT_FIELDS)


def test_evidence_span_covers_degree_and_major() -> None:
    sentence = "本科及以上学历，计算机、软件工程、人工智能等相关专业，3 年及以上经验"
    rows = _education_rows(_job(requirements=sentence))

    assert rows[0]["evidence_start"] == sentence.index("本科")
    assert rows[0]["evidence_end"] == sentence.index("专业") + len("专业")
