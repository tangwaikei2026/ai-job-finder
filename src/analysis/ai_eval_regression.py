from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from src.analysis.ai_eval_jobs import (
    AI_RELATIONS,
    CAREER_POOLS,
    CLASSIFICATION_INPUT_FIELDS,
    EXCLUSION_REASON_LABELS,
    ROLE_FAMILIES,
    SENIORITY_LEVELS,
    classification_input,
    classify_body_primary_ai_evaluation,
    job_content_sha256,
    normalized_job_content,
)


EXPECTED_CASE_COUNT = 117
EXPECTED_POOL_DISTRIBUTION = {"P1": 66, "P2": 18, "REF": 12, "X": 21}
ASSERTION_FIELDS = (
    "role_family",
    "ai_relation",
    "seniority_level",
    "career_pool",
    "reason_codes",
)
REQUIRED_FIELDS = {
    "case_id",
    "job_id",
    "content_sha256",
    *CLASSIFICATION_INPUT_FIELDS,
    "company",
    "location",
    "expected_role_family",
    "expected_ai_relation",
    "expected_seniority_level",
    "expected_career_pool",
    "expected_reason_codes",
    "evidence",
    "boundary_tags",
}
FORBIDDEN_FIELDS = {
    "expected_candidate_include",
    "label_version",
    "label_owner",
    "label_status",
    "provenance",
    "snapshot_date",
    "snapshot_at",
    "snapshot_datetime",
}


class RegressionDataIntegrityError(ValueError):
    """Raised before classification when the frozen snapshot is invalid."""


def _require_unique(rows: Sequence[Mapping[str, Any]], field: str) -> None:
    values = [row[field] for row in rows]
    if len(set(values)) != len(values):
        duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
        raise RegressionDataIntegrityError(
            f"frozen regression field {field!r} is not unique: {duplicates}"
        )


def _validate_case_structure(case: Mapping[str, Any], index: int) -> None:
    missing = sorted(REQUIRED_FIELDS - set(case))
    forbidden = sorted(FORBIDDEN_FIELDS & set(case))
    if missing:
        raise RegressionDataIntegrityError(
            f"frozen regression case {index} missing fields: {missing}"
        )
    if forbidden:
        raise RegressionDataIntegrityError(
            f"frozen regression case {index} has forbidden fields: {forbidden}"
        )
    for field in ("case_id", "job_id", "content_sha256", *CLASSIFICATION_INPUT_FIELDS):
        if not isinstance(case[field], str):
            raise RegressionDataIntegrityError(
                f"frozen regression case {index} field {field!r} must be a string"
            )
    if not isinstance(case["expected_reason_codes"], list) or not all(
        isinstance(value, str) for value in case["expected_reason_codes"]
    ):
        raise RegressionDataIntegrityError(
            f"frozen regression case {index} expected_reason_codes must be a string list"
        )
    if not isinstance(case["boundary_tags"], list) or not all(
        isinstance(value, str) for value in case["boundary_tags"]
    ):
        raise RegressionDataIntegrityError(
            f"frozen regression case {index} boundary_tags must be a string list"
        )


def _validate_enums(case: Mapping[str, Any]) -> None:
    checks = (
        ("expected_role_family", ROLE_FAMILIES),
        ("expected_ai_relation", AI_RELATIONS),
        ("expected_seniority_level", SENIORITY_LEVELS),
        ("expected_career_pool", CAREER_POOLS),
    )
    for field, allowed in checks:
        if case[field] not in allowed:
            raise RegressionDataIntegrityError(
                f"{case['case_id']} has invalid {field}: {case[field]!r}"
            )
    invalid_reason_codes = sorted(
        set(case["expected_reason_codes"]) - set(EXCLUSION_REASON_LABELS)
    )
    if invalid_reason_codes:
        raise RegressionDataIntegrityError(
            f"{case['case_id']} has invalid expected reason codes: "
            f"{invalid_reason_codes}"
        )
    if case["expected_career_pool"] == "X" and not case["expected_reason_codes"]:
        raise RegressionDataIntegrityError(
            f"{case['case_id']} is X but has no expected reason code"
        )
    context_not_primary_markers = {
        *case["boundary_tags"],
        *case["expected_reason_codes"],
    }
    if (
        "ai_context_not_primary" in context_not_primary_markers
        and case["expected_ai_relation"] != "ai_context_only"
    ):
        raise RegressionDataIntegrityError(
            f"{case['case_id']} uses ai_context_not_primary without ai_context_only"
        )


