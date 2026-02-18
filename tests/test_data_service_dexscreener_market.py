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
            age_hours = {
                "tokena": 72,
                "tokenb": 48,
                "tokenc": 12,
                "tokend": 3,
            }.get(token, 2)
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
                "pairCreatedAt": int((utc_now() - timedelta(hours=age_hours)).timestamp() * 1000),
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


class FailIfSearchedDexClient(FakeDexClient):
    async def search_pairs(self, _query):
        raise AssertionError("search_pairs must not be called for canonical symbols")


class PairFetchDexClient(FakeDexClient):
    async def get_pair(self, chain_id, pair_address):
        return {
            "chainId": chain_id,
            "pairAddress": pair_address,
            "baseToken": {"address": "baseMintX", "symbol": "TOKX", "name": "Token X"},
            "quoteToken": {"address": "quoteMintY", "symbol": "SOL"},
            "priceUsd": "0.0123",
            "priceChange": {"h24": "4.0"},
            "volume": {"h24": 222222.0},
            "liquidity": {"usd": 333333.0},
            "marketCap": 123456.0,
        }


@pytest.mark.asyncio
async def test_dexscreener_boosted_pairs_aggregates_and_sorts(monkeypatch):
    monkeypatch.setattr(settings, "DEXSCREENER_ENABLED", False)
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_LIQUIDITY_USD", 0.0)
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_VOLUME_24H_USD", 0.0)
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_TOKEN_AGE_HOURS", 0.0)
    monkeypatch.setattr(settings, "DEXSCREENER_REQUIRE_UNIQUE_BASE_SYMBOL", False)
    monkeypatch.setattr(settings, "DEXSCREENER_BLOCKED_TOKEN_ADDRESSES", "")
    monkeypatch.setattr(settings, "DEXSCREENER_BLOCKED_PAIR_ADDRESSES", "")
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
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_VOLUME_24H_USD", 0.0)
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_TOKEN_AGE_HOURS", 0.0)
    monkeypatch.setattr(settings, "DEXSCREENER_REQUIRE_UNIQUE_BASE_SYMBOL", False)
    monkeypatch.setattr(settings, "DEXSCREENER_BLOCKED_TOKEN_ADDRESSES", "")
    monkeypatch.setattr(settings, "DEXSCREENER_BLOCKED_PAIR_ADDRESSES", "")
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


@pytest.mark.asyncio
async def test_dynamic_dex_symbols_builds_compact_aliases_and_pair_cache(monkeypatch):
    monkeypatch.setattr(settings, "DEXSCREENER_ENABLED", True)
    monkeypatch.setattr(settings, "DEXSCREENER_DYNAMIC_UNIVERSE_ENABLED", True)
    monkeypatch.setattr(settings, "DEXSCREENER_DYNAMIC_UNIVERSE_SIZE", 5)
    monkeypatch.setattr(settings, "DEXSCREENER_DYNAMIC_UNIVERSE_MODE", "top")
    monkeypatch.setattr(settings, "DEXSCREENER_DYNAMIC_UNIVERSE_SORT", "boosts")
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_LIQUIDITY_USD", 0.0)
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_VOLUME_24H_USD", 0.0)
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_TOKEN_AGE_HOURS", 0.0)
    monkeypatch.setattr(settings, "DEXSCREENER_REQUIRE_UNIQUE_BASE_SYMBOL", False)
    monkeypatch.setattr(settings, "DEXSCREENER_BLOCKED_TOKEN_ADDRESSES", "")
    monkeypatch.setattr(settings, "DEXSCREENER_BLOCKED_PAIR_ADDRESSES", "")
    monkeypatch.setattr(settings, "DEXSCREENER_CHAIN", "solana")

    service = DataService()
    service.dexscreener_client = FakeDexClient()

    symbols = await service.get_dynamic_dex_symbols()

    assert symbols
    assert all(len(symbol) <= 10 for symbol in symbols)
    for symbol in symbols:
        assert symbol in service.dex_pair_cache
        assert service.dex_pair_cache[symbol]["chain_id"] == "solana"
        assert service.dex_pair_cache[symbol]["pair_address"]
        assert service.dex_pair_cache[symbol]["token_address"]


