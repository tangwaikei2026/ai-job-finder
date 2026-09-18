#!/usr/bin/env python3
"""Read-only, single-post production diagnostic for Tencent job details."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from threading import Lock
from typing import Any, Mapping, Sequence

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.collectors.tencent import TencentRawCollector  # noqa: E402
from src.main import load_config  # noqa: E402
from src.models import RawJobPosting  # noqa: E402


DIAGNOSTIC_CONTRACT_VERSION = 1
POST_ID_PATTERN = re.compile(r"^[0-9]+$")


def _json_type(value: Any, *, observed: bool = True) -> str:
    if not observed:
        return "missing"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def _exception_name(exc: BaseException) -> str:
    return f"{type(exc).__module__}.{type(exc).__name__}"


def _present(value: Any) -> bool:
    return bool(str(value or "").strip())


class _ResponseRecorder:
    def __init__(self) -> None:
        self.request_count = 0
        self.responses: list[dict[str, Any]] = []

    def capture_request(self, request: httpx.Request) -> None:
        self.request_count += 1

    def capture(self, response: httpx.Response) -> None:
        row: dict[str, Any] = {
            "http_status": response.status_code,
            "content_type": response.headers.get("Content-Type"),
            "json_parse_result": "NOT_OBSERVED",
            "payload_code": None,
            "payload_data_type": "not_observed",
            "responsibility_present": False,
            "requirement_present": False,
        }
        try:
            response.read()
            payload = response.json()
        except Exception as exc:
            row["json_parse_result"] = "ERROR"
            row["json_exception_class"] = _exception_name(exc)
            row["json_exception_message"] = str(exc)
        else:
            row["json_parse_result"] = "SUCCESS"
            if isinstance(payload, Mapping):
                row["payload_code"] = payload.get("Code")
                observed = "Data" in payload
                data = payload.get("Data")
                row["payload_data_type"] = _json_type(data, observed=observed)
                if isinstance(data, Mapping):
                    row["responsibility_present"] = _present(
                        data.get("Responsibility")
                    )
                    row["requirement_present"] = _present(data.get("Requirement"))
            else:
                row["payload_data_type"] = "not_observed"
        self.responses.append(row)


def _validate_post_id(value: str) -> str:
    post_id = value.strip()
    if not POST_ID_PATTERN.fullmatch(post_id):
        raise argparse.ArgumentTypeError("postId must contain digits only")
    return post_id


def diagnose_detail(
    config: Mapping[str, Any],
    post_id: str,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Fetch exactly one detail through TencentRawCollector without writing files."""
    if not POST_ID_PATTERN.fullmatch(post_id):
        raise ValueError("postId must contain digits only")
    platforms = config.get("platforms")
    if not isinstance(platforms, Mapping):
        raise ValueError("config platforms must be a mapping")
    platform_value = platforms.get("tencent")
    if not isinstance(platform_value, Mapping):
        raise ValueError("Tencent platform config is missing")
    platform_config = dict(platform_value)
    endpoint = str(platform_config.get("detail_api") or "")
    if not endpoint:
        raise ValueError("Tencent detail_api is missing")

    max_attempts = max(1, int(platform_config.get("detail_max_retries", 1)))
    timeout_seconds = max(
        0.1,
        float(platform_config.get("detail_timeout_seconds", 8)),
    )
    detail_url = str(platform_config.get("detail_url") or "")
    job = RawJobPosting(
        job_id=post_id,
        platform="tencent",
        title="",
        company=str(platform_config.get("name") or "腾讯"),
        url=detail_url.format(job_id=post_id) if detail_url else "",
    )
    collector = TencentRawCollector(platform_config, dict(config), client=client)
    collector._detail_request_lock = Lock()
    collector._last_detail_request_at = 0.0
    recorder = _ResponseRecorder()
    request_hooks = collector.client.event_hooks.setdefault("request", [])
    response_hooks = collector.client.event_hooks.setdefault("response", [])
    request_hook = recorder.capture_request
    response_hook = recorder.capture
    request_hooks.append(request_hook)
    response_hooks.append(response_hook)

    detail: Mapping[str, Any] | None = None
    caught: Exception | None = None
    try:
        detail = collector._fetch_detail(job)
    except Exception as exc:
        caught = exc
    finally:
        request_hooks.remove(request_hook)
        response_hooks.remove(response_hook)
        collector.close()

    latest = recorder.responses[-1] if recorder.responses else {
        "http_status": None,
        "content_type": None,
        "json_parse_result": "NOT_OBSERVED",
        "payload_code": None,
        "payload_data_type": "not_observed",
        "responsibility_present": False,
        "requirement_present": False,
    }
    responsibility_present = latest["responsibility_present"]
    requirement_present = latest["requirement_present"]
    if detail is not None:
        responsibility_present = _present(detail.get("Responsibility"))
        requirement_present = _present(detail.get("Requirement"))

    return {
        "diagnostic_contract_version": DIAGNOSTIC_CONTRACT_VERSION,
        "platform": "tencent",
        "post_id": post_id,
        "endpoint": endpoint,
        "bounded": {
            "max_attempts": max_attempts,
            "timeout_seconds": timeout_seconds,
        },
        "request_count": recorder.request_count,
        "response_count": len(recorder.responses),
        "http_status": latest["http_status"],
        "content_type": latest["content_type"],
        "json_parse_result": latest["json_parse_result"],
        "payload_code": latest["payload_code"],
        "payload_data_type": latest["payload_data_type"],
        "responsibility_present": responsibility_present,
        "requirement_present": requirement_present,
        "collector_parse_result": "ERROR" if caught else "SUCCESS",
        "exception_class": _exception_name(caught) if caught else None,
        "exception_message": str(caught) if caught else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--post-id", required=True, type=_validate_post_id)
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    evidence = diagnose_detail(load_config(args.config.resolve()), args.post_id)
    print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if evidence["collector_parse_result"] == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
