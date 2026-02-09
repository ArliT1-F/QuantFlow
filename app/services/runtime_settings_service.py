"""
Service for reading and updating persisted runtime settings.
"""
from typing import Dict, Any

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.runtime_setting import RuntimeSetting


class RuntimeSettingsService:
    """Persisted settings service."""

    MAX_POSITION_SIZE_KEY = "max_position_size"
    STOP_LOSS_PERCENTAGE_KEY = "stop_loss_percentage"
    TAKE_PROFIT_PERCENTAGE_KEY = "take_profit_percentage"

    SETTING_KEYS = (
        MAX_POSITION_SIZE_KEY,
        STOP_LOSS_PERCENTAGE_KEY,
        TAKE_PROFIT_PERCENTAGE_KEY,
    )

    def apply_persisted_settings(self, risk_manager=None) -> Dict[str, float]:
        """Load persisted values from DB and apply them to runtime settings."""
        runtime = self.get_trading_settings()
        self._apply_runtime_settings(runtime, risk_manager=risk_manager)
        return runtime

    def get_trading_settings(self) -> Dict[str, float]:
        """Return effective runtime settings (decimal form)."""
        defaults = {
            self.MAX_POSITION_SIZE_KEY: float(settings.MAX_POSITION_SIZE),
            self.STOP_LOSS_PERCENTAGE_KEY: float(settings.STOP_LOSS_PERCENTAGE),
            self.TAKE_PROFIT_PERCENTAGE_KEY: float(settings.TAKE_PROFIT_PERCENTAGE),
        }

        db = SessionLocal()
        try:
            rows = db.query(RuntimeSetting).filter(RuntimeSetting.key.in_(self.SETTING_KEYS)).all()
            for row in rows:
                defaults[row.key] = float(row.value)
            return defaults
        finally:
            db.close()

    def update_trading_settings(self, payload: Dict[str, Any], risk_manager=None) -> Dict[str, float]:
        """Persist provided percent values and apply them in-process."""
        parsed = self._validate_payload(payload)
        runtime = {
            self.MAX_POSITION_SIZE_KEY: parsed["max_position_size_percent"] / 100.0,
            self.STOP_LOSS_PERCENTAGE_KEY: parsed["stop_loss_percent"] / 100.0,
            self.TAKE_PROFIT_PERCENTAGE_KEY: parsed["take_profit_percent"] / 100.0,
        }

        db = SessionLocal()
        try:
            for key, value in runtime.items():
                row = db.query(RuntimeSetting).filter(RuntimeSetting.key == key).first()
                if row is None:
                    db.add(RuntimeSetting(key=key, value=value))
                else:
                    row.value = value
            db.commit()
        finally:
            db.close()

        self._apply_runtime_settings(runtime, risk_manager=risk_manager)
        return runtime

    def to_percent_response(self, runtime: Dict[str, float]) -> Dict[str, float]:
        """Convert decimal runtime values to percent values for UI."""
        return {
            "max_position_size_percent": round(runtime[self.MAX_POSITION_SIZE_KEY] * 100.0, 4),
            "stop_loss_percent": round(runtime[self.STOP_LOSS_PERCENTAGE_KEY] * 100.0, 4),
            "take_profit_percent": round(runtime[self.TAKE_PROFIT_PERCENTAGE_KEY] * 100.0, 4),
        }

    def _apply_runtime_settings(self, runtime: Dict[str, float], risk_manager=None):
        settings.MAX_POSITION_SIZE = runtime[self.MAX_POSITION_SIZE_KEY]
        settings.STOP_LOSS_PERCENTAGE = runtime[self.STOP_LOSS_PERCENTAGE_KEY]
        settings.TAKE_PROFIT_PERCENTAGE = runtime[self.TAKE_PROFIT_PERCENTAGE_KEY]
        if risk_manager is not None:
            risk_manager.update_risk_limits({"max_position_size": settings.MAX_POSITION_SIZE})

    def _validate_payload(self, payload: Dict[str, Any]) -> Dict[str, float]:
        required = ("max_position_size_percent", "stop_loss_percent", "take_profit_percent")
        missing = [k for k in required if k not in payload]
        if missing:
            raise ValueError(f"Missing settings keys: {', '.join(missing)}")

        max_position = float(payload["max_position_size_percent"])
        stop_loss = float(payload["stop_loss_percent"])
        take_profit = float(payload["take_profit_percent"])

        if max_position <= 0 or max_position > 100:
            raise ValueError("max_position_size_percent must be between 0 and 100")
        if stop_loss <= 0 or stop_loss > 100:
            raise ValueError("stop_loss_percent must be between 0 and 100")
        if take_profit <= 0 or take_profit > 100:
            raise ValueError("take_profit_percent must be between 0 and 100")

        return {
            "max_position_size_percent": max_position,
            "stop_loss_percent": stop_loss,
            "take_profit_percent": take_profit,
        }
