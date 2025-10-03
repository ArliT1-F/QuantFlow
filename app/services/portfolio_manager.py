"""
Portfolio management system for tracking positions and performance
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.portfolio import Portfolio, PortfolioSnapshot
from app.models.trade import Trade, Position

logger = logging.getLogger(__name__)

class PortfolioManager:
    """Portfolio management system for tracking positions and performance"""
    
    def __init__(self):
        self.portfolio_id = None
        self.cash_balance = 0.0
        self.total_value = 0.0
        self.positions = {}
        self.trade_history = []
        self.performance_metrics = {}
        
        logger.info("Portfolio manager initialized")
    
    async def initialize(self):
        """Initialize portfolio manager"""
        try:
            # Create or get default portfolio
            await self._create_or_get_portfolio()
            
            # Load existing positions
            await self._load_positions()
            
            logger.info("Portfolio manager initialized successfully")
            
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
                    total_value=10000.0,  # Default starting capital
                    cash_balance=10000.0,
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
            quantity = trade_data["quantity"]
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
            
            # Execute the trade
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
            
            # Simulate trade execution
            # In a real implementation, this would interface with a broker API
            
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
    
    async def _update_portfolio_after_trade(self, trade_result: Dict[str, Any]):
        """Update portfolio after trade execution"""
        try:
            symbol = trade_result["symbol"]
            side = trade_result["side"]
            quantity = trade_result["quantity"]
            price = trade_result["price"]
            fees = trade_result["fees"]
            
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
                    
                    # Update realized P&L
                    if "realized_pnl" not in self.positions.get(symbol, {}):
                        self.positions[symbol]["realized_pnl"] = 0.0
                    self.positions[symbol]["realized_pnl"] += realized_pnl
            
            # Update total portfolio value
            await self._calculate_total_value()
            
        except Exception as e:
            logger.error(f"Error updating portfolio after trade: {e}")
    
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
    
    async def update_portfolio(self):
        """Update portfolio with current market prices"""
        try:
            # Update current prices for all positions
            # In a real implementation, this would fetch current market prices
            
            total_unrealized_pnl = 0.0
            
            for symbol, pos in self.positions.items():
                # Simulate price update (in reality, fetch from market data)
                current_price = pos["current_price"] * (1 + np.random.normal(0, 0.01))  # 1% random change
                
                # Calculate unrealized P&L
                unrealized_pnl = (current_price - pos["average_price"]) * pos["quantity"]
                
                pos["current_price"] = current_price
                pos["unrealized_pnl"] = unrealized_pnl
                
                total_unrealized_pnl += unrealized_pnl
            
            # Update total portfolio value
            await self._calculate_total_value()
            
            # Update portfolio in database
            await self._update_portfolio_in_db()
            
            logger.info(f"Portfolio updated: Total Value: {self.total_value:.2f}, Unrealized P&L: {total_unrealized_pnl:.2f}")
            
        except Exception as e:
            logger.error(f"Error updating portfolio: {e}")
    
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
                total_realized_pnl = 0.0
                
                for symbol, pos in self.positions.items():
                    invested_amount += pos["quantity"] * pos["current_price"]
                    total_realized_pnl += pos["realized_pnl"]
                
                portfolio.invested_amount = invested_amount
                portfolio.total_pnl = total_realized_pnl
                
                # Calculate total P&L percentage
                if self.total_value > 0:
                    portfolio.total_pnl_percentage = (total_realized_pnl / (self.total_value - total_realized_pnl)) * 100
                
                portfolio.updated_at = datetime.utcnow()
                
                db.commit()
            
            db.close()
            
        except Exception as e:
            logger.error(f"Error updating portfolio in database: {e}")
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get portfolio performance metrics"""
        try:
            # Calculate various performance metrics
            total_realized_pnl = sum(pos["realized_pnl"] for pos in self.positions.values())
            total_unrealized_pnl = sum(pos["unrealized_pnl"] for pos in self.positions.values())
            
            # Calculate returns
            initial_capital = 10000.0  # Default starting capital
            total_return = (self.total_value - initial_capital) / initial_capital * 100
            
            # Calculate Sharpe ratio (simplified)
            sharpe_ratio = self._calculate_sharpe_ratio()
            
            # Calculate max drawdown
            max_drawdown = self._calculate_max_drawdown()
            
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
                "num_trades": len(self.trade_history)
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return {}
    
    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio (simplified)"""
        try:
            # Simplified Sharpe ratio calculation
            # In reality, this would use historical returns
            return 1.2  # Simulated Sharpe ratio
            
        except Exception as e:
            logger.error(f"Error calculating Sharpe ratio: {e}")
            return 0.0
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown (simplified)"""
        try:
            # Simplified max drawdown calculation
            # In reality, this would track historical peak values
            return 0.05  # Simulated 5% max drawdown
            
        except Exception as e:
            logger.error(f"Error calculating max drawdown: {e}")
            return 0.0
    
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