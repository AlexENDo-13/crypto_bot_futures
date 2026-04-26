"""
BingX API Client v13.1 - PRODUCTION FIX
Based on verified BingX Futures API implementation:
- Signature = HMAC_SHA256(secret, query_string) where query_string = urlencode(sorted(params))
- apiKey ONLY in X-BX-APIKEY header, NEVER in query string or signature
- All requests use v2 endpoints
- All values passed as strings
- Empty body for POST requests
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
        """Update API credentials and FORCE recreate session with new headers"""
        old_key = self.api_key
        self.api_key = api_key.strip() if api_key else ""
        self.api_secret = api_secret.strip() if api_secret else ""
        self.logger.info(f"API credentials updated (key changed: {old_key != self.api_key})")
        self._circuit_open = False
        self._consecutive_errors = 0
        # CRITICAL: Force recreate session on next request
        if self._session and not self._session.closed:
            asyncio.create_task(self._close_session())
            self._session = None

    async def _get_or_create_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(**self._connector_kwargs)
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["X-BX-APIKEY"] = self.api_key
                self.logger.debug(f"Session created with X-BX-APIKEY: {self.api_key[:10]}...")
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

    def _generate_signature(self, params: dict) -> str:
        """
        BingX v2 signature format:
        signature = HMAC_SHA256(secret, query_string)
        where query_string = urlencode(sorted(params))
        CRITICAL: apiKey is NOT included in params for signing
        """
        str_params = {k: str(v) for k, v in sorted(params.items()) if k != "signature"}
        query_string = urllib.parse.urlencode(str_params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        self.logger.debug(f"Signing: {query_string[:80]}... -> sig={signature[:16]}...")
        return signature

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

        url = f"{self.base_url}{endpoint}"
        query_params = {}
        if params:
            query_params = {k: str(v) for k, v in params.items()}

        if signed:
            query_params["timestamp"] = str(int(time.time() * 1000))
            query_params["recvWindow"] = str(self._recv_window)
            query_params["signature"] = self._generate_signature(query_params)

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
                    self.logger.error(f"Full response: {data}")
                    self.logger.error(f"api_key present: {bool(self.api_key)}, api_secret present: {bool(self.api_secret)}")
                    # Force recreate session on signature error
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
        if start_time: params["startTime"] = start_time
        if end_time: params["endTime"] = end_time
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

    # ==================== PRIVATE API ====================
    async def get_account_balance(self) -> dict:
        """Query account balance using v2 endpoint with correct signature"""
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
        if symbol: params["symbol"] = symbol
        response = await self._request("GET", "/openApi/swap/v2/user/positions", params, signed=True)
        if response.get("code") == 0 and "data" in response:
            data = response["data"]
            if isinstance(data, dict) and "positions" in data:
                return data["positions"]
            return data if isinstance(data, list) else []
        return []

    async def set_leverage(self, symbol: str, leverage: int, position_side: str = "BOTH") -> dict:
        params = {"symbol": symbol, "leverage": leverage, "positionSide": position_side}
        response = await self._request("POST", "/openApi/swap/v2/trade/leverage", params, signed=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Set leverage failed: {response.get('msg')}")
        return response

    async def set_margin_mode(self, symbol: str, margin_mode: str) -> dict:
        params = {"symbol": symbol, "marginMode": margin_mode}
        response = await self._request("POST", "/openApi/swap/v2/trade/marginMode", params, signed=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Set margin mode failed: {response.get('msg')}")
        return response

    async def place_order(self, symbol: str, side: str, position_side: str,
                          order_type: str, quantity: float, price: Optional[float] = None) -> dict:
        params = {
            "symbol": symbol,
            "side": side,
            "positionSide": position_side,
            "type": order_type,
            "quantity": str(quantity)
        }
        if order_type.upper() == "LIMIT" and price:
            params["price"] = str(price)
            params["timeInForce"] = "GTC"
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
            "stopPrice": str(stop_price),
            "closePosition": "true" if close_position else "false"
        }
        if quantity is not None and not close_position:
            params["quantity"] = str(quantity)
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
        """
        Close position fully or partially via /trade/order with closePosition flag.
        quantity="0" closes entire position.
        """
        side = "SELL" if position_side == "LONG" else "BUY"
        params = {
            "symbol": symbol,
            "side": side,
            "positionSide": position_side,
            "type": "MARKET",
            "quantity": quantity,
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
