"""
CryptoBot v9.0 - BingX API Client
Fixed signature generation for GET and POST
"""
import time
import hmac
import hashlib
import asyncio
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode
import logging

try:
    import aiohttp
    AIOHTTP_OK = True
except ImportError:
    AIOHTTP_OK = False

class BingXAPIClient:
    def __init__(self, api_key: str = "", api_secret: str = "",
                 base_url: str = "https://open-api.bingx.com",
                 testnet: bool = True, pool_size: int = 10):
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.base_url = base_url.rstrip("/")
        self.testnet = testnet
        self.logger = logging.getLogger("CryptoBot.API")
        self._time_offset: int = 0
        self._min_interval: float = 0.05
        self._last_request_time: float = 0.0
        self._session: Optional[aiohttp.ClientSession] = None
        self._health_status = {"ok": True, "last_error": None, "failures": 0}
        has_key = "YES" if self.api_key else "NO"
        self.logger.info("BingXAPIClient v9.0 | base=%s api_key=%s", self.base_url, has_key)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=20, limit_per_host=10, enable_cleanup_closed=True, force_close=False)
            timeout = aiohttp.ClientTimeout(total=15, connect=5)
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout, headers={"Accept": "application/json"})
        return self._session

    @property
    def is_healthy(self) -> bool:
        return self._health_status["ok"] and self._health_status["failures"] < 5

    def _generate_signature(self, query_string: str) -> str:
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    async def _rate_limit(self):
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    async def _request(self, method: str, endpoint: str, params: Dict = None, signed: bool = False) -> Dict:
        if not AIOHTTP_OK:
            return {"code": -1, "msg": "aiohttp not installed"}
        params = params or {}
        # Add timestamp for all requests
        params["timestamp"] = str(int(time.time() * 1000) + self._time_offset)
        params["recvWindow"] = "5000"
        # Generate signature BEFORE any URL encoding
        if signed:
            if not self.api_secret:
                return {"code": -1, "msg": "API Secret empty"}
            query_string = urlencode(sorted(params.items()))
            params["signature"] = self._generate_signature(query_string)
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-BX-APIKEY"] = self.api_key
        try:
            await self._rate_limit()
            session = await self._get_session()
            if method.upper() == "GET":
                # Build full URL with query string manually to ensure correct encoding
                query_string = urlencode(sorted(params.items()))
                full_url = "%s%s?%s" % (self.base_url, endpoint, query_string)
                async with session.get(full_url, headers=headers) as resp:
                    data = await resp.json()
            else:
                url = "%s%s" % (self.base_url, endpoint)
                async with session.post(url, data=params, headers=headers) as resp:
                    data = await resp.json()
            code = data.get("code")
            if code not in (0, None, 200):
                self.logger.warning("API error %s: %s", code, data.get("msg", ""))
            return data
        except aiohttp.client_exceptions.ClientConnectorError as e:
            return {"code": -1, "msg": "Connection error: %s" % e}
        except asyncio.TimeoutError:
            return {"code": -1, "msg": "Request timeout"}
        except Exception as e:
            return {"code": -1, "msg": "Request failed: %s" % e}

    async def get_server_time(self) -> Dict:
        return await self._request("GET", "/openApi/swap/v2/server/time")

    async def get_symbols(self) -> List[Dict]:
        data = await self._request("GET", "/openApi/swap/v2/quote/contracts")
        if data.get("code") == 0:
            return data.get("data", [])
        return []

    async def get_ticker(self, symbol: str = "") -> Dict:
        params = {"symbol": symbol} if symbol else {}
        return await self._request("GET", "/openApi/swap/v2/quote/ticker", params)

    async def get_tickers_batch(self) -> Dict[str, Dict]:
        data = await self._request("GET", "/openApi/swap/v2/quote/ticker")
        if data.get("code") == 0:
            tickers = data.get("data", [])
            return {t.get("symbol", ""): t for t in tickers if t.get("symbol")}
        return {}

    async def get_klines(self, symbol: str, interval: str = "15m", limit: int = 100) -> List[List]:
        data = await self._request("GET", "/openApi/swap/v3/quote/klines",
                                    {"symbol": symbol, "interval": interval, "limit": str(limit)})
        if data.get("code") == 0:
            result = data.get("data")
            if isinstance(result, list):
                return result
            self.logger.warning("Klines data is not a list for %s: %s", symbol, type(result).__name__)
            return []
        self.logger.warning("Klines error for %s: %s", symbol, data.get("msg", "unknown"))
        return []

    async def get_funding_rate(self, symbol: str) -> Dict:
        return await self._request("GET", "/openApi/swap/v2/quote/premiumIndex", {"symbol": symbol})

    async def get_balance(self) -> Dict:
        result = await self._request("GET", "/openApi/swap/v3/user/balance", signed=True)
        if result.get("code") == 0:
            data = result.get("data", {})
            if isinstance(data, list) and len(data) > 0:
                for asset in data:
                    if asset.get("asset", "").upper() in ("USDT", "USDC", ""):
                        return {"code": 0, "data": {"balance": float(asset.get("balance", 0)), "available": float(asset.get("available", asset.get("free", 0))), "margin": float(asset.get("margin", 0)), "asset": asset.get("asset", "USDT")}}
                asset = data[0]
                return {"code": 0, "data": {"balance": float(asset.get("balance", 0)), "available": float(asset.get("available", asset.get("free", 0))), "margin": float(asset.get("margin", 0)), "asset": asset.get("asset", "USDT")}}
            elif isinstance(data, dict):
                return result
        return result

    async def place_order(self, symbol: str, side: str, position_side: str,
                          order_type: str = "MARKET", quantity: float = 0,
                          price: float = 0, stop_price: float = 0,
                          leverage: int = 1) -> Dict:
        params = {"symbol": symbol, "side": side, "positionSide": position_side, "type": order_type, "leverage": str(leverage)}
        if quantity > 0:
            params["quantity"] = str(quantity)
        if price > 0:
            params["price"] = str(price)
        if stop_price > 0:
            params["stopPrice"] = str(stop_price)
        return await self._request("POST", "/openApi/swap/v2/trade/order", params, signed=True)

    async def get_positions(self, symbol: str = "") -> List[Dict]:
        params = {"symbol": symbol} if symbol else {}
        data = await self._request("GET", "/openApi/swap/v2/user/positions", params, signed=True)
        if data.get("code") == 0:
            return data.get("data", [])
        return []

    async def close_position(self, symbol: str, position_side: str, quantity: float) -> Dict:
        return await self.place_order(
            symbol=symbol, side="SELL" if position_side == "LONG" else "BUY",
            position_side=position_side, order_type="MARKET", quantity=quantity
        )

    async def set_leverage(self, symbol: str, leverage: int, position_side: str = "LONG") -> Dict:
        return await self._request("POST", "/openApi/swap/v2/trade/leverage",
                                    {"symbol": symbol, "leverage": str(leverage), "positionSide": position_side}, signed=True)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
