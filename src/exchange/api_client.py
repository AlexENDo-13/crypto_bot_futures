"""
CryptoBot v9.0 - Async BingX API Client
Features: aiohttp async, WebSocket real-time, circuit breaker,
          connection pooling, automatic failover
"""
import time
import hmac
import hashlib
import asyncio
import json
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode
import logging

try:
    import aiohttp
    import aiohttp.client_exceptions
    AIOHTTP_OK = True
except ImportError:
    AIOHTTP_OK = False

try:
    import websockets
    WEBSOCKET_OK = True
except ImportError:
    WEBSOCKET_OK = False

class CircuitBreaker:
    """Circuit breaker pattern for API resilience."""
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half-open
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        async with self._lock:
            if self.state == "open":
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "half-open"
                else:
                    raise Exception("Circuit breaker OPEN")

        try:
            result = await func(*args, **kwargs)
            async with self._lock:
                if self.state == "half-open":
                    self.state = "closed"
                    self.failure_count = 0
            return result
        except Exception as e:
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
            raise e

class BingXAPIClient:
    """Async BingX Futures API Client v9.0"""

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
        self._circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        self._health_status = {"ok": True, "last_error": None, "failures": 0, "latency": 0}
        self._health_lock = asyncio.Lock()
        self._ws_task = None
        self._ws_prices: Dict[str, float] = {}
        self._ws_connected = False

        has_key = "YES" if self.api_key else "NO"
        self.logger.info("BingXAPIClient v9.0 | base=%s api_key=%s", self.base_url, has_key)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=20, limit_per_host=10,
                enable_cleanup_closed=True,
                force_close=False,
                ttl_dns_cache=300
            )
            timeout = aiohttp.ClientTimeout(total=15, connect=5)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={"Accept": "application/json"}
            )
        return self._session

    @property
    def is_healthy(self) -> bool:
        return self._health_status["ok"] and self._health_status["failures"] < 5

    async def _record_health(self, success: bool, error: str = None, latency: float = 0):
        async with self._health_lock:
            if success:
                self._health_status["ok"] = True
                self._health_status["failures"] = max(0, self._health_status["failures"] - 1)
                self._health_status["last_error"] = None
                self._health_status["latency"] = latency
            else:
                self._health_status["failures"] += 1
                self._health_status["last_error"] = error
                if self._health_status["failures"] >= 5:
                    self._health_status["ok"] = False

    async def _sync_server_time(self):
        try:
            resp = await self._request("GET", "/openApi/swap/v2/server/time", signed=False)
            if resp.get("code") == 0:
                server_time = resp.get("data", {}).get("serverTime", 0)
                if server_time:
                    self._time_offset = server_time - int(time.time() * 1000)
        except Exception as e:
            self.logger.warning("Time sync failed: %s", e)

    def update_credentials(self, api_key: str, api_secret: str):
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.logger.info("API credentials updated | key=%s", "YES" if self.api_key else "NO")

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        query_string = urlencode(sorted(params.items()))
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

    async def _request(self, method: str, endpoint: str, params: Dict = None,
                       signed: bool = False) -> Dict:
        if not AIOHTTP_OK:
            return {"code": -1, "msg": "aiohttp not installed"}

        url = "%s%s" % (self.base_url, endpoint)
        params = params or {}
        params["timestamp"] = int(time.time() * 1000) + self._time_offset
        params["recvWindow"] = 5000

        if signed:
            if not self.api_secret:
                return {"code": -1, "msg": "API Secret empty"}
            params["signature"] = self._generate_signature(params)

        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-BX-APIKEY"] = self.api_key

        start_time = time.time()
        try:
            await self._rate_limit()
            session = await self._get_session()

            if method.upper() == "GET":
                async with session.get(url, params=params, headers=headers) as resp:
                    data = await resp.json()
            else:
                async with session.post(url, data=params, headers=headers) as resp:
                    data = await resp.json()

            latency = time.time() - start_time
            code = data.get("code")
            if code not in (0, None, 200):
                self.logger.warning("API error %s: %s", code, data.get("msg", ""))

            await self._record_health(True, latency=latency)
            return data

        except aiohttp.client_exceptions.ClientConnectorError as e:
            await self._record_health(False, str(e))
            return {"code": -1, "msg": "Connection error: %s" % e}
        except asyncio.TimeoutError:
            await self._record_health(False, "timeout")
            return {"code": -1, "msg": "Request timeout"}
        except Exception as e:
            await self._record_health(False, str(e))
            return {"code": -1, "msg": "Request failed: %s" % e}

    async def get_server_time(self) -> Dict:
        return await self._circuit.call(self._request, "GET", "/openApi/swap/v2/server/time")

    async def get_symbols(self) -> List[Dict]:
        data = await self._circuit.call(self._request, "GET", "/openApi/swap/v2/quote/contracts")
        if data.get("code") == 0:
            return data.get("data", [])
        return []

    async def get_ticker(self, symbol: str = "") -> Dict:
        params = {"symbol": symbol} if symbol else {}
        return await self._circuit.call(self._request, "GET", "/openApi/swap/v2/quote/ticker", params)

    async def get_tickers_batch(self) -> Dict[str, Dict]:
        data = await self._circuit.call(self._request, "GET", "/openApi/swap/v2/quote/ticker")
        if data.get("code") == 0:
            tickers = data.get("data", [])
            return {t.get("symbol", ""): t for t in tickers if t.get("symbol")}
        return {}

    async def get_klines(self, symbol: str, interval: str = "15m", limit: int = 100) -> List[List]:
        data = await self._circuit.call(self._request, "GET", "/openApi/swap/v3/quote/klines",
                                        {"symbol": symbol, "interval": interval, "limit": limit})
        if data.get("code") == 0:
            result = data.get("data")
            if isinstance(result, list):
                return result
            return []
        return []

    async def get_funding_rate(self, symbol: str) -> Dict:
        return await self._circuit.call(self._request, "GET", "/openApi/swap/v2/quote/premiumIndex",
                                        {"symbol": symbol})

    async def get_balance(self) -> Dict:
        result = await self._circuit.call(self._request, "GET", "/openApi/swap/v3/user/balance", signed=True)
        if result.get("code") == 0:
            data = result.get("data", {})
            if isinstance(data, list) and len(data) > 0:
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
        return result

    async def place_order(self, symbol: str, side: str, position_side: str,
                          order_type: str = "MARKET", quantity: float = 0,
                          price: float = 0, stop_price: float = 0,
                          leverage: int = 1) -> Dict:
        params = {
            "symbol": symbol, "side": side, "positionSide": position_side,
            "type": order_type, "leverage": leverage
        }
        if quantity > 0:
            params["quantity"] = quantity
        if price > 0:
            params["price"] = price
        if stop_price > 0:
            params["stopPrice"] = stop_price
        return await self._circuit.call(self._request, "POST", "/openApi/swap/v2/trade/order", params, signed=True)

    async def get_positions(self, symbol: str = "") -> List[Dict]:
        params = {"symbol": symbol} if symbol else {}
        data = await self._circuit.call(self._request, "GET", "/openApi/swap/v2/user/positions", params, signed=True)
        if data.get("code") == 0:
            return data.get("data", [])
        return []

    async def close_position(self, symbol: str, position_side: str, quantity: float) -> Dict:
        return await self.place_order(
            symbol=symbol,
            side="SELL" if position_side == "LONG" else "BUY",
            position_side=position_side,
            order_type="MARKET",
            quantity=quantity
        )

    async def set_leverage(self, symbol: str, leverage: int, position_side: str = "LONG") -> Dict:
        return await self._circuit.call(self._request, "POST", "/openApi/swap/v2/trade/leverage",
                                        {"symbol": symbol, "leverage": leverage, "positionSide": position_side},
                                        signed=True)

    # --- WebSocket ---
    async def start_websocket(self, symbols: List[str]):
        if not WEBSOCKET_OK or not self.api_key:
            return
        self._ws_task = asyncio.create_task(self._ws_loop(symbols))

    async def _ws_loop(self, symbols: List[str]):
        ws_url = "wss://open-api-ws.bingx.com/market"
        while True:
            try:
                async with websockets.connect(ws_url) as ws:
                    self._ws_connected = True
                    self.logger.info("WebSocket connected")
                    # Subscribe to ticker streams
                    for sym in symbols[:10]:  # Limit to 10 for WS
                        sub_msg = {
                            "id": str(int(time.time() * 1000)),
                            "reqType": "sub",
                            "dataType": "%s@ticker" % sym.replace("-", "").lower()
                        }
                        await ws.send(json.dumps(sub_msg))

                    async for message in ws:
                        try:
                            data = json.loads(message)
                            if "data" in data:
                                tick = data["data"]
                                sym = tick.get("s", "").upper()
                                if sym:
                                    self._ws_prices[sym] = float(tick.get("c", 0))
                        except Exception:
                            pass
            except Exception as e:
                self.logger.warning("WebSocket error: %s, reconnecting...", e)
                self._ws_connected = False
                await asyncio.sleep(5)

    async def stop_websocket(self):
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

    async def close(self):
        await self.stop_websocket()
        if self._session and not self._session.closed:
            await self._session.close()
