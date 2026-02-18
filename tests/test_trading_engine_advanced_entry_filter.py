from app.core.config import settings
from app.services.trading_engine import TradingEngine, TradingSignal


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


def _signal(symbol: str, confidence: float, price: float, stop_loss: float, take_profit: float, closes):
    return TradingSignal(
        symbol=symbol,
        action="BUY",
        confidence=confidence,
        price=price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        strategy="momentum",
        metadata={"closes_by_symbol": {symbol: closes}},
    )


def test_advanced_edge_filter_rejects_high_volatility_low_edge(monkeypatch):
    monkeypatch.setattr(settings, "ADVANCED_ENTRY_FILTER_ENABLED", True)
    monkeypatch.setattr(settings, "ENTRY_FILTER_VOL_WINDOW", 20)
    monkeypatch.setattr(settings, "ENTRY_FILTER_VOL_MULTIPLIER", 0.75)
    monkeypatch.setattr(settings, "ENTRY_FILTER_MIN_EXPECTED_EDGE", 0.004)
    monkeypatch.setattr(settings, "ENTRY_FILTER_MIN_RR", 1.2)

    engine = _build_engine()
    signal = _signal(
        symbol="AVAX-USD",
        confidence=0.9,
        price=100.0,
        stop_loss=96.0,
        take_profit=106.0,
        closes=[100, 120, 90, 130, 85, 125, 80, 120, 75, 115, 78, 118],
    )
    assert engine._passes_edge_filter(signal) is False


def test_advanced_edge_filter_accepts_strong_trend_high_edge(monkeypatch):
    monkeypatch.setattr(settings, "ADVANCED_ENTRY_FILTER_ENABLED", True)
    monkeypatch.setattr(settings, "ENTRY_FILTER_MIN_HISTORY", 8)
    monkeypatch.setattr(settings, "ENTRY_FILTER_TREND_Z_MIN", 0.1)

    engine = _build_engine()
    signal = _signal(
        symbol="BTC-USD",
        confidence=0.9,
        price=110.0,
        stop_loss=103.0,
        take_profit=130.0,
        closes=[100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
    )
    assert engine._passes_edge_filter(signal) is True


def test_consolidation_caps_signals_per_cycle(monkeypatch):
    monkeypatch.setattr(settings, "MIN_SIGNAL_CONFIDENCE", 0.1)
    monkeypatch.setattr(settings, "MAX_SIGNALS_PER_CYCLE", 2)

    engine = _build_engine()
    signals = [
        TradingSignal(symbol="BTC-USD", action="BUY", confidence=0.95, price=100.0, stop_loss=95.0, take_profit=120.0, strategy="momentum"),
        TradingSignal(symbol="ETH-USD", action="BUY", confidence=0.85, price=100.0, stop_loss=95.0, take_profit=120.0, strategy="momentum"),
        TradingSignal(symbol="SOL-USD", action="BUY", confidence=0.75, price=100.0, stop_loss=95.0, take_profit=120.0, strategy="momentum"),
    ]
    consolidated = engine._consolidate_signals(signals)
    assert len(consolidated) == 2
    assert consolidated[0].confidence >= consolidated[1].confidence


def test_edge_filter_adapts_rr_floor_for_low_runtime_tp(monkeypatch):
    monkeypatch.setattr(settings, "ADVANCED_ENTRY_FILTER_ENABLED", True)
    monkeypatch.setattr(settings, "ENTRY_FILTER_MIN_RR", 1.2)
    monkeypatch.setattr(settings, "TAKE_PROFIT_PERCENTAGE", 0.01)
    monkeypatch.setattr(settings, "STOP_LOSS_PERCENTAGE", 0.08)

    engine = _build_engine()
    signal = _signal(
        symbol="DOGE-USD",
        confidence=0.85,
        price=100.0,
        stop_loss=92.0,
        take_profit=101.0,
        closes=[100.0, 100.2, 100.4, 100.6, 100.8, 101.0, 101.2, 101.4, 101.6],
    )
    assert engine._passes_edge_filter(signal) is True
