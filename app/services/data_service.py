"""
Data service for fetching and managing market data
"""
import asyncio
import logging
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from urllib.parse import quote_plus
import yfinance as yf
import pandas as pd
from alpha_vantage.timeseries import TimeSeries

from app.core.config import settings
from app.services.okx_client import OkxClient
from app.services.dexscreener_client import DexScreenerClient

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class DataService:
    """Service for fetching and managing market data from multiple sources"""
    
    def __init__(self):
        self.alpha_vantage = None
        self.cache = {}
        self.cache_expiry = {}
        self.history_cache = {}
        self.history_cache_expiry = {}
        self.is_running_flag = False
        self.data_task = None
        self.okx_client = None
        self.dexscreener_client = None
        self.dex_pair_cache: Dict[str, Dict[str, Any]] = {}
        self.dex_pair_cache_expiry: Dict[str, datetime] = {}
        self.dex_history: Dict[str, List[Dict[str, Any]]] = {}
        self.dex_boost_cache: Dict[str, Dict[str, Any]] = {}
        self.dex_boost_cache_expiry: Dict[str, datetime] = {}
        self.dex_boost_cache_written_at: Dict[str, datetime] = {}
        self.market_metrics: Dict[str, int] = {
            "boost_requests": 0,
            "fetch_success": 0,
            "fetch_error": 0,
            "cache_hit": 0,
            "stale_fallback": 0,
        }
        self.market_last_error: str = ""
        self.market_last_refresh: Optional[datetime] = None
        self.dex_fetch_semaphore = asyncio.Semaphore(6)
        
        # Initialize Alpha Vantage if API key is available
        if settings.ALPHA_VANTAGE_ENABLED and settings.ALPHA_VANTAGE_API_KEY:
            try:
                self.alpha_vantage = TimeSeries(key=settings.ALPHA_VANTAGE_API_KEY)
                logger.info("Alpha Vantage initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Alpha Vantage: {e}")

        if settings.OKX_ENABLED and settings.OKX_MARKET_DATA_ENABLED:
            try:
                self.okx_client = OkxClient(
                    api_key=settings.OKX_API_KEY,
                    secret_key=settings.OKX_SECRET_KEY,
                    passphrase=settings.OKX_PASSPHRASE,
                    base_url=settings.OKX_BASE_URL,
                    demo=settings.OKX_DEMO_TRADING
                )
                logger.info("OKX client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OKX client: {e}")

        if settings.DEXSCREENER_ENABLED:
            try:
                self.dexscreener_client = DexScreenerClient(
                    timeout_seconds=settings.DEXSCREENER_TIMEOUT_SECONDS,
                    max_retries=settings.DEXSCREENER_MAX_RETRIES,
                    max_concurrency=settings.DEXSCREENER_MAX_CONCURRENCY,
                )
                logger.info("DexScreener client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize DexScreener client: {e}")
        
        logger.info("Data service initialized")
    
    async def start_data_collection(self):
        """Start background data collection"""
        self.is_running_flag = True
        self.data_task = asyncio.create_task(self._data_collection_loop())
        logger.info("Data collection started")
    
    async def stop_data_collection(self):
        """Stop background data collection"""
        self.is_running_flag = False
        if self.data_task:
            self.data_task.cancel()
            try:
                await self.data_task
            except asyncio.CancelledError:
                pass
        if self.dexscreener_client:
            await self.dexscreener_client.close()
        logger.info("Data collection stopped")
    
    def is_running(self) -> bool:
        """Check if data service is running"""
        return self.is_running_flag
    
    async def _data_collection_loop(self):
        """Background data collection loop"""
        while self.is_running_flag:
            try:
                # Update data for all symbols
                await self._update_all_symbols_data()
                
                # Wait before next update
                await asyncio.sleep(settings.DATA_UPDATE_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in data collection loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def _update_all_symbols_data(self):
        """Update data for all configured symbols"""
        for symbol in settings.DEFAULT_SYMBOLS:
            try:
                await self.get_latest_data_for_symbol(symbol)
            except Exception as e:
                logger.error(f"Error updating data for {symbol}: {e}")
    
    async def get_latest_data(self, include_history: bool = False) -> Dict[str, Any]:
        """Get latest data for all symbols"""
        data = {}
        for symbol in settings.DEFAULT_SYMBOLS:
            symbol_data = await self.get_latest_data_for_symbol(symbol, include_history=include_history)
            if symbol_data:
                data[symbol] = symbol_data
        return data
    
    async def get_latest_data_for_symbol(self, symbol: str, include_history: bool = False) -> Optional[Dict[str, Any]]:
        """Get latest data for a specific symbol"""
        # Check cache first
        if include_history and self._is_history_cache_valid(symbol):
            return self.history_cache.get(symbol)
        if self._is_cache_valid(symbol) and not include_history:
            return self.cache.get(symbol)
        
        try:
            if self.dexscreener_client:
                dex_data = await self._fetch_dexscreener_data(symbol, include_history=include_history)
                if dex_data:
                    if "history" in dex_data:
                        self._cache_history_data(symbol, dex_data)
                        cache_copy = dex_data.copy()
                        cache_copy.pop("history", None)
                        self._cache_data(symbol, cache_copy)
                    else:
                        self._cache_data(symbol, dex_data)
                    return dex_data
                # If explicitly enabled and no usable pair found, fall back only if Yahoo is enabled.
                if not settings.YAHOO_FINANCE_ENABLED and not self.okx_client:
                    return None

            if self.okx_client:
                okx_data = await self._fetch_okx_data(symbol, include_history=include_history)
                if okx_data:
                    if "history" in okx_data:
                        self._cache_history_data(symbol, okx_data)
                        cache_copy = okx_data.copy()
                        cache_copy.pop("history", None)
                        self._cache_data(symbol, cache_copy)
                    else:
                        self._cache_data(symbol, okx_data)
                    return okx_data
                # If explicitly enabled and no usable pair found, fall back only if Yahoo is enabled.
                if not settings.YAHOO_FINANCE_ENABLED:
                    return None

            # Fetch from Yahoo Finance (primary source)
            yahoo_data = None
            if settings.YAHOO_FINANCE_ENABLED:
                yahoo_data = await self._fetch_yahoo_data(symbol, include_history=include_history)
            
            # Fetch from Alpha Vantage if available (secondary source)
            alpha_data = None
            if self.alpha_vantage and "-USD" not in symbol.upper():
                alpha_data = await self._fetch_alpha_vantage_data(symbol)
            
            # Combine and process data
            combined_data = self._combine_data_sources(yahoo_data, alpha_data)
            
            # Cache the data (without history to keep cache light)
            if combined_data and "history" in combined_data:
                self._cache_history_data(symbol, combined_data)
                cache_copy = combined_data.copy()
                cache_copy.pop("history", None)
                self._cache_data(symbol, cache_copy)
            else:
                self._cache_data(symbol, combined_data)
            
            return combined_data
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return self.cache.get(symbol)  # Return cached data if available

    def _okx_inst_id(self, symbol: str) -> str:
        if "-" in symbol:
            base, quote = symbol.split("-", 1)
            if quote.upper() == "USD":
                quote = settings.OKX_QUOTE_CCY
            return f"{base.upper()}-{quote.upper()}"
        return f"{symbol.upper()}-{settings.OKX_QUOTE_CCY}"

    async def _fetch_okx_data(self, symbol: str, include_history: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch data from OKX market API"""
        try:
            inst_id = self._okx_inst_id(symbol)
            ticker = self.okx_client.get_ticker(inst_id)
            if not ticker:
                return None

            last = float(ticker.get("last", 0))
            open24h = float(ticker.get("open24h", 0))
            high24h = float(ticker.get("high24h", 0))
            low24h = float(ticker.get("low24h", 0))
            vol24h = float(ticker.get("vol24h", 0))
            change = last - open24h if open24h else 0.0
            change_percent = (change / open24h * 100) if open24h else 0.0

            data = {
                "symbol": symbol,
                "price": last,
                "open": open24h,
                "high": high24h,
                "low": low24h,
                "volume": vol24h,
                "change": change,
                "change_percent": change_percent,
                "timestamp": utc_now()
            }

            if include_history:
                candles = self.okx_client.get_candles(inst_id, bar="1D", limit=90)
                if candles:
                    data["history"] = candles

            return data
        except Exception as e:
            logger.error(f"Error fetching OKX data for {symbol}: {e}")
            return None

    async def _fetch_dexscreener_data(self, symbol: str, include_history: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch data from DexScreener."""
        try:
            pair_info = await self._resolve_dex_pair(symbol)
            if not pair_info:
                return None

            pair = await self.dexscreener_client.get_pair(pair_info["chain_id"], pair_info["pair_address"])
            if not pair:
                return None

            liquidity_usd = float((pair.get("liquidity") or {}).get("usd") or 0.0)
            if liquidity_usd < settings.DEXSCREENER_MIN_LIQUIDITY_USD:
                return None

            price = float(pair.get("priceUsd") or 0.0)
            if price <= 0:
                return None

            change_percent = float((pair.get("priceChange") or {}).get("h24") or 0.0)
            open_price = price / (1.0 + (change_percent / 100.0)) if change_percent != -100 else price
            if open_price <= 0:
                open_price = price
            change = price - open_price
            volume = float((pair.get("volume") or {}).get("h24") or 0.0)

            data = {
                "symbol": symbol,
                "price": price,
                "open": open_price,
                "high": price,
                "low": price,
                "volume": volume,
                "change": change,
                "change_percent": change_percent,
                "market_cap": pair.get("marketCap"),
                "timestamp": utc_now()
            }

            self._append_dex_history(symbol, data)
            if include_history:
                data["history"] = list(self.dex_history.get(symbol, []))

            return data
        except Exception as e:
            logger.error(f"Error fetching DexScreener data for {symbol}: {e}")
            return None

    async def _resolve_dex_pair(self, symbol: str) -> Optional[Dict[str, str]]:
        """Resolve and cache best DexScreener pair for a symbol."""
        if self._is_dex_pair_cache_valid(symbol):
            return self.dex_pair_cache.get(symbol)

        if not self.dexscreener_client:
            return None

        query = self._build_dex_query(symbol)
        if not query:
            return None

        pairs = await self.dexscreener_client.search_pairs(quote_plus(query))
        if not pairs:
            return None

        selected = self._select_best_dex_pair(symbol, pairs)
        if not selected:
            return None

        cached = {"chain_id": selected["chainId"], "pair_address": selected["pairAddress"]}
        self.dex_pair_cache[symbol] = cached
        self.dex_pair_cache_expiry[symbol] = utc_now() + timedelta(hours=6)
        return cached

    def _select_best_dex_pair(self, symbol: str, pairs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        target_chain = settings.DEXSCREENER_CHAIN.strip().lower()
        quote_symbol = settings.DEXSCREENER_QUOTE_SYMBOL.strip().upper()
        filtered = []
        for pair in pairs:
            if not isinstance(pair, dict):
                continue
            chain = str(pair.get("chainId") or "").lower()
            if target_chain and chain != target_chain:
                continue
            quote = str((pair.get("quoteToken") or {}).get("symbol") or "").upper()
            if quote_symbol and quote and quote != quote_symbol:
                continue
            liquidity_usd = float((pair.get("liquidity") or {}).get("usd") or 0.0)
            if liquidity_usd < settings.DEXSCREENER_MIN_LIQUIDITY_USD:
                continue
            filtered.append(pair)

        candidates = filtered if filtered else pairs
        if not candidates:
            return None

        def score(p: Dict[str, Any]) -> float:
            liquidity = float((p.get("liquidity") or {}).get("usd") or 0.0)
            volume = float((p.get("volume") or {}).get("h24") or 0.0)
            return (liquidity * 2.0) + volume

        candidates.sort(key=score, reverse=True)
        best = candidates[0]
        if "chainId" not in best or "pairAddress" not in best:
            return None
        return best

    def _build_dex_query(self, symbol: str) -> str:
        base = symbol.split("-", 1)[0].strip().upper()
        quote = settings.DEXSCREENER_QUOTE_SYMBOL.strip().upper()
        if not base:
            return symbol
        return f"{base}/{quote}" if quote else base

    def _is_dex_pair_cache_valid(self, symbol: str) -> bool:
        expiry = self.dex_pair_cache_expiry.get(symbol)
        if not expiry:
            return False
        return utc_now() < expiry

    def _append_dex_history(self, symbol: str, latest: Dict[str, Any]):
        history = self.dex_history.setdefault(symbol, [])
        candle = {
            "timestamp": latest["timestamp"].isoformat(),
            "open": float(latest["open"]),
            "high": float(latest["high"]),
            "low": float(latest["low"]),
            "close": float(latest["price"]),
            "volume": float(latest["volume"]),
        }
        history.append(candle)
        if len(history) > 500:
            del history[:-500]

    async def get_dexscreener_boosted_pairs(
        self,
        page: int = 1,
        page_size: int = 50,
        mode: str = "top",
        sort_by: str = "volume",
        chain: str = "",
        min_liquidity: Optional[float] = None
    ) -> Dict[str, Any]:
        """Fetch boosted pairs from DexScreener and return a ranked/paged list."""
        self.market_metrics["boost_requests"] += 1
        if not self.dexscreener_client:
            return self._apply_freshness_meta(
                self._empty_market_payload(),
                as_of=utc_now(),
                is_stale=True,
                age_seconds=0,
                source_counts={},
                stale_reason="DexScreener client is not enabled",
            )

        mode = (mode or "top").lower()
        sort_by = (sort_by or "volume").lower()
        page = max(int(page or 1), 1)
        page_size = min(max(int(page_size or 50), 5), 250)
        selected_chain = (chain or settings.DEXSCREENER_CHAIN).strip().lower()
        selected_min_liquidity = float(min_liquidity) if min_liquidity is not None else settings.DEXSCREENER_MIN_LIQUIDITY_USD

        cache_key = f"{mode}|{sort_by}|{selected_chain}|{selected_min_liquidity:.2f}|{page}|{page_size}"
        fresh_cached = self._get_cached_dex_boosts(cache_key, allow_stale=False)
        if fresh_cached:
            payload, as_of, source_counts, _, age_seconds = fresh_cached
            self.market_metrics["cache_hit"] += 1
            return self._apply_freshness_meta(payload, as_of, False, age_seconds, source_counts)

        stale_cached = self._get_cached_dex_boosts(cache_key, allow_stale=True)
        try:
            primary_task = self.dexscreener_client.get_token_boosts_top()
            secondary_task = self.dexscreener_client.get_token_boosts_latest()
            profile_task = self.dexscreener_client.get_token_profiles_latest()
            top_boosts, latest_boosts, profiles = await asyncio.gather(
                primary_task, secondary_task, profile_task
            )

            if mode == "latest":
                merged_entries = self._dedupe_boost_entries(
                    self._normalize_boost_entries(latest_boosts, source="latest"),
                    self._normalize_boost_entries(top_boosts, source="top"),
                )
            else:
                merged_entries = self._dedupe_boost_entries(
                    self._normalize_boost_entries(top_boosts, source="top"),
                    self._normalize_boost_entries(latest_boosts, source="latest"),
                )

            for profile in self._normalize_profile_entries(profiles):
                key = (profile["chain_id"], profile["token_address"])
                if key not in merged_entries:
                    merged_entries[key] = {
                        "chain_id": profile["chain_id"],
                        "token_address": profile["token_address"],
                        "boost_amount": 0.0,
                        "boost_count": 0,
                        "sources": {"profile"},
                    }

            if selected_chain:
                merged_entries = {
                    key: value
                    for key, value in merged_entries.items()
                    if key[0] == selected_chain
                }

            if not merged_entries:
                as_of = utc_now()
                empty_payload = self._empty_market_payload()
                source_counts = {
                    "top": len(top_boosts),
                    "latest": len(latest_boosts),
                    "profiles": len(profiles),
                    "tokens": 0,
                    "pairs": 0,
                }
                self._cache_dex_boosts(cache_key, empty_payload, as_of, source_counts)
                self.market_metrics["fetch_success"] += 1
                self.market_last_refresh = as_of
                return self._apply_freshness_meta(empty_payload, as_of, False, 0, source_counts)

            by_chain: Dict[str, List[str]] = {}
            for entry in merged_entries.values():
                chain_id = entry["chain_id"]
                by_chain.setdefault(chain_id, []).append(entry["token_address"])

            best_pairs_by_token: Dict[tuple, Dict[str, Any]] = {}
            token_pair_count = 0
            responses = await self._fetch_pairs_by_chain(by_chain)
            for chain_id, pairs in responses:
                if isinstance(pairs, Exception):
                    logger.error(f"Error fetching DexScreener tokens for chain %s: %s", chain_id, pairs)
                    continue
                for pair in pairs:
                    if not isinstance(pair, dict):
                        continue
                    token_pair_count += 1
                    liquidity_usd = self._to_float((pair.get("liquidity") or {}).get("usd"))
                    if liquidity_usd < selected_min_liquidity:
                        continue
                    base_token = pair.get("baseToken") or {}
                    base_address = str(base_token.get("address") or "").lower().strip()
                    chain_value = str(pair.get("chainId") or chain_id or "").lower().strip()
                    if not base_address or not chain_value:
                        continue
                    key = (chain_value, base_address)
                    current = best_pairs_by_token.get(key)
                    if current is None or self._pair_score(pair) > self._pair_score(current):
                        best_pairs_by_token[key] = pair

            formatted_pairs: List[Dict[str, Any]] = []
            for key, pair in best_pairs_by_token.items():
                boost_entry = merged_entries.get(key, {})
                formatted_pairs.append(self._format_dexscreener_pair(pair, boost_entry))

            deduped_pairs = self._dedupe_pairs_by_address(formatted_pairs)
            deduped_pairs.sort(key=lambda item: self._stable_sort_key(item, sort_by))

            total = len(deduped_pairs)
            start = (page - 1) * page_size
            end = start + page_size
            paged_items = deduped_pairs[start:end] if start < total else []
            avg_change = (
                sum(self._to_float(item.get("change_percent")) for item in deduped_pairs) / total
                if total
                else 0.0
            )

            payload = {
                "items": paged_items,
                "total": total,
                "summary": {
                    "volume": sum(self._to_float(item.get("volume")) for item in deduped_pairs),
                    "liquidity": sum(self._to_float(item.get("liquidity")) for item in deduped_pairs),
                    "avg_change_percent": avg_change,
                },
            }
            source_counts = {
                "top": len(top_boosts),
                "latest": len(latest_boosts),
                "profiles": len(profiles),
                "tokens": token_pair_count,
                "pairs": total,
            }
            as_of = utc_now()
            self._cache_dex_boosts(cache_key, payload, as_of, source_counts)
            self.market_metrics["fetch_success"] += 1
            self.market_last_refresh = as_of
            return self._apply_freshness_meta(payload, as_of, False, 0, source_counts)
        except Exception as error:
            self.market_metrics["fetch_error"] += 1
            self.market_last_error = str(error)
            if stale_cached:
                payload, as_of, source_counts, _, age_seconds = stale_cached
                self.market_metrics["stale_fallback"] += 1
                logger.warning("Using stale DexScreener cache after fetch failure: %s", error)
                return self._apply_freshness_meta(
                    payload,
                    as_of,
                    True,
                    age_seconds,
                    source_counts,
                    stale_reason=str(error),
                )
            raise

    def _empty_market_payload(self) -> Dict[str, Any]:
        return {
            "items": [],
            "total": 0,
            "summary": {
                "volume": 0.0,
                "liquidity": 0.0,
                "avg_change_percent": 0.0,
            },
        }

    async def _fetch_pairs_by_chain(self, by_chain: Dict[str, List[str]]) -> List[tuple]:
        tasks: List[asyncio.Task] = []
        task_keys: List[str] = []
        for chain_id, addresses in by_chain.items():
            for chunk in self._chunked(sorted(set(addresses)), 30):
                task_keys.append(chain_id)
                tasks.append(asyncio.create_task(self._fetch_tokens_chunk(chain_id, chunk)))
        responses = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []
        return list(zip(task_keys, responses))

    async def _fetch_tokens_chunk(self, chain_id: str, token_addresses: List[str]) -> List[Dict[str, Any]]:
        async with self.dex_fetch_semaphore:
            return await self.dexscreener_client.get_tokens(chain_id, token_addresses)

    def _cache_dex_boosts(self, cache_key: str, payload: Dict[str, Any], as_of: datetime, source_counts: Dict[str, int]):
        self.dex_boost_cache[cache_key] = {
            "payload": deepcopy(payload),
            "as_of": as_of,
            "source_counts": dict(source_counts),
        }
        self.dex_boost_cache_written_at[cache_key] = as_of
        self.dex_boost_cache_expiry[cache_key] = utc_now() + timedelta(seconds=45)

    def _get_cached_dex_boosts(self, cache_key: str, allow_stale: bool) -> Optional[tuple]:
        cached = self.dex_boost_cache.get(cache_key)
        if not cached:
            return None
        as_of = cached.get("as_of") or self.dex_boost_cache_written_at.get(cache_key) or utc_now()
        source_counts = cached.get("source_counts") or {}
        payload = cached.get("payload") or self._empty_market_payload()
        expiry = self.dex_boost_cache_expiry.get(cache_key)
        is_stale = not expiry or utc_now() >= expiry
        if is_stale and not allow_stale:
            return None
        age_seconds = max(int((utc_now() - as_of).total_seconds()), 0)
        return deepcopy(payload), as_of, dict(source_counts), is_stale, age_seconds

    def _apply_freshness_meta(
        self,
        payload: Dict[str, Any],
        as_of: datetime,
        is_stale: bool,
        age_seconds: int,
        source_counts: Dict[str, int],
        stale_reason: str = "",
    ) -> Dict[str, Any]:
        result = deepcopy(payload)
        result["meta"] = {
            "as_of": as_of.isoformat(),
            "is_stale": bool(is_stale),
            "age_seconds": max(int(age_seconds), 0),
            "source_counts": dict(source_counts),
        }
        if stale_reason:
            result["meta"]["stale_reason"] = stale_reason
        return result

    def _dedupe_boost_entries(self, primary: List[Dict[str, Any]], secondary: List[Dict[str, Any]]) -> Dict[tuple, Dict[str, Any]]:
        entries: Dict[tuple, Dict[str, Any]] = {}
        for entry in primary + secondary:
            key = (entry["chain_id"], entry["token_address"])
            if key not in entries:
                entries[key] = {
                    "chain_id": entry["chain_id"],
                    "token_address": entry["token_address"],
                    "boost_amount": self._to_float(entry.get("boost_amount")),
                    "boost_count": int(self._to_float(entry.get("boost_count"))),
                    "sources": set(entry.get("sources") or []),
                }
                continue
            current = entries[key]
            current["boost_amount"] = max(
                self._to_float(current.get("boost_amount")),
                self._to_float(entry.get("boost_amount")),
            )
            current["boost_count"] = max(
                int(self._to_float(current.get("boost_count"))),
                int(self._to_float(entry.get("boost_count"))),
            )
            current["sources"].update(entry.get("sources") or [])
        return entries

    def _stable_sort_key(self, item: Dict[str, Any], sort_by: str) -> tuple:
        boost_amount = self._to_float(item.get("boost_amount"))
        liquidity = self._to_float(item.get("liquidity"))
        volume = self._to_float(item.get("volume"))
        change_percent = self._to_float(item.get("change_percent"))
        pair_address = str(item.get("pair_address") or "")
        chain_id = str(item.get("chain") or "")

        if sort_by == "boosts":
            primary = boost_amount
        elif sort_by == "liquidity":
            primary = liquidity
        elif sort_by == "change":
            primary = change_percent
        else:
            primary = volume

        return (
            -primary,
            -liquidity,
            -volume,
            -boost_amount,
            chain_id,
            pair_address,
        )

    def _pair_tie_break_key(self, item: Dict[str, Any]) -> tuple:
        return (
            self._to_float(item.get("liquidity")),
            self._to_float(item.get("volume")),
            self._to_float(item.get("boost_amount")),
        )

    def _dedupe_pairs_by_address(self, pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: Dict[tuple, Dict[str, Any]] = {}
        for item in pairs:
            key = (str(item.get("chain") or "").lower(), str(item.get("pair_address") or "").lower())
            if not key[0] or not key[1]:
                continue
            existing = deduped.get(key)
            if existing is None or self._pair_tie_break_key(item) > self._pair_tie_break_key(existing):
                deduped[key] = item
        return list(deduped.values())

    def get_market_health(self) -> Dict[str, Any]:
        dex_metrics = self.dexscreener_client.get_metrics() if self.dexscreener_client else {}
        return {
            "service": "dexscreener",
            "enabled": bool(self.dexscreener_client),
            "telemetry": {
                "boost_requests": self.market_metrics.get("boost_requests", 0),
                "fetch_success": self.market_metrics.get("fetch_success", 0),
                "fetch_error": self.market_metrics.get("fetch_error", 0),
                "cache_hit": self.market_metrics.get("cache_hit", 0),
                "stale_fallback": self.market_metrics.get("stale_fallback", 0),
                "fetch_retry": dex_metrics.get("retries", 0),
                "fetch_timeout": dex_metrics.get("timeouts", 0),
                "fetch_requests": dex_metrics.get("requests", 0),
                "fetch_client_errors": dex_metrics.get("errors", 0),
            },
            "cache_entries": len(self.dex_boost_cache),
            "last_refresh": self.market_last_refresh.isoformat() if self.market_last_refresh else None,
            "last_error": self.market_last_error or None,
            "timestamp": utc_now().isoformat(),
        }

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _normalize_boost_entries(self, boosts: List[Dict[str, Any]], source: str = "") -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for item in boosts or []:
            if not isinstance(item, dict):
                continue
            chain_id = str(item.get("chainId") or item.get("chain_id") or item.get("chain") or "").strip().lower()
            token_address = str(
                item.get("tokenAddress")
                or item.get("token_address")
                or item.get("address")
                or ""
            ).strip().lower()
            if not chain_id or not token_address:
                continue
            boost_amount = self._to_float(item.get("totalAmount") or item.get("amount"))
            boost_count = int(self._to_float(item.get("boosts") or item.get("boostCount")))
            entries.append({
                "chain_id": chain_id,
                "token_address": token_address,
                "boost_amount": boost_amount,
                "boost_count": boost_count,
                "sources": {source} if source else set(),
                "raw": item
            })
        return entries

    def _normalize_profile_entries(self, profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for item in profiles or []:
            if not isinstance(item, dict):
                continue
            chain_id = str(item.get("chainId") or item.get("chain_id") or "").strip().lower()
            token_address = str(item.get("tokenAddress") or item.get("token_address") or "").strip().lower()
            if not chain_id or not token_address:
                continue
            entries.append({
                "chain_id": chain_id,
                "token_address": token_address,
            })
        return entries

    def _pair_score(self, pair: Dict[str, Any]) -> float:
        liquidity = self._to_float((pair.get("liquidity") or {}).get("usd"))
        volume = self._to_float((pair.get("volume") or {}).get("h24"))
        return (liquidity * 2.0) + volume

    def _format_dexscreener_pair(self, pair: Dict[str, Any], boost_entry: Dict[str, Any]) -> Dict[str, Any]:
        base = pair.get("baseToken") or {}
        quote = pair.get("quoteToken") or {}
        price = self._to_float(pair.get("priceUsd"))
        change_percent = self._to_float((pair.get("priceChange") or {}).get("h24"))
        volume = self._to_float((pair.get("volume") or {}).get("h24"))
        liquidity = self._to_float((pair.get("liquidity") or {}).get("usd"))
        market_cap = pair.get("marketCap") or pair.get("fdv")

        return {
            "symbol": f"{base.get('symbol')}/{quote.get('symbol')}".strip("/"),
            "name": base.get("name") or base.get("symbol"),
            "price": price,
            "change_percent": change_percent,
            "volume": volume,
            "liquidity": liquidity,
            "market_cap": market_cap,
            "chain": pair.get("chainId"),
            "dex": pair.get("dexId"),
            "pair_address": pair.get("pairAddress"),
            "url": pair.get("url"),
            "boost_amount": boost_entry.get("boost_amount", 0),
            "boost_count": boost_entry.get("boost_count", 0)
        }

    @staticmethod
    def _chunked(items: List[str], size: int) -> List[List[str]]:
        return [items[i:i + size] for i in range(0, len(items), size)]
    
    async def _fetch_yahoo_data(self, symbol: str, include_history: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch data from Yahoo Finance"""
        try:
            # Prefer lightweight history download to avoid quoteSummary rate limits
            hist = yf.download(
                tickers=symbol,
                period="90d",
                interval="1d",
                progress=False,
                threads=False
            )
            
            if hist.empty:
                return None
            
            latest = hist.iloc[-1]
            
            data = {
                "symbol": symbol,
                "price": float(latest["Close"]),
                "open": float(latest["Open"]),
                "high": float(latest["High"]),
                "low": float(latest["Low"]),
                "volume": int(latest["Volume"]),
                "change": float(latest["Close"] - latest["Open"]),
                "change_percent": float((latest["Close"] - latest["Open"]) / latest["Open"] * 100),
                "timestamp": utc_now()
            }

            if include_history:
                history = []
                for idx, row in hist.iterrows():
                    history.append({
                        "timestamp": idx.isoformat(),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": float(row["Volume"])
                    })
                data["history"] = history
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching Yahoo data for {symbol}: {e}")
            return None
    
    async def _fetch_alpha_vantage_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch data from Alpha Vantage"""
        try:
            # Get intraday data
            data, _ = self.alpha_vantage.get_intraday(symbol, interval='1min', outputsize='compact')
            
            if not data:
                return None
            
            # Convert to DataFrame and get latest
            df = pd.DataFrame(data).T
            df.index = pd.to_datetime(df.index)
            latest = df.iloc[-1]
            
            alpha_data = {
                "symbol": symbol,
                "price": float(latest["4. close"]),
                "open": float(latest["1. open"]),
                "high": float(latest["2. high"]),
                "low": float(latest["3. low"]),
                "volume": int(latest["5. volume"]),
                "timestamp": utc_now()
            }
            
            return alpha_data
            
        except Exception as e:
            logger.error(f"Error fetching Alpha Vantage data for {symbol}: {e}")
            return None
    
    def _combine_data_sources(self, yahoo_data: Optional[Dict], alpha_data: Optional[Dict]) -> Dict[str, Any]:
        """Combine data from multiple sources"""
        if not yahoo_data and not alpha_data:
            return {}
        
        # Use Yahoo as primary, Alpha Vantage as fallback
        primary_data = yahoo_data or alpha_data
        secondary_data = alpha_data if yahoo_data else None
        
        combined = primary_data.copy()
        
        # Add any missing fields from secondary source
        if secondary_data:
            for key, value in secondary_data.items():
                if key not in combined or combined[key] is None:
                    combined[key] = value
        
        return combined
    
    def _is_cache_valid(self, symbol: str) -> bool:
        """Check if cached data is still valid"""
        if symbol not in self.cache:
            return False
        
        expiry_time = self.cache_expiry.get(symbol)
        if not expiry_time:
            return False
        
        return utc_now() < expiry_time
    
    def _cache_data(self, symbol: str, data: Dict[str, Any]):
        """Cache data with expiry"""
        self.cache[symbol] = data
        self.cache_expiry[symbol] = utc_now() + timedelta(minutes=5)  # 5-minute cache

    def _cache_history_data(self, symbol: str, data: Dict[str, Any]):
        """Cache data including history with a shorter expiry."""
        self.history_cache[symbol] = data
        self.history_cache_expiry[symbol] = utc_now() + timedelta(seconds=max(settings.DATA_UPDATE_INTERVAL // 2, 15))

    def _is_history_cache_valid(self, symbol: str) -> bool:
        if symbol not in self.history_cache:
            return False
        expiry_time = self.history_cache_expiry.get(symbol)
        if not expiry_time:
            return False
        return utc_now() < expiry_time
    
    async def get_historical_data(self, symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """Get historical data for backtesting"""
        try:
            if self.dexscreener_client:
                cached = self.dex_history.get(symbol, [])
                if cached:
                    df = pd.DataFrame(cached)
                    if not df.empty and {"timestamp", "open", "high", "low", "close", "volume"}.issubset(df.columns):
                        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
                        df = df.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
                        df = df.rename(columns={
                            "open": "Open",
                            "high": "High",
                            "low": "Low",
                            "close": "Close",
                            "volume": "Volume"
                        })
                        if not df.empty:
                            return self._add_technical_indicators(df)

            if self.okx_client:
                inst_id = self._okx_inst_id(symbol)
                candles = self.okx_client.get_candles(inst_id, bar="1D", limit=365)
                if not candles:
                    return None
                df = pd.DataFrame(candles)
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.set_index("timestamp")
                df = df.rename(columns={
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume"
                })
                return self._add_technical_indicators(df)

            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            
            if hist.empty:
                return None
            
            # Add technical indicators
            hist = self._add_technical_indicators(hist)
            
            return hist
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return None
    
    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to DataFrame"""
        try:
            # Simple Moving Averages
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            df['SMA_200'] = df['Close'].rolling(window=200).mean()
            
            # Exponential Moving Averages
            df['EMA_12'] = df['Close'].ewm(span=12).mean()
            df['EMA_26'] = df['Close'].ewm(span=26).mean()
            
            # MACD
            df['MACD'] = df['EMA_12'] - df['EMA_26']
            df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
            df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
            
            # RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # Bollinger Bands
            df['BB_Middle'] = df['Close'].rolling(window=20).mean()
            bb_std = df['Close'].rolling(window=20).std()
            df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
            df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
            
            # Volume indicators
            df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
            df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding technical indicators: {e}")
            return df
    
