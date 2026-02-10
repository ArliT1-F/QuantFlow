from datetime import timedelta

import pytest

from app.core.config import settings
from app.services.data_service import DataService, utc_now


class FakeDexClient:
    def __init__(self):
        self.fail_mode = False
        self._metrics = {
            "requests": 0,
            "retries": 0,
            "timeouts": 0,
            "errors": 0,
        }

    async def get_token_boosts_top(self):
        self._metrics["requests"] += 1
        if self.fail_mode:
            self._metrics["errors"] += 1
            raise RuntimeError("forced failure")
        return [
            {"chainId": "solana", "tokenAddress": "tokenA", "totalAmount": 120.0, "boostCount": 12},
            {"chainId": "solana", "tokenAddress": "tokenB", "totalAmount": 25.0, "boostCount": 4},
        ]

    async def get_token_boosts_latest(self):
        self._metrics["requests"] += 1
        if self.fail_mode:
            self._metrics["errors"] += 1
            raise RuntimeError("forced failure")
        return [
            {"chainId": "solana", "tokenAddress": "tokenB", "totalAmount": 30.0, "boostCount": 5},
            {"chainId": "solana", "tokenAddress": "tokenC", "totalAmount": 12.0, "boostCount": 2},
        ]

    async def get_token_profiles_latest(self):
        self._metrics["requests"] += 1
        if self.fail_mode:
            self._metrics["errors"] += 1
            raise RuntimeError("forced failure")
        return [
            {"chainId": "solana", "tokenAddress": "tokenD"},
        ]

    async def get_tokens(self, chain_id, token_addresses):
        self._metrics["requests"] += 1
        if self.fail_mode:
            self._metrics["errors"] += 1
            raise RuntimeError("forced failure")
        rows = []
        for token_address in token_addresses:
            token = token_address.lower()
            liquidity = {
                "tokena": 250_000.0,
                "tokenb": 140_000.0,
                "tokenc": 90_000.0,
                "tokend": 50_000.0,
            }.get(token, 10_000.0)
            volume = {
                "tokena": 180_000.0,
                "tokenb": 125_000.0,
                "tokenc": 50_000.0,
                "tokend": 20_000.0,
            }.get(token, 1_000.0)
            rows.append({
                "chainId": chain_id,
                "dexId": "pumpfun",
                "pairAddress": f"{token}-pair",
                "baseToken": {"address": token_address, "symbol": token.upper(), "name": token.upper()},
                "quoteToken": {"symbol": "USDT"},
                "priceUsd": "0.00123",
                "priceChange": {"h24": "5.2"},
                "volume": {"h24": volume},
                "liquidity": {"usd": liquidity},
                "url": f"https://dexscreener.com/{chain_id}/{token}-pair",
            })
            # Add a worse duplicate for tokenA to verify best-pair selection.
            if token == "tokena":
                rows.append({
                    "chainId": chain_id,
                    "dexId": "pumpfun",
                    "pairAddress": f"{token}-pair-alt",
                    "baseToken": {"address": token_address, "symbol": token.upper(), "name": token.upper()},
                    "quoteToken": {"symbol": "USDT"},
                    "priceUsd": "0.0011",
                    "priceChange": {"h24": "3.2"},
                    "volume": {"h24": 10_000.0},
                    "liquidity": {"usd": 20_000.0},
                    "url": f"https://dexscreener.com/{chain_id}/{token}-pair-alt",
                })
        return rows

    def get_metrics(self):
        return dict(self._metrics)

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_dexscreener_boosted_pairs_aggregates_and_sorts(monkeypatch):
    monkeypatch.setattr(settings, "DEXSCREENER_ENABLED", False)
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_LIQUIDITY_USD", 0.0)
    monkeypatch.setattr(settings, "DEXSCREENER_CHAIN", "")

    service = DataService()
    service.dexscreener_client = FakeDexClient()

    payload = await service.get_dexscreener_boosted_pairs(
        page=1,
        page_size=250,
        mode="top",
        sort_by="boosts",
        chain="solana",
        min_liquidity=0.0,
    )

    assert payload["total"] >= 4
    assert payload["items"][0]["pair_address"] == "tokena-pair"
    assert payload["meta"]["is_stale"] is False
    assert payload["meta"]["source_counts"]["profiles"] == 1

    pair_keys = {
        f"{row.get('chain', '').lower()}::{row.get('pair_address', '').lower()}"
        for row in payload["items"]
    }
    assert len(pair_keys) == len(payload["items"])


@pytest.mark.asyncio
async def test_dexscreener_boosted_pairs_uses_stale_cache_on_failure(monkeypatch):
    monkeypatch.setattr(settings, "DEXSCREENER_ENABLED", False)
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_LIQUIDITY_USD", 0.0)
    monkeypatch.setattr(settings, "DEXSCREENER_CHAIN", "")

    service = DataService()
    fake_client = FakeDexClient()
    service.dexscreener_client = fake_client

    first = await service.get_dexscreener_boosted_pairs(
        page=1,
        page_size=50,
        mode="top",
        sort_by="volume",
        chain="solana",
        min_liquidity=0.0,
    )
    assert first["meta"]["is_stale"] is False

    for key in list(service.dex_boost_cache_expiry.keys()):
        service.dex_boost_cache_expiry[key] = utc_now() - timedelta(seconds=1)

    fake_client.fail_mode = True
    stale = await service.get_dexscreener_boosted_pairs(
        page=1,
        page_size=50,
        mode="top",
        sort_by="volume",
        chain="solana",
        min_liquidity=0.0,
    )
    assert stale["meta"]["is_stale"] is True
    assert service.market_metrics["stale_fallback"] >= 1

    health = service.get_market_health()
    assert health["telemetry"]["boost_requests"] >= 2
    assert health["telemetry"]["fetch_error"] >= 1
