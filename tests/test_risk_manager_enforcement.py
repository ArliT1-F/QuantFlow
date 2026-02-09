import pytest

from app.services.risk_manager import RiskManager
from app.strategies.base_strategy import Signal


class DummyPortfolioManager:
    def __init__(self):
        self.total_value = 1000.0
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
