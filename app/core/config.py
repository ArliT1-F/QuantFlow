"""
Application configuration management
"""
import os
from typing import List, Optional
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
    
    # Notification Settings
    EMAIL_ENABLED: bool = False
    EMAIL_HOST: str = "smtp.gmail.com"
    EMAIL_PORT: int = 587
    EMAIL_USER: Optional[str] = None
    EMAIL_PASSWORD: Optional[str] = None
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/trading_bot.log"
    
    # Data Collection
    DATA_UPDATE_INTERVAL: int = 60  # seconds
    BACKTEST_DAYS: int = 252  # 1 year of trading days
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Global settings instance
settings = Settings()
