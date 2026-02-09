"""
Core trading engine that orchestrates all trading activities
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from collections import deque

from app.core.config import settings
from app.services.data_service import DataService
from app.services.notification_service import NotificationService
from app.services.risk_manager import RiskManager
from app.services.portfolio_manager import PortfolioManager
from app.services.backtest_service import BacktestService
from app.strategies.base_strategy import BaseStrategy
from app.strategies.momentum_strategy import MomentumStrategy
from app.strategies.mean_reversion_strategy import MeanReversionStrategy
from app.strategies.technical_analysis_strategy import TechnicalAnalysisStrategy

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
    quantity: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy: str = ""
    metadata: Dict[str, Any] = None

class TradingEngine:
    """Main trading engine that coordinates all trading activities"""
    
    def __init__(
        self,
        data_service: DataService,
        notification_service: NotificationService,
        risk_manager: Optional[RiskManager] = None,
        portfolio_manager: Optional[PortfolioManager] = None
    ):
        self.data_service = data_service
        self.notification_service = notification_service
        self.portfolio_manager = portfolio_manager or PortfolioManager()
        self.risk_manager = risk_manager or RiskManager(portfolio_manager=self.portfolio_manager)
        
        # Trading state
        self.state = TradingState.STOPPED
        self.is_running_flag = False
        
        # Strategies
        self.strategies: Dict[str, BaseStrategy] = {}
        self._initialize_strategies()
        self.active_strategy_names = set(self.strategies.keys())
        
        # Trading loop
        self.trading_task: Optional[asyncio.Task] = None

        # Recent events
        self.recent_events = deque(maxlen=50)
        self.last_trade_at: Dict[str, datetime] = {}
        
        logger.info("Trading engine initialized")
    
    def _initialize_strategies(self):
        """Initialize all trading strategies"""
        strategy_classes = {
            "momentum": MomentumStrategy,
            "mean_reversion": MeanReversionStrategy,
            "technical_analysis": TechnicalAnalysisStrategy
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
            await self._select_active_strategies()
            
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
                market_data = await self.data_service.get_latest_data(include_history=True)
                
                if not market_data:
                    logger.warning("No market data available, skipping iteration")
                    await asyncio.sleep(settings.DATA_UPDATE_INTERVAL)
                    continue
                
                # Generate signals from all strategies
                signals = await self._generate_signals(market_data)
                
                # Process signals
                await self._process_signals(signals)

                # Enforce stop-loss/take-profit exits
                await self._process_exit_conditions(market_data)
                
                # Update portfolio with latest market data
                await self.portfolio_manager.update_portfolio(market_data)
                
                # Risk management checks
                risk_ok, risk_reason = await self.risk_manager.check_risk_limits()
                if not risk_ok:
                    self._add_event("risk_halt", "", "risk_manager", risk_reason)
                    await self.notification_service.send_risk_alert("Hard Limit Breach", risk_reason)
                    self.is_running_flag = False
                    self.state = TradingState.STOPPED
                    break
                
                # Wait for next iteration
                await asyncio.sleep(settings.DATA_UPDATE_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying
        
        logger.info("Trading loop stopped")
    
    async def _generate_signals(self, market_data: Dict) -> List[TradingSignal]:
        """Generate trading signals from all strategies"""
        signals = []
        closes_by_symbol = {}
        for symbol, data in market_data.items():
            history = data.get("history") or []
            closes = [float(h["close"]) for h in history if isinstance(h, dict) and h.get("close") is not None]
            if len(closes) >= 3:
                closes_by_symbol[symbol] = closes
        
        for symbol, data in market_data.items():
            for strategy_name, strategy in self.strategies.items():
                if strategy_name not in self.active_strategy_names:
                    continue
                try:
                    signal = await strategy.generate_signal(symbol, data)
                    if signal and signal.action != "HOLD":
                        signal.metadata = signal.metadata or {}
                        signal.metadata["closes_by_symbol"] = closes_by_symbol
                        signal.strategy = strategy_name
                        signals.append(signal)
                except Exception as e:
                    logger.error(f"Error generating signal for {symbol} with {strategy_name}: {e}")
        
        return signals

    async def _select_active_strategies(self):
        """
        Select strategies that are currently profitable on a quick rolling backtest.
        Falls back to the best available strategy if none are positive.
        """
        try:
            if not self.strategies:
                self.active_strategy_names = set()
                return

            evaluator = BacktestService(self.data_service)
            candidate_names = list(self.strategies.keys())
            symbols = settings.DEFAULT_SYMBOLS[:4]
            result = await evaluator.run_backtest(
                symbols=symbols,
                days=120,
                strategies=candidate_names,
                initial_capital=max(self.portfolio_manager.total_value, settings.DEFAULT_CAPITAL)
            )
            summary = (result.get("summary") or {}).get("strategies", {})
            scored = []
            for name in candidate_names:
                stats = summary.get(name, {})
                avg_return = float(stats.get("avg_return_percent", -9999.0))
                avg_dd = float(stats.get("avg_max_drawdown_percent", 100.0))
                scored.append((name, avg_return, avg_dd))

            keep = [name for name, avg_return, avg_dd in scored if avg_return > 0 and avg_dd <= 20.0]
            if not keep:
                keep = [max(scored, key=lambda item: item[1])[0]]
            self.active_strategy_names = set(keep)
            logger.info(f"Active strategies selected: {sorted(self.active_strategy_names)}")
        except Exception as e:
            logger.warning(f"Strategy selection failed, using all strategies: {e}")
            self.active_strategy_names = set(self.strategies.keys())
    
    async def _process_signals(self, signals: List[TradingSignal]):
        """Process trading signals and execute trades"""
        consolidated_signals = self._consolidate_signals(signals)
        for signal in consolidated_signals:
            try:
                # Risk management check
                is_valid, reason = await self.risk_manager.validate_signal(signal)
                if not is_valid:
                    logger.info(f"Signal rejected by risk manager: {signal.symbol} {signal.action} ({reason})")
                    self._add_event("rejected", signal.symbol, signal.strategy, reason)
                    continue
                
                # Execute trade
                trade_result = await self._execute_trade(signal)
                
                if trade_result:
                    logger.info(f"Trade executed: {signal.symbol} {signal.action} at {signal.price}")
                    
                    # Send notification
                    await self.notification_service.send_trade_notification(trade_result)
                    await self.risk_manager.record_trade(trade_result)
                    self.last_trade_at[signal.symbol] = datetime.utcnow()
                    if signal.strategy in self.strategies:
                        self.strategies[signal.strategy].update_performance(trade_result)
                    self._add_event("trade", signal.symbol, signal.strategy, "executed", trade_result)
                
            except Exception as e:
                logger.error(f"Error processing signal {signal.symbol}: {e}")

    def _consolidate_signals(self, signals: List[TradingSignal]) -> List[TradingSignal]:
        """Consolidate multiple strategy signals into at most one signal per symbol."""
        by_symbol: Dict[str, Dict[str, Any]] = {}
        now = datetime.utcnow()
        for signal in signals:
            if signal.action not in ("BUY", "SELL"):
                continue
            if not self._passes_cooldown(signal.symbol, now, signal.strategy):
                continue

            entry = by_symbol.setdefault(signal.symbol, {
                "buy_strength": 0.0,
                "sell_strength": 0.0,
                "best_buy": None,
                "best_sell": None,
            })
            weighted_conf = signal.confidence * self._strategy_weight(signal.strategy)
            if signal.action == "BUY":
                entry["buy_strength"] += weighted_conf
                if entry["best_buy"] is None or signal.confidence > entry["best_buy"].confidence:
                    entry["best_buy"] = signal
            else:
                entry["sell_strength"] += weighted_conf
                if entry["best_sell"] is None or signal.confidence > entry["best_sell"].confidence:
                    entry["best_sell"] = signal

        consolidated: List[TradingSignal] = []
        for symbol, data in by_symbol.items():
            buy_strength = data["buy_strength"]
            sell_strength = data["sell_strength"]
            selected = None

            if buy_strength > 0 and sell_strength > 0:
                ratio = settings.CONFLICT_STRENGTH_RATIO
                if buy_strength >= sell_strength * ratio:
                    selected = data["best_buy"]
                elif sell_strength >= buy_strength * ratio:
                    selected = data["best_sell"]
                else:
                    self._add_event("signal_conflict", symbol, "consensus", "conflicting signals dropped")
                    continue
            elif buy_strength > 0:
                selected = data["best_buy"]
            elif sell_strength > 0:
                selected = data["best_sell"]

            if selected is None:
                continue
            if selected.confidence < settings.MIN_SIGNAL_CONFIDENCE:
                continue
            if not self._passes_position_rules(selected, now):
                continue
            consolidated.append(selected)

        consolidated.sort(key=lambda s: s.confidence, reverse=True)
        return consolidated

    def _passes_cooldown(self, symbol: str, now: datetime, strategy: str) -> bool:
        if strategy == "risk_exit":
            return True
        last_trade_at = self.last_trade_at.get(symbol)
        if last_trade_at is None:
            return True
        elapsed = (now - last_trade_at).total_seconds()
        return elapsed >= settings.SIGNAL_COOLDOWN_SECONDS

    def _passes_position_rules(self, signal: TradingSignal, now: datetime) -> bool:
        has_position = signal.symbol in self.portfolio_manager.positions and self.portfolio_manager.positions[signal.symbol].get("quantity", 0) > 0
        if signal.action == "SELL":
            if not has_position:
                return False
            if signal.strategy == "risk_exit":
                return True
            opened_at = self.portfolio_manager.positions[signal.symbol].get("opened_at")
            if opened_at is None:
                return True
            hold_seconds = (now - opened_at).total_seconds()
            return hold_seconds >= settings.MIN_HOLD_SECONDS
        if signal.action == "BUY":
            if has_position:
                return False
        return True

    def _strategy_weight(self, strategy_name: str) -> float:
        strategy = self.strategies.get(strategy_name)
        if strategy is None:
            return 1.0
        perf = strategy.get_performance_metrics()
        total_trades = perf.get("total_trades", 0)
        if total_trades < 5:
            return 1.0
        win_rate = perf.get("win_rate", 0.0)
        total_pnl = perf.get("total_pnl", 0.0)
        base = 0.7 + (win_rate * 0.6)
        pnl_adj = 0.15 if total_pnl > 0 else -0.15
        return min(max(base + pnl_adj, 0.5), 1.5)
    
    async def _execute_trade(self, signal: TradingSignal) -> Optional[Dict]:
        """Execute a trade based on signal"""
        try:
            if not self._passes_edge_filter(signal):
                logger.info(f"Signal failed edge filter for {signal.symbol} {signal.action}")
                return None

            # Calculate position size
            position_size = signal.quantity if signal.quantity is not None else await self.risk_manager.calculate_position_size(signal)
            
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

    def _passes_edge_filter(self, signal: TradingSignal) -> bool:
        """
        Reject trades whose expected edge is too small compared with fees/slippage.
        This avoids churn on near-flat signals.
        """
        if signal.strategy == "risk_exit":
            return True
        if signal.price <= 0:
            return False

        # Approximate 0.1% per side fee + slippage buffer.
        min_reward = 0.004
        if signal.take_profit is not None:
            expected_reward = abs(signal.take_profit - signal.price) / signal.price
            if expected_reward < min_reward:
                return False
        if signal.stop_loss is not None and signal.take_profit is not None:
            risk = abs(signal.price - signal.stop_loss) / signal.price
            reward = abs(signal.take_profit - signal.price) / signal.price
            if risk <= 0:
                return False
            if (reward / risk) < 1.2:
                return False
        return True
    
    async def _process_exit_conditions(self, market_data: Dict):
        """Check stop-loss and take-profit for open positions"""
        try:
            for symbol, pos in list(self.portfolio_manager.positions.items()):
                if symbol not in market_data:
                    continue
                price = market_data[symbol].get("price")
                if price is None:
                    continue
                stop_loss = pos.get("stop_loss")
                take_profit = pos.get("take_profit")
                if stop_loss and price <= stop_loss:
                    logger.info(f"Stop-loss triggered for {symbol} at {price}")
                    exit_signal = TradingSignal(
                        symbol=symbol,
                        action="SELL",
                        confidence=1.0,
                        price=price,
                        quantity=pos.get("quantity", 0),
                        strategy="risk_exit",
                        metadata={"reason": "stop_loss"}
                    )
                    await self._execute_trade(exit_signal)
                elif take_profit and price >= take_profit:
                    logger.info(f"Take-profit triggered for {symbol} at {price}")
                    exit_signal = TradingSignal(
                        symbol=symbol,
                        action="SELL",
                        confidence=1.0,
                        price=price,
                        quantity=pos.get("quantity", 0),
                        strategy="risk_exit",
                        metadata={"reason": "take_profit"}
                    )
                    await self._execute_trade(exit_signal)
        except Exception as e:
            logger.error(f"Error processing exit conditions: {e}")

    def _add_event(self, event_type: str, symbol: str, strategy: str, message: str, details: Optional[Dict] = None):
        self.recent_events.appendleft({
            "type": event_type,
            "symbol": symbol,
            "strategy": strategy,
            "message": message,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get trading performance metrics"""
        return await self.portfolio_manager.get_performance_metrics()
    
    async def get_active_positions(self) -> List[Dict]:
        """Get all active positions"""
        return await self.portfolio_manager.get_active_positions()
    
    async def get_trading_history(self, limit: int = 100) -> List[Dict]:
        """Get trading history"""
        return await self.portfolio_manager.get_trading_history(limit)
