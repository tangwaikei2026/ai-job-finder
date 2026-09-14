from __future__ import annotations

import json
from pathlib import Path

import yaml

from tools.run_daily import run_daily


DATE = "2026-09-11"


def _manifest(statuses):
    return {
        "job_count": 1,
        "complete": all(status == "success" for status in statuses.values()),
        "platforms": [
            {
                "platform": platform,
                "status": status,
                "complete": status == "success",
                "stopped_by": "source_total_reached" if status == "success" else "error",
                "error": "" if status == "success" else "failed",
            }
            for platform, status in statuses.items()
        ],
    }


def _replace(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".test-tmp")
    temporary.write_text(value)
    temporary.replace(path)


def _scenario(
    tmp_path: Path,
    initial,
    *,
    retry=None,
    clean_code=0,
    analysis_code=0,
    output_dir="data/raw",
):
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"output_dir": output_dir}))
    raw_dir = (tmp_path / output_dir).resolve()
    data_dir = raw_dir.parent
    calls = []
    retry = retry or {}

    def runner(command, cwd):
        command = list(command)
        calls.append(command)
        if command[1:3] == ["-m", "src.main"]:
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_path = raw_dir / f"{DATE}.json"
            manifest_path = raw_dir / f"{DATE}_manifest.json"
            if "--platform" not in command:
                _replace(raw_path, json.dumps([{"platform": "ok", "job_id": "1"}]))
                _replace(manifest_path, json.dumps(_manifest(initial)))
                return 0 if all(value == "success" for value in initial.values()) else 1
            platform = command[command.index("--platform") + 1]
            outcome = retry.get(platform, "error")
            if outcome == "success":
                final = dict(initial)
                final[platform] = "success"
                _replace(manifest_path, json.dumps(_manifest(final)))
                return 0
            return 1
        if command[1:4] == ["-m", "src.clean.cli", "clean-jobs"]:
            if clean_code == 0:
                clean = data_dir / "clean" / f"{DATE}.json"
                clean.parent.mkdir(parents=True, exist_ok=True)
                clean.write_text("[]")
            return clean_code
        if command[1:5] == ["-m", "src.analysis.pipeline", "run", "--date"]:
            if analysis_code == 0:
                analysis = data_dir / "analysis"
                for relative in (
                    f"classification/{DATE}.jsonl",
                    f"events/{DATE}.jsonl",
                    f"trends/snapshots/{DATE}.json",
                ):
                    path = analysis / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("{}\n")
            return analysis_code
        raise AssertionError(command)

    result = run_daily(DATE, config_path=config, root=tmp_path, command_runner=runner)
    return result, calls


def test_all_platforms_success(tmp_path):
    (code, _, status), calls = _scenario(tmp_path, {"a": "success", "b": "success"})
    assert code == 0
    assert status["status"] == "SUCCESS"
    assert status["crawl"]["retried_platforms"] == []
    assert len(calls) == 3
    assert [call[2] for call in calls] == ["src.main", "src.clean.cli", "src.analysis.pipeline"]


def test_failed_platform_retry_succeeds(tmp_path):
    (code, _, status), calls = _scenario(
        tmp_path, {"a": "success", "b": "error"}, retry={"b": "success"}
    )
    assert code == 0
    assert status["status"] == "SUCCESS"
    assert status["crawl"]["retried_platforms"] == ["b"]
    assert status["crawl"]["final_failed_platforms"] == []
    assert [call[call.index("--platform") + 1] for call in calls if "--platform" in call] == ["b"]


def test_failed_platform_retry_still_fails_is_degraded(tmp_path):
    (code, _, status), _ = _scenario(tmp_path, {"a": "success", "b": "error"})
    assert code == 0
    assert status["status"] == "DEGRADED"
    assert status["crawl"]["initial_return_code"] == 1
    assert status["crawl"]["initial_failed_platforms"] == ["b"]
    assert status["crawl"]["initial_platform_errors"] == {"b": "failed"}
    assert status["crawl"]["retried_platforms"] == ["b"]
    assert status["crawl"]["retry_return_codes"] == {"b": 1}
    assert status["crawl"]["final_failed_platforms"] == ["b"]
    assert status["crawl"]["final_incomplete_platforms"] == ["b"]
    assert status["crawl"]["final_platform_errors"] == {"b": "failed"}
    assert status["clean"]["status"] == status["analysis"]["status"] == "SUCCESS"


