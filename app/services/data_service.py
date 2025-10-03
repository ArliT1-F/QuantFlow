"""
Data service for fetching and managing market data
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import yfinance as yf
import pandas as pd
import numpy as np
from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.fundamentaldata import FundamentalData

from app.core.config import settings

logger = logging.getLogger(__name__)

class DataService:
    """Service for fetching and managing market data from multiple sources"""
    
    def __init__(self):
        self.alpha_vantage = None
        self.fundamental_data = None
        self.cache = {}
        self.cache_expiry = {}
        self.is_running_flag = False
        self.data_task = None
        
        # Initialize Alpha Vantage if API key is available
        if settings.ALPHA_VANTAGE_API_KEY:
            try:
                self.alpha_vantage = TimeSeries(key=settings.ALPHA_VANTAGE_API_KEY)
                self.fundamental_data = FundamentalData(key=settings.ALPHA_VANTAGE_API_KEY)
                logger.info("Alpha Vantage initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Alpha Vantage: {e}")
        
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
    
    async def get_latest_data(self) -> Dict[str, Any]:
        """Get latest data for all symbols"""
        data = {}
        for symbol in settings.DEFAULT_SYMBOLS:
            symbol_data = await self.get_latest_data_for_symbol(symbol)
            if symbol_data:
                data[symbol] = symbol_data
        return data
    
    async def get_latest_data_for_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get latest data for a specific symbol"""
        # Check cache first
        if self._is_cache_valid(symbol):
            return self.cache.get(symbol)
        
        try:
            # Fetch from Yahoo Finance (primary source)
            yahoo_data = await self._fetch_yahoo_data(symbol)
            
            # Fetch from Alpha Vantage if available (secondary source)
            alpha_data = None
            if self.alpha_vantage:
                alpha_data = await self._fetch_alpha_vantage_data(symbol)
            
            # Combine and process data
            combined_data = self._combine_data_sources(yahoo_data, alpha_data)
            
            # Cache the data
            self._cache_data(symbol, combined_data)
            
            return combined_data
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return self.cache.get(symbol)  # Return cached data if available
    
    async def _fetch_yahoo_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch data from Yahoo Finance"""
        try:
            ticker = yf.Ticker(symbol)
            
            # Get current price and basic info
            info = ticker.info
            hist = ticker.history(period="5d", interval="1d")
            
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
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE", 0),
                "dividend_yield": info.get("dividendYield", 0),
                "beta": info.get("beta", 0),
                "timestamp": datetime.utcnow()
            }
            
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
    
    async def get_fundamental_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get fundamental data for a symbol"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            fundamental_data = {
                "symbol": symbol,
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE", 0),
                "forward_pe": info.get("forwardPE", 0),
                "peg_ratio": info.get("pegRatio", 0),
                "price_to_book": info.get("priceToBook", 0),
                "price_to_sales": info.get("priceToSalesTrailing12Months", 0),
                "dividend_yield": info.get("dividendYield", 0),
                "beta": info.get("beta", 0),
                "debt_to_equity": info.get("debtToEquity", 0),
                "return_on_equity": info.get("returnOnEquity", 0),
                "revenue_growth": info.get("revenueGrowth", 0),
                "earnings_growth": info.get("earningsGrowth", 0),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", "")
            }
            
            return fundamental_data
            
        except Exception as e:
            logger.error(f"Error fetching fundamental data for {symbol}: {e}")
            return None