"""
Data service for fetching and managing market data
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import yfinance as yf
import pandas as pd
from alpha_vantage.timeseries import TimeSeries

from app.core.config import settings
from app.services.okx_client import OkxClient

logger = logging.getLogger(__name__)

class DataService:
    """Service for fetching and managing market data from multiple sources"""
    
    def __init__(self):
        self.alpha_vantage = None
        self.cache = {}
        self.cache_expiry = {}
        self.is_running_flag = False
        self.data_task = None
        self.okx_client = None
        
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
        if self._is_cache_valid(symbol) and not include_history:
            return self.cache.get(symbol)
        
        try:
            if self.okx_client:
                okx_data = await self._fetch_okx_data(symbol, include_history=include_history)
                if okx_data:
                    if "history" in okx_data:
                        cache_copy = okx_data.copy()
                        cache_copy.pop("history", None)
                        self._cache_data(symbol, cache_copy)
                    else:
                        self._cache_data(symbol, okx_data)
                    return okx_data
                # If OKX is enabled for market data but returns nothing, do not fall back
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
                "timestamp": datetime.utcnow()
            }

            if include_history:
                candles = self.okx_client.get_candles(inst_id, bar="1D", limit=90)
                if candles:
                    data["history"] = candles

            return data
        except Exception as e:
            logger.error(f"Error fetching OKX data for {symbol}: {e}")
            return None
    
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
                "timestamp": datetime.utcnow()
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
                "timestamp": datetime.utcnow()
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
        
        return datetime.utcnow() < expiry_time
    
    def _cache_data(self, symbol: str, data: Dict[str, Any]):
        """Cache data with expiry"""
        self.cache[symbol] = data
        self.cache_expiry[symbol] = datetime.utcnow() + timedelta(minutes=5)  # 5-minute cache
    
    async def get_historical_data(self, symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """Get historical data for backtesting"""
        try:
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
    
