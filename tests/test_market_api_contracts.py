import pytest
from fastapi import HTTPException

from app.api import routes
from app.core.config import settings


class StubDataService:
    async def get_dexscreener_boosted_pairs(self, **kwargs):
        return {
            "items": [
                {
                    "symbol": "TOK/USDT",
                    "name": "Token",
                    "price": 1.25,
                    "change_percent": 3.4,
                    "volume": 100000.0,
                    "liquidity": 55000.0,
                    "market_cap": None,
                    "chain": "solana",
                    "dex": "pumpfun",
                    "pair_address": "abc123",
                    "url": "https://dexscreener.com/solana/abc123",
                    "boost_amount": 10.0,
                    "boost_count": 3,
                }
            ],
            "total": 1,
            "summary": {
                "volume": 100000.0,
                "liquidity": 55000.0,
                "avg_change_percent": 3.4,
            },
            "meta": {
                "as_of": "2026-01-01T00:00:00+00:00",
                "is_stale": False,
                "age_seconds": 2,
                "source_counts": {"top": 30, "latest": 30, "profiles": 10, "tokens": 80, "pairs": 1},
            },
        }

    def get_market_health(self):
        return {
            "service": "dexscreener",
            "enabled": True,
            "telemetry": {
                "boost_requests": 10,
                "fetch_success": 9,
                "fetch_error": 1,
                "cache_hit": 4,
                "stale_fallback": 1,
                "fetch_retry": 2,
                "fetch_timeout": 1,
                "fetch_requests": 25,
                "fetch_client_errors": 1,
            },
            "cache_entries": 5,
            "last_refresh": "2026-01-01T00:00:00+00:00",
            "last_error": None,
            "timestamp": "2026-01-01T00:00:05+00:00",
        }


@pytest.mark.asyncio
async def test_market_boosts_rejects_invalid_query(monkeypatch):
    monkeypatch.setattr(settings, "DEXSCREENER_ENABLED", True)
    monkeypatch.setattr(routes, "data_service", StubDataService())

    with pytest.raises(HTTPException) as exc:
        await routes.get_dexscreener_boosts(mode="wrong-mode")
    assert exc.value.status_code == 422
    assert exc.value.detail["error_code"] == "market.invalid_query"


@pytest.mark.asyncio
async def test_market_boosts_returns_meta_contract(monkeypatch):
    monkeypatch.setattr(settings, "DEXSCREENER_ENABLED", True)
    monkeypatch.setattr(routes, "data_service", StubDataService())

    payload = await routes.get_dexscreener_boosts(mode="top", sort="liquidity", page_size="25")
    assert payload["count"] == 1
    assert payload["meta"]["is_stale"] is False
    assert payload["meta"]["age_seconds"] == 2
    assert payload["results"][0]["pair_address"] == "abc123"


@pytest.mark.asyncio
async def test_market_health_endpoint(monkeypatch):
    monkeypatch.setattr(routes, "data_service", StubDataService())

    payload = await routes.get_market_health()
    assert payload["service"] == "dexscreener"
    assert payload["telemetry"]["fetch_retry"] == 2
