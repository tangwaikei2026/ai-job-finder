from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import httpx

from src.raw.models import CollectionManifest, CollectionResult

logger = logging.getLogger(__name__)


class RawCollector(ABC):
    platform: str

    def __init__(
        self,
        platform_config: dict[str, Any],
        collection_config: dict[str, Any],
        client: httpx.Client | None = None,
    ):
        self.platform_config = platform_config
        self.collection_config = collection_config
        self.cities = [str(city).strip() for city in collection_config.get("cities", []) if city]
        self.include_unknown_location = bool(
            collection_config.get("include_unknown_location", False)
        )
        self.max_retries = max(1, int(collection_config.get("max_retries", 3)))
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=float(collection_config.get("timeout_seconds", 30)),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            follow_redirects=True,
        )

    @abstractmethod
    def collect(self) -> CollectionResult:
        raise NotImplementedError

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                wait = min(2 ** (attempt - 1), 4) + random.uniform(0, 0.25)
                logger.warning(
                    "[%s] request failed (%d/%d): %s; retrying in %.1fs",
                    self.platform,
                    attempt,
                    self.max_retries,
                    exc,
                    wait,
                )
                time.sleep(wait)
        assert last_error is not None
        raise last_error

    def request_json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        response = self.request(method, url, **kwargs)
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError(f"expected JSON object, got {type(data).__name__}")
        return data

    @staticmethod
    def _city_token(value: str) -> str:
        return value.strip().removesuffix("市")

    def location_in_scope(self, location: str) -> bool:
        if not location.strip():
            return self.include_unknown_location
        if not self.cities:
            return True
        normalized_location = self._city_token(location)
        return any(
            self._city_token(city) in normalized_location
            for city in self.cities
        )

    @staticmethod
    def finish_manifest(
        manifest: CollectionManifest,
        started_monotonic: float,
    ) -> None:
        manifest.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        manifest.duration_seconds = round(time.monotonic() - started_monotonic, 3)
