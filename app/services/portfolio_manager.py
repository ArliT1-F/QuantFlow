"""
Portfolio management system for tracking positions and performance
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import numpy as np
from app.core.database import SessionLocal
from app.core.config import settings
from app.services.okx_client import OkxClient
from app.models.portfolio import Portfolio, PortfolioSnapshot
from app.models.trade import Trade, Position

logger = logging.getLogger(__name__)

class PortfolioManager:
    """Portfolio management system for tracking positions and performance"""
    
    def __init__(self, okx_client: Optional[OkxClient] = None):
        self.portfolio_id = None
        self.cash_balance = 0.0
        self.total_value = 0.0
        self.initial_capital = settings.DEFAULT_CAPITAL
        self.total_realized_pnl = 0.0
        self.positions = {}
        self.trade_history = []
        self.performance_metrics = {}
        self.initialized = False
        self.okx_client = okx_client
        self._last_snapshot_at: Optional[datetime] = None
        self._snapshot_interval = settings.PORTFOLIO_SNAPSHOT_INTERVAL
        
        logger.info("Portfolio manager initialized")
    
    async def initialize(self):
        """Initialize portfolio manager"""
        if self.initialized:
            return
        try:
            # Create or get default portfolio
            await self._create_or_get_portfolio()
            
            # Load existing positions
            await self._load_positions()

            # Record an initial snapshot so the dashboard has data
            await self._record_snapshot(force=True)
            
            logger.info("Portfolio manager initialized successfully")
            self.initialized = True
            
        except Exception as e:
            logger.error(f"Error initializing portfolio manager: {e}")
            raise
    
    async def _create_or_get_portfolio(self):
        """Create or get default portfolio"""
        try:
            db = SessionLocal()
            
            # Look for existing portfolio
            portfolio = db.query(Portfolio).filter(Portfolio.is_active == True).first()
            
            if not portfolio:
                # Create new portfolio
                portfolio = Portfolio(
                    name="Default Trading Portfolio",
                    total_value=settings.DEFAULT_CAPITAL,
                    cash_balance=settings.DEFAULT_CAPITAL,
                    invested_amount=0.0,
                    total_pnl=0.0,
                    total_pnl_percentage=0.0
                )
                
                db.add(portfolio)
                db.commit()
                db.refresh(portfolio)
                
                logger.info("Created new portfolio")
            else:
                logger.info("Loaded existing portfolio")
            
            self.portfolio_id = portfolio.id
            self.cash_balance = portfolio.cash_balance
            self.total_value = portfolio.total_value
            self.total_realized_pnl = portfolio.total_pnl
            self.initial_capital = portfolio.total_value if portfolio.total_value > 0 else settings.DEFAULT_CAPITAL
            
            db.close()
            
        except Exception as e:
            logger.error(f"Error creating/getting portfolio: {e}")
            raise
    
    async def _load_positions(self):
        """Load existing positions"""
        try:
            db = SessionLocal()
            
            positions = db.query(Position).filter(
                Position.portfolio_id == self.portfolio_id,
                Position.quantity != 0
            ).all()
            
            for position in positions:
                self.positions[position.symbol] = {
                    "quantity": position.quantity,
                    "average_price": position.average_price,
                    "current_price": position.current_price,
                    "unrealized_pnl": position.unrealized_pnl,
                    "realized_pnl": position.realized_pnl,
                    "stop_loss": position.stop_loss,
                    "take_profit": position.take_profit,
                    "opened_at": position.opened_at
                }
            
            db.close()
            logger.info(f"Loaded {len(self.positions)} positions")
            
        except Exception as e:
            logger.error(f"Error loading positions: {e}")
    
    async def execute_trade(self, trade_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute a trade and update portfolio
        
        Args:
            trade_data: Trade data dictionary
            
        Returns:
            Trade result dictionary or None
        """
        try:
            symbol = trade_data["symbol"]
            side = trade_data["side"]
            quantity = float(trade_data["quantity"])
            price = trade_data["price"]
            strategy = trade_data.get("strategy", "")
            stop_loss = trade_data.get("stop_loss")
            take_profit = trade_data.get("take_profit")
            
            # Calculate trade value
            trade_value = quantity * price
            
            # Check if we have enough cash for buy orders
            if side == "BUY" and trade_value > self.cash_balance:
                logger.warning(f"Insufficient cash for {symbol} trade: {trade_value} > {self.cash_balance}")
                return None
            
            # Prevent selling without a position (no shorting)
            if side == "SELL":
                if symbol not in self.positions or self.positions[symbol]["quantity"] <= 0:
                    logger.warning(f"No position to sell for {symbol}")
                    return None
                # Cap sell quantity to available position
                if quantity > self.positions[symbol]["quantity"]:
                    trade_data["quantity"] = self.positions[symbol]["quantity"]
                    quantity = trade_data["quantity"]
                    trade_value = quantity * price
            
            # Execute the trade (live if enabled)
            trade_result = await self._process_trade_execution(trade_data)
            
            if trade_result:
                # Update portfolio
                await self._update_portfolio_after_trade(trade_result)
                
                # Record trade in database
                await self._record_trade_in_db(trade_result)
                
                # Update positions
                await self._update_positions(trade_result)
                
                logger.info(f"Trade executed: {symbol} {side} {quantity} @ {price}")
            
            return trade_result
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return None
    
    async def _process_trade_execution(self, trade_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process trade execution"""
        try:
            symbol = trade_data["symbol"]
            side = trade_data["side"]
            quantity = trade_data["quantity"]
            price = trade_data["price"]
            
            # Place live order if enabled
            if settings.OKX_ENABLED and settings.OKX_TRADING_ENABLED and self.okx_client:
                inst_id = self._okx_inst_id(symbol)
                okx_result = self.okx_client.place_market_order(
                    inst_id=inst_id,
                    side=side.lower(),
                    size=str(quantity),
                    td_mode="cash"
                )
                if okx_result.get("code") != "0":
                    logger.error(f"OKX order failed: {okx_result}")
                    return None

            # Simulate trade execution (paper trading or post-live order tracking)
            execution_price = price  # Assume execution at signal price
            fees = quantity * execution_price * 0.001  # 0.1% fee
            
            trade_result = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": execution_price,
                "fees": fees,
                "timestamp": datetime.utcnow(),
                "status": "FILLED",
                "strategy": trade_data.get("strategy", ""),
                "stop_loss": trade_data.get("stop_loss"),
                "take_profit": trade_data.get("take_profit")
            }
            
            return trade_result
            
        except Exception as e:
            logger.error(f"Error processing trade execution: {e}")
            return None

    def _okx_inst_id(self, symbol: str) -> str:
        if "-" in symbol:
            base, quote = symbol.split("-", 1)
            if quote.upper() == "USD":
                quote = settings.OKX_QUOTE_CCY
            return f"{base.upper()}-{quote.upper()}"
        return f"{symbol.upper()}-{settings.OKX_QUOTE_CCY}"
    
    async def _update_portfolio_after_trade(self, trade_result: Dict[str, Any]) -> float:
        """Update portfolio after trade execution"""
        try:
            symbol = trade_result["symbol"]
            side = trade_result["side"]
            quantity = trade_result["quantity"]
            price = trade_result["price"]
            fees = trade_result["fees"]
            trade_result.setdefault("pnl", 0.0)
            
            trade_value = quantity * price
            
            if side == "BUY":
                # Deduct cash and add position
                self.cash_balance -= (trade_value + fees)
                
                if symbol in self.positions:
                    # Update existing position
                    pos = self.positions[symbol]
                    total_quantity = pos["quantity"] + quantity
                    total_cost = (pos["quantity"] * pos["average_price"]) + trade_value
                    new_avg_price = total_cost / total_quantity
                    
                    self.positions[symbol]["quantity"] = total_quantity
                    self.positions[symbol]["average_price"] = new_avg_price
                else:
                    # Create new position
                    self.positions[symbol] = {
                        "quantity": quantity,
                        "average_price": price,
                        "current_price": price,
                        "unrealized_pnl": 0.0,
                        "realized_pnl": 0.0,
                        "stop_loss": trade_result.get("stop_loss"),
                        "take_profit": trade_result.get("take_profit"),
                        "opened_at": datetime.utcnow()
                    }
            
            else:  # SELL
                # Add cash and reduce position
                self.cash_balance += (trade_value - fees)
                
                if symbol in self.positions:
                    pos = self.positions[symbol]
                    
                    if quantity >= pos["quantity"]:
                        # Close entire position
                        realized_pnl = (price - pos["average_price"]) * pos["quantity"] - fees
                        del self.positions[symbol]
                    else:
                        # Partial close
                        realized_pnl = (price - pos["average_price"]) * quantity - fees
                        self.positions[symbol]["quantity"] -= quantity
                        self.positions[symbol]["realized_pnl"] += realized_pnl
                    
                    # Track realized P&L at portfolio level
                    self.total_realized_pnl += realized_pnl
                    trade_result["pnl"] = realized_pnl
                else:
                    trade_result["pnl"] = 0.0
            
            # Update total portfolio value
            await self._calculate_total_value()
            return trade_result.get("pnl", 0.0)
            
        except Exception as e:
            logger.error(f"Error updating portfolio after trade: {e}")
            return 0.0
    
    async def _calculate_total_value(self):
        """Calculate total portfolio value"""
        try:
            # Calculate invested amount
            invested_amount = 0.0
            
            for symbol, pos in self.positions.items():
                invested_amount += pos["quantity"] * pos["current_price"]
            
            # Total value = cash + invested amount
            self.total_value = self.cash_balance + invested_amount
            
        except Exception as e:
            logger.error(f"Error calculating total value: {e}")
    
    async def _record_trade_in_db(self, trade_result: Dict[str, Any]):
        """Record trade in database"""
        try:
            db = SessionLocal()
            
            trade = Trade(
                symbol=trade_result["symbol"],
                side=trade_result["side"],
                quantity=trade_result["quantity"],
                price=trade_result["price"],
                timestamp=trade_result["timestamp"],
                strategy=trade_result["strategy"],
                status=trade_result["status"],
                fees=trade_result["fees"],
                stop_loss=trade_result.get("stop_loss"),
                take_profit=trade_result.get("take_profit"),
                portfolio_id=self.portfolio_id
            )
            
            db.add(trade)
            db.commit()
            
            db.close()
            
        except Exception as e:
            logger.error(f"Error recording trade in database: {e}")
    
    async def _update_positions(self, trade_result: Dict[str, Any]):
        """Update positions in database"""
        try:
            db = SessionLocal()
            
            symbol = trade_result["symbol"]
            
            # Get or create position
            position = db.query(Position).filter(
                Position.symbol == symbol,
                Position.portfolio_id == self.portfolio_id
            ).first()
            
            if symbol in self.positions:
                pos_data = self.positions[symbol]
                
                if position:
                    # Update existing position
                    position.quantity = pos_data["quantity"]
                    position.average_price = pos_data["average_price"]
                    position.current_price = pos_data["current_price"]
                    position.unrealized_pnl = pos_data["unrealized_pnl"]
                    position.realized_pnl = pos_data["realized_pnl"]
                    position.stop_loss = pos_data.get("stop_loss")
                    position.take_profit = pos_data.get("take_profit")
                    position.updated_at = datetime.utcnow()
                else:
                    # Create new position
                    position = Position(
                        symbol=symbol,
                        quantity=pos_data["quantity"],
                        average_price=pos_data["average_price"],
                        current_price=pos_data["current_price"],
                        unrealized_pnl=pos_data["unrealized_pnl"],
                        realized_pnl=pos_data["realized_pnl"],
                        stop_loss=pos_data.get("stop_loss"),
                        take_profit=pos_data.get("take_profit"),
                        portfolio_id=self.portfolio_id
                    )
                    db.add(position)
            else:
                # Position was closed, delete from database
                if position:
                    db.delete(position)
            
            db.commit()
            db.close()
            
        except Exception as e:
            logger.error(f"Error updating positions: {e}")
    
    async def update_portfolio(self, market_data: Optional[Dict[str, Any]] = None):
        """Update portfolio with current market prices"""
        try:
            # Update current prices for all positions
            total_unrealized_pnl = 0.0
            
            for symbol, pos in self.positions.items():
                current_price = pos["current_price"]
                if market_data and symbol in market_data:
                    market_price = market_data[symbol].get("price")
                    if market_price is not None:
                        current_price = float(market_price)
                
                # Calculate unrealized P&L
                unrealized_pnl = (current_price - pos["average_price"]) * pos["quantity"]
                
                pos["current_price"] = current_price
                pos["unrealized_pnl"] = unrealized_pnl
                
                total_unrealized_pnl += unrealized_pnl
            
            # Update total portfolio value
            await self._calculate_total_value()
            
            # Update portfolio in database
            await self._update_portfolio_in_db()

            # Record periodic snapshots for performance tracking
            await self._record_snapshot_if_due()
            
            logger.info(f"Portfolio updated: Total Value: {self.total_value:.2f}, Unrealized P&L: {total_unrealized_pnl:.2f}")
            
        except Exception as e:
            logger.error(f"Error updating portfolio: {e}")

    async def _record_snapshot_if_due(self):
        """Record a portfolio snapshot based on the configured interval"""
        now = datetime.utcnow()
        if self._last_snapshot_at is None:
            await self._record_snapshot(force=True)
            return
        elapsed = (now - self._last_snapshot_at).total_seconds()
        if elapsed >= self._snapshot_interval:
            await self._record_snapshot(force=True)

    async def _record_snapshot(self, force: bool = False):
        """Persist a portfolio snapshot"""
        if not self.portfolio_id:
            return
        if not force:
            return
        try:
            db = SessionLocal()
            invested_amount = sum(pos["quantity"] * pos["current_price"] for pos in self.positions.values())
            total_pnl = self.total_realized_pnl + sum(pos["unrealized_pnl"] for pos in self.positions.values())
            total_pnl_percentage = 0.0
            if self.initial_capital > 0:
                total_pnl_percentage = ((self.total_value - self.initial_capital) / self.initial_capital) * 100
            snapshot_metrics = self._calculate_snapshot_metrics(db, self.total_value)

            snapshot = PortfolioSnapshot(
                portfolio_id=self.portfolio_id,
                total_value=self.total_value,
                cash_balance=self.cash_balance,
                invested_amount=invested_amount,
                total_pnl=total_pnl,
                total_pnl_percentage=total_pnl_percentage,
                daily_return=snapshot_metrics["daily_return"],
                weekly_return=snapshot_metrics["weekly_return"],
                monthly_return=snapshot_metrics["monthly_return"],
                sharpe_ratio=snapshot_metrics["sharpe_ratio"],
                max_drawdown=snapshot_metrics["max_drawdown"]
            )
            db.add(snapshot)
            db.commit()
            db.close()
            self._last_snapshot_at = datetime.utcnow()
        except Exception as e:
            logger.error(f"Error recording portfolio snapshot: {e}")
    
    async def _update_portfolio_in_db(self):
        """Update portfolio in database"""
        try:
            db = SessionLocal()
            
            portfolio = db.query(Portfolio).filter(Portfolio.id == self.portfolio_id).first()
            
            if portfolio:
                portfolio.total_value = self.total_value
                portfolio.cash_balance = self.cash_balance
                
                # Calculate invested amount
                invested_amount = 0.0
                
                for symbol, pos in self.positions.items():
                    invested_amount += pos["quantity"] * pos["current_price"]
                
                portfolio.invested_amount = invested_amount
                portfolio.total_pnl = self.total_realized_pnl
                
                # Calculate total P&L percentage
                if self.initial_capital > 0:
                    portfolio.total_pnl_percentage = ((self.total_value - self.initial_capital) / self.initial_capital) * 100
                
                portfolio.updated_at = datetime.utcnow()
                
                db.commit()
            
            db.close()
            
        except Exception as e:
            logger.error(f"Error updating portfolio in database: {e}")
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get portfolio performance metrics"""
        try:
            # Calculate various performance metrics
            total_realized_pnl = self.total_realized_pnl
            total_unrealized_pnl = sum(pos["unrealized_pnl"] for pos in self.positions.values())
            
            # Calculate returns
            total_return = (self.total_value - self.initial_capital) / self.initial_capital * 100 if self.initial_capital > 0 else 0.0
            
            db = SessionLocal()
            num_trades = db.query(Trade).filter(Trade.portfolio_id == self.portfolio_id).count()
            recent_snapshots = db.query(PortfolioSnapshot).filter(
                PortfolioSnapshot.portfolio_id == self.portfolio_id
            ).order_by(PortfolioSnapshot.timestamp.asc()).limit(1000).all()
            db.close()
            history_values = [float(s.total_value) for s in recent_snapshots if s.total_value is not None]
            if self.total_value > 0 and (not history_values or history_values[-1] != float(self.total_value)):
                history_values.append(float(self.total_value))

            sharpe_ratio = self._calculate_sharpe_ratio(history_values)
            max_drawdown = self._calculate_max_drawdown(history_values)

            metrics = {
                "total_value": self.total_value,
                "cash_balance": self.cash_balance,
                "invested_amount": sum(pos["quantity"] * pos["current_price"] for pos in self.positions.values()),
                "total_realized_pnl": total_realized_pnl,
                "total_unrealized_pnl": total_unrealized_pnl,
                "total_pnl": total_realized_pnl + total_unrealized_pnl,
                "total_return_percent": total_return,
                "sharpe_ratio": sharpe_ratio,
                "max_drawdown": max_drawdown,
                "num_positions": len(self.positions),
                "num_trades": num_trades
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return {}
    
    def _calculate_sharpe_ratio(self, equity_curve: List[float]) -> float:
        """Calculate annualized Sharpe ratio from equity curve returns."""
        try:
            if len(equity_curve) < 3:
                return 0.0
            returns = []
            for i in range(1, len(equity_curve)):
                prev_value = equity_curve[i - 1]
                curr_value = equity_curve[i]
                if prev_value > 0:
                    returns.append((curr_value - prev_value) / prev_value)
            if len(returns) < 2:
                return 0.0
            returns_arr = np.array(returns, dtype=float)
            std = returns_arr.std(ddof=1)
            if std <= 1e-12:
                return 0.0
            sharpe = (returns_arr.mean() / std) * np.sqrt(365.0)
            return float(round(sharpe, 4))
        except Exception as e:
            logger.error(f"Error calculating Sharpe ratio: {e}")
            return 0.0
    
    def _calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """Calculate maximum drawdown (%) from equity curve."""
        try:
            if not equity_curve:
                return 0.0
            peak = equity_curve[0]
            max_drawdown = 0.0
            for value in equity_curve:
                if value > peak:
                    peak = value
                if peak > 0:
                    drawdown = (peak - value) / peak
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown
            return float(round(max_drawdown * 100.0, 4))
        except Exception as e:
            logger.error(f"Error calculating max drawdown: {e}")
            return 0.0

    def _calculate_snapshot_metrics(self, db, current_total_value: float) -> Dict[str, float]:
        """Calculate period returns and performance metrics for a new snapshot."""
        snapshots = db.query(PortfolioSnapshot).filter(
            PortfolioSnapshot.portfolio_id == self.portfolio_id
        ).order_by(PortfolioSnapshot.timestamp.asc()).limit(1000).all()

        history_values = [float(s.total_value) for s in snapshots if s.total_value is not None]
        if current_total_value > 0 and (not history_values or history_values[-1] != float(current_total_value)):
            history_values.append(float(current_total_value))

        now = datetime.utcnow()
        daily_return = self._calculate_period_return(snapshots, current_total_value, now, 1)
        weekly_return = self._calculate_period_return(snapshots, current_total_value, now, 7)
        monthly_return = self._calculate_period_return(snapshots, current_total_value, now, 30)

        return {
            "daily_return": daily_return,
            "weekly_return": weekly_return,
            "monthly_return": monthly_return,
            "sharpe_ratio": self._calculate_sharpe_ratio(history_values),
            "max_drawdown": self._calculate_max_drawdown(history_values),
        }

    def _calculate_period_return(self, snapshots: List[PortfolioSnapshot], current_value: float, now: datetime, period_days: int) -> float:
        """Calculate return (%) since the most recent snapshot older than period_days."""
        if current_value <= 0:
            return 0.0

        cutoff = now.timestamp() - (period_days * 86400)
        base_snapshot = None
        for snap in reversed(snapshots):
            if not snap.timestamp or not snap.total_value or snap.total_value <= 0:
                continue
            snap_dt = snap.timestamp.replace(tzinfo=None) if snap.timestamp.tzinfo else snap.timestamp
            if snap_dt.timestamp() <= cutoff:
                base_snapshot = snap
                break
        if base_snapshot is None and snapshots:
            base_snapshot = snapshots[-1]
        if base_snapshot is None or not base_snapshot.total_value or base_snapshot.total_value <= 0:
            return 0.0
        period_return = ((current_value - float(base_snapshot.total_value)) / float(base_snapshot.total_value)) * 100.0
        return float(round(period_return, 4))
    
    async def get_active_positions(self) -> List[Dict[str, Any]]:
        """Get all active positions"""
        try:
            positions = []
            
            for symbol, pos in self.positions.items():
                position_data = {
                    "symbol": symbol,
                    "quantity": pos["quantity"],
                    "average_price": pos["average_price"],
                    "current_price": pos["current_price"],
                    "unrealized_pnl": pos["unrealized_pnl"],
                    "realized_pnl": pos["realized_pnl"],
                    "total_pnl": pos["unrealized_pnl"] + pos["realized_pnl"],
                    "pnl_percentage": ((pos["current_price"] - pos["average_price"]) / pos["average_price"]) * 100,
                    "stop_loss": pos.get("stop_loss"),
                    "take_profit": pos.get("take_profit"),
                    "opened_at": pos["opened_at"].isoformat() if pos["opened_at"] else None
                }
                positions.append(position_data)
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting active positions: {e}")
            return []
    
    async def get_trading_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get trading history"""
        try:
            db = SessionLocal()
            
            trades = db.query(Trade).filter(
                Trade.portfolio_id == self.portfolio_id
            ).order_by(Trade.timestamp.desc()).limit(limit).all()
            
            trade_history = []
            for trade in trades:
                trade_data = {
                    "id": trade.id,
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "quantity": trade.quantity,
                    "price": trade.price,
                    "timestamp": trade.timestamp.isoformat(),
                    "strategy": trade.strategy,
                    "status": trade.status,
                    "fees": trade.fees,
                    "stop_loss": trade.stop_loss,
                    "take_profit": trade.take_profit
                }
                trade_history.append(trade_data)
            
            db.close()
            return trade_history
            
        except Exception as e:
            logger.error(f"Error getting trading history: {e}")
            return []

    async def get_performance_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get portfolio performance history"""
        try:
            db = SessionLocal()
            snapshots = db.query(PortfolioSnapshot).filter(
                PortfolioSnapshot.portfolio_id == self.portfolio_id
            ).order_by(PortfolioSnapshot.timestamp.desc()).limit(limit).all()
            db.close()

            history = []
            for snap in reversed(snapshots):
                history.append({
                    "timestamp": snap.timestamp.isoformat() if snap.timestamp else None,
                    "total_value": snap.total_value,
                    "cash_balance": snap.cash_balance,
                    "invested_amount": snap.invested_amount,
                    "total_pnl": snap.total_pnl,
                    "total_pnl_percentage": snap.total_pnl_percentage
                })
            return history
        except Exception as e:
            logger.error(f"Error getting performance history: {e}")
            return []
