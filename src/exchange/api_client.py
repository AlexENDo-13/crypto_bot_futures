"""
BingX API Client v18.8 — FINAL FIX:
- POST params in URL query string (body=None)
- set_leverage uses 'side' param
- quantity/stopPrice/price as NUMBER in params dict
- _build_signed_payload converts to str only for signing
- closePosition as string "true"/"false"
- No Content-Type header (not needed for empty body)
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
        self.api_key = api_key.strip() if api_key else ""
        self.api_secret = api_secret.strip() if api_secret else ""
        self.base_url = base_url.rstrip("/")
        self.testnet = testnet
        self.logger = logging.getLogger("CryptoBot.API")
        self._session: Optional[aiohttp.ClientSession] = None
        self._symbol_specs: Dict[str, dict] = {}
        self._connector_kwargs = {
            "limit": pool_size * 2, "limit_per_host": pool_size,
            "enable_cleanup_closed": True, "force_close": False
        }
        self._timeout = aiohttp.ClientTimeout(total=20, connect=8)
        self._consecutive_errors = 0
        self._total_requests = 0
        self._circuit_open = False
        self._circuit_open_time = 0
        self._circuit_recovery_after = 30
        self._last_request_time = 0
        self._adaptive_interval = 0.05
        self._recv_window = 5000

    def update_credentials(self, api_key: str, api_secret: str):
        old_key = self.api_key
        self.api_key = api_key.strip() if api_key else ""
        self.api_secret = api_secret.strip() if api_secret else ""
        self.logger.info(f"API credentials updated (key changed: {old_key != self.api_key})")
        self._circuit_open = False
        self._consecutive_errors = 0
        if self._session and not self._session.closed:
            asyncio.create_task(self._close_session())
        self._session = None

    async def _get_or_create_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(**self._connector_kwargs)
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["X-BX-APIKEY"] = self.api_key
                self.logger.info(f"Session created with X-BX-APIKEY: {self.api_key[:8]}...")
            else:
                self.logger.warning("Session created WITHOUT api_key!")
            self._session = aiohttp.ClientSession(
                connector=connector, timeout=self._timeout, headers=headers
            )
        return self._session

    async def _close_session(self):
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    def _build_signed_payload(self, params: Optional[dict] = None) -> dict:
        """Build payload with timestamp and recvWindow. All values as strings for signing."""
        payload = {}
        if params:
            for k, v in params.items():
                if v is not None:
                    payload[k] = str(v)
        payload["timestamp"] = str(int(time.time() * 1000))
        payload["recvWindow"] = str(self._recv_window)
        return payload

    def _sign_payload(self, payload: dict) -> str:
        """Create HMAC SHA256 signature from sorted payload."""
        sorted_items = sorted(payload.items(), key=lambda x: x[0])
        query_string = urllib.parse.urlencode(sorted_items)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature, query_string

    async def _request(self, method: str, endpoint: str, params: Optional[dict] = None,
                       signed: bool = False, retries: int = 3) -> dict:
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._adaptive_interval:
            await asyncio.sleep(self._adaptive_interval - elapsed)
        self._last_request_time = time.time()

        if self._circuit_open:
            if now - self._circuit_open_time > self._circuit_recovery_after:
                self.logger.info("Circuit breaker: attempting recovery")
                self._circuit_open = False
                self._consecutive_errors = 0
            else:
                return {"code": -1, "msg": "Circuit breaker open"}

        if signed and (not self.api_key or not self.api_secret):
            return {"code": -1, "msg": "API key and secret required for signed request"}

        last_error = None
        for attempt in range(retries):
            try:
                session = await self._get_or_create_session()

                if method.upper() == "GET":
                    if signed:
                        payload = self._build_signed_payload(params)
                        signature, query_string = self._sign_payload(payload)
                        full_url = f"{self.base_url}{endpoint}?{query_string}&signature={signature}"
                        self.logger.debug(f"GET {full_url[:120]}...")
                        async with session.get(full_url, timeout=self._timeout) as response:
                            text = await response.text()
                            try:
                                data = await response.json(content_type=None)
                            except:
                                data = {"code": -1, "msg": f"Invalid JSON: {text[:200]}"}
                    else:
                        url = f"{self.base_url}{endpoint}"
                        async with session.get(url, params=params, timeout=self._timeout) as response:
                            text = await response.text()
                            try:
                                data = await response.json(content_type=None)
                            except:
                                data = {"code": -1, "msg": f"Invalid JSON: {text[:200]}"}

                elif method.upper() == "POST":
                    if signed:
                        payload = self._build_signed_payload(params)
                        signature, query_string = self._sign_payload(payload)
                        full_url = f"{self.base_url}{endpoint}?{query_string}&signature={signature}"
                        self.logger.debug(f"POST {full_url[:120]}...")
                        async with session.post(full_url, timeout=self._timeout) as response:
                            text = await response.text()
                            try:
                                data = await response.json(content_type=None)
                            except:
                                data = {"code": -1, "msg": f"Invalid JSON: {text[:200]}"}
                    else:
                        url = f"{self.base_url}{endpoint}"
                        async with session.post(url, params=params, timeout=self._timeout) as response:
                            text = await response.text()
                            try:
                                data = await response.json(content_type=None)
                            except:
                                data = {"code": -1, "msg": f"Invalid JSON: {text[:200]}"}

                elif method.upper() == "DELETE":
                    if signed:
                        payload = self._build_signed_payload(params)
                        signature, query_string = self._sign_payload(payload)
                        full_url = f"{self.base_url}{endpoint}?{query_string}&signature={signature}"
                        async with session.delete(full_url, timeout=self._timeout) as response:
                            text = await response.text()
                            try:
                                data = await response.json(content_type=None)
                            except:
                                data = {"code": -1, "msg": f"Invalid JSON: {text[:200]}"}
                    else:
                        url = f"{self.base_url}{endpoint}"
                        async with session.delete(url, params=params, timeout=self._timeout) as response:
                            text = await response.text()
                            try:
                                data = await response.json(content_type=None)
                            except:
                                data = {"code": -1, "msg": f"Invalid JSON: {text[:200]}"}
                else:
                    return {"code": -1, "msg": f"Unsupported method {method}"}

                self._total_requests += 1
                msg = str(data.get("msg", "")).lower()
                code = data.get("code", data.get("status", -1))

                self.logger.debug(f"API {method} {endpoint} -> code={code}")

                if code == 100400 or "api is not exist" in msg:
                    last_error = data
                    self.logger.warning(f"Endpoint {endpoint} not found (100400)")
                    break

                if code == 100412:
                    last_error = data
                    self._consecutive_errors += 1
                    self.logger.error(f"BingX 100412 error on {endpoint}: {data.get('msg')}")
                    await asyncio.sleep(2 ** attempt)
                    continue

                if code == 100001 or ("signature" in msg and "mismatch" in msg):
                    last_error = data
                    self._consecutive_errors += 1
                    self.logger.error(f"SIGNATURE MISMATCH on {endpoint}! Attempt {attempt+1}/{retries}")
                    self.logger.error(f"Response: {data}")
                    self.logger.error(f"api_key present: {bool(self.api_key)}, secret_len: {len(self.api_secret)}")
                    debug_payload = self._build_signed_payload(params)
                    _, debug_qs = self._sign_payload(debug_payload)
                    self.logger.error(f"Signed query string: {debug_qs}")
                    self.logger.error(f"Base URL: {self.base_url}")
                    await self._close_session()
                    await asyncio.sleep(2 ** attempt)
                    continue

                if "null apikey" in msg or "unable to find api key" in msg:
                    last_error = data
                    self._consecutive_errors += 1
                    self.logger.error(f"API KEY NOT IN HEADER!")
                    await self._close_session()
                    await asyncio.sleep(1)
                    continue

                if "timestamp" in msg and ("invalid" in msg or "window" in msg):
                    last_error = data
                    self._consecutive_errors += 1
                    self.logger.error(f"TIMESTAMP ERROR: {data.get('msg')}")
                    await asyncio.sleep(1)
                    continue

                if code == 0 or code == 200 or code == "0":
                    self._consecutive_errors = 0
                    self._adaptive_interval = max(0.02, self._adaptive_interval * 0.95)
                    return data

                last_error = data
                self._consecutive_errors += 1

                if self._consecutive_errors >= 10:
                    self.logger.critical("Circuit breaker OPEN")
                    self._circuit_open = True
                    self._circuit_open_time = time.time()
                    return {"code": -1, "msg": "Circuit breaker open"}

                backoff = (2 ** attempt) + 0.5
                self.logger.warning(f"API error (attempt {attempt+1}/{retries}): {data.get('msg')}, backoff {backoff:.1f}s")
                await asyncio.sleep(backoff)

            except asyncio.TimeoutError:
                last_error = {"code": -1, "msg": f"Timeout on {endpoint}"}
                self._consecutive_errors += 1
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                last_error = {"code": -1, "msg": str(e)}
                self._consecutive_errors += 1
                await asyncio.sleep(2 ** attempt)

        self._adaptive_interval = min(2.0, self._adaptive_interval * 1.5)
        return last_error or {"code": -1, "msg": "All retries failed"}

    # ==================== PUBLIC API ====================
    async def get_klines(self, symbol: str, interval: str = "15m", limit: int = 100,
                         start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        response = await self._request("GET", "/openApi/swap/v2/quote/klines", params, signed=False)
        if response.get("code") == 0 and "data" in response:
            return response["data"]
        return []

    async def get_ticker(self, symbol: str) -> dict:
        response = await self._request("GET", "/openApi/swap/v2/quote/ticker", {"symbol": symbol}, signed=False)
        if response.get("code") == 0 and "data" in response:
            data = response["data"]
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            return data
        return {}

    async def get_tickers_batch(self) -> dict:
        response = await self._request("GET", "/openApi/swap/v2/quote/ticker", {}, signed=False)
        if response.get("code") == 0 and "data" in response:
            data = response["data"]
            result = {}
            for item in data if isinstance(data, list) else [data]:
                sym = item.get("symbol", "")
                if sym:
                    result[sym] = item
            return result
        return {}

    async def get_symbol_info(self) -> dict:
        response = await self._request("GET", "/openApi/swap/v2/quote/contracts", {}, signed=False)
        self.logger.info(f"Symbol info response code: {response.get('code')}")
        if response.get("code") == 0 and "data" in response:
            for item in response.get("data", []):
                sym = item.get("symbol", "")
                if sym:
                    self._symbol_specs[sym] = item
            return response
        return response

    def get_symbol_specs(self, symbol: str) -> Optional[dict]:
        return self._symbol_specs.get(symbol)

    # ==================== PRIVATE API ====================
    async def get_account_balance(self) -> dict:
        response = await self._request("GET", "/openApi/swap/v2/user/balance", {}, signed=True)
        self.logger.info(f"Balance response: {response}")
        if response.get("code") == 0 and "data" in response:
            data = response["data"]
            if isinstance(data, dict):
                if "balance" in data and isinstance(data["balance"], dict):
                    return data["balance"]
                return data
        return {}

    async def get_account_info(self) -> dict:
        return await self.get_account_balance()

    async def get_positions(self, symbol: Optional[str] = None) -> list:
        params = {}
        if symbol:
            params["symbol"] = symbol
        response = await self._request("GET", "/openApi/swap/v2/user/positions", params, signed=True)
        if response.get("code") == 0 and "data" in response:
            data = response["data"]
            if isinstance(data, dict) and "positions" in data:
                return data["positions"]
            return data if isinstance(data, list) else []
        return []

    async def set_leverage(self, symbol: str, leverage: int, side: str = "BOTH") -> dict:
        """Set leverage. 'side' must be BOTH (one-way) or LONG/SHORT (hedge mode)."""
        params = {"symbol": symbol, "leverage": leverage, "side": side}
        response = await self._request("POST", "/openApi/swap/v2/trade/leverage", params, signed=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Set leverage failed: {response.get('msg')}")
        return response

    async def set_margin_mode(self, symbol: str, margin_mode: str) -> dict:
        self.logger.debug(f"Margin mode skipped (not available on v2)")
        return {"code": 0}

    async def place_order(self, symbol: str, side: str, position_side: str,
                          order_type: str, quantity: float, price: Optional[float] = None) -> dict:
        # quantity as NUMBER per BingX swap v2 spec
        params = {
            "symbol": symbol,
            "side": side,
            "positionSide": position_side,
            "type": order_type,
            "quantity": quantity
        }
        if order_type.upper() == "LIMIT" and price:
            params["price"] = price
            params["timeInForce"] = "GTC"
        self.logger.info(f"Placing order: {params}")
        response = await self._request("POST", "/openApi/swap/v2/trade/order", params, signed=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Order failed: {response.get('msg')}")
        return {"error": True, "msg": response.get("msg", "Unknown"), "code": response.get("code", -1)}

    async def place_stop_order(self, symbol: str, side: str, stop_price: float,
                               order_type: str = "STOP_MARKET", position_side: str = "BOTH",
                               close_position: bool = True, quantity: Optional[float] = None) -> dict:
        params = {
            "symbol": symbol,
            "side": side,
            "positionSide": position_side,
            "type": order_type,
            "stopPrice": stop_price,
            "closePosition": "true" if close_position else "false"
        }
        if quantity is not None and not close_position:
            params["quantity"] = quantity
        response = await self._request("POST", "/openApi/swap/v2/trade/order", params, signed=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Stop order failed: {response.get('msg')}")
        return {"error": True, "msg": response.get("msg", "Unknown"), "code": response.get("code", -1)}

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        params = {"symbol": symbol, "orderId": order_id}
        response = await self._request("DELETE", "/openApi/swap/v2/trade/order", params, signed=True)
        return response.get("code") == 0

    async def cancel_all_orders(self, symbol: Optional[str] = None) -> bool:
        params = {}
        if symbol:
            params["symbol"] = symbol
        response = await self._request("DELETE", "/openApi/swap/v2/trade/allOpenOrders", params, signed=True)
        return response.get("code") == 0

    async def get_open_orders(self, symbol: str) -> list:
        params = {"symbol": symbol}
        response = await self._request("GET", "/openApi/swap/v2/trade/openOrders", params, signed=True)
        if response.get("code") == 0 and "data" in response:
            return response["data"].get("orders", [])
        return []

    async def close_position(self, symbol: str, position_side: str, quantity: str = "0") -> dict:
        side = "SELL" if position_side == "LONG" else "BUY"
        qty_num = float(quantity) if quantity else 0.0
        params = {
            "symbol": symbol,
            "side": side,
            "positionSide": position_side,
            "type": "MARKET",
            "quantity": qty_num,
            "closePosition": "true" if quantity == "0" else "false"
        }
        response = await self._request("POST", "/openApi/swap/v2/trade/order", params, signed=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Close position failed: {response.get('msg')}")
        return {"error": True, "msg": response.get("msg", "Unknown"), "code": response.get("code", -1)}

    async def close(self):
        self.logger.info("Closing API client...")
        await self._close_session()

    def get_health(self) -> dict:
        return {
            "consecutive_errors": self._consecutive_errors,
            "total_requests": self._total_requests,
            "circuit_open": self._circuit_open,
            "adaptive_interval": self._adaptive_interval,
        }