@pytest.mark.asyncio
async def test_dexscreener_boosted_pairs_applies_age_volume_and_blocklist_filters(monkeypatch):
    monkeypatch.setattr(settings, "DEXSCREENER_ENABLED", False)
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_LIQUIDITY_USD", 0.0)
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_VOLUME_24H_USD", 100_000.0)
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_TOKEN_AGE_HOURS", 24.0)
    monkeypatch.setattr(settings, "DEXSCREENER_REQUIRE_UNIQUE_BASE_SYMBOL", False)
    monkeypatch.setattr(settings, "DEXSCREENER_BLOCKED_TOKEN_ADDRESSES", "tokenb")
    monkeypatch.setattr(settings, "DEXSCREENER_BLOCKED_PAIR_ADDRESSES", "")
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

    results = payload["items"]
    assert results
    assert all(item["volume"] >= 100_000.0 for item in results)
    assert all(item["pair_age_hours"] >= 24.0 for item in results)
    assert all(item["base_token_address"] != "tokenb" for item in results)


class AmbiguousSymbolDexClient(FakeDexClient):
    async def get_token_boosts_top(self):
        return [
            {"chainId": "solana", "tokenAddress": "tokenA", "totalAmount": 80.0, "boostCount": 8},
            {"chainId": "solana", "tokenAddress": "tokenX", "totalAmount": 90.0, "boostCount": 9},
            {"chainId": "solana", "tokenAddress": "tokenY", "totalAmount": 70.0, "boostCount": 7},
        ]

    async def get_token_boosts_latest(self):
        return []

    async def get_token_profiles_latest(self):
        return []

    async def get_tokens(self, chain_id, token_addresses):
        now_ms = int(utc_now().timestamp() * 1000)
        rows = []
        for token_address in token_addresses:
            token = token_address.lower()
            symbol = "KIMCHI" if token in {"tokena", "tokenx"} else "UNIQ"
            rows.append({
                "chainId": chain_id,
                "dexId": "pumpfun",
                "pairAddress": f"{token}-pair",
                "baseToken": {"address": token_address, "symbol": symbol, "name": symbol},
                "quoteToken": {"symbol": "SOL"},
                "priceUsd": "0.01",
                "priceChange": {"h24": "1.0"},
                "volume": {"h24": 500_000.0},
                "liquidity": {"usd": 500_000.0},
                "pairCreatedAt": now_ms - int(72 * 3600 * 1000),
                "url": f"https://dexscreener.com/{chain_id}/{token}-pair",
            })
        return rows


@pytest.mark.asyncio
async def test_dexscreener_boosted_pairs_drops_ambiguous_base_symbols(monkeypatch):
    monkeypatch.setattr(settings, "DEXSCREENER_ENABLED", False)
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_LIQUIDITY_USD", 0.0)
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_VOLUME_24H_USD", 0.0)
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_TOKEN_AGE_HOURS", 0.0)
    monkeypatch.setattr(settings, "DEXSCREENER_REQUIRE_UNIQUE_BASE_SYMBOL", True)
    monkeypatch.setattr(settings, "DEXSCREENER_BLOCKED_TOKEN_ADDRESSES", "")
    monkeypatch.setattr(settings, "DEXSCREENER_BLOCKED_PAIR_ADDRESSES", "")
    monkeypatch.setattr(settings, "DEXSCREENER_CHAIN", "solana")

    service = DataService()
    service.dexscreener_client = AmbiguousSymbolDexClient()

    payload = await service.get_dexscreener_boosted_pairs(
        page=1,
        page_size=250,
        mode="top",
        sort_by="boosts",
        chain="solana",
        min_liquidity=0.0,
    )

    base_symbols = {row["base_symbol"] for row in payload["items"]}
    assert "KIMCHI" not in base_symbols
    assert "UNIQ" in base_symbols


@pytest.mark.asyncio
async def test_resolve_dex_pair_rejects_canonical_dash_symbols():
    service = DataService()
    service.dexscreener_client = FailIfSearchedDexClient()

    resolved = await service._resolve_dex_pair("BTC-USD")
    assert resolved is None


@pytest.mark.asyncio
async def test_resolve_dex_pair_rejects_unknown_compact_alias_without_cache():
    service = DataService()
    service.dexscreener_client = FailIfSearchedDexClient()

    resolved = await service._resolve_dex_pair("UNKNOWN123")
    assert resolved is None


@pytest.mark.asyncio
async def test_latest_data_includes_base_and_quote_token_addresses(monkeypatch):
    monkeypatch.setattr(settings, "DEXSCREENER_MIN_LIQUIDITY_USD", 0.0)
    service = DataService()
    service.dexscreener_client = PairFetchDexClient()
    service.dex_pair_cache["TOKX123"] = {
        "chain_id": "solana",
        "pair_address": "pairX",
        "token_address": "baseMintX",
    }
    service.dex_pair_cache_expiry["TOKX123"] = utc_now() + timedelta(hours=1)

    data = await service.get_latest_data_for_symbol("TOKX123")
    assert data is not None
    assert data["base_token_address"] == "basemintx"
    assert data["quote_token_address"] == "quoteminty"
