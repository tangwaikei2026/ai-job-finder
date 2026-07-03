from __future__ import annotations

from typing import Any

from src.raw import main as raw_main
from src.raw.models import CollectionManifest, CollectionResult, RawJobPosting


class FakeCollector:
    instances: list[FakeCollector] = []

    def __init__(
        self,
        platform_config: dict[str, Any],
        collection_config: dict[str, Any],
    ):
        self.platform_config = platform_config
        self.collection_config = collection_config
        self.closed = False
        self.instances.append(self)

    def collect(self) -> CollectionResult:
        platform = str(self.platform_config["platform"])
        if self.platform_config.get("raise_error"):
            raise RuntimeError(f"fake failure for {platform}")

        job_ids = self.platform_config.get("job_ids", [f"{platform}-job"])
        jobs = [
            RawJobPosting(
                job_id=str(job_id),
                platform=platform,
                title=f"{platform} AI 测试工程师",
                company=f"{platform} company",
            )
            for job_id in job_ids
        ]
        manifest = CollectionManifest(
            platform=platform,
            name=str(self.platform_config["name"]),
            status="success",
            complete=True,
            source_total=len(jobs),
            records_fetched=len(jobs),
            jobs_mapped=len(jobs),
            jobs_in_scope=len(jobs),
        )
        return CollectionResult(jobs=jobs, manifest=manifest)

    def close(self) -> None:
        self.closed = True
        if self.platform_config.get("raise_close_error"):
            raise RuntimeError(
                f"fake close failure for {self.platform_config['platform']}"
            )


def _config(**platforms: dict[str, Any]) -> dict[str, Any]:
    return {
        "cities": ["上海"],
        "platforms": platforms,
    }


def _platform(
    platform: str,
    *,
    enabled: bool = True,
    **updates: Any,
) -> dict[str, Any]:
    return {
        "platform": platform,
        "name": f"{platform} platform",
        "enabled": enabled,
        **updates,
    }


def _install_registry(monkeypatch, *platforms: str) -> None:
    FakeCollector.instances.clear()
    monkeypatch.setattr(
        raw_main,
        "COLLECTOR_REGISTRY",
        {platform: FakeCollector for platform in platforms},
    )


def test_collect_all_skips_disabled_platform(monkeypatch) -> None:
    _install_registry(monkeypatch, "disabled")
    config = _config(disabled=_platform("disabled", enabled=False))

    jobs, manifests = raw_main.collect_all(config)

    assert jobs == []
    assert manifests == []
    assert FakeCollector.instances == []


def test_collect_all_only_collects_selected_platform(monkeypatch) -> None:
    _install_registry(monkeypatch, "alpha", "beta")
    config = _config(
        alpha=_platform("alpha"),
        beta=_platform("beta"),
    )

    jobs, manifests = raw_main.collect_all(config, selected_platform="beta")

    assert [job.platform for job in jobs] == ["beta"]
    assert [manifest.platform for manifest in manifests] == ["beta"]
    assert [item.platform_config["platform"] for item in FakeCollector.instances] == [
        "beta"
    ]


def test_collect_all_reports_enabled_unregistered_platform(monkeypatch) -> None:
    _install_registry(monkeypatch)
    config = _config(unregistered=_platform("unregistered"))

    jobs, manifests = raw_main.collect_all(config)

    assert jobs == []
    assert len(manifests) == 1
    assert manifests[0].platform == "unregistered"
    assert manifests[0].status == "error"
    assert manifests[0].complete is False
    assert manifests[0].stopped_by == "unregistered"
    assert "No raw collector registered" in manifests[0].error


def test_collect_all_records_collector_exception_in_manifest(monkeypatch) -> None:
    _install_registry(monkeypatch, "broken")
    config = _config(broken=_platform("broken", raise_error=True))

    jobs, manifests = raw_main.collect_all(config)

    assert jobs == []
    assert len(manifests) == 1
    assert manifests[0].platform == "broken"
    assert manifests[0].status == "error"
    assert manifests[0].complete is False
    assert "fake failure for broken" in manifests[0].error


def test_collect_all_continues_after_collector_exception(monkeypatch) -> None:
    _install_registry(monkeypatch, "broken", "healthy")
    config = _config(
        broken=_platform("broken", raise_error=True),
        healthy=_platform("healthy"),
    )

    jobs, manifests = raw_main.collect_all(config)

    assert [job.platform for job in jobs] == ["healthy"]
    assert [manifest.platform for manifest in manifests] == ["broken", "healthy"]
    assert [manifest.status for manifest in manifests] == ["error", "success"]


def test_collect_all_continues_after_unregistered_platform(monkeypatch) -> None:
    _install_registry(monkeypatch, "healthy")
    config = _config(
        unregistered=_platform("unregistered"),
        healthy=_platform("healthy"),
    )

    jobs, manifests = raw_main.collect_all(config)

    assert [job.platform for job in jobs] == ["healthy"]
    assert [manifest.platform for manifest in manifests] == [
        "unregistered",
        "healthy",
    ]
    assert [manifest.status for manifest in manifests] == ["error", "success"]


def test_collect_all_aggregates_jobs_and_manifests(monkeypatch) -> None:
    _install_registry(monkeypatch, "alpha", "beta")
    config = _config(
        alpha=_platform("alpha", job_ids=["a-1", "a-2"]),
        beta=_platform("beta", job_ids=["b-1"]),
    )

    jobs, manifests = raw_main.collect_all(config)

    assert [job.unique_key for job in jobs] == [
        "alpha:a-1",
        "alpha:a-2",
        "beta:b-1",
    ]
    assert [manifest.platform for manifest in manifests] == ["alpha", "beta"]
    assert [manifest.jobs_in_scope for manifest in manifests] == [2, 1]


def test_collect_all_closes_collector_after_success(monkeypatch) -> None:
    _install_registry(monkeypatch, "healthy")
    config = _config(healthy=_platform("healthy"))

    raw_main.collect_all(config)

    assert len(FakeCollector.instances) == 1
    assert FakeCollector.instances[0].closed is True


def test_collect_all_closes_collector_after_exception(monkeypatch) -> None:
    _install_registry(monkeypatch, "broken")
    config = _config(broken=_platform("broken", raise_error=True))

    try:
        raw_main.collect_all(config)
    except RuntimeError:
        pass

    assert len(FakeCollector.instances) == 1
    assert FakeCollector.instances[0].closed is True


def test_collect_all_records_constructor_exception_in_manifest(monkeypatch) -> None:
    class BrokenConstructor:
        def __init__(self, platform_config, collection_config):
            raise RuntimeError("fake constructor failure")

    monkeypatch.setattr(
        raw_main,
        "COLLECTOR_REGISTRY",
        {"broken": BrokenConstructor},
    )
    config = _config(broken=_platform("broken"))

    jobs, manifests = raw_main.collect_all(config)

    assert jobs == []
    assert len(manifests) == 1
    assert manifests[0].status == "error"
    assert "fake constructor failure" in manifests[0].error


def test_collect_all_records_close_exception_and_keeps_jobs(monkeypatch) -> None:
    _install_registry(monkeypatch, "close-broken")
    config = _config(
        **{
            "close-broken": _platform(
                "close-broken",
                raise_close_error=True,
            )
        }
    )

    jobs, manifests = raw_main.collect_all(config)

    assert [job.platform for job in jobs] == ["close-broken"]
    assert len(manifests) == 1
    assert manifests[0].status == "partial"
    assert manifests[0].complete is False
    assert manifests[0].stopped_by == "close_error"
    assert "fake close failure" in manifests[0].error
