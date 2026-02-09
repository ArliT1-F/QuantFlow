from datetime import datetime

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
