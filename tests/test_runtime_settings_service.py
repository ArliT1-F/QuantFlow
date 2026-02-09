import pytest

from app.services.runtime_settings_service import RuntimeSettingsService


def test_validate_payload_accepts_valid_percentages():
    service = RuntimeSettingsService()
    payload = {
        "max_position_size_percent": 10,
        "stop_loss_percent": 5,
        "take_profit_percent": 15,
    }
    parsed = service._validate_payload(payload)
    assert parsed["max_position_size_percent"] == 10.0
    assert parsed["stop_loss_percent"] == 5.0
    assert parsed["take_profit_percent"] == 15.0


@pytest.mark.parametrize(
    "payload",
    [
        {"max_position_size_percent": 0, "stop_loss_percent": 5, "take_profit_percent": 15},
        {"max_position_size_percent": 10, "stop_loss_percent": -1, "take_profit_percent": 15},
        {"max_position_size_percent": 10, "stop_loss_percent": 5, "take_profit_percent": 101},
    ],
)
def test_validate_payload_rejects_invalid_ranges(payload):
    service = RuntimeSettingsService()
    with pytest.raises(ValueError):
        service._validate_payload(payload)


def test_to_percent_response_converts_decimal_values():
    service = RuntimeSettingsService()
    response = service.to_percent_response(
        {
            service.MAX_POSITION_SIZE_KEY: 0.2,
            service.STOP_LOSS_PERCENTAGE_KEY: 0.08,
            service.TAKE_PROFIT_PERCENTAGE_KEY: 0.15,
        }
    )
    assert response["max_position_size_percent"] == 20.0
    assert response["stop_loss_percent"] == 8.0
    assert response["take_profit_percent"] == 15.0
