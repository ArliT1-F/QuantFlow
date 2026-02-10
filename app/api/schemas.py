"""
Pydantic schemas for API request/response contracts.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


VALID_MARKET_MODES = {"top", "latest"}
VALID_MARKET_SORTS = {"volume", "liquidity", "boosts", "change"}


class MarketErrorDetail(BaseModel):
    error_code: str
    message: str
    errors: Optional[List[Dict[str, Any]]] = None


class DexScreenerBoostQuery(BaseModel):
    limit: Optional[int] = Field(default=None, ge=1, le=250)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=5, le=250)
    mode: str = Field(default="top")
    sort: str = Field(default="boosts")
    chain: str = Field(default="", max_length=40)
    min_liquidity: Optional[float] = Field(default=None, ge=0)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        normalized = str(value or "top").strip().lower()
        if normalized not in VALID_MARKET_MODES:
            raise ValueError(f"mode must be one of: {', '.join(sorted(VALID_MARKET_MODES))}")
        return normalized

    @field_validator("sort")
    @classmethod
    def validate_sort(cls, value: str) -> str:
        normalized = str(value or "boosts").strip().lower()
        if normalized not in VALID_MARKET_SORTS:
            raise ValueError(f"sort must be one of: {', '.join(sorted(VALID_MARKET_SORTS))}")
        return normalized

    @field_validator("chain")
    @classmethod
    def validate_chain(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized and not all(ch.isalnum() or ch in {"_", "-"} for ch in normalized):
            raise ValueError("chain must use alphanumeric, underscore, or hyphen characters")
        return normalized


class MarketPairOut(BaseModel):
    symbol: str = ""
    name: str = ""
    price: float = 0.0
    change_percent: float = 0.0
    volume: float = 0.0
    liquidity: float = 0.0
    market_cap: Optional[Any] = None
    chain: str = ""
    dex: str = ""
    pair_address: str = ""
    url: str = ""
    boost_amount: float = 0.0
    boost_count: int = 0


class MarketSummaryOut(BaseModel):
    volume: float = 0.0
    liquidity: float = 0.0
    avg_change_percent: float = 0.0


class MarketMetaOut(BaseModel):
    as_of: str
    is_stale: bool
    age_seconds: int = Field(default=0, ge=0)
    source_counts: Dict[str, int] = Field(default_factory=dict)
    stale_reason: Optional[str] = None


class DexScreenerBoostResponse(BaseModel):
    results: List[MarketPairOut] = Field(default_factory=list)
    count: int = 0
    total: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 1
    mode: str = "top"
    sort: str = "boosts"
    chain: str = ""
    min_liquidity: float = 0.0
    effective_min_liquidity: float = 0.0
    summary: MarketSummaryOut = Field(default_factory=MarketSummaryOut)
    meta: MarketMetaOut
    timestamp: str


class MarketHealthResponse(BaseModel):
    service: str = "dexscreener"
    enabled: bool = False
    telemetry: Dict[str, int] = Field(default_factory=dict)
    cache_entries: int = 0
    last_refresh: Optional[str] = None
    last_error: Optional[str] = None
    timestamp: str
