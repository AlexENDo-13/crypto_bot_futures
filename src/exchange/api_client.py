"""
BingX API Client v9.1 (FIXED)
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
    def __init__(self, api_key: str = "", api_secret: str = "",
                 base_url: str = "https://open-api.bingx.com", testnet: bool = True, pool_size: int = 10):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.testnet = testnet
        self.logger = logging.getLogger("CryptoBot.API")
        self._session: Optional[aiohttp.ClientSession] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._connector_kwargs = {
            "limit": pool_size * 2, "limit_per_host": pool_size,
            "enable_cleanup_closed": True, "force_close": False
        }
        self._timeout = aiohttp.ClientTimeout(total=15, connect=5)
        self._symbol_specs: Dict[str, dict] = {}

    async def _get_or_create_session(self) -> aiohttp.ClientSession:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(**self._connector_kwargs)
            self._session = aiohttp.ClientSession(
                connector=connector, timeout=self._timeout, headers={"Accept": "application/json"}
            )
        return self._session

    async def _close_session(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _generate_signature(self, params: dict) -> str:
        query_string = urllib.parse.urlencode(sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def _request(self, method: str, endpoint: str, params: Optional[dict] = None, signed: bool = False) -> dict:
        if not self.api_key and signed:
            return {"code": -1, "msg": "API key required for signed request"}
        url = f"{self.base_url}{endpoint}"
        query_params = params.copy() if params else {}
        if signed:
            query_params["timestamp"] = str(int(time.time() * 1000))
            query_params["signature"] = self._generate_signature(query_params)
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

    async def get_klines(self, symbol: str, interval: str = "15m", limit: int = 100,
                         start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict[str, Any]]:
        endpoint = "/openApi/swap/v3/quote/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time: params["startTime"] = start_time
        if end_time: params["endTime"] = end_time
        response = await self._request("GET", endpoint, params, signed=False)
        if response.get("code") == 0 and "data" in response:
            return response["data"]
        return []

    async def get_ticker(self, symbol: str) -> dict:
        endpoint = "/openApi/swap/v3/quote/ticker"
        params = {"symbol": symbol}
        response = await self._request("GET", endpoint, params, signed=False)
        if response.get("code") == 0 and "data" in response:
            return response["data"]
        return {}

    async def get_orderbook(self, symbol: str, limit: int = 20) -> dict:
        endpoint = "/openApi/swap/v3/quote/depth"
        params = {"symbol": symbol, "limit": limit}
        response = await self._request("GET", endpoint, params, signed=False)
        if response.get("code") == 0 and "data" in response:
            return response["data"]
        return {}

    async def get_tickers_batch(self) -> dict:
        endpoint = "/openApi/swap/v3/quote/ticker"
        response = await self._request("GET", endpoint, {}, signed=False)
        if response.get("code") == 0 and "data" in response:
            data = response["data"]
            result = {}
            for item in data if isinstance(data, list) else [data]:
                sym = item.get("symbol", "")
                if sym: result[sym] = item
            return result
        return {}

    async def get_symbol_info(self) -> dict:
        endpoint = "/openApi/swap/v3/quote/contracts"
        response = await self._request("GET", endpoint, signed=False)
        if response.get("code") == 0 and "data" in response:
            for item in response.get("data", []):
                sym = item.get("symbol", "")
                if sym: self._symbol_specs[sym] = item
            return response
        return response

    def get_symbol_specs(self, symbol: str) -> Optional[dict]:
        return self._symbol_specs.get(symbol)

    async def get_account_balance(self) -> dict:
        endpoint = "/openApi/swap/v3/account/balance"
        response = await self._request("GET", endpoint, signed=True)
        self.logger.info(f"Balance API response: {response}")
        if response.get("code") == 0 and "data" in response:
            data = response["data"]
            self.logger.info(f"Balance data: {data}")
            return data
        self.logger.warning(f"Balance fetch failed: {response.get('msg', 'Unknown')}")
        return {}

    async def get_account_info(self) -> dict:
        return await self.get_account_balance()

    async def get_positions(self, symbol: Optional[str] = None) -> list:
        endpoint = "/openApi/swap/v3/user/positions"
        params = {}
        if symbol: params["symbol"] = symbol
        response = await self._request("GET", endpoint, params, signed=True)
        if response.get("code") == 0 and "data" in response:
            data = response["data"]
            if isinstance(data, dict) and "positions" in data:
                return data["positions"]
            return data if isinstance(data, list) else []
        return []

    async def set_leverage(self, symbol: str, leverage: int, position_side: str = "BOTH") -> dict:
        endpoint = "/openApi/swap/v3/trade/leverage"
        params = {"symbol": symbol, "leverage": leverage, "positionSide": position_side}
        response = await self._request("POST", endpoint, params, signed=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Set leverage failed: {response.get('msg')}")
        return response

    async def set_margin_mode(self, symbol: str, margin_mode: str) -> dict:
        endpoint = "/openApi/swap/v3/trade/marginMode"
        params = {"symbol": symbol, "marginMode": margin_mode}
        response = await self._request("POST", endpoint, params, signed=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Set margin mode failed: {response.get('msg')}")
        return response

    async def place_order(self, symbol: str, side: str, position_side: str,
                          order_type: str, quantity: float, price: Optional[float] = None) -> dict:
        endpoint = "/openApi/swap/v3/trade/order"
        params = {"symbol": symbol, "side": side, "positionSide": position_side,
                  "type": order_type, "quantity": quantity}
        if order_type.upper() == "LIMIT" and price:
            params["price"] = price
            params["timeInForce"] = "GTC"
        response = await self._request("POST", endpoint, params, signed=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Order failed: {response.get('msg')}")
        return {"error": True, "msg": response.get("msg", "Unknown"), "code": response.get("code", -1)}

    async def place_stop_order(self, symbol: str, side: str, stop_price: float,
                               order_type: str = "STOP_MARKET", position_side: str = "BOTH",
                               close_position: bool = True, quantity: Optional[float] = None) -> dict:
        endpoint = "/openApi/swap/v3/trade/order"
        params = {"symbol": symbol, "side": side, "positionSide": position_side,
                  "type": order_type, "stopPrice": stop_price,
                  "closePosition": "true" if close_position else "false"}
        if quantity is not None and not close_position:
            params["quantity"] = quantity
        response = await self._request("POST", endpoint, params, signed=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Stop order failed: {response.get('msg')}")
        return {"error": True, "msg": response.get("msg", "Unknown"), "code": response.get("code", -1)}

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

    async def close_position(self, symbol: str, position_side: str) -> dict:
        side = "SELL" if position_side == "LONG" else "BUY"
        endpoint = "/openApi/swap/v3/trade/order"
        params = {"symbol": symbol, "side": side, "positionSide": position_side,
                  "type": "MARKET", "closePosition": "true"}
        response = await self._request("POST", endpoint, params, signed=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Close position failed: {response.get('msg')}")
        return {"error": True, "msg": response.get("msg", "Unknown"), "code": response.get("code", -1)}

    async def close(self):
        self.logger.info("Closing API client...")
        await self._close_session()
        if self._loop and self._loop.is_running():
            self._loop.stop()
            self._loop = None
