"""
BingX API Client v9.0
Asynchronous REST client with robust event-loop handling.
"""
import asyncio
import hashlib
import hmac
import time
import urllib.parse
import logging
from typing import Dict, List, Optional, Any

import aiohttp


class BingXAPIClient:
    """
    Async client for BingX perpetual futures.
    Handles all HTTP requests, authentication and response parsing.
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        base_url: str = "https://open-api.bingx.com",
        testnet: bool = True,
        pool_size: int = 10
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.testnet = testnet
        self.logger = logging.getLogger("CryptoBot.API")

        self._session: Optional[aiohttp.ClientSession] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._connector_kwargs = {
            "limit": pool_size * 2,
            "limit_per_host": pool_size,
            "enable_cleanup_closed": True,
            "force_close": False
        }
        self._timeout = aiohttp.ClientTimeout(total=15, connect=5)

    # ------------------------------------------------------------------
    # Core request infrastructure
    # ------------------------------------------------------------------
    async def _get_or_create_session(self) -> aiohttp.ClientSession:
        """Return an active session tied to a running event loop."""
        try:
            # Проверяем, запущен ли цикл
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # Если цикл отсутствует, создаём новый и устанавливаем как текущий
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop

        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(**self._connector_kwargs)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=self._timeout,
                headers={"Accept": "application/json"}
            )
        return self._session

    async def _close_session(self):
        """Safely close the internal session."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    def _generate_signature(self, params: dict) -> str:
        """Generate HMAC-SHA256 signature for authenticated endpoints."""
        query_string = urllib.parse.urlencode(sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        signed: bool = False
    ) -> dict:
        """
        Perform an HTTP request with automatic retry on event-loop errors.
        """
        if not self.api_key and signed:
            return {"code": -1, "msg": "API key required for signed request"}

        # Build full URL
        url = f"{self.base_url}{endpoint}"

        # Prepare query parameters
        query_params = params.copy() if params else {}
        if signed:
            # For BingX, timestamp in milliseconds is mandatory
            query_params["timestamp"] = str(int(time.time() * 1000))
            signature = self._generate_signature(query_params)
            query_params["signature"] = signature
            # API key is sometimes passed as a parameter or header; here as parameter per BingX docs
            query_params["apiKey"] = self.api_key

        try:
            session = await self._get_or_create_session()
            if method.upper() == "GET":
                async with session.get(url, params=query_params) as response:
                    return await response.json(content_type=None)
            elif method.upper() == "POST":
                async with session.post(url, json=query_params) as response:
                    return await response.json(content_type=None)
            elif method.upper() == "DELETE":
                async with session.delete(url, params=query_params) as response:
                    return await response.json(content_type=None)
            else:
                return {"code": -1, "msg": f"Unsupported method {method}"}
        except RuntimeError as e:
            if "Event loop is closed" in str(e) or "no running event loop" in str(e):
                self.logger.debug(f"Event loop error, resetting and retrying: {e}")
                # Явно сбрасываем сессию и создаём новый цикл
                await self._close_session()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._loop = loop
                return await self._request(method, endpoint, params, signed)
            self.logger.warning(f"Request failed: {e}")
            return {"code": -1, "msg": str(e)}
        except Exception as e:
            self.logger.warning(f"Request error: {e}")
            return {"code": -1, "msg": str(e)}

    # ------------------------------------------------------------------
    # Public API methods (Market Data)
    # ------------------------------------------------------------------
    async def get_klines(
        self,
        symbol: str,
        interval: str = "15m",
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch kline/candlestick data.
        Returns list of OHLCV candles.
        """
        endpoint = "/openApi/swap/v3/quote/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        response = await self._request("GET", endpoint, params, signed=False)
        if response.get("code") == 0 and "data" in response:
            # Standard OHLCV format
            return response["data"]
        else:
            self.logger.warning(f"Klines error for {symbol}: {response.get('msg', 'Unknown')}")
            return []

    async def get_ticker(self, symbol: str) -> dict:
        """Get 24hr ticker price change statistics."""
        endpoint = "/openApi/swap/v3/quote/ticker"
        params = {"symbol": symbol}
        response = await self._request("GET", endpoint, params, signed=False)
        if response.get("code") == 0 and "data" in response:
            return response["data"]
        return {}

    async def get_orderbook(self, symbol: str, limit: int = 20) -> dict:
        """Get orderbook depth."""
        endpoint = "/openApi/swap/v3/quote/depth"
        params = {"symbol": symbol, "limit": limit}
        response = await self._request("GET", endpoint, params, signed=False)
        if response.get("code") == 0 and "data" in response:
            return response["data"]
        return {}

    # ------------------------------------------------------------------
    # Account / Trading methods (signed)
    # ------------------------------------------------------------------
    async def get_account_balance(self) -> dict:
        """Fetch USDT balance and positions."""
        endpoint = "/openApi/swap/v3/account/balance"
        response = await self._request("GET", endpoint, signed=True)
        if response.get("code") == 0 and "data" in response:
            return response["data"]
        return {}

    async def place_order(
        self, symbol: str, side: str, position_side: str,
        order_type: str, quantity: float, price: Optional[float] = None
    ) -> dict:
        """Place a futures order."""
        endpoint = "/openApi/swap/v3/trade/order"
        params = {
            "symbol": symbol,
            "side": side,            # BUY or SELL
            "positionSide": position_side,  # LONG or SHORT
            "type": order_type,      # MARKET, LIMIT, etc.
            "quantity": quantity
        }
        if order_type.upper() == "LIMIT" and price:
            params["price"] = price
            params["timeInForce"] = "GTC"
        response = await self._request("POST", endpoint, params, signed=True)
        if response.get("code") == 0:
            return response.get("data", {})
        else:
            self.logger.error(f"Order failed: {response.get('msg')}")
            return {}

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        endpoint = "/openApi/swap/v3/trade/order"
        params = {"symbol": symbol, "orderId": order_id}
        response = await self._request("DELETE", endpoint, params, signed=True)
        return response.get("code") == 0

    async def get_open_orders(self, symbol: str) -> list:
        endpoint = "/openApi/swap/v3/trade/openOrders"
        params = {"symbol": symbol}
        response = await self._request("GET", endpoint, params, signed=True)
        if response.get("code") == 0 and "data" in response:
            return response["data"].get("orders", [])
        return []

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    async def close(self):
        """Close the client session and stop the loop if necessary."""
        self.logger.info("Closing API client...")
        await self._close_session()
        if self._loop and self._loop.is_running():
            self._loop.stop()
        self._loop = None
