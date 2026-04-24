"""
CryptoBot v7.1 - BingX API Client
"""
import time
import hmac
import hashlib
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode
import logging

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False


class BingXAPIClient:
    """BingX Futures API Client v7.1"""

    def __init__(self, api_key: str = "", api_secret: str = "",
                 base_url: str = "https://open-api.bingx.com",
                 testnet: bool = True, pool_size: int = 10):
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.base_url = base_url.rstrip("/")
        self.testnet = testnet
        self.logger = logging.getLogger("CryptoBot.API")

        self.session = None
        if REQUESTS_OK:
            self.session = requests.Session()
            retry = Retry(
                total=3, backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504, 429]
            )
            adapter = HTTPAdapter(
                max_retries=retry,
                pool_connections=pool_size,
                pool_maxsize=pool_size
            )
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)

        has_key = "YES" if self.api_key else "NO"
        self.logger.info("BingXAPIClient v7.1 | base=%s api_key=%s", self.base_url, has_key)

    def update_credentials(self, api_key: str, api_secret: str):
        """Update API credentials without recreating client."""
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.logger.info("API credentials updated | key=%s", "YES" if self.api_key else "NO")

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature for BingX API."""
        query_string = urlencode(sorted(params.items()))
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def _request(self, method: str, endpoint: str, params: Dict = None,
                 signed: bool = False, retries: int = 3) -> Dict:
        if not REQUESTS_OK:
            return {"code": -1, "msg": "requests not installed"}

        url = "%s%s" % (self.base_url, endpoint)
        params = params or {}
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 5000

        if signed:
            if not self.api_secret:
                return {"code": -1, "msg": "API Secret empty"}
            params["signature"] = self._generate_signature(params)

        headers = {}
        if self.api_key:
            headers["X-BX-APIKEY"] = self.api_key

        last_error = None
        for attempt in range(retries):
            try:
                if method.upper() == "GET":
                    resp = self.session.get(url, params=params, headers=headers, timeout=15)
                else:
                    resp = self.session.post(url, json=params, headers=headers, timeout=15)

                resp.raise_for_status()
                data = resp.json()

                # Handle specific BingX error codes
                code = data.get("code")
                if code in (100412, 100001):
                    self.logger.warning("BingX error %s: %s, retrying...", code, data.get("msg", ""))
                    time.sleep(0.5 * (attempt + 1))
                    continue

                if code not in (0, None, 200):
                    self.logger.warning("API error %s: %s", code, data.get("msg", ""))

                return data
            except requests.exceptions.Timeout:
                last_error = "timeout"
                time.sleep(0.5 * (attempt + 1))
            except requests.exceptions.ConnectionError:
                last_error = "connection_error"
                time.sleep(0.5 * (attempt + 1))
            except Exception as e:
                last_error = str(e)
                time.sleep(0.5 * (attempt + 1))

        return {"code": -1, "msg": "%s after %d retries" % (last_error, retries)}

    def get_server_time(self) -> Dict:
        return self._request("GET", "/openApi/swap/v2/server/time")

    def get_symbols(self) -> List[Dict]:
        data = self._request("GET", "/openApi/swap/v2/quote/contracts")
        if data.get("code") == 0:
            return data.get("data", [])
        return []

    def get_ticker(self, symbol: str) -> Dict:
        return self._request("GET", "/openApi/swap/v2/quote/ticker", {"symbol": symbol})

    def get_klines(self, symbol: str, interval: str = "15m", limit: int = 100) -> List[List]:
        data = self._request("GET", "/openApi/swap/v3/quote/klines", {
            "symbol": symbol, "interval": interval, "limit": limit
        })
        if data.get("code") == 0:
            return data.get("data", [])
        return []

    def get_balance(self) -> Dict:
        result = self._request("GET", "/openApi/swap/v3/user/balance", signed=True)
        if result.get("code") == 0:
            data = result.get("data", {})
            if isinstance(data, list) and len(data) > 0:
                for asset in data:
                    if asset.get("asset", "").upper() in ("USDT", "USDC", ""):
                        return {
                            "code": 0,
                            "data": {
                                "balance": float(asset.get("balance", 0)),
                                "available": float(asset.get("available", asset.get("free", 0))),
                                "margin": float(asset.get("margin", 0)),
                                "asset": asset.get("asset", "USDT")
                            }
                        }
                asset = data[0]
                return {
                    "code": 0,
                    "data": {
                        "balance": float(asset.get("balance", 0)),
                        "available": float(asset.get("available", asset.get("free", 0))),
                        "margin": float(asset.get("margin", 0)),
                        "asset": asset.get("asset", "USDT")
                    }
                }
            elif isinstance(data, dict):
                return result
        return result

    def place_order(self, symbol: str, side: str, position_side: str,
                    order_type: str = "MARKET", quantity: float = 0,
                    price: float = 0, stop_price: float = 0,
                    leverage: int = 1) -> Dict:
        params = {
            "symbol": symbol,
            "side": side,
            "positionSide": position_side,
            "type": order_type,
            "leverage": leverage
        }
        if quantity > 0:
            params["quantity"] = quantity
        if price > 0:
            params["price"] = price
        if stop_price > 0:
            params["stopPrice"] = stop_price
        return self._request("POST", "/openApi/swap/v2/trade/order", params, signed=True)

    def get_positions(self, symbol: str = "") -> List[Dict]:
        params = {}
        if symbol:
            params["symbol"] = symbol
        data = self._request("GET", "/openApi/swap/v2/user/positions", params, signed=True)
        if data.get("code") == 0:
            return data.get("data", [])
        return []

    def close_position(self, symbol: str, position_side: str) -> Dict:
        return self.place_order(
            symbol=symbol,
            side="SELL" if position_side == "LONG" else "BUY",
            position_side=position_side,
            order_type="MARKET"
        )
