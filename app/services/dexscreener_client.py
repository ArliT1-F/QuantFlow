"""
Client for DexScreener public API (market data only).
"""
import asyncio
import random
from typing import Any, Dict, List, Optional

import aiohttp


class DexScreenerClient:
    """Lightweight async client for DexScreener endpoints."""

    def __init__(
        self,
        timeout_seconds: int = 10,
        base_url: str = "https://api.dexscreener.com",
        max_retries: int = 3,
        max_concurrency: int = 8,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=max(timeout_seconds, 1))
        self.max_retries = max(0, int(max_retries))
        self._semaphore = asyncio.Semaphore(max(1, int(max_concurrency)))
        self._session: Optional[aiohttp.ClientSession] = None
        self._metrics = {
            "requests": 0,
            "retries": 0,
            "timeouts": 0,
            "errors": 0,
        }

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def search_pairs(self, query: str) -> List[Dict[str, Any]]:
        payload = await self._get_json(f"/latest/dex/search?q={query}")
        pairs = payload.get("pairs", [])
        return pairs if isinstance(pairs, list) else []

    async def get_pair(self, chain_id: str, pair_address: str) -> Optional[Dict[str, Any]]:
        payload = await self._get_json(f"/latest/dex/pairs/{chain_id}/{pair_address}")
        if isinstance(payload.get("pair"), dict):
            return payload.get("pair")
        pairs = payload.get("pairs", [])
        if isinstance(pairs, list) and pairs:
            return pairs[0]
        return None

    async def get_token_boosts_latest(self) -> List[Dict[str, Any]]:
        payload = await self._get_json("/token-boosts/latest/v1")
        tokens = payload.get("tokens") if isinstance(payload, dict) else payload
        if isinstance(tokens, list):
            return tokens
        if isinstance(payload, list):
            return payload
        return []

    async def get_token_boosts_top(self) -> List[Dict[str, Any]]:
        payload = await self._get_json("/token-boosts/top/v1")
        tokens = payload.get("tokens") if isinstance(payload, dict) else payload
        if isinstance(tokens, list):
            return tokens
        if isinstance(payload, list):
            return payload
        return []

    async def get_token_profiles_latest(self) -> List[Dict[str, Any]]:
        payload = await self._get_json("/token-profiles/latest/v1")
        if isinstance(payload, list):
            return payload
        tokens = payload.get("tokens") if isinstance(payload, dict) else []
        return tokens if isinstance(tokens, list) else []

    async def get_tokens(self, chain_id: str, token_addresses: List[str]) -> List[Dict[str, Any]]:
        if not token_addresses:
            return []
        addr_list = ",".join(token_addresses)
        payload = await self._get_json(f"/tokens/v1/{chain_id}/{addr_list}")
        if isinstance(payload, list):
            return payload
        pairs = payload.get("pairs", []) if isinstance(payload, dict) else []
        return pairs if isinstance(pairs, list) else []

    async def _get_json(self, path: str) -> Any:
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        self._metrics["requests"] += 1

        transient_status_codes = {429, 500, 502, 503, 504}
        for attempt in range(self.max_retries + 1):
            try:
                async with self._semaphore:
                    async with session.get(url, timeout=self.timeout) as response:
                        if response.status in transient_status_codes and attempt < self.max_retries:
                            self._metrics["retries"] += 1
                            await self._sleep_backoff(attempt)
                            continue
                        response.raise_for_status()
                        return await response.json()
            except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
                self._metrics["timeouts"] += 1
                if attempt < self.max_retries:
                    self._metrics["retries"] += 1
                    await self._sleep_backoff(attempt)
                    continue
                self._metrics["errors"] += 1
                raise
            except aiohttp.ClientResponseError as error:
                if error.status in transient_status_codes and attempt < self.max_retries:
                    self._metrics["retries"] += 1
                    await self._sleep_backoff(attempt)
                    continue
                self._metrics["errors"] += 1
                raise
            except aiohttp.ClientError:
                if attempt < self.max_retries:
                    self._metrics["retries"] += 1
                    await self._sleep_backoff(attempt)
                    continue
                self._metrics["errors"] += 1
                raise
        self._metrics["errors"] += 1
        raise RuntimeError("DexScreener request failed after retries")

    async def _sleep_backoff(self, attempt: int):
        base_delay = 0.3 * (2 ** max(attempt, 0))
        jitter = random.uniform(0.01, 0.16)
        await asyncio.sleep(base_delay + jitter)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def get_metrics(self) -> Dict[str, int]:
        return dict(self._metrics)
