from datetime import datetime, timedelta
import pytest

from app.services.trading_engine import TradingEngine, TradingSignal
from app.core.config import settings


class DummyDataService:
    pass


class DummyNotificationService:
    async def send_alert(self, *args, **kwargs):
        return True

    async def send_trade_notification(self, *args, **kwargs):
        return True

    async def send_risk_alert(self, *args, **kwargs):
        return True


class DummyPortfolioManager:
    def __init__(self):
        self.total_value = 10000.0
        self.positions = {}
        self.last_trade_data = None

    async def execute_trade(self, trade_data):
        self.last_trade_data = trade_data
        return {
            "symbol": trade_data["symbol"],
            "side": trade_data["side"],
            "quantity": trade_data["quantity"],
            "price": trade_data["price"],
            "strategy": trade_data.get("strategy", ""),
            "status": "FILLED",
        }


def _build_engine():
    return TradingEngine(
        data_service=DummyDataService(),
        notification_service=DummyNotificationService(),
        portfolio_manager=DummyPortfolioManager(),
    )


def test_consolidate_signals_drops_unresolved_conflict(monkeypatch):
    monkeypatch.setattr(settings, "CONFLICT_STRENGTH_RATIO", 1.35)
    monkeypatch.setattr(settings, "MIN_SIGNAL_CONFIDENCE", 0.5)
    engine = _build_engine()
    signals = [
        TradingSignal(symbol="ADA-USD", action="BUY", confidence=0.72, price=0.27, strategy="momentum", stop_loss=0.26, take_profit=0.29),
        TradingSignal(symbol="ADA-USD", action="SELL", confidence=0.69, price=0.27, strategy="technical_analysis", stop_loss=0.28, take_profit=0.25),
    ]
    consolidated = engine._consolidate_signals(signals)
    assert consolidated == []


def test_consolidate_signals_keeps_dominant_buy(monkeypatch):
    monkeypatch.setattr(settings, "CONFLICT_STRENGTH_RATIO", 1.2)
    monkeypatch.setattr(settings, "MIN_SIGNAL_CONFIDENCE", 0.5)
    engine = _build_engine()
    signals = [
        TradingSignal(symbol="BTC-USD", action="BUY", confidence=0.9, price=70000, strategy="momentum", stop_loss=68000, take_profit=74000),
        TradingSignal(symbol="BTC-USD", action="SELL", confidence=0.4, price=70000, strategy="technical_analysis", stop_loss=71000, take_profit=68000),
    ]
    consolidated = engine._consolidate_signals(signals)
    assert len(consolidated) == 1
    assert consolidated[0].action == "BUY"


def test_consolidate_signals_blocks_sell_during_min_hold(monkeypatch):
    monkeypatch.setattr(settings, "MIN_HOLD_SECONDS", 3600)
    monkeypatch.setattr(settings, "MIN_SIGNAL_CONFIDENCE", 0.5)
    engine = _build_engine()
    engine.portfolio_manager.positions["SOL-USD"] = {
        "quantity": 1.0,
        "current_price": 100.0,
        "opened_at": datetime.utcnow(),
    }
    signals = [
        TradingSignal(symbol="SOL-USD", action="SELL", confidence=0.9, price=100.0, strategy="technical_analysis", stop_loss=101.0, take_profit=96.0),
    ]
    consolidated = engine._consolidate_signals(signals)
    assert consolidated == []


@pytest.mark.asyncio
async def test_select_active_strategies_uses_all_when_backtest_has_no_coverage(monkeypatch):
    engine = _build_engine()
    await engine._select_active_strategies()
    assert engine.active_strategy_names == set(engine.strategies.keys())


@pytest.mark.asyncio
async def test_select_active_strategies_uses_all_when_backtest_is_flat(monkeypatch):
    engine = _build_engine()
    await engine._select_active_strategies()
    assert engine.active_strategy_names == set(engine.strategies.keys())


def test_passes_hourly_trade_limit_blocks_when_quota_is_reached(monkeypatch):
    monkeypatch.setattr(settings, "MAX_TRADES_PER_HOUR", 1)
    engine = _build_engine()
    engine.trade_timestamps.append(datetime.utcnow())
    signal = TradingSignal(
        symbol="BTC-USD",
        action="BUY",
        confidence=0.9,
        price=100.0,
        strategy="momentum",
        stop_loss=95.0,
        take_profit=120.0,
    )
    assert engine._passes_hourly_trade_limit(signal) is False


def test_passes_hourly_trade_limit_cleans_stale_entries(monkeypatch):
    monkeypatch.setattr(settings, "MAX_TRADES_PER_HOUR", 1)
    engine = _build_engine()
    engine.trade_timestamps.append(datetime.utcnow() - timedelta(hours=2))
    signal = TradingSignal(
        symbol="ETH-USD",
        action="BUY",
        confidence=0.9,
        price=100.0,
        strategy="momentum",
        stop_loss=95.0,
        take_profit=120.0,
    )
    assert engine._passes_hourly_trade_limit(signal) is True


@pytest.mark.asyncio
async def test_execute_trade_caps_buy_notional(monkeypatch):
    monkeypatch.setattr(settings, "ADVANCED_ENTRY_FILTER_ENABLED", False)
    monkeypatch.setattr(settings, "ENTRY_FILTER_MIN_EXPECTED_EDGE", 0.0)
    monkeypatch.setattr(settings, "ENTRY_FILTER_MIN_RR", 0.0)
    monkeypatch.setattr(settings, "MAX_BUY_NOTIONAL_USD", 1.0)

    engine = _build_engine()
    signal = TradingSignal(
        symbol="MICRO-USD",
        action="BUY",
        confidence=0.9,
        price=0.0002,
        quantity=20000.0,  # would be $4.00 without cap
        strategy="momentum",
        stop_loss=0.00019,
        take_profit=0.00022,
    )
    result = await engine._execute_trade(signal)
    assert result is not None
    assert engine.portfolio_manager.last_trade_data is not None
    notional = engine.portfolio_manager.last_trade_data["quantity"] * signal.price
    assert notional <= 1.0 + 1e-9
