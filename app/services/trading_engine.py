"""
Core trading engine that orchestrates all trading activities
"""
import asyncio
import logging
import math
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
        self.trade_timestamps = deque()
        self.rejected_signals_total = 0
        
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
                symbols = await self._build_trading_symbols()
                # Get current market data
                market_data = await self.data_service.get_latest_data_for_symbols(symbols, include_history=True)
                
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

    async def _build_trading_symbols(self) -> List[str]:
        """Build symbol universe for the next loop iteration."""
        symbols: List[str] = []
        dynamic_symbols: List[str] = []
        try:
            if settings.DEXSCREENER_DYNAMIC_UNIVERSE_ENABLED and settings.DEXSCREENER_ENABLED:
                dynamic_symbols = await self.data_service.get_dynamic_dex_symbols()
        except Exception as e:
            logger.warning(f"Unable to load dynamic Dex symbols: {e}")
        if dynamic_symbols:
            symbols.extend(dynamic_symbols)
        else:
            symbols.extend(settings.DEFAULT_SYMBOLS)
        for symbol in self.portfolio_manager.positions.keys():
            symbols.append(symbol)
        deduped: List[str] = []
        seen = set()
        for raw_symbol in symbols:
            symbol = str(raw_symbol or "").strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            deduped.append(symbol)
        return deduped
    
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
                        signal.metadata["base_token_address"] = data.get("base_token_address")
                        signal.metadata["quote_token_address"] = data.get("quote_token_address")
                        signal.metadata["pair_address"] = data.get("pair_address")
                        signal.strategy = strategy_name
                        signals.append(signal)
                except Exception as e:
                    logger.error(f"Error generating signal for {symbol} with {strategy_name}: {e}")
        
        return signals

    async def _select_active_strategies(self):
        """
        Keep all configured strategies active in simplified mode.
        """
        self.active_strategy_names = set(self.strategies.keys())
    
    async def _process_signals(self, signals: List[TradingSignal]):
        """Process trading signals and execute trades"""
        consolidated_signals = self._consolidate_signals(signals)
        for signal in consolidated_signals:
            try:
                if not self._passes_hourly_trade_limit(signal):
                    self.rejected_signals_total += 1
                    self._add_event("rejected", signal.symbol, signal.strategy, "hourly trade limit reached")
                    continue

                # Risk management check
                is_valid, reason = await self.risk_manager.validate_signal(signal)
                if not is_valid:
                    logger.info(f"Signal rejected by risk manager: {signal.symbol} {signal.action} ({reason})")
                    self.rejected_signals_total += 1
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
                else:
                    self.rejected_signals_total += 1
                    self._add_event("rejected", signal.symbol, signal.strategy, "execution rejected")
                
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

        consolidated.sort(key=self._signal_priority, reverse=True)
        return consolidated[:max(int(settings.MAX_SIGNALS_PER_CYCLE), 1)]

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

    def _passes_hourly_trade_limit(self, signal: TradingSignal) -> bool:
        # Risk exits should bypass throughput limits to preserve hard protection.
        if signal.strategy == "risk_exit":
            return True
        max_per_hour = max(int(settings.MAX_TRADES_PER_HOUR), 1)
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=1)
        while self.trade_timestamps and self.trade_timestamps[0] < cutoff:
            self.trade_timestamps.popleft()
        return len(self.trade_timestamps) < max_per_hour

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

    def _signal_priority(self, signal: TradingSignal) -> float:
        expected_reward = self._expected_reward_ratio(signal)
        risk_ratio = self._risk_ratio(signal)
        rr_ratio = (expected_reward / risk_ratio) if risk_ratio > 0 else 0.0
        bounded_rr = min(max(rr_ratio, 0.5), 3.0)
        return signal.confidence * self._strategy_weight(signal.strategy) * (1.0 + expected_reward) * bounded_rr

    def _expected_reward_ratio(self, signal: TradingSignal) -> float:
        if signal.price <= 0 or signal.take_profit is None:
            return 0.0
        return abs(signal.take_profit - signal.price) / signal.price

    def _risk_ratio(self, signal: TradingSignal) -> float:
        if signal.price <= 0 or signal.stop_loss is None:
            return 0.0
        return abs(signal.price - signal.stop_loss) / signal.price

    def _extract_closes(self, signal: TradingSignal) -> List[float]:
        metadata = signal.metadata or {}
        closes_by_symbol = metadata.get("closes_by_symbol") or {}
        closes = closes_by_symbol.get(signal.symbol) or []
        normalized: List[float] = []
        for value in closes:
            try:
                close = float(value)
            except (TypeError, ValueError):
                continue
            if close > 0:
                normalized.append(close)
        return normalized

    def _return_stats(self, closes: List[float]) -> Optional[Dict[str, float]]:
        if len(closes) < 3:
            return None
        window = max(2, min(int(settings.ENTRY_FILTER_VOL_WINDOW), len(closes) - 1))
        sample = closes[-(window + 1):]
        returns: List[float] = []
        for idx in range(1, len(sample)):
            prev = sample[idx - 1]
            curr = sample[idx]
            if prev <= 0:
                continue
            returns.append((curr - prev) / prev)
        if len(returns) < 2:
            return None
        mean_return = sum(returns) / len(returns)
        variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
        std_return = math.sqrt(max(variance, 0.0))
        return {
            "mean": mean_return,
            "std": std_return,
            "count": float(len(returns))
        }
    
    async def _execute_trade(self, signal: TradingSignal) -> Optional[Dict]:
        """Execute a trade based on signal"""
        try:
            if not self._passes_edge_filter(signal):
                logger.info(f"Signal failed edge filter for {signal.symbol} {signal.action}")
                return None

            # Calculate position size
            position_size = signal.quantity if signal.quantity is not None else await self.risk_manager.calculate_position_size(signal)
            if signal.action == "BUY" and signal.price > 0 and settings.MAX_BUY_NOTIONAL_USD > 0:
                max_units = settings.MAX_BUY_NOTIONAL_USD / signal.price
                position_size = min(position_size, max_units)
            
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
                "base_token_address": (signal.metadata or {}).get("base_token_address", ""),
                "quote_token_address": (signal.metadata or {}).get("quote_token_address", ""),
                "pair_address": (signal.metadata or {}).get("pair_address", ""),
                "timestamp": datetime.utcnow()
            }
            
            # Execute through portfolio manager
            trade_result = await self.portfolio_manager.execute_trade(trade_data)
            if trade_result:
                self.trade_timestamps.append(datetime.utcnow())
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

        expected_reward = self._expected_reward_ratio(signal)
        risk_ratio = self._risk_ratio(signal)
        if expected_reward <= 0 or risk_ratio <= 0:
            return False

        if not settings.ADVANCED_ENTRY_FILTER_ENABLED:
            if expected_reward < settings.ENTRY_FILTER_MIN_EXPECTED_EDGE:
                return False
            if (expected_reward / risk_ratio) < settings.ENTRY_FILTER_MIN_RR:
                return False
            return True

        fee_and_slippage = (
            (settings.ENTRY_FILTER_FEE_BPS_PER_SIDE * 2.0) + settings.ENTRY_FILTER_SLIPPAGE_BPS
        ) / 10000.0
        stats = self._return_stats(self._extract_closes(signal))
        volatility = stats["std"] if stats else 0.0

        min_reward = max(
            settings.ENTRY_FILTER_MIN_EXPECTED_EDGE,
            fee_and_slippage + (volatility * settings.ENTRY_FILTER_VOL_MULTIPLIER)
        )
        if expected_reward < min_reward:
            return False

        rr_ratio = expected_reward / risk_ratio
        rr_floor = max(settings.ENTRY_FILTER_MIN_RR, 1.0 + min(1.0, volatility * 8.0))
        configured_rr = settings.TAKE_PROFIT_PERCENTAGE / max(settings.STOP_LOSS_PERCENTAGE, 1e-9)
        if configured_rr < rr_floor:
            rr_floor = max(configured_rr * 0.9, 0.05)
        if rr_ratio < rr_floor:
            return False

        if stats and stats["count"] >= float(settings.ENTRY_FILTER_MIN_HISTORY):
            trend_z = (stats["mean"] / max(stats["std"], 1e-9)) * math.sqrt(stats["count"])
            if signal.action == "BUY" and trend_z < settings.ENTRY_FILTER_TREND_Z_MIN:
                return False
            if signal.action == "SELL" and trend_z > -settings.ENTRY_FILTER_TREND_Z_MIN:
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
