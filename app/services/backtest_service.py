"""
Backtest service for strategy evaluation using historical data
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np

from app.core.config import settings
from app.services.data_service import DataService
from app.strategies.momentum_strategy import MomentumStrategy
from app.strategies.mean_reversion_strategy import MeanReversionStrategy
from app.strategies.technical_analysis_strategy import TechnicalAnalysisStrategy


class BacktestService:
    """Runs historical backtests for configured strategies."""

    def __init__(self, data_service: DataService):
        self.data_service = data_service
        self.strategy_classes = {
            "momentum": MomentumStrategy,
            "mean_reversion": MeanReversionStrategy,
            "technical_analysis": TechnicalAnalysisStrategy
        }

    async def run_backtest(
        self,
        symbols: Optional[List[str]] = None,
        days: int = settings.BACKTEST_DAYS,
        strategies: Optional[List[str]] = None,
        initial_capital: float = settings.DEFAULT_CAPITAL
    ) -> Dict[str, Any]:
        symbols = symbols or settings.DEFAULT_SYMBOLS
        strategies = strategies or list(self.strategy_classes.keys())

        results = {}
        for strategy_name in strategies:
            if strategy_name not in self.strategy_classes:
                continue
            strategy = self.strategy_classes[strategy_name]()
            strategy_result = await self._run_strategy_backtest(strategy, symbols, days, initial_capital)
            results[strategy_name] = strategy_result

        return {
            "summary": self._summarize_results(results),
            "strategies": results
        }

    async def _run_strategy_backtest(
        self,
        strategy,
        symbols: List[str],
        days: int,
        initial_capital: float
    ) -> Dict[str, Any]:
        per_symbol = {}
        for symbol in symbols:
            hist = await self.data_service.get_historical_data(symbol, period="1y")
            if hist is None or hist.empty:
                continue

            hist = hist.tail(days)
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

            symbol_result = await self._simulate_trades(strategy, symbol, history, initial_capital)
            per_symbol[symbol] = symbol_result

        return per_symbol

    async def _simulate_trades(
        self,
        strategy,
        symbol: str,
        history: List[Dict[str, Any]],
        initial_capital: float
    ) -> Dict[str, Any]:
        cash = initial_capital
        position = None
        equity_curve = []
        trades = []

        lookback = max(
            strategy.parameters.get("lookback_period", 20),
            strategy.parameters.get("sma_long", 30),
            strategy.parameters.get("bb_period", 20)
        )

        for i in range(lookback, len(history)):
            window = history[: i + 1]
            latest = window[-1]

            # Stop-loss / take-profit check
            if position:
                low = latest["low"]
                high = latest["high"]
                if position["stop_loss"] and low <= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    cash += position["quantity"] * exit_price
                    trades.append({"pnl": (exit_price - position["entry_price"]) * position["quantity"], "result": "stop_loss"})
                    position = None
                elif position["take_profit"] and high >= position["take_profit"]:
                    exit_price = position["take_profit"]
                    cash += position["quantity"] * exit_price
                    trades.append({"pnl": (exit_price - position["entry_price"]) * position["quantity"], "result": "take_profit"})
                    position = None

            data = {
                "symbol": symbol,
                "price": latest["close"],
                "open": latest["open"],
                "high": latest["high"],
                "low": latest["low"],
                "volume": latest["volume"],
                "change": latest["close"] - latest["open"],
                "change_percent": ((latest["close"] - latest["open"]) / latest["open"] * 100) if latest["open"] > 0 else 0,
                "timestamp": latest["timestamp"],
                "history": window
            }

            signal = await strategy.generate_signal(symbol, data)
            if signal and signal.action == "BUY" and position is None:
                allocation = cash * settings.MAX_POSITION_SIZE
                quantity = int(allocation / latest["close"])
                if quantity > 0:
                    cash -= quantity * latest["close"]
                    position = {
                        "quantity": quantity,
                        "entry_price": latest["close"],
                        "stop_loss": signal.stop_loss,
                        "take_profit": signal.take_profit
                    }
            elif signal and signal.action == "SELL" and position is not None:
                cash += position["quantity"] * latest["close"]
                trades.append({"pnl": (latest["close"] - position["entry_price"]) * position["quantity"], "result": "signal_exit"})
                position = None

            equity = cash + (position["quantity"] * latest["close"] if position else 0)
            equity_curve.append(equity)

        return self._calculate_metrics(initial_capital, equity_curve, trades)

    def _calculate_metrics(self, initial_capital: float, equity_curve: List[float], trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not equity_curve:
            return {
                "total_return_percent": 0.0,
                "max_drawdown_percent": 0.0,
                "num_trades": 0,
                "win_rate": 0.0,
                "ending_value": initial_capital
            }

        ending_value = equity_curve[-1]
        total_return = (ending_value - initial_capital) / initial_capital * 100 if initial_capital > 0 else 0.0

        peak = equity_curve[0]
        max_drawdown = 0.0
        for value in equity_curve:
            peak = max(peak, value)
            drawdown = (peak - value) / peak if peak > 0 else 0.0
            max_drawdown = max(max_drawdown, drawdown)

        wins = len([t for t in trades if t["pnl"] > 0])
        win_rate = (wins / len(trades)) * 100 if trades else 0.0

        return {
            "total_return_percent": round(total_return, 2),
            "max_drawdown_percent": round(max_drawdown * 100, 2),
            "num_trades": len(trades),
            "win_rate": round(win_rate, 2),
            "ending_value": round(ending_value, 2)
        }

    def _summarize_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        if not results:
            return {}

        summary = {}
        for strategy_name, data in results.items():
            returns = [v["total_return_percent"] for v in data.values() if "total_return_percent" in v]
            drawdowns = [v["max_drawdown_percent"] for v in data.values() if "max_drawdown_percent" in v]
            summary[strategy_name] = {
                "avg_return_percent": round(float(np.mean(returns)) if returns else 0.0, 2),
                "avg_max_drawdown_percent": round(float(np.mean(drawdowns)) if drawdowns else 0.0, 2),
                "symbols_tested": len(data)
            }

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "strategies": summary
        }
