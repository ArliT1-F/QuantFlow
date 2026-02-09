"""
Application configuration management
"""
import os
import json
from typing import Any, List, Optional
from pydantic import validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    DATABASE_URL: str = "postgresql://username:password@localhost:5432/trading_bot"
    
    # API Keys
    ALPHA_VANTAGE_ENABLED: bool = False
    ALPHA_VANTAGE_API_KEY: Optional[str] = None
    YAHOO_FINANCE_ENABLED: bool = True

    # OKX Configuration
    OKX_ENABLED: bool = False
    OKX_MARKET_DATA_ENABLED: bool = False
    OKX_TRADING_ENABLED: bool = False
    OKX_DEMO_TRADING: bool = True
    OKX_BASE_URL: str = "https://www.okx.com"
    OKX_API_KEY: Optional[str] = None
    OKX_SECRET_KEY: Optional[str] = None
    OKX_PASSPHRASE: Optional[str] = None
    OKX_QUOTE_CCY: str = "USDT"
    
    # Trading Configuration
    DEFAULT_CAPITAL: float = 10000.0
    MAX_POSITION_SIZE: float = 0.1  # 10% of portfolio
    STOP_LOSS_PERCENTAGE: float = 0.05  # 5%
    TAKE_PROFIT_PERCENTAGE: float = 0.15  # 15%
    MAX_DAILY_TRADES: int = 10
    MIN_VOLUME: int = 0  # Minimum daily volume (0 disables hard minimum for crypto)
    
    # Risk Management
    MAX_PORTFOLIO_RISK: float = 0.02  # 2% portfolio risk per trade
    CORRELATION_THRESHOLD: float = 0.7
    MAX_SECTOR_EXPOSURE: float = 0.3  # 30% max exposure to any sector
    MIN_POSITION_UNITS: float = 0.0005  # smallest tradable size
    MIN_POSITION_NOTIONAL: float = 10.0  # minimum USD notional per trade
    SIGNAL_COOLDOWN_SECONDS: int = 900
    MIN_SIGNAL_CONFIDENCE: float = 0.55
    CONFLICT_STRENGTH_RATIO: float = 1.35
    MIN_HOLD_SECONDS: int = 900
    
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
    
    @validator('DEFAULT_CAPITAL', 'MAX_POSITION_SIZE', 'STOP_LOSS_PERCENTAGE', 'TAKE_PROFIT_PERCENTAGE')
    def validate_positive_numbers(cls, v):
        if v <= 0:
            raise ValueError('Must be positive')
        return v
    
    @validator('MAX_POSITION_SIZE')
    def validate_position_size(cls, v):
        if v > 1.0:
            raise ValueError('Position size cannot exceed 100%')
        return v

    @validator('MIN_SIGNAL_CONFIDENCE')
    def validate_confidence(cls, v):
        if v < 0 or v > 1:
            raise ValueError('MIN_SIGNAL_CONFIDENCE must be between 0 and 1')
        return v

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
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Global settings instance
settings = Settings()
