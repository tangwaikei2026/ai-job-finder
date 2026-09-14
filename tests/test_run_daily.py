from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

import tools.run_daily as daily_runner
from tools.run_daily import run_daily


DATE = "2026-09-11"


def _raw_rows(statuses):
    return [
        {
            "platform": platform,
            "job_id": f"{platform}-1",
            "title": "Title",
            "company": "Company",
        }
        for platform, status in statuses.items()
        if status != "error"
    ]


def _clean_rows(rows):
    return [
        {
            **row,
            "locations_norm": [],
            "location_level": [],
            "province_norm": [],
            "city_norm": [],
        }
        for row in rows
    ]


def _manifest(statuses, config_path: Path):
    rows = _raw_rows(statuses)
    return {
        "config": str(config_path.resolve()),
        "job_count": len(rows),
        "complete": all(status == "success" for status in statuses.values()),
        "platforms": [
            {
                "platform": platform,
                "status": status,
                "complete": status == "success",
                "jobs_in_scope": 0 if status == "error" else 1,
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


def _seed_observation(raw_dir: Path, config: Path, statuses) -> None:
    _replace(raw_dir / f"{DATE}.json", json.dumps(_raw_rows(statuses)))
    _replace(
        raw_dir / f"{DATE}_manifest.json",
        json.dumps(_manifest(statuses, config)),
    )


def _scenario(
    tmp_path: Path,
    initial,
    *,
    retry=None,
    clean_code=0,
    analysis_code=0,
    output_dir="data/raw",
    resume_from=None,
    seed_clean=True,
    preexisting_status=None,
):
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"output_dir": output_dir}))
    raw_dir = (tmp_path / output_dir).resolve()
    data_dir = raw_dir.parent
    calls = []
    retry = retry or {}
    if preexisting_status is not None:
        _replace(
            data_dir / "analysis" / "runs" / f"{DATE}.json",
            json.dumps(preexisting_status),
        )
    if resume_from is not None:
        _seed_observation(raw_dir, config, initial)
        if resume_from == "analysis" and seed_clean:
            clean = data_dir / "clean" / f"{DATE}.json"
            _replace(clean, json.dumps(_clean_rows(_raw_rows(initial))))

    def runner(command, cwd):
        command = list(command)
        calls.append(command)
        if command[1:3] == ["-m", "src.main"]:
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_path = raw_dir / f"{DATE}.json"
            manifest_path = raw_dir / f"{DATE}_manifest.json"
            if "--platform" not in command:
                _replace(raw_path, json.dumps(_raw_rows(initial)))
                _replace(manifest_path, json.dumps(_manifest(initial, config)))
                return 0 if all(value == "success" for value in initial.values()) else 1
            platform = command[command.index("--platform") + 1]
            outcome = retry.get(platform, "error")
            if outcome == "success":
                final = dict(initial)
                final[platform] = "success"
                _replace(raw_path, json.dumps(_raw_rows(final)))
                _replace(manifest_path, json.dumps(_manifest(final, config)))
                return 0
            return 1
        if command[1:4] == ["-m", "src.clean.cli", "clean-jobs"]:
            if clean_code == 0:
                clean = data_dir / "clean" / f"{DATE}.json"
                raw_rows = json.loads((raw_dir / f"{DATE}.json").read_text())
                _replace(clean, json.dumps(_clean_rows(raw_rows)))
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

    result = run_daily(
        DATE,
        config_path=config,
        root=tmp_path,
        command_runner=runner,
        resume_from=resume_from,
    )
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
    _replace(manifest_path, json.dumps(_manifest({"old": "success"}, config)))
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


def test_all_python_stages_use_runner_sys_executable(tmp_path):
    (_, _, status), calls = _scenario(
        tmp_path,
        {"a": "error", "b": "success"},
        retry={"a": "success"},
    )

    assert status["python_executable"] == sys.executable
    assert calls
    assert all(command[0] == sys.executable for command in calls)


def test_wrong_python_on_path_does_not_change_stage_interpreter(
    tmp_path, monkeypatch
):
    wrong_bin = tmp_path / "wrong-bin"
    wrong_bin.mkdir()
    (wrong_bin / "python").write_text("#!/bin/sh\nexit 99\n")
    monkeypatch.setenv("PATH", str(wrong_bin))

    (_, _, _), calls = _scenario(tmp_path, {"a": "success"})

    assert [command[0] for command in calls] == [sys.executable] * 3


def test_unsupported_python_fails_before_crawl(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"output_dir": "data/raw"}))
    calls = []
    monkeypatch.setattr(daily_runner, "_python_version", lambda: (3, 9, 18))

    code, status_path, status = run_daily(
        DATE,
        config_path=config,
        root=tmp_path,
        command_runner=lambda command, cwd: calls.append(list(command)) or 0,
    )

    assert code == 1
    assert calls == []
    assert status["status"] == status["crawl"]["status"] == "FAILED"
    assert status["reason"] == "unsupported_python"
    assert "Python 3.10+ is required" in status["crawl"]["error"]
    assert json.loads(status_path.read_text())["reason"] == "unsupported_python"


