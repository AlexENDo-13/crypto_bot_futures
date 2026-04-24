"""
CryptoBot v6.0 - BingX API Client
Robust API client with retry logic and error handling.
"""
import time
import hmac
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode
import logging

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class BingXAPIClient:
    """BingX Futures API Client v6.0."""

    def __init__(self, api_key: str = "", api_secret: str = "", 
                 base_url: str = "https://open-api.bingx.com", 
                 testnet: bool = True, pool_size: int = 10):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.testnet = testnet
        self.logger = logging.getLogger("CryptoBot.API")

        self.session = None
        if REQUESTS_AVAILABLE:
            self.session = requests.Session()
            retry = Retry(total=3, backoff_factor=0.5, 
                         status_forcelist=[500, 502, 503, 504, 429])
            adapter = HTTPAdapter(max_retries=retry, pool_connections=pool_size, 
                                 pool_maxsize=pool_size)
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)

        self.logger.info(f"BingXAPIClient v6.0 | base={self.base_url} pool={pool_size}")

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature."""
        query_string = urlencode(sorted(params.items()))
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def _request(self, method: str, endpoint: str, params: Dict = None, 
                 signed: bool = False) -> Dict:
        """Make API request with error handling."""
        if not REQUESTS_AVAILABLE:
            return {"code": -1, "msg": "requests library not installed"}

        url = f"{self.base_url}{endpoint}"
        params = params or {}
        params["timestamp"] = int(time.time() * 1000)

        if signed and self.api_secret:
            params["signature"] = self._generate_signature(params)

        headers = {}
        if self.api_key:
            headers["X-BX-APIKEY"] = self.api_key

        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params, headers=headers, timeout=10)
            else:
                response = self.session.post(url, json=params, headers=headers, timeout=10)

            response.raise_for_status()
            data = response.json()

            if data.get("code") not in (0, None, 200):
                self.logger.warning(f"API error {data.get('code')}: {data.get('msg')}")

            return data

        except requests.exceptions.Timeout:
            self.logger.error("API request timeout")
            return {"code": -1, "msg": "timeout"}
        except requests.exceptions.ConnectionError:
            self.logger.error("API connection error")
            return {"code": -1, "msg": "connection_error"}
        except Exception as e:
            self.logger.error(f"API request failed: {e}")
            return {"code": -1, "msg": str(e)}

    def get_server_time(self) -> Dict:
        """Get server time."""
        return self._request("GET", "/openApi/swap/v2/server/time")

    def get_symbols(self) -> List[Dict]:
        """Get all trading symbols."""
        data = self._request("GET", "/openApi/swap/v2/quote/contracts")
        if data.get("code") == 0:
            return data.get("data", [])
        return []

    def get_ticker(self, symbol: str) -> Dict:
        """Get 24h ticker data."""
        return self._request("GET", "/openApi/swap/v2/quote/ticker", 
                            {"symbol": symbol})

    def get_klines(self, symbol: str, interval: str = "15m", 
                   limit: int = 100) -> List[List]:
        """Get candlestick data."""
        data = self._request("GET", "/openApi/swap/v3/quote/klines", {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        })
        if data.get("code") == 0:
            return data.get("data", [])
        return []

    def get_balance(self) -> Dict:
        """Get account balance."""
        return self._request("GET", "/openApi/swap/v3/user/balance", signed=True)

    def place_order(self, symbol: str, side: str, position_side: str,
                    order_type: str = "MARKET", quantity: float = 0,
                    price: float = 0, stop_price: float = 0,
                    leverage: int = 1) -> Dict:
        """Place an order."""
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

        return self._request("POST", "/openApi/swap/v2/trade/order", 
                            params, signed=True)

    def get_positions(self, symbol: str = "") -> List[Dict]:
        """Get open positions."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        data = self._request("GET", "/openApi/swap/v2/user/positions", 
                            params, signed=True)
        if data.get("code") == 0:
            return data.get("data", [])
        return []

    def close_position(self, symbol: str, position_side: str) -> Dict:
        """Close a position."""
        return self.place_order(
            symbol=symbol,
            side="SELL" if position_side == "LONG" else "BUY",
            position_side=position_side,
            order_type="MARKET"
        )
