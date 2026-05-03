"""Tests for the Oura webhook subscription management service.

Covers `_webhook_headers`, `_verification_token`, the four CRUD functions
(create, delete, renew, list), and `register_all_webhooks` (which posts
SUBSCRIBE_DATA_TYPES x [create, update] = 12 subscriptions).

Audit follow-up: docs/comprehensive-scan-2026-04-30.md section 5
flagged this as zero-test.

Run: cd backend && uv run python -m pytest tests/test_oura_webhooks.py -v
"""

from __future__ import annotations

import os
import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "T0TXLkHFSeZRYGIIejSFVkhQrvRE-bWLkwXSkkdWiKQ=")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-tests-dont-call-anthropic")

import httpx

from app.config import settings
from app.services import oura_webhooks


# Fake httpx.AsyncClient ---------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_data: dict | list | None = None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}",
                request=httpx.Request("POST", "https://example/"),
                response=httpx.Response(self.status_code),
            )


class _FakeAsyncClient:
    """Records every call (method, url, headers, json) and returns canned responses."""

    calls: list[dict] = []
    next_responses: list[_FakeResponse] = []

    def __init__(self, *args, **kwargs):
        self.init_kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def _record(self, method, url, **kwargs):
        _FakeAsyncClient.calls.append({"method": method, "url": url, **kwargs})
        if _FakeAsyncClient.next_responses:
            return _FakeAsyncClient.next_responses.pop(0)
        return _FakeResponse(status_code=200, json_data={"id": "fake-sub-id"})

    async def post(self, url, **kwargs):
        return await self._record("POST", url, **kwargs)

    async def get(self, url, **kwargs):
        return await self._record("GET", url, **kwargs)

    async def put(self, url, **kwargs):
        return await self._record("PUT", url, **kwargs)

    async def delete(self, url, **kwargs):
        return await self._record("DELETE", url, **kwargs)


@pytest.fixture(autouse=True)
def _reset_fake_client(monkeypatch):
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.next_responses = []
    monkeypatch.setattr(oura_webhooks.httpx, "AsyncClient", _FakeAsyncClient)


# _webhook_headers + _verification_token ---------------------------------


def test_webhook_headers_carries_settings_credentials(monkeypatch):
    monkeypatch.setattr(settings, "oura_client_id", "test-client-id")
    monkeypatch.setattr(settings, "oura_client_secret", "test-client-secret")
    headers = oura_webhooks._webhook_headers()
    assert headers["x-client-id"] == "test-client-id"
    assert headers["x-client-secret"] == "test-client-secret"
    assert headers["Content-Type"] == "application/json"


def test_verification_token_reads_settings(monkeypatch):
    monkeypatch.setattr(settings, "oura_webhook_verification_token", "tok-abc")
    assert oura_webhooks._verification_token() == "tok-abc"


# create_subscription -----------------------------------------------------


@pytest.mark.asyncio
async def test_create_subscription_posts_to_oura_with_body_and_headers(monkeypatch):
    monkeypatch.setattr(settings, "oura_webhook_verification_token", "verify-tok")
    monkeypatch.setattr(settings, "oura_client_id", "cid")
    monkeypatch.setattr(settings, "oura_client_secret", "csecret")

    _FakeAsyncClient.next_responses = [
        _FakeResponse(200, {"id": "sub-1", "data_type": "daily_sleep", "event_type": "create"})
    ]

    result = await oura_webhooks.create_subscription(
        callback_url="https://example.com/webhook",
        data_type="daily_sleep",
        event_type="create",
    )
    assert result["id"] == "sub-1"

    [call] = _FakeAsyncClient.calls
    assert call["method"] == "POST"
    assert call["url"] == oura_webhooks.OURA_WEBHOOK_URL
    assert call["headers"]["x-client-id"] == "cid"
    body = call["json"]
    assert body["callback_url"] == "https://example.com/webhook"
    assert body["data_type"] == "daily_sleep"
    assert body["event_type"] == "create"
    assert body["verification_token"] == "verify-tok"