def test_resume_from_clean_skips_crawl_and_retry_then_runs_clean_analysis(tmp_path):
    (code, _, status), calls = _scenario(
        tmp_path,
        {"healthy": "success", "dynamic": "partial"},
        resume_from="clean",
    )

    assert code == 0
    assert status["status"] == "DEGRADED"
    assert status["resume_from"] == "clean"
    assert status["crawl"]["reused_artifacts"] is True
    assert status["crawl"]["retry_skipped"] is True
    assert [command[2] for command in calls] == [
        "src.clean.cli",
        "src.analysis.pipeline",
    ]
    assert not any("src.main" in command for command in calls)


def test_resume_from_analysis_skips_crawl_retry_and_clean(tmp_path):
    (code, _, status), calls = _scenario(
        tmp_path,
        {"a": "success"},
        resume_from="analysis",
    )

    assert code == 0
    assert status["status"] == "SUCCESS"
    assert status["resume_from"] == "analysis"
    assert status["clean"] == {"status": "SUCCESS", "reused_artifact": True}
    assert len(calls) == 1
    assert calls[0][1:3] == ["-m", "src.analysis.pipeline"]


@pytest.mark.parametrize(
    "invalid_case",
    [
        "raw_missing",
        "manifest_missing",
        "empty_platform_manifest",
        "all_error_manifest",
        "invalid_manifest",
        "config_mismatch",
        "count_mismatch",
        "platform_count_mismatch",
        "invalid_raw",
    ],
)
def test_resume_from_clean_invalid_observation_fails_closed(
    tmp_path, invalid_case
):
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"output_dir": "data/raw"}))
    raw_dir = tmp_path / "data" / "raw"
    statuses = {"a": "success"}
    if invalid_case != "raw_missing":
        raw_value = {} if invalid_case == "invalid_raw" else _raw_rows(statuses)
        _replace(raw_dir / f"{DATE}.json", json.dumps(raw_value))
    if invalid_case != "manifest_missing":
        manifest = _manifest(statuses, config)
        if invalid_case == "empty_platform_manifest":
            manifest["platforms"] = []
        elif invalid_case == "all_error_manifest":
            statuses = {"a": "error"}
            _replace(raw_dir / f"{DATE}.json", json.dumps(_raw_rows(statuses)))
            manifest = _manifest(statuses, config)
        elif invalid_case == "config_mismatch":
            manifest["config"] = str(tmp_path / "other-config.yaml")
        elif invalid_case == "count_mismatch":
            manifest["job_count"] = 2
        elif invalid_case == "platform_count_mismatch":
            manifest["platforms"][0]["jobs_in_scope"] = 0
        manifest_text = "{" if invalid_case == "invalid_manifest" else json.dumps(manifest)
        _replace(raw_dir / f"{DATE}_manifest.json", manifest_text)
    calls = []

    code, _, status = run_daily(
        DATE,
        config_path=config,
        root=tmp_path,
        command_runner=lambda command, cwd: calls.append(list(command)) or 0,
        resume_from="clean",
    )

    assert code == 1
    assert calls == []
    assert status["status"] == status["crawl"]["status"] == "FAILED"
    assert status["clean"]["status"] == status["analysis"]["status"] == "SKIPPED"
    assert status["resume_from"] == "clean"
    assert "resume validation failed" in status["crawl"]["error"]


@pytest.mark.parametrize(
    "clean_value",
    [
        None,
        [],
        [{"platform": "a", "job_id": "a-1"}],
        _clean_rows([{"platform": "a", "job_id": "stale-a"}]),
    ],
)
def test_resume_from_analysis_missing_or_invalid_clean_fails_closed(
    tmp_path, clean_value
):
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"output_dir": "data/raw"}))
    raw_dir = tmp_path / "data" / "raw"
    _seed_observation(raw_dir, config, {"a": "success"})
    if clean_value is not None:
        _replace(
            tmp_path / "data" / "clean" / f"{DATE}.json",
            json.dumps(clean_value),
        )
    calls = []

    code, _, status = run_daily(
        DATE,
        config_path=config,
        root=tmp_path,
        command_runner=lambda command, cwd: calls.append(list(command)) or 0,
        resume_from="analysis",
    )

    assert code == 1
    assert calls == []
    assert status["clean"]["status"] == "FAILED"
    assert status["analysis"]["status"] == "SKIPPED"


def test_resume_atomically_replaces_old_failed_status(tmp_path):
    (code, status_path, status), _ = _scenario(
        tmp_path,
        {"a": "success"},
        resume_from="clean",
        preexisting_status={"date": DATE, "status": "FAILED", "old": True},
    )

    persisted = json.loads(status_path.read_text())
    assert code == 0
    assert status["status"] == "SUCCESS"
    assert persisted["status"] == "SUCCESS"
    assert persisted["resume_from"] == "clean"
    assert "old" not in persisted


def test_cli_passes_resume_mode_to_runner(monkeypatch, tmp_path, capsys):
    captured = {}

    def fake_run_daily(run_date, *, config_path, resume_from):
        captured.update(date=run_date, config=config_path, resume_from=resume_from)
        return 0, tmp_path / "status.json", {"status": "SUCCESS"}

    monkeypatch.setattr(daily_runner, "run_daily", fake_run_daily)

    assert daily_runner.main(["--date", DATE, "--resume-from", "clean"]) == 0
    assert captured["resume_from"] == "clean"
    assert json.loads(capsys.readouterr().out)["status"] == "SUCCESS"
