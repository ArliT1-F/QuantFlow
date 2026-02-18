"""
Application configuration management
"""
import os
import json
from typing import Any, List, Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Ensure repository .env values win over stale exported shell variables.
load_dotenv(override=True)

class Settings(BaseSettings):
    """Application settings"""
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")
    
    # Database
    DATABASE_URL: str = "postgresql://username:password@localhost:5432/trading_bot"
    
    # Solana execution configuration
    SOLANA_TRADING_MODE: str = "demo"  # demo | live
    SOLANA_EXECUTOR_URL: str = ""
    SOLANA_WALLET_PUBLIC_KEY: str = ""
    SOLANA_QUOTE_MINT: str = "So11111111111111111111111111111111111111112"
    SOLANA_SLIPPAGE_BPS: int = 100
    SOLANA_EXECUTOR_REQUIRE_AUTH: bool = True
    SOLANA_EXECUTOR_AUTH_HEADER: str = "X-Executor-Key"
    SOLANA_EXECUTOR_API_KEY: str = ""
    SOLANA_EXECUTOR_TIMEOUT_SECONDS: int = 20
    SOLANA_EXECUTOR_MAX_RETRIES: int = 2
    SOLANA_EXECUTOR_BACKOFF_SECONDS: float = 0.4

    # DEX Screener Configuration (market data only)
    DEXSCREENER_ENABLED: bool = False
    DEXSCREENER_CHAIN: str = ""
    DEXSCREENER_QUOTE_SYMBOL: str = "USDT"
    DEXSCREENER_TIMEOUT_SECONDS: int = 10
    DEXSCREENER_MAX_RETRIES: int = 3
    DEXSCREENER_MAX_CONCURRENCY: int = 8
    DEXSCREENER_MIN_LIQUIDITY_USD: float = 50000.0
    DEXSCREENER_MIN_VOLUME_24H_USD: float = 1000000.0
    DEXSCREENER_MIN_TOKEN_AGE_HOURS: float = 24.0
    DEXSCREENER_REQUIRE_UNIQUE_BASE_SYMBOL: bool = True
    DEXSCREENER_BLOCKED_TOKEN_ADDRESSES: str = ""
    DEXSCREENER_BLOCKED_PAIR_ADDRESSES: str = ""
    DEXSCREENER_DYNAMIC_UNIVERSE_ENABLED: bool = True
    DEXSCREENER_DYNAMIC_UNIVERSE_SIZE: int = 30
    DEXSCREENER_DYNAMIC_UNIVERSE_MODE: str = "top"
    DEXSCREENER_DYNAMIC_UNIVERSE_SORT: str = "boosts"
    
    # Trading Configuration
    DEFAULT_CAPITAL: float = 10000.0
    MAX_POSITION_SIZE: float = 0.1  # 10% of portfolio
    STOP_LOSS_PERCENTAGE: float = 0.05  # 5%
    TAKE_PROFIT_PERCENTAGE: float = 0.15  # 15%
    MAX_DAILY_TRADES: int = 10
    MAX_TRADES_PER_HOUR: int = 200
    MIN_VOLUME: int = 0  # Minimum daily volume (0 disables hard minimum for crypto)
    
    # Risk Management
    MAX_PORTFOLIO_RISK: float = 0.02  # 2% portfolio risk per trade
    CORRELATION_THRESHOLD: float = 0.7
    MAX_SECTOR_EXPOSURE: float = 0.3  # 30% max exposure to any sector
    MIN_POSITION_UNITS: float = 0.0005  # smallest tradable size
    MIN_POSITION_NOTIONAL: float = 10.0  # minimum USD notional per trade
    FIXED_TRADE_NOTIONAL_USD: float = 0.0  # 0 disables fixed-notional sizing
    MAX_BUY_NOTIONAL_USD: float = 0.0  # 0 disables hard buy-notional cap
    MIN_TAKE_PROFIT_PERCENTAGE: float = 0.0
    MAX_TAKE_PROFIT_PERCENTAGE: float = 1.0
    SIGNAL_COOLDOWN_SECONDS: int = 900
    MIN_SIGNAL_CONFIDENCE: float = 0.55
    CONFLICT_STRENGTH_RATIO: float = 1.35
    MIN_HOLD_SECONDS: int = 900
    MAX_SIGNALS_PER_CYCLE: int = 3

    # Advanced Entry Filter (adaptive/regime-aware)
    ADVANCED_ENTRY_FILTER_ENABLED: bool = True
    ENTRY_FILTER_MIN_HISTORY: int = 8
    ENTRY_FILTER_VOL_WINDOW: int = 20
    ENTRY_FILTER_MIN_EXPECTED_EDGE: float = 0.004
    ENTRY_FILTER_FEE_BPS_PER_SIDE: float = 10.0
    ENTRY_FILTER_SLIPPAGE_BPS: float = 6.0
    ENTRY_FILTER_VOL_MULTIPLIER: float = 0.75
    ENTRY_FILTER_MIN_RR: float = 1.2
    ENTRY_FILTER_TREND_Z_MIN: float = 0.15
    
    # Notification Settings
    EMAIL_ENABLED: bool = False
    EMAIL_HOST: str = "smtp.gmail.com"
    EMAIL_PORT: int = 587
    EMAIL_USER: Optional[str] = None
    EMAIL_PASSWORD: Optional[str] = None
    EMAIL_TO: str = ""
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    API_AUTH_ENABLED: bool = True
    API_AUTH_TOKEN: str = "change-me-api-token"
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/trading_bot.log"
    
    # Data Collection
    DATA_UPDATE_INTERVAL: int = 60  # seconds
    BACKTEST_DAYS: int = 252  # 1 year of trading days
    PORTFOLIO_SNAPSHOT_INTERVAL: int = 60  # seconds
    
    # Supported Symbols
    DEFAULT_SYMBOLS: List[str] = [
        "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD",
        "DOGE-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "BCH-USD"
    ]
    
    # Strategy Configuration
    ENABLED_STRATEGIES: List[str] = [
        "momentum", "mean_reversion", "technical_analysis"
    ]
    
    @field_validator('DEFAULT_CAPITAL', 'MAX_POSITION_SIZE', 'STOP_LOSS_PERCENTAGE', 'TAKE_PROFIT_PERCENTAGE')
    @classmethod
    def validate_positive_numbers(cls, v):
        if v <= 0:
            raise ValueError('Must be positive')
        return v
    
    @field_validator('MAX_POSITION_SIZE')
    @classmethod
    def validate_position_size(cls, v):
        if v > 1.0:
            raise ValueError('Position size cannot exceed 100%')
        return v

    @field_validator('MIN_SIGNAL_CONFIDENCE')
    @classmethod
    def validate_confidence(cls, v):
        if v < 0 or v > 1:
            raise ValueError('MIN_SIGNAL_CONFIDENCE must be between 0 and 1')
        return v

    @field_validator('SOLANA_TRADING_MODE')
    @classmethod
    def validate_solana_trading_mode(cls, v):
        mode = str(v or "").strip().lower()
        if mode not in {"demo", "live"}:
            raise ValueError('SOLANA_TRADING_MODE must be "demo" or "live"')
        return mode

    @field_validator('MAX_TRADES_PER_HOUR')
    @classmethod
    def validate_hourly_trades(cls, v):
        if v <= 0:
            raise ValueError('MAX_TRADES_PER_HOUR must be positive')
        return v

    @field_validator('SOLANA_EXECUTOR_TIMEOUT_SECONDS')
    @classmethod
    def validate_executor_timeout(cls, v):
        if int(v) <= 0:
            raise ValueError('SOLANA_EXECUTOR_TIMEOUT_SECONDS must be positive')
        return int(v)

    @field_validator('SOLANA_EXECUTOR_MAX_RETRIES')
    @classmethod
    def validate_executor_retries(cls, v):
        if int(v) < 0:
            raise ValueError('SOLANA_EXECUTOR_MAX_RETRIES cannot be negative')
        return int(v)

    @field_validator('SOLANA_EXECUTOR_BACKOFF_SECONDS')
    @classmethod
    def validate_executor_backoff(cls, v):
        if float(v) < 0:
            raise ValueError('SOLANA_EXECUTOR_BACKOFF_SECONDS cannot be negative')
        return float(v)

    @field_validator('FIXED_TRADE_NOTIONAL_USD')
    @classmethod
    def validate_fixed_notional(cls, v):
        if v < 0:
            raise ValueError('FIXED_TRADE_NOTIONAL_USD cannot be negative')
        return v

    @field_validator('MAX_BUY_NOTIONAL_USD')
    @classmethod
    def validate_max_buy_notional(cls, v):
        if v < 0:
            raise ValueError('MAX_BUY_NOTIONAL_USD cannot be negative')
        return v

    @field_validator('MIN_TAKE_PROFIT_PERCENTAGE', 'MAX_TAKE_PROFIT_PERCENTAGE')
    @classmethod
    def validate_take_profit_bounds(cls, v):
        if v < 0 or v > 1:
            raise ValueError('Take profit bounds must be between 0 and 1')
        return v

    @model_validator(mode='after')
    def validate_take_profit_range(self):
        if self.MIN_TAKE_PROFIT_PERCENTAGE > self.MAX_TAKE_PROFIT_PERCENTAGE:
            raise ValueError('MIN_TAKE_PROFIT_PERCENTAGE cannot exceed MAX_TAKE_PROFIT_PERCENTAGE')
        if self.TAKE_PROFIT_PERCENTAGE < self.MIN_TAKE_PROFIT_PERCENTAGE:
            raise ValueError('TAKE_PROFIT_PERCENTAGE is below MIN_TAKE_PROFIT_PERCENTAGE')
        if self.TAKE_PROFIT_PERCENTAGE > self.MAX_TAKE_PROFIT_PERCENTAGE:
            raise ValueError('TAKE_PROFIT_PERCENTAGE is above MAX_TAKE_PROFIT_PERCENTAGE')
        return self

    @staticmethod
    def _parse_str_list(value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith('[') and stripped.endswith(']'):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in stripped.split(',') if item.strip()]
        return [str(value).strip()] if str(value).strip() else []

    def get_cors_origins(self) -> List[str]:
        origins = self._parse_str_list(self.CORS_ORIGINS)
        return origins or ["http://localhost:8000", "http://127.0.0.1:8000"]

    def get_email_recipients(self) -> List[str]:
        return self._parse_str_list(self.EMAIL_TO)
    
# Global settings instance
settings = Settings()
