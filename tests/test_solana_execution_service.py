import requests

from app.core.config import settings
from app.services.solana_execution_service import SolanaExecutionService


class _FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.content = b"{}"

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")


def test_demo_execution_returns_filled(monkeypatch):
    monkeypatch.setattr(settings, "SOLANA_TRADING_MODE", "demo")
    service = SolanaExecutionService()
    result = service.execute({"symbol": "TOK1", "side": "BUY", "quantity": 10, "price": 0.5})
    assert result is not None
    assert result["execution_mode"] == "demo"
    assert result["status"] == "FILLED"


def test_live_execution_requires_auth_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "SOLANA_TRADING_MODE", "live")
    monkeypatch.setattr(settings, "SOLANA_EXECUTOR_URL", "http://executor.local/swap")
    monkeypatch.setattr(settings, "SOLANA_EXECUTOR_REQUIRE_AUTH", True)
    monkeypatch.setattr(settings, "SOLANA_EXECUTOR_AUTH_HEADER", "X-Executor-Key")
    monkeypatch.setattr(settings, "SOLANA_EXECUTOR_API_KEY", "")
    service = SolanaExecutionService()
    result = service.execute({"symbol": "TOK1", "side": "BUY", "quantity": 10, "price": 0.5})
    assert result is None


def test_live_execution_retries_and_uses_idempotency_headers(monkeypatch):
    monkeypatch.setattr(settings, "SOLANA_TRADING_MODE", "live")
    monkeypatch.setattr(settings, "SOLANA_EXECUTOR_URL", "http://executor.local/swap")
    monkeypatch.setattr(settings, "SOLANA_EXECUTOR_REQUIRE_AUTH", False)
    monkeypatch.setattr(settings, "SOLANA_EXECUTOR_AUTH_HEADER", "X-Executor-Key")
    monkeypatch.setattr(settings, "SOLANA_EXECUTOR_API_KEY", "")
    monkeypatch.setattr(settings, "SOLANA_EXECUTOR_MAX_RETRIES", 2)
    monkeypatch.setattr(settings, "SOLANA_EXECUTOR_BACKOFF_SECONDS", 0.0)
    monkeypatch.setattr(settings, "SOLANA_EXECUTOR_TIMEOUT_SECONDS", 5)

    calls = []

    def _fake_post(url, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if len(calls) == 1:
            return _FakeResponse(status_code=503, body={"ok": False})
        return _FakeResponse(
            status_code=200,
            body={"ok": True, "filled_price": 0.51, "fees": 0.02, "tx_signature": "sig_123"},
        )

    monkeypatch.setattr("app.services.solana_execution_service.requests.post", _fake_post)
    monkeypatch.setattr("app.services.solana_execution_service.time.sleep", lambda _x: None)

    service = SolanaExecutionService()
    result = service.execute(
        {
            "symbol": "TOK1",
            "side": "BUY",
            "quantity": 10,
            "price": 0.5,
            "base_token_address": "baseMint",
            "quote_token_address": "quoteMint",
            "pair_address": "pairAddress",
        }
    )

    assert result is not None
    assert result["execution_mode"] == "live"
    assert result["tx_signature"] == "sig_123"
    assert len(calls) == 2
    first_headers = calls[0]["headers"]
    second_headers = calls[1]["headers"]
    assert first_headers["Idempotency-Key"]
    assert first_headers["Idempotency-Key"] == second_headers["Idempotency-Key"]
    assert calls[0]["json"]["client_order_id"] == calls[1]["json"]["client_order_id"]
