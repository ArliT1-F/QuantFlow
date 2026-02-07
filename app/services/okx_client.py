"""
OKX REST API client (public market data + private trading)
"""
from typing import Any, Dict, Optional, List
from datetime import datetime
import base64
import hashlib
import hmac
import json
import requests


class OkxClient:
    def __init__(
        self,
        api_key: Optional[str],
        secret_key: Optional[str],
        passphrase: Optional[str],
        base_url: str = "https://www.okx.com",
        demo: bool = False
    ):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.base_url = base_url.rstrip("/")
        self.demo = demo

    def _timestamp(self) -> str:
        return datetime.utcnow().isoformat(timespec="milliseconds") + "Z"

    def _sign(self, timestamp: str, method: str, request_path: str, body: str) -> str:
        message = f"{timestamp}{method.upper()}{request_path}{body}"
        mac = hmac.new(self.secret_key.encode(), message.encode(), hashlib.sha256)
        return base64.b64encode(mac.digest()).decode()

    def _headers(self, signed: bool, timestamp: Optional[str] = None, signature: Optional[str] = None) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.demo:
            headers["x-simulated-trading"] = "1"
        if signed:
            headers.update({
                "OK-ACCESS-KEY": self.api_key or "",
                "OK-ACCESS-PASSPHRASE": self.passphrase or "",
                "OK-ACCESS-TIMESTAMP": timestamp or "",
                "OK-ACCESS-SIGN": signature or ""
            })
        return headers

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None, signed: bool = False) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        params = params or {}
        body = body or {}
        body_str = json.dumps(body) if body else ""

        headers = {}
        if signed:
            if not (self.api_key and self.secret_key and self.passphrase):
                raise RuntimeError("OKX API keys are required for private endpoints")
            ts = self._timestamp()
            sign = self._sign(ts, method, path, body_str)
            headers = self._headers(True, ts, sign)
        else:
            headers = self._headers(False)

        if method.upper() == "GET":
            response = requests.get(url, params=params, headers=headers, timeout=15)
        else:
            response = requests.post(url, params=params, data=body_str, headers=headers, timeout=15)

        response.raise_for_status()
        return response.json()

    def get_ticker(self, inst_id: str) -> Dict[str, Any]:
        data = self._request("GET", "/api/v5/market/ticker", params={"instId": inst_id})
        if data.get("code") != "0" or not data.get("data"):
            return {}
        return data["data"][0]

    def get_candles(self, inst_id: str, bar: str = "1D", limit: int = 90) -> List[Dict[str, Any]]:
        data = self._request("GET", "/api/v5/market/candles", params={"instId": inst_id, "bar": bar, "limit": str(limit)})
        if data.get("code") != "0" or not data.get("data"):
            return []
        candles = []
        for row in data["data"]:
            # [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
            candles.append({
                "timestamp": datetime.utcfromtimestamp(int(row[0]) / 1000).isoformat() + "Z",
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5])
            })
        return list(reversed(candles))

    def place_market_order(self, inst_id: str, side: str, size: str, td_mode: str = "cash") -> Dict[str, Any]:
        body = {
            "instId": inst_id,
            "tdMode": td_mode,
            "side": side,
            "ordType": "market",
            "sz": size
        }
        return self._request("POST", "/api/v5/trade/order", body=body, signed=True)