def _validate_evidence(case: Mapping[str, Any]) -> None:
    evidence = case["evidence"]
    if not isinstance(evidence, dict):
        raise RegressionDataIntegrityError(
            f"{case['case_id']} evidence must be a mapping"
        )
    for field, snippets in evidence.items():
        if field not in CLASSIFICATION_INPUT_FIELDS:
            raise RegressionDataIntegrityError(
                f"{case['case_id']} evidence uses invalid source field {field!r}"
            )
        if not isinstance(snippets, list) or not all(
            isinstance(snippet, str) and snippet for snippet in snippets
        ):
            raise RegressionDataIntegrityError(
                f"{case['case_id']} evidence.{field} must be a non-empty string list"
            )
        missing = [snippet for snippet in snippets if snippet not in case[field]]
        if missing:
            raise RegressionDataIntegrityError(
                f"{case['case_id']} evidence.{field} is not an original substring: {missing}"
            )


def validate_frozen_regression_cases(
    rows: Sequence[Mapping[str, Any]],
    *,
    expected_count: int = EXPECTED_CASE_COUNT,
) -> None:
    if len(rows) != expected_count:
        raise RegressionDataIntegrityError(
            f"frozen regression expected {expected_count} cases, found {len(rows)}"
        )
    for index, case in enumerate(rows, start=1):
        if not isinstance(case, Mapping):
            raise RegressionDataIntegrityError(
                f"frozen regression case {index} must be a mapping"
            )
        _validate_case_structure(case, index)
        _validate_enums(case)
        _validate_evidence(case)

    for field in ("case_id", "job_id", "content_sha256"):
        _require_unique(rows, field)
    normalized = [normalized_job_content(case) for case in rows]
    if len(set(normalized)) != len(normalized):
        raise RegressionDataIntegrityError(
            "frozen regression normalized title/description/requirements are not unique"
        )

    hash_failures = [
        {
            "case_id": case["case_id"],
            "expected": case["content_sha256"],
            "actual": job_content_sha256(case),
        }
        for case in rows
        if job_content_sha256(case) != case["content_sha256"]
    ]
    if hash_failures:
        raise RegressionDataIntegrityError(
            "frozen regression data integrity hash failure: "
            + json.dumps(hash_failures, ensure_ascii=False)
        )

    distribution = Counter(case["expected_career_pool"] for case in rows)
    if dict(distribution) != EXPECTED_POOL_DISTRIBUTION:
        raise RegressionDataIntegrityError(
            f"unexpected frozen career-pool distribution: {dict(distribution)}"
        )


