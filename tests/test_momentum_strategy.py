from datetime import datetime

import pytest

from app.strategies.momentum_strategy import MomentumStrategy


@pytest.mark.asyncio
async def test_momentum_strategy_generates_buy_for_moderate_move_with_volume():
    strategy = MomentumStrategy()
    history = []
    closes = [
        100.0,
        101.0, 100.234,
        101.234, 100.468,
        101.468, 100.702,
        101.702, 100.936,
        101.936, 101.17,
        102.17, 101.404,
        102.404, 103.404,
    ]
    for idx, close in enumerate(closes):
        history.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 100.0 if idx < len(closes) - 1 else 220.0,
            }
        )

    data = {
        "symbol": "BTC-USD",
        "price": closes[-1],
        "open": closes[-1],
        "high": closes[-1],
        "low": closes[-1],
        "volume": 220.0,
        "timestamp": datetime.utcnow().isoformat(),
        "history": history,
    }

    signal = await strategy.generate_signal("BTC-USD", data)
    assert signal is not None
    assert signal.action == "BUY"
    assert signal.confidence >= strategy.parameters["min_confidence"]


@pytest.mark.asyncio
async def test_momentum_strategy_uses_change_percent_during_short_history_bootstrap():
    strategy = MomentumStrategy()
    history = [
        {
            "timestamp": datetime.utcnow().isoformat(),
            "open": 10.0,
            "high": 10.0,
            "low": 10.0,
            "close": 10.0,
            "volume": 1000.0,
        },
        {
            "timestamp": datetime.utcnow().isoformat(),
            "open": 10.01,
            "high": 10.01,
            "low": 10.01,
            "close": 10.01,
            "volume": 1200.0,
        },
    ]

    data = {
        "symbol": "AVAX-USD",
        "price": 10.01,
        "open": 10.01,
        "high": 10.01,
        "low": 10.01,
        "volume": 1200.0,
        "change_percent": 0.9,
        "timestamp": datetime.utcnow().isoformat(),
        "history": history,
    }

    signal = await strategy.generate_signal("AVAX-USD", data)
    assert signal is not None
    assert signal.action == "BUY"
