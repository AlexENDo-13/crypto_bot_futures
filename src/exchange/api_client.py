"""
BingX API Client v9.2 - Self-Healing Adaptive Client
Auto-detects correct endpoints, retries with backoff, never gives up.
"""
import asyncio
import hashlib
import hmac
import time
import random
import urllib.parse
import logging
from typing import Dict, List, Optional, Any

import aiohttp


class EndpointPool:
    """Pool of API endpoints with health tracking."""
    def __init__(self):
        self.endpoints = {
            "balance": [
                "/openApi/swap/v3/user/balance",
                "/openApi/swap/v2/user/balance",
                "/openApi/swap/v1/user/balance",
            ],
            "positions": [
                "/openApi/swap/v3/user/positions",
                "/openApi/swap/v2/user/positions",
            ],
            "klines": [
                "/openApi/swap/v3/quote/klines",
                "/openApi/swap/v2/quote/klines",
            ],
            "ticker": [
                "/openApi/swap/v3/quote/ticker",
                "/openApi/swap/v2/quote/ticker",
            ],
            "contracts": [
                "/openApi/swap/v3/quote/contracts",
                "/openApi/swap/v2/quote/contracts",
            ],
            "order": [
                "/openApi/swap/v3/trade/order",
                "/openApi/swap/v2/trade/order",
            ],
            "leverage": [
                "/openApi/swap/v3/trade/leverage",
                "/openApi/swap/v2/trade/leverage",
            ],
            "marginMode": [
                "/openApi/swap/v3/trade/marginMode",
                "/openApi/swap/v2/trade/marginMode",
            ],
            "openOrders": [
                "/openApi/swap/v3/trade/openOrders",
                "/openApi/swap/v2/trade/openOrders",
            ],
        }
        self._health = {k: {ep: {"ok": 0, "fail": 0, "last_used": 0} for ep in eps} 
                        for k, eps in self.endpoints.items()}
        self._preferred = {k: eps[0] for k, eps in self.endpoints.items()}

    def get(self, category: str) -> str:
        """Get best endpoint for category based on health."""
        eps = self.endpoints.get(category, [])
        if not eps:
            return ""
        # Sort by success rate
        scored = []
        for ep in eps:
            h = self._health[category][ep]
            total = h["ok"] + h["fail"]
            score = h["ok"] / max(total, 1)
            scored.append((score, ep))
        scored.sort(reverse=True)
        best = scored[0][1]
        self._health[category][best]["last_used"] = time.time()
        return best

    def report(self, category: str, endpoint: str, success: bool):
        if category in self._health and endpoint in self._health[category]:
            if success:
                self._health[category][endpoint]["ok"] += 1
            else:
                self._health[category][endpoint]["fail"] += 1

    def get_health_report(self) -> dict:
        return {k: {ep: dict(stats) for ep, stats in v.items()} 
                for k, v in self._health.items()}


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
        self._endpoints = EndpointPool()
        self._consecutive_errors = 0
        self._total_requests = 0
        self._error_rate = 0.0
        self._last_request_time = 0
        self._min_request_interval = 0.05  # 50ms between requests
        self._adaptive_interval = 0.05
        self._circuit_open = False
        self._circuit_open_time = 0
        self._circuit_recovery_after = 30  # seconds

    def update_credentials(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.logger.info("API credentials updated")

    async def _get_or_create_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(**self._connector_kwargs)
            self._session = aiohttp.ClientSession(
                connector=connector, timeout=self._timeout,
                headers={"Accept": "application/json"}
            )
        return self._session

    async def _close_session(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _generate_signature(self, params: dict) -> str:
        query_string = urllib.parse.urlencode(sorted(params.items()))
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    async def _request(self, method: str, endpoint: str, params: Optional[dict] = None, 
                       signed: bool = False, retries: int = 3) -> dict:
        # Rate limiting
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._adaptive_interval:
            await asyncio.sleep(self._adaptive_interval - elapsed)
        self._last_request_time = time.time()

        # Circuit breaker check
        if self._circuit_open:
            if now - self._circuit_open_time > self._circuit_recovery_after:
                self.logger.info("Circuit breaker: attempting recovery")
                self._circuit_open = False
                self._consecutive_errors = 0
            else:
                self.logger.warning(f"Circuit breaker OPEN, retry after {self._circuit_recovery_after - (now - self._circuit_open_time):.0f}s")
                return {"code": -1, "msg": "Circuit breaker open - API temporarily unavailable"}

        if not self.api_key and signed:
            return {"code": -1, "msg": "API key required for signed request"}

        url = f"{self.base_url}{endpoint}"
        query_params = params.copy() if params else {}
        if signed:
            query_params["timestamp"] = str(int(time.time() * 1000))
            query_params["signature"] = self._generate_signature(query_params)
            query_params["apiKey"] = self.api_key

        last_error = None
        for attempt in range(retries):
            try:
                session = await self._get_or_create_session()
                if method.upper() == "GET":
                    async with session.get(url, params=query_params, timeout=self._timeout) as response:
                        data = await response.json(content_type=None)
                elif method.upper() == "POST":
                    async with session.post(url, json=query_params, timeout=self._timeout) as response:
                        data = await response.json(content_type=None)
                elif method.upper() == "DELETE":
                    async with session.delete(url, params=query_params, timeout=self._timeout) as response:
                        data = await response.json(content_type=None)
                else:
                    return {"code": -1, "msg": f"Unsupported method {method}"}

                self._total_requests += 1

                # Check for API errors
                if data.get("code") == 100400 or "api is not exist" in str(data.get("msg", "")).lower():
                    last_error = data
                    self.logger.warning(f"Endpoint {endpoint} not found (attempt {attempt+1}/{retries})")
                    break  # Don't retry - endpoint is wrong

                if data.get("code") == 0 or (data.get("code") == 200):
                    # Success
                    self._consecutive_errors = 0
                    self._error_rate = max(0, self._error_rate - 0.1)
                    self._adaptive_interval = max(0.02, self._adaptive_interval * 0.95)
                    return data

                # API returned error code
                last_error = data
                self._consecutive_errors += 1
                self._error_rate = min(1.0, self._error_rate + 0.2)

                # Circuit breaker
                if self._consecutive_errors >= 10:
                    self.logger.critical("Circuit breaker OPEN - too many consecutive errors")
                    self._circuit_open = True
                    self._circuit_open_time = time.time()
                    return {"code": -1, "msg": "Circuit breaker open"}

                # Exponential backoff
                backoff = (2 ** attempt) + random.uniform(0, 1)
                self.logger.warning(f"API error (attempt {attempt+1}/{retries}): {data.get('msg')}, backoff {backoff:.1f}s")
                await asyncio.sleep(backoff)

            except asyncio.TimeoutError:
                last_error = {"code": -1, "msg": f"Timeout on {endpoint}"}
                self._consecutive_errors += 1
                self.logger.warning(f"Request timeout (attempt {attempt+1}/{retries})")
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                last_error = {"code": -1, "msg": str(e)}
                self._consecutive_errors += 1
                self.logger.warning(f"Request error (attempt {attempt+1}/{retries}): {e}")
                await asyncio.sleep(2 ** attempt)

        # All retries failed
        self._error_rate = min(1.0, self._error_rate + 0.3)
        self._adaptive_interval = min(2.0, self._adaptive_interval * 1.5)
        return last_error or {"code": -1, "msg": "All retries failed"}

    async def _request_with_fallback(self, method: str, category: str, params: Optional[dict] = None, 
                                      signed: bool = False) -> dict:
        """Try primary endpoint, fall back to alternatives if it fails."""
        endpoints = self._endpoints.endpoints.get(category, [])
        if not endpoints:
            return {"code": -1, "msg": f"No endpoints for category {category}"}

        for ep in endpoints:
            response = await self._request(method, ep, params, signed, retries=2)
            success = response.get("code") == 0 or response.get("code") == 200
            self._endpoints.report(category, ep, success)

            if success:
                return response

            # If endpoint doesn't exist, try next immediately
            if response.get("code") == 100400 or "api is not exist" in str(response.get("msg", "")).lower():
                self.logger.warning(f"Endpoint {ep} invalid, trying fallback...")
                continue

            # Other error - might be temporary, but try fallback anyway
            if ep != endpoints[-1]:
                await asyncio.sleep(0.5)

        return response  # Return last error

    # Public API
    async def get_klines(self, symbol: str, interval: str = "15m", limit: int = 100,
                         start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time: params["startTime"] = start_time
        if end_time: params["endTime"] = end_time
        response = await self._request_with_fallback("GET", "klines", params, signed=False)
        if response.get("code") == 0 and "data" in response:
            return response["data"]
        return []

    async def get_ticker(self, symbol: str) -> dict:
        response = await self._request_with_fallback("GET", "ticker", {"symbol": symbol}, signed=False)
        if response.get("code") == 0 and "data" in response:
            return response["data"]
        return {}

    async def get_orderbook(self, symbol: str, limit: int = 20) -> dict:
        response = await self._request("GET", "/openApi/swap/v3/quote/depth", {"symbol": symbol, "limit": limit}, signed=False)
        if response.get("code") == 0 and "data" in response:
            return response["data"]
        return {}

    async def get_tickers_batch(self) -> dict:
        response = await self._request_with_fallback("GET", "ticker", {}, signed=False)
        if response.get("code") == 0 and "data" in response:
            data = response["data"]
            result = {}
            for item in data if isinstance(data, list) else [data]:
                sym = item.get("symbol", "")
                if sym: result[sym] = item
            return result
        return {}

    async def get_symbol_info(self) -> dict:
        response = await self._request_with_fallback("GET", "contracts", {}, signed=False)
        self.logger.info(f"Symbol info response: {response}")
        if response.get("code") == 0 and "data" in response:
            for item in response.get("data", []):
                sym = item.get("symbol", "")
                if sym: self._symbol_specs[sym] = item
            return response
        return response

    def get_symbol_specs(self, symbol: str) -> Optional[dict]:
        return self._symbol_specs.get(symbol)

    # Account / Trading (signed)
    async def get_account_balance(self) -> dict:
        response = await self._request_with_fallback("GET", "balance", {}, signed=True)
        self.logger.info(f"Balance response: {response}")
        if response.get("code") == 0 and "data" in response:
            return response["data"]
        return {}

    async def get_account_info(self) -> dict:
        return await self.get_account_balance()

    async def get_positions(self, symbol: Optional[str] = None) -> list:
        params = {}
        if symbol: params["symbol"] = symbol
        response = await self._request_with_fallback("GET", "positions", params, signed=True)
        if response.get("code") == 0 and "data" in response:
            data = response["data"]
            if isinstance(data, dict) and "positions" in data:
                return data["positions"]
            return data if isinstance(data, list) else []
        return []

    async def set_leverage(self, symbol: str, leverage: int, position_side: str = "BOTH") -> dict:
        params = {"symbol": symbol, "leverage": leverage, "positionSide": position_side}
        response = await self._request_with_fallback("POST", "leverage", params, signed=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Set leverage failed: {response.get('msg')}")
        return response

    async def set_margin_mode(self, symbol: str, margin_mode: str) -> dict:
        params = {"symbol": symbol, "marginMode": margin_mode}
        response = await self._request_with_fallback("POST", "marginMode", params, signed=True)
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
        response = await self._request_with_fallback("POST", "order", params, signed=True)
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
        response = await self._request_with_fallback("POST", "order", params, signed=True)
        if response.get("code") == 0:
            return response.get("data", {})
        self.logger.error(f"Stop order failed: {response.get('msg')}")
        return {"error": True, "msg": response.get("msg", "Unknown"), "code": response.get("code", -1)}

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        params = {"symbol": symbol, "orderId": order_id}
        response = await self._request_with_fallback("DELETE", "order", params, signed=True)
        return response.get("code") == 0

    async def get_open_orders(self, symbol: str) -> list:
        params = {"symbol": symbol}
        response = await self._request_with_fallback("GET", "openOrders", params, signed=True)
        if response.get("code") == 0 and "data" in response:
            return response["data"].get("orders", [])
        return []

    async def close_position(self, symbol: str, position_side: str) -> dict:
        side = "SELL" if position_side == "LONG" else "BUY"
        params = {"symbol": symbol, "side": side, "positionSide": position_side,
                  "type": "MARKET", "closePosition": "true"}
        response = await self._request_with_fallback("POST", "order", params, signed=True)
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
            "error_rate": self._error_rate,
            "total_requests": self._total_requests,
            "circuit_open": self._circuit_open,
            "adaptive_interval": self._adaptive_interval,
            "endpoints": self._endpoints.get_health_report(),
        }
