"""
BingX API Client v12.0 - ULTIMATE FIX
Based on CCXT working implementation [^35^] and old BingX demo [^39^]:
Signature = HMAC_SHA256(secret, method + path + query_string)
where query_string = urlencode(sorted(params))
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
        self.api_key = api_key
        self.api_secret = api_secret
        self.logger.info("API credentials updated")
        self._circuit_open = False
        self._consecutive_errors = 0
        if self._session and not self._session.closed:
            asyncio.create_task(self._close_session())

    async def _get_or_create_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(**self._connector_kwargs)
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            if self.api_key:
                headers["X-BX-APIKEY"] = self.api_key
            self._session = aiohttp.ClientSession(
                connector=connector, timeout=self._timeout, headers=headers
            )
        return self._session

    async def _close_session(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _generate_signature_v1(self, method: str, path: str, params: dict) -> str:
        """
        OLD BingX signature format (works for v1/v2 endpoints):
        signature = HMAC_SHA256(secret, method + path + query_string)
        From CCXT [^35^] and old demo [^39^]
        """
        sorted_params = sorted(params.items())
        query_string = urllib.parse.urlencode(sorted_params)

        origin_string = f"{method.upper()}{path}{query_string}"

        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            origin_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        self.logger.debug(f"V1 signing: {method.upper()}{path}... -> sig={signature[:16]}...")
        return signature

    def _generate_signature_v2(self, params: dict) -> str:
        """
        NEW BingX signature format (works for v3 endpoints):
        signature = HMAC_SHA256(secret, query_string)
        From official docs [^36^]
        """
        sorted_params = sorted(params.items())
        query_string = urllib.parse.urlencode(sorted_params)

        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        self.logger.debug(f"V2 signing: {query_string[:80]}... -> sig={signature[:16]}...")
        return signature

    async def _request(self, method: str, endpoint: str, params: Optional[dict] = None,
                       signed: bool = False, use_v1_sig: bool = False, retries: int = 3) -> dict:
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

        url = f"{self.base_url}{endpoint}"
        query_params = params.copy() if params else {}

        if signed:
            timestamp = str(int(time.time() * 1000))
            query_params["timestamp"] = timestamp
            query_params["apiKey"] = self.api_key
            query_params["recvWindow"] = str(self._recv_window)

            if use_v1_sig:
                query_params["signature"] = self._generate_signature_v1(method, endpoint, query_params)
            else:
                query_params["signature"] = self._generate_signature_v2(query_params)

        last_error = None
        for attempt in range(retries):
            try:
                session = await self._get_or_create_session()

                if method.upper() == "GET":
                    async with session.get(url, params=query_params, timeout=self._timeout) as response:
                        text = await response.text()
                        try:
                            data = await response.json(content_type=None)
                        except:
                            data = {"code": -1, "msg": f"Invalid JSON: {text[:200]}"}
                elif method.upper() == "POST":
                    async with session.post(url, params=query_params, timeout=self._timeout) as response:
                        text = await response.text()
                        try:
                            data = await response.json(content_type=None)
                        except:
                            data = {"code": -1, "msg": f"Invalid JSON: {text[:200]}"}
                elif method.upper() == "DELETE":
                    async with session.delete(url, params=query_params, timeout=self._timeout) as response:
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

                if code == 100400 or "api is not exist" in msg:
                    last_error = data
                    self.logger.warning(f"Endpoint {endpoint} not found (100400)")
                    break

                if code == 100001 or ("signature" in msg and "mismatch" in msg):
                    last_error = data
                    self._consecutive_errors += 1
                    self.logger.error(f"SIGNATURE MISMATCH on {endpoint}! Attempt {attempt+1}/{retries}")
                    self.logger.error(f"Full response: {data}")
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
        if start_time: params["startTime"] = start_time
        if end_time: params["endTime"] = end_time
        response = await self._request("GET", "/openApi/swap/v3/quote/klines", params, signed=False)
        if response.get("code") == 0 and "data" in response:
            return response["data"]
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
                if sym: result[sym] = item
            return result
        return {}

    async def get_symbol_info(self) -> dict:
        response = await self._request("GET", "/openApi/swap/v2/quote/contracts", {}, signed=False)
        self.logger.info(f"Symbol info response code: {response.get('code')}")
        if response.get("code") == 0 and "data" in response:
            for item in response.get("data", []):
                sym = item.get("symbol", "")
                if sym: self._symbol_specs[sym] = item
            return response
        return response

    def get_symbol_specs(self, symbol: str) -> Optional[dict]:
        return self._symbol_specs.get(symbol)

    # ==================== PRIVATE API - try v1 signature first, then v2 ====================
    async def get_account_balance(self) -> dict:
        """Query account balance - try v1 signature (method+path+query) first"""
        # Try v1 signature format (old BingX style)
        response = await self._request("GET", "/openApi/swap/v2/user/balance", {}, signed=True, use_v1_sig=True)
        self.logger.info(f"Balance v1 response: {response}")
        if response.get("code") == 0 and "data" in response:
            return response["data"]

        # Try v2 signature format (query_string only)
        response = await self._request("GET", "/openApi/swap/v2/user/balance", {}, signed=True, use_v1_sig=False)
        self.logger.info(f"Balance v2 response: {response}")
        if response.get("code") == 0 and "data" in response:
            return response["data"]

        # Try v3 endpoint with v2 signature
        response = await self._request("GET", "/openApi/swap/v3/user/balance", {}, signed=True, use_v1_sig=False)
        self.logger.info(f"Balance v3 response: {response}")
        if response.get("code") == 0 and "data" in response:
            return response["data"]

        return {}

    async def get_account_info(self) -> dict:
        return await self.get_account_balance()

    async def get_positions(self, symbol: Optional[str] = None) -> list:
        params = {}
        if symbol: params["symbol"] = symbol
        # Try v1 signature
        response = await self._request("GET", "/openApi/swap/v2/user/positions", params, signed=True, use_v1_sig=True)
        if response.get("code") == 0 and "data" in response:
            data = response["data"]
            if isinstance(data, dict) and "positions" in data:
                return data["positions"]
            return data if isinstance(data, list) else []

        # Try v2 signature
        response = await self._request("GET", "/openApi/swap/v2/user/positions", params, signed=True, use_v1_sig=False)
        if response.get("code") == 0 and "data" in response:
            data = response["data"]
            if isinstance(data, dict) and "positions" in data:
                return data["positions"]
            return data if isinstance(data, list) else []
        return []

    async def set_leverage(self, symbol: str, leverage: int, position_side: str = "BOTH") -> dict:
        params = {"symbol": symbol, "leverage": leverage, "positionSide": position_side}
        response = await self._request("POST", "/openApi/swap/v2/trade/leverage", params, signed=True, use_v1_sig=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Set leverage failed: {response.get('msg')}")
        return response

    async def set_margin_mode(self, symbol: str, margin_mode: str) -> dict:
        params = {"symbol": symbol, "marginMode": margin_mode}
        response = await self._request("POST", "/openApi/swap/v2/trade/marginMode", params, signed=True, use_v1_sig=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Set margin mode failed: {response.get('msg')}")
        return response

    async def place_order(self, symbol: str, side: str, position_side: str,
                          order_type: str, quantity: float, price: Optional[float] = None) -> dict:
        params = {"symbol": symbol, "side": side, "positionSide": position_side,
                  "type": order_type, "quantity": quantity}
        if order_type.upper() == "LIMIT" and price:
            params["price"] = price
            params["timeInForce"] = "GTC"
        response = await self._request("POST", "/openApi/swap/v2/trade/order", params, signed=True, use_v1_sig=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Order failed: {response.get('msg')}")
        return {"error": True, "msg": response.get("msg", "Unknown"), "code": response.get("code", -1)}

    async def place_stop_order(self, symbol: str, side: str, stop_price: float,
                               order_type: str = "STOP_MARKET", position_side: str = "BOTH",
                               close_position: bool = True, quantity: Optional[float] = None) -> dict:
        params = {"symbol": symbol, "side": side, "positionSide": position_side,
                  "type": order_type, "stopPrice": stop_price,
                  "closePosition": "true" if close_position else "false"}
        if quantity is not None and not close_position:
            params["quantity"] = quantity
        response = await self._request("POST", "/openApi/swap/v2/trade/order", params, signed=True, use_v1_sig=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Stop order failed: {response.get('msg')}")
        return {"error": True, "msg": response.get("msg", "Unknown"), "code": response.get("code", -1)}

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        params = {"symbol": symbol, "orderId": order_id}
        response = await self._request("DELETE", "/openApi/swap/v2/trade/order", params, signed=True, use_v1_sig=True)
        return response.get("code") == 0

    async def cancel_all_orders(self, symbol: Optional[str] = None) -> bool:
        params = {}
        if symbol:
            params["symbol"] = symbol
        response = await self._request("DELETE", "/openApi/swap/v2/trade/allOpenOrders", params, signed=True, use_v1_sig=True)
        return response.get("code") == 0

    async def get_open_orders(self, symbol: str) -> list:
        params = {"symbol": symbol}
        response = await self._request("GET", "/openApi/swap/v2/trade/openOrders", params, signed=True, use_v1_sig=True)
        if response.get("code") == 0 and "data" in response:
            return response["data"].get("orders", [])
        return []

    async def close_position(self, symbol: str, position_side: str) -> dict:
        side = "SELL" if position_side == "LONG" else "BUY"
        params = {"symbol": symbol, "side": side, "positionSide": position_side,
                  "type": "MARKET", "closePosition": "true"}
        response = await self._request("POST", "/openApi/swap/v2/trade/order", params, signed=True, use_v1_sig=True)
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
