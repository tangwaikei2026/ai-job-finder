import copy
import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools" / "generate_market_report.py"
SPEC = importlib.util.spec_from_file_location("generate_market_report", MODULE_PATH)
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def change(before, after, comparable=True):
    return {"from": before, "to": after, "delta": after - before if comparable else None,
            "pct_change": None, "comparable": comparable}


def snapshot():
    return {
        "artifact_type": "trend_snapshot_v1", "trend_version": "trend_v1", "snapshot_date": "2026-09-07",
        "active_jobs": 2, "by_market_relevance": {"core": 1, "adjacent": 1},
        "by_role_family": {"product": 2}, "by_role_family_any": {"product": 2, "development": 1},
        "hybrid_role_count": 1, "hybrid_role_share": {"share": 0.5},
        "by_ai_relation": {"core_ai_evaluation": 2}, "by_career_pool": {"P1": 1, "X": 1},
        "by_skill_tag": {"Python": 2},
    }


def comparison(comparable=True):
    item = change(1, 2, comparable)
    info = {"comparable": comparable, "reason_codes": ["SOURCE_INCOMPLETE"] if not comparable else [],
            "included_platforms": ["a"] if comparable else [], "excluded_platforms": ["b"]}
    return {
        "artifact_type": "trend_comparison_v1", "trend_version": "trend_v1",
        "from_date": "2026-09-04", "to_date": "2026-09-07",
        "comparability": {key: copy.deepcopy(info) for key in ("inventory", "presence_flow", "content_flow")},
        "market": {"active_jobs": copy.deepcopy(item), "core_jobs": copy.deepcopy(item),
                   "adjacent_jobs": copy.deepcopy(item), "hybrid_role_share": copy.deepcopy(item)},
        "by_role_family": {"product": copy.deepcopy(item)}, "by_role_family_any": {"product": copy.deepcopy(item)},
        "by_ai_relation": {"core_ai_evaluation": copy.deepcopy(item)}, "by_career_pool": {"P1": copy.deepcopy(item)},
        "by_skill_tag": {"Python": copy.deepcopy(item)},
        "lifecycle": {"NEW": copy.deepcopy(item), "UPDATED": copy.deepcopy(item), "REMOVED": copy.deepcopy(item),
                      "REAPPEARED": change(0, 1, comparable)},
        "company_changes": {"Company": {"active_jobs": copy.deepcopy(item)}},
    }


def test_snapshot_report_renders_non_additive_fields():
    output = report.render_snapshot(snapshot())
    assert "snapshot_date: 2026-09-07" in output
    assert "Role Responsibility Coverage — NON_ADDITIVE" in output
    assert "Skill Tags — NON_ADDITIVE" in output


def test_comparison_report_renders_lifecycle_without_relabeling_reappeared():
    output = report.render_comparison(comparison())
    assert "from_date: 2026-09-04" in output
    assert "| REAPPEARED | 0 | 1 | 1 | True |" in output
    assert "| NEW | 1 | 2 | 1 | True |" in output


def test_not_comparable_keeps_null_delta_and_renders_guard():
    output = report.render_comparison(comparison(comparable=False))
    assert "NOT COMPARABLE" in output
    assert 'reason_codes: ["SOURCE_INCOMPLETE"]' in output
    assert "| active_jobs | 1 | 2 | null | False |" in output