@pytest.mark.asyncio
async def test_create_subscription_raises_on_4xx():
    _FakeAsyncClient.next_responses = [_FakeResponse(401)]
    with pytest.raises(httpx.HTTPStatusError):
        await oura_webhooks.create_subscription(
            callback_url="https://example.com/webhook",
            data_type="daily_sleep",
        )


# delete_subscription -----------------------------------------------------


@pytest.mark.asyncio
async def test_delete_returns_true_on_204():
    _FakeAsyncClient.next_responses = [_FakeResponse(204)]
    assert await oura_webhooks.delete_subscription("sub-1") is True

    [call] = _FakeAsyncClient.calls
    assert call["method"] == "DELETE"
    assert call["url"] == f"{oura_webhooks.OURA_WEBHOOK_URL}/sub-1"


@pytest.mark.asyncio
async def test_delete_returns_false_on_non_204():
    _FakeAsyncClient.next_responses = [_FakeResponse(404)]
    assert await oura_webhooks.delete_subscription("sub-1") is False


# renew_subscription ------------------------------------------------------


@pytest.mark.asyncio
async def test_renew_puts_to_renew_path():
    _FakeAsyncClient.next_responses = [_FakeResponse(200, {"id": "sub-1", "expires_at": "2027-01-01"})]
    result = await oura_webhooks.renew_subscription("sub-1")
    assert result["id"] == "sub-1"

    [call] = _FakeAsyncClient.calls
    assert call["method"] == "PUT"
    assert call["url"] == f"{oura_webhooks.OURA_WEBHOOK_URL}/renew/sub-1"


@pytest.mark.asyncio
async def test_renew_raises_on_4xx():
    _FakeAsyncClient.next_responses = [_FakeResponse(404)]
    with pytest.raises(httpx.HTTPStatusError):
        await oura_webhooks.renew_subscription("sub-1")


# list_subscriptions ------------------------------------------------------


@pytest.mark.asyncio
async def test_list_returns_subscriptions_array():
    _FakeAsyncClient.next_responses = [_FakeResponse(200, [{"id": "a"}, {"id": "b"}])]
    result = await oura_webhooks.list_subscriptions()
    assert result == [{"id": "a"}, {"id": "b"}]

    [call] = _FakeAsyncClient.calls
    assert call["method"] == "GET"
    assert call["url"] == oura_webhooks.OURA_WEBHOOK_URL


# register_all_webhooks --------------------------------------------------


@pytest.mark.asyncio
async def test_register_all_webhooks_posts_one_per_data_type_and_event_type():
    """Should POST exactly len(SUBSCRIBE_DATA_TYPES) * 2 (create + update) times."""
    _FakeAsyncClient.next_responses = [
        _FakeResponse(200, {"id": f"sub-{i}"})
        for i in range(len(oura_webhooks.SUBSCRIBE_DATA_TYPES) * 2)
    ]

    results = await oura_webhooks.register_all_webhooks("https://meld.example.com")
    expected_count = len(oura_webhooks.SUBSCRIBE_DATA_TYPES) * 2
    assert len(results) == expected_count
    assert len(_FakeAsyncClient.calls) == expected_count

    callback_url = "https://meld.example.com/api/webhooks/oura"
    posted_combos = {
        (call["json"]["data_type"], call["json"]["event_type"])
        for call in _FakeAsyncClient.calls
    }
    expected_combos = {
        (dt, et)
        for dt in oura_webhooks.SUBSCRIBE_DATA_TYPES
        for et in ("create", "update")
    }
    assert posted_combos == expected_combos
    assert all(call["json"]["callback_url"] == callback_url for call in _FakeAsyncClient.calls)


@pytest.mark.asyncio
async def test_register_all_webhooks_continues_on_individual_failure():
    """If one subscription fails, the rest still register and the error is logged."""
    n = len(oura_webhooks.SUBSCRIBE_DATA_TYPES) * 2
    responses = [_FakeResponse(200, {"id": f"sub-{i}"}) for i in range(n)]
    responses[3] = _FakeResponse(500)  # one mid-stream failure
    _FakeAsyncClient.next_responses = responses

    results = await oura_webhooks.register_all_webhooks("https://meld.example.com")
    assert len(results) == n - 1, "successful ones still returned"
    assert len(_FakeAsyncClient.calls) == n, "all attempts made"
