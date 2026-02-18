import pytest

from app.services.risk_manager import RiskManager
from app.strategies.base_strategy import Signal


class DummyPortfolioManager:
    def __init__(self):
        self.total_value = 1000.0
        self.cash_balance = 1000.0
        self.positions = {
            "BTC-USD": {"quantity": 2.0, "current_price": 100.0}
        }
        self.portfolio_id = 1


@pytest.mark.asyncio
async def test_check_risk_limits_blocks_on_daily_loss():
    pm = DummyPortfolioManager()
    rm = RiskManager(portfolio_manager=pm)
    rm.daily_pnl = -60.0
    rm.risk_limits.max_daily_loss = 0.05

    ok, reason = await rm.check_risk_limits()
    assert not ok
    assert "daily loss limit exceeded" in reason


@pytest.mark.asyncio
async def test_sell_signal_uses_existing_position_size():
    pm = DummyPortfolioManager()
    rm = RiskManager(portfolio_manager=pm)
    signal = Signal(
        symbol="BTC-USD",
        action="SELL",
        confidence=1.0,
        price=100.0,
        stop_loss=105.0,
        take_profit=95.0,
        metadata={},
    )
    size = await rm.calculate_position_size(signal)
    assert size == 2.0


@pytest.mark.asyncio
async def test_buy_position_size_is_capped_by_available_cash():
    pm = DummyPortfolioManager()
    pm.cash_balance = 19.75
    rm = RiskManager(portfolio_manager=pm)
    rm.risk_limits.max_position_size = 0.2
    signal = Signal(
        symbol="TEST-USD",
        action="BUY",
        confidence=0.9,
        price=0.5,
        stop_loss=0.46,
        take_profit=0.55,
        metadata={},
    )
    size = await rm.calculate_position_size(signal)
    assert size > 0
    assert (size * signal.price) <= pm.cash_balance


@pytest.mark.asyncio
async def test_buy_position_size_respects_fixed_trade_notional(monkeypatch):
    monkeypatch.setattr("app.services.risk_manager.settings.FIXED_TRADE_NOTIONAL_USD", 1.0)
    monkeypatch.setattr("app.services.risk_manager.settings.MIN_POSITION_NOTIONAL", 1.0)
    pm = DummyPortfolioManager()
    rm = RiskManager(portfolio_manager=pm)
    signal = Signal(
        symbol="TEST-USD",
        action="BUY",
        confidence=0.9,
        price=2.0,
        stop_loss=1.5,
        take_profit=2.4,
        metadata={},
    )
    size = await rm.calculate_position_size(signal)
    assert size == pytest.approx(0.5, rel=1e-6)


@pytest.mark.asyncio
async def test_fixed_notional_is_not_forced_up_by_min_notional(monkeypatch):
    monkeypatch.setattr("app.services.risk_manager.settings.FIXED_TRADE_NOTIONAL_USD", 1.0)
    monkeypatch.setattr("app.services.risk_manager.settings.MIN_POSITION_NOTIONAL", 10.0)
    pm = DummyPortfolioManager()
    rm = RiskManager(portfolio_manager=pm)
    signal = Signal(
        symbol="TEST-USD",
        action="BUY",
        confidence=0.9,
        price=2.0,
        stop_loss=1.5,
        take_profit=2.4,
        metadata={},
    )
    size = await rm.calculate_position_size(signal)
    assert size == pytest.approx(0.5, rel=1e-6)
