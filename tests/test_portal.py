from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from src.portal import bootstrap_portal


LIST_URL = "https://example.test/positions"
LIST_API = "https://example.test/api/v1/search/job/posts"


@dataclass
class FakeNavigationResponse:
    status: int
    url: str


@dataclass
class FakeRequest:
    url: str = LIST_API
    method: str = "POST"
    post_data: str = json.dumps({"offset": 0, "limit": 10})


@dataclass
class FakeApiResponse:
    url: str
    payload: dict[str, Any]
    status: int = 200

    def json(self) -> dict[str, Any]:
        return self.payload


class FakePage:
    def __init__(
        self,
        navigation_outcomes: list[FakeNavigationResponse | Exception],
        *,
        request_after_waits: int | None,
        filter_response_after_waits: int | None = None,
    ) -> None:
        self.navigation_outcomes = list(navigation_outcomes)
        self.request_after_waits = request_after_waits
        self.filter_response_after_waits = filter_response_after_waits
        self.listeners: dict[str, list[Any]] = {"request": [], "response": []}
        self.goto_count = 0
        self.goto_kwargs: list[dict[str, Any]] = []
        self.successful_navigation_count = 0
        self.wait_count = 0
        self.wait_durations: list[int] = []

    def on(self, event: str, listener: Any) -> None:
        self.listeners[event].append(listener)

    def remove_listener(self, event: str, listener: Any) -> None:
        self.listeners[event].remove(listener)

    def goto(self, url: str, **kwargs: Any) -> FakeNavigationResponse:
        self.goto_count += 1
        self.goto_kwargs.append(kwargs)
        outcome = self.navigation_outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        self.successful_navigation_count += 1
        return outcome

    def wait_for_timeout(self, duration: int) -> None:
        self.wait_count += 1
        self.wait_durations.append(duration)
        if (
            self.successful_navigation_count
            and self.request_after_waits == self.wait_count
        ):
            request = FakeRequest()
            for listener in list(self.listeners["request"]):
                listener(request)
        if self.filter_response_after_waits == self.wait_count:
            response = FakeApiResponse(
                url="https://example.test/api/v1/config/job/filters/6",
                payload={"data": {"city_list": [{"code": "CN"}]}},
            )
            for listener in list(self.listeners["response"]):
                listener(response)


def success_response(url: str = LIST_URL) -> FakeNavigationResponse:
    return FakeNavigationResponse(status=200, url=url)


def test_bootstrap_portal_accepts_200_and_matching_list_api() -> None:
    page = FakePage([success_response()], request_after_waits=1)

    result = bootstrap_portal(page, LIST_URL)

    assert result.request_url == LIST_API
    assert result.request_body == {"offset": 0, "limit": 10}
    assert page.goto_count == 1
    assert page.goto_kwargs[0]["wait_until"] == "domcontentloaded"


def test_bootstrap_portal_accepts_redirect_to_final_200() -> None:
    final_url = "https://example.test/current/positions"
    page = FakePage([success_response(final_url)], request_after_waits=1)

    result = bootstrap_portal(page, LIST_URL)

    assert result.request_url == LIST_API
    assert page.goto_count == 1


def test_bootstrap_portal_preserves_shared_filter_capture() -> None:
    page = FakePage(
        [success_response()],
        request_after_waits=1,
        filter_response_after_waits=2,
    )

    result = bootstrap_portal(
        page,
        LIST_URL,
        filter_marker="/api/v1/config/job/filters/6",
    )

    assert result.filter_data == {"city_list": [{"code": "CN"}]}
    assert page.goto_count == 1


def test_bootstrap_portal_direct_404_is_navigation_failure() -> None:
    page = FakePage(
        [FakeNavigationResponse(status=404, url=LIST_URL)],
        request_after_waits=None,
    )

    with pytest.raises(RuntimeError, match="NAVIGATION_FAILURE.*HTTP 404"):
        bootstrap_portal(page, LIST_URL)

    assert page.goto_count == 1
    assert page.wait_count == 0


def test_bootstrap_portal_redirect_to_404_is_navigation_failure() -> None:
    final_url = "https://example.test/missing"
    page = FakePage(
        [FakeNavigationResponse(status=404, url=final_url)],
        request_after_waits=None,
    )

    with pytest.raises(RuntimeError, match=f"NAVIGATION_FAILURE.*{final_url}"):
        bootstrap_portal(page, LIST_URL)


def test_bootstrap_portal_200_without_list_api_is_distinct_failure() -> None:
    page = FakePage([success_response()], request_after_waits=None)

    with pytest.raises(RuntimeError, match="LIST_API_NOT_OBSERVED"):
        bootstrap_portal(page, LIST_URL, attempts=2, wait_ms=500)

    assert page.goto_count == 1
    assert page.wait_count == 4


def test_bootstrap_portal_recovers_from_first_navigation_exception() -> None:
    page = FakePage(
        [RuntimeError("temporary navigation failure"), success_response()],
        request_after_waits=2,
    )

    result = bootstrap_portal(page, LIST_URL)

    assert result.request_url == LIST_API
    assert page.goto_count == 2
    assert page.wait_count == 2
    assert page.wait_durations == [1000, 250]


def test_bootstrap_portal_waits_second_window_without_renavigating() -> None:
    page = FakePage([success_response()], request_after_waits=40)

    result = bootstrap_portal(page, LIST_URL, attempts=2, wait_ms=9000)

    assert result.request_url == LIST_API
    assert page.goto_count == 1
    assert page.wait_count == 40