def test_clean_failure_stops_analysis(tmp_path):
    (code, _, status), calls = _scenario(tmp_path, {"a": "success"}, clean_code=7)
    assert code == 1
    assert status["status"] == "FAILED"
    assert status["clean"]["status"] == "FAILED"
    assert status["analysis"]["status"] == "SKIPPED"
    assert not any("src.analysis.pipeline" in call for call in calls)


def test_analysis_failure_is_failed(tmp_path):
    (code, _, status), _ = _scenario(tmp_path, {"a": "success"}, analysis_code=9)
    assert code == 1
    assert status["status"] == "FAILED"
    assert status["analysis"]["status"] == "FAILED"


def test_same_date_rerun_overwrites_status_and_outputs(tmp_path):
    first, first_calls = _scenario(tmp_path, {"a": "success"})
    second, second_calls = _scenario(tmp_path, {"a": "success"})
    assert first[0] == second[0] == 0
    assert first[1] == second[1]
    assert json.loads(second[1].read_text())["status"] == "SUCCESS"
    assert len(first_calls) == len(second_calls) == 3


def test_manifest_without_failed_platform_does_not_retry(tmp_path):
    (_, _, status), calls = _scenario(tmp_path, {"a": "success", "b": "partial"})
    assert status["status"] == "DEGRADED"
    assert status["crawl"]["initial_failed_platforms"] == []
    assert not any("--platform" in call for call in calls)
    assert len(calls) == 3


def test_stale_manifest_is_not_mixed_with_partially_replaced_raw(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"output_dir": "data/raw"}))
    raw_dir = tmp_path / "data" / "raw"
    raw_path = raw_dir / f"{DATE}.json"
    manifest_path = raw_dir / f"{DATE}_manifest.json"
    _replace(raw_path, "[]")
    _replace(manifest_path, json.dumps(_manifest({"old": "success"})))
    calls = []

    def runner(command, cwd):
        calls.append(list(command))
        _replace(raw_path, json.dumps([{"platform": "new", "job_id": "2"}]))
        return 1

    code, status_path, status = run_daily(
        DATE, config_path=config, root=tmp_path, command_runner=runner
    )
    assert code == 1
    assert status["status"] == status["crawl"]["status"] == "FAILED"
    assert "both raw and manifest" in status["crawl"]["error"]
    assert len(calls) == 1
    assert json.loads(status_path.read_text())["status"] == "FAILED"


def test_empty_platform_manifest_is_failed_before_clean(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"output_dir": "data/raw"}))
    raw_dir = tmp_path / "data" / "raw"
    calls = []

    def runner(command, cwd):
        calls.append(list(command))
        _replace(raw_dir / f"{DATE}.json", "[]")
        _replace(raw_dir / f"{DATE}_manifest.json", json.dumps({"platforms": []}))
        return 1

    code, _, status = run_daily(DATE, config_path=config, root=tmp_path, command_runner=runner)
    assert code == 1
    assert status["crawl"]["status"] == "FAILED"
    assert status["clean"]["status"] == status["analysis"]["status"] == "SKIPPED"
    assert len(calls) == 1


def test_all_platforms_still_failed_does_not_clean(tmp_path):
    (code, _, status), calls = _scenario(tmp_path, {"a": "error", "b": "error"})
    assert code == 1
    assert status["crawl"]["status"] == "FAILED"
    assert status["crawl"]["retried_platforms"] == ["a", "b"]
    assert status["crawl"]["final_failed_platforms"] == ["a", "b"]
    assert len(calls) == 3
    assert all(call[2] == "src.main" for call in calls)


def test_custom_data_root_is_used_for_every_stage(tmp_path):
    (code, status_path, status), calls = _scenario(
        tmp_path, {"a": "success"}, output_dir="runtime/raw"
    )
    data_root = (tmp_path / "runtime").resolve()
    assert code == 0
    assert status["status"] == "SUCCESS"
    assert status_path == data_root / "analysis" / "runs" / f"{DATE}.json"
    clean_call = next(call for call in calls if "src.clean.cli" in call)
    analysis_call = next(call for call in calls if "src.analysis.pipeline" in call)
    assert clean_call[clean_call.index("--input") + 1] == str(data_root / "raw" / f"{DATE}.json")
    assert clean_call[clean_call.index("--output-dir") + 1] == str(data_root / "clean")
    assert analysis_call[analysis_call.index("--data-dir") + 1] == str(data_root)
