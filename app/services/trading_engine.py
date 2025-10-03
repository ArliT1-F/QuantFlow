"""
Core trading engine that orchestrates all trading activities
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from app.core.config import settings
from app.services.data_service import DataService
from app.services.notification_service import NotificationService
from app.services.risk_manager import RiskManager
from app.services.portfolio_manager import PortfolioManager
from app.strategies.base_strategy import BaseStrategy
from app.strategies.momentum_strategy import MomentumStrategy
from app.strategies.mean_reversion_strategy import MeanReversionStrategy
from app.strategies.technical_analysis_strategy import TechnicalAnalysisStrategy
from app.strategies.ml_strategy import MLStrategy

logger = logging.getLogger(__name__)

class TradingState(Enum):
    """Trading engine states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

@dataclass
class TradingSignal:
    """Trading signal data structure"""
    symbol: str
    action: str  # BUY, SELL, HOLD
    confidence: float  # 0-1
    price: float
    quantity: Optional[int] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy: str = ""
    metadata: Dict[str, Any] = None

class TradingEngine:
    """Main trading engine that coordinates all trading activities"""
    
    def __init__(self, data_service: DataService, notification_service: NotificationService):
        self.data_service = data_service
        self.notification_service = notification_service
        self.risk_manager = RiskManager()
        self.portfolio_manager = PortfolioManager()
        
        # Trading state
        self.state = TradingState.STOPPED
        self.is_running_flag = False
        
        # Strategies
        self.strategies: Dict[str, BaseStrategy] = {}
        self._initialize_strategies()
        
        # Trading loop
        self.trading_task: Optional[asyncio.Task] = None
        
        logger.info("Trading engine initialized")
    
    def _initialize_strategies(self):
        """Initialize all trading strategies"""
        strategy_classes = {
            "momentum": MomentumStrategy,
            "mean_reversion": MeanReversionStrategy,
            "technical_analysis": TechnicalAnalysisStrategy,
            "ml_strategy": MLStrategy
        }
        
        for strategy_name in settings.ENABLED_STRATEGIES:
            if strategy_name in strategy_classes:
                try:
                    strategy = strategy_classes[strategy_name]()
                    self.strategies[strategy_name] = strategy
                    logger.info(f"Initialized strategy: {strategy_name}")
                except Exception as e:
                    logger.error(f"Failed to initialize strategy {strategy_name}: {e}")
    
    async def start(self):
        """Start the trading engine"""
        if self.state != TradingState.STOPPED:
            logger.warning("Trading engine is already running")
            return
        
        try:
            self.state = TradingState.STARTING
            logger.info("Starting trading engine...")
            
            # Initialize portfolio manager
            await self.portfolio_manager.initialize()
            
            # Start trading loop
            self.is_running_flag = True
            self.trading_task = asyncio.create_task(self._trading_loop())
            
            self.state = TradingState.RUNNING
            logger.info("Trading engine started successfully")
            
            # Send notification
            await self.notification_service.send_alert(
                "Trading Engine Started",
                "The automated trading bot has been started successfully."
            )
            
        except Exception as e:
            self.state = TradingState.ERROR
            logger.error(f"Failed to start trading engine: {e}")
            raise
    
    async def stop(self):
        """Stop the trading engine"""
        if self.state != TradingState.RUNNING:
            logger.warning("Trading engine is not running")
            return
        
        try:
            self.state = TradingState.STOPPING
            logger.info("Stopping trading engine...")
            
            # Stop trading loop
            self.is_running_flag = False
            if self.trading_task:
                self.trading_task.cancel()
                try:
                    await self.trading_task
                except asyncio.CancelledError:
                    pass
            
            self.state = TradingState.STOPPED
            logger.info("Trading engine stopped successfully")
            
            # Send notification
            await self.notification_service.send_alert(
                "Trading Engine Stopped",
                "The automated trading bot has been stopped."
            )
            
        except Exception as e:
            logger.error(f"Error stopping trading engine: {e}")
            self.state = TradingState.ERROR
    
    def is_running(self) -> bool:
        """Check if trading engine is running"""
        return self.state == TradingState.RUNNING
    
    async def _trading_loop(self):
        """Main trading loop"""
        logger.info("Trading loop started")
        
        while self.is_running_flag:
            try:
                # Get current market data
                market_data = await self.data_service.get_latest_data()
                
                if not market_data:
                    logger.warning("No market data available, skipping iteration")
                    await asyncio.sleep(settings.DATA_UPDATE_INTERVAL)
                    continue
                
                # Generate signals from all strategies
                signals = await self._generate_signals(market_data)
                
                # Process signals
                await self._process_signals(signals)
                
                # Update portfolio
                await self.portfolio_manager.update_portfolio()
                
                # Risk management checks
                await self.risk_manager.check_risk_limits()
                
                # Wait for next iteration
                await asyncio.sleep(settings.DATA_UPDATE_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying
        
        logger.info("Trading loop stopped")
    
    async def _generate_signals(self, market_data: Dict) -> List[TradingSignal]:
        """Generate trading signals from all strategies"""
        signals = []
        
        for symbol, data in market_data.items():
            for strategy_name, strategy in self.strategies.items():
                try:
                    signal = await strategy.generate_signal(symbol, data)
                    if signal and signal.action != "HOLD":
                        signal.strategy = strategy_name
                        signals.append(signal)
                except Exception as e:
                    logger.error(f"Error generating signal for {symbol} with {strategy_name}: {e}")
        
        return signals
    
    async def _process_signals(self, signals: List[TradingSignal]):
        """Process trading signals and execute trades"""
        for signal in signals:
            try:
                # Risk management check
                if not await self.risk_manager.validate_signal(signal):
                    logger.info(f"Signal rejected by risk manager: {signal.symbol} {signal.action}")
                    continue
                
                # Execute trade
                trade_result = await self._execute_trade(signal)
                
                if trade_result:
                    logger.info(f"Trade executed: {signal.symbol} {signal.action} at {signal.price}")
                    
                    # Send notification
                    await self.notification_service.send_trade_notification(trade_result)
                
            except Exception as e:
                logger.error(f"Error processing signal {signal.symbol}: {e}")
    
    async def _execute_trade(self, signal: TradingSignal) -> Optional[Dict]:
        """Execute a trade based on signal"""
        try:
            # Calculate position size
            position_size = await self.risk_manager.calculate_position_size(signal)
            
            if position_size <= 0:
                logger.info(f"Position size too small for {signal.symbol}")
                return None
            
            # Create trade order
            trade_data = {
                "symbol": signal.symbol,
                "side": signal.action,
                "quantity": position_size,
                "price": signal.price,
                "strategy": signal.strategy,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
                "timestamp": datetime.utcnow()
            }
            
            # Execute through portfolio manager
            trade_result = await self.portfolio_manager.execute_trade(trade_data)
            
            return trade_result
            
        except Exception as e:
            logger.error(f"Error executing trade for {signal.symbol}: {e}")
            return None
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get trading performance metrics"""
        return await self.portfolio_manager.get_performance_metrics()
    
    async def get_active_positions(self) -> List[Dict]:
        """Get all active positions"""
        return await self.portfolio_manager.get_active_positions()
    
    async def get_trading_history(self, limit: int = 100) -> List[Dict]:
        """Get trading history"""
        return await self.portfolio_manager.get_trading_history(limit)