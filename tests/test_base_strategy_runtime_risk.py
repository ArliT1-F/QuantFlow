from typing import Optional, Dict, Any

from app.core.config import settings
from app.strategies.base_strategy import BaseStrategy, Signal


class DummyStrategy(BaseStrategy):
    async def generate_signal(self, symbol: str, data: Dict[str, Any]) -> Optional[Signal]:
        return None


def test_stop_loss_and_take_profit_use_runtime_settings(monkeypatch):
    strategy = DummyStrategy()
    monkeypatch.setattr(settings, "STOP_LOSS_PERCENTAGE", 0.1)
    monkeypatch.setattr(settings, "TAKE_PROFIT_PERCENTAGE", 0.2)

    buy_stop = strategy.calculate_stop_loss(price=100, action="BUY")
    buy_take = strategy.calculate_take_profit(price=100, action="BUY")

    assert buy_stop == 90.0
    assert buy_take == 120.0