def load_frozen_regression_cases(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        documents = list(yaml.safe_load_all(file))
    rows = [document for document in documents if document is not None]
    validate_frozen_regression_cases(rows)
    return [dict(row) for row in rows]


def _actual_labels(case: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    inputs = classification_input(case)
    result = classify_body_primary_ai_evaluation(inputs)
    classification = result["body_primary_ai_evaluation"]
    actual = {
        "role_family": classification["role_family"],
        "ai_relation": classification["ai_relation"],
        "seniority_level": classification["seniority_level"],
        "career_pool": classification["career_pool"],
        "reason_codes": result["reason_codes"],
    }
    return actual, result


def run_frozen_regression(path: Path) -> dict[str, Any]:
    cases = load_frozen_regression_cases(path)
    field_errors: Counter[str] = Counter()
    pool_confusion: Counter[tuple[str, str]] = Counter()
    binary_confusion: Counter[tuple[str, str]] = Counter()
    boundary_totals: Counter[str] = Counter()
    boundary_passes: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    passed = 0

    for case in cases:
        actual, audit = _actual_labels(case)
        expected = {
            field: case[f"expected_{field}"]
            for field in ASSERTION_FIELDS
        }
        differences = {
            field: {"expected": expected[field], "actual": actual[field]}
            for field in ASSERTION_FIELDS
            if expected[field] != actual[field]
        }
        case_passed = not differences
        passed += int(case_passed)
        for field in differences:
            field_errors[field] += 1

        expected_pool = expected["career_pool"]
        actual_pool = actual["career_pool"]
        pool_confusion[(expected_pool, actual_pool)] += 1
        expected_binary = "positive" if expected_pool in {"P1", "P2", "REF"} else "negative"
        actual_binary = "positive" if actual_pool in {"P1", "P2", "REF"} else "negative"
        binary_confusion[(expected_binary, actual_binary)] += 1

        for tag in case["boundary_tags"]:
            boundary_totals[tag] += 1
            boundary_passes[tag] += int(case_passed)

        if differences:
            failures.append(
                {
                    "case_id": case["case_id"],
                    "job_id": case["job_id"],
                    "title": case["title"],
                    "differences": differences,
                    "evidence": case["evidence"],
                    "production_rule_id": audit["rule_id"],
                    "triggered_rules": audit["triggered_rules"],
                    "actual_reason_codes": audit["reason_codes"],
                }
            )

    pool_labels = ("P1", "P2", "REF", "X")
    boundary_results = [
        {
            "boundary_tag": tag,
            "total": boundary_totals[tag],
            "passed": boundary_passes[tag],
            "failed": boundary_totals[tag] - boundary_passes[tag],
            "pass_rate": round(boundary_passes[tag] / boundary_totals[tag], 4),
        }
        for tag in sorted(boundary_totals)
    ]
    return {
        "regression_file": str(path),
        "production_entrypoint": (
            "src.analysis.ai_eval_jobs.classify_body_primary_ai_evaluation"
        ),
        "classification_input_fields": list(CLASSIFICATION_INPUT_FIELDS),
        "total": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "field_errors": {field: field_errors[field] for field in ASSERTION_FIELDS},
        "career_pool_confusion": {
            expected: {
                actual: pool_confusion[(expected, actual)] for actual in pool_labels
            }
            for expected in pool_labels
        },
        "positive_negative_confusion": {
            expected: {
                actual: binary_confusion[(expected, actual)]
                for actual in ("positive", "negative")
            }
            for expected in ("positive", "negative")
        },
        "boundary_tag_results": boundary_results,
        "failures": failures,
    }


def run_split_regression(path: Path, expectations_path: Path) -> dict[str, Any]:
    """Two evaluators over the untouched frozen JD cases and explicit market overlay."""
    from src.analysis.ai_eval_jobs import classify_market, classify_personal_fit

    cases = load_frozen_regression_cases(path)
    expectations = yaml.safe_load(expectations_path.read_text(encoding="utf-8"))
    reason_by_case = {}
    for code, ids in expectations["market_reason_cases"].items():
        for case_id in ids:
            if case_id in reason_by_case:
                raise RegressionDataIntegrityError(f"duplicate market expectation: {case_id}")
            reason_by_case[case_id] = [code]
    if set(reason_by_case) != {case["case_id"] for case in cases}:
        raise RegressionDataIntegrityError("market expectations must cover exactly the frozen cases")
    reports = {name: {"total": 0, "passed": 0, "failed": 0, "failures": []} for name in ("market", "fit")}
    for case in cases:
        case_id = case["case_id"]
        market = classify_market(case)
        expected = {
            "in_scope": case_id not in expectations["out_of_scope"],
            "role_family": case["expected_role_family"],
            "ai_relation": expectations["ai_relation_overrides"].get(case_id, case["expected_ai_relation"]),
            "seniority_level": case["expected_seniority_level"],
            "reason_codes": reason_by_case[case_id],
        }
        evaluations = [("market", expected, market)]
        if market["in_scope"]:
            fit = classify_personal_fit(case, market)
            evaluations.append(("fit", {"career_pool": case["expected_career_pool"],
                                        "fit_reason_codes": case["expected_reason_codes"]}, fit))
        for name, wanted, actual in evaluations:
            differences = {key: {"expected": value, "actual": actual[key]}
                           for key, value in wanted.items() if actual[key] != value}
            reports[name]["total"] += 1
            reports[name]["passed"] += int(not differences)
            reports[name]["failed"] += int(bool(differences))
            if differences:
                reports[name]["failures"].append({"case_id": case_id, "differences": differences})
    return reports


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the frozen AI/Agent classification regression set"
    )
    parser.add_argument("regression_file", type=Path)
    parser.add_argument("--market-expectations", type=Path)
    args = parser.parse_args(argv)
    if args.market_expectations:
        report = run_split_regression(args.regression_file, args.market_expectations)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return int(any(result["failed"] for result in report.values()))
    report = run_frozen_regression(args.regression_file)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
