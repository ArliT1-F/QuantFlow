"""
Solana execution service with demo/live modes.
"""
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


class SolanaExecutionService:
    """Executes swap intents in demo or live mode."""

    def __init__(self):
        self.mode = str(getattr(settings, "SOLANA_TRADING_MODE", "demo") or "demo").strip().lower()

    def is_live(self) -> bool:
        return self.mode == "live"

    def execute(self, trade_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.is_live():
            return self._execute_live(trade_data)
        return self._execute_demo(trade_data)

    def _execute_demo(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        quantity = float(trade_data["quantity"])
        price = float(trade_data["price"])
        fees = quantity * price * 0.001
        return {
            "status": "FILLED",
            "execution_price": price,
            "fees": fees,
            "tx_signature": "",
            "execution_mode": "demo",
        }

    def _execute_live(self, trade_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        executor_url = str(getattr(settings, "SOLANA_EXECUTOR_URL", "") or "").strip()
        if not executor_url:
            logger.error("SOLANA_TRADING_MODE=live requires SOLANA_EXECUTOR_URL")
            return None

        request_id = str(trade_data.get("request_id") or uuid4())
        timeout_seconds = int(getattr(settings, "SOLANA_EXECUTOR_TIMEOUT_SECONDS", 20))
        max_retries = int(getattr(settings, "SOLANA_EXECUTOR_MAX_RETRIES", 2))
        backoff_seconds = float(getattr(settings, "SOLANA_EXECUTOR_BACKOFF_SECONDS", 0.4))
        require_auth = bool(getattr(settings, "SOLANA_EXECUTOR_REQUIRE_AUTH", True))
        auth_header_name = str(getattr(settings, "SOLANA_EXECUTOR_AUTH_HEADER", "X-Executor-Key") or "").strip()
        auth_api_key = str(getattr(settings, "SOLANA_EXECUTOR_API_KEY", "") or "").strip()

        if require_auth and (not auth_header_name or not auth_api_key):
            logger.error("Live Solana execution requires SOLANA_EXECUTOR_AUTH_HEADER and SOLANA_EXECUTOR_API_KEY")
            return None

        headers = {
            "Content-Type": "application/json",
            "X-Request-Id": request_id,
            "Idempotency-Key": request_id,
        }
        if auth_header_name and auth_api_key:
            headers[auth_header_name] = auth_api_key

        payload = {
            "symbol": trade_data["symbol"],
            "side": trade_data["side"],
            "quantity": float(trade_data["quantity"]),
            "price": float(trade_data["price"]),
            "notional_usd": float(trade_data["quantity"]) * float(trade_data["price"]),
            "chain": "solana",
            "base_token_address": str(trade_data.get("base_token_address") or "").strip(),
            "quote_token_address": str(
                trade_data.get("quote_token_address") or getattr(settings, "SOLANA_QUOTE_MINT", "")
            ).strip(),
            "pair_address": str(trade_data.get("pair_address") or "").strip(),
            "slippage_bps": int(getattr(settings, "SOLANA_SLIPPAGE_BPS", 100)),
            "wallet_public_key": str(getattr(settings, "SOLANA_WALLET_PUBLIC_KEY", "") or "").strip(),
            "client_order_id": request_id,
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        retryable_codes = {408, 409, 425, 429, 500, 502, 503, 504}
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    executor_url,
                    json=payload,
                    headers=headers,
                    timeout=timeout_seconds,
                )
                if response.status_code in retryable_codes and attempt < max_retries:
                    sleep_seconds = max(backoff_seconds, 0.0) * (2 ** attempt)
                    time.sleep(sleep_seconds)
                    continue

                response.raise_for_status()
                body = response.json() if response.content else {}
                if not bool(body.get("ok", True)):
                    logger.error("Solana executor rejected order: %s", body)
                    return None

                execution_price = float(body.get("filled_price") or payload["price"])
                fees = float(body.get("fees") or (payload["quantity"] * execution_price * 0.001))
                tx_signature = str(body.get("tx_signature") or body.get("signature") or "")
                return {
                    "status": "FILLED",
                    "execution_price": execution_price,
                    "fees": fees,
                    "tx_signature": tx_signature,
                    "execution_mode": "live",
                    "request_id": request_id,
                }
            except requests.RequestException as error:
                if attempt < max_retries:
                    sleep_seconds = max(backoff_seconds, 0.0) * (2 ** attempt)
                    time.sleep(sleep_seconds)
                    continue
                logger.error("Live Solana execution failed: %s", error)
                return None
            except Exception as error:
                logger.error("Live Solana execution failed: %s", error)
                return None
        return None
