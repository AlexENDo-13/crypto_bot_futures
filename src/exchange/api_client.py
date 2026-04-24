"""
BingX API Client v5.0 - Async-ready, connection pooling,
comprehensive error handling, and request signing.
"""
import time
import hmac
import hashlib
import urllib.parse
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.core.config import get_config
from src.core.logger import get_logger
from src.core.events import get_event_bus, EventType

logger = get_logger()


@dataclass
class APIResponse:
    success: bool
    data: Any = None
    error_code: Optional[str] = None
    error_msg: Optional[str] = None
    raw: Optional[requests.Response] = None
    latency_ms: float = 0.0

    @property
    def is_ok(self) -> bool:
        return self.success and self.data is not None


class BingXAPIClient:
    """Production-grade BingX API client"""

    ERROR_CODES = {
        "100001": "Invalid signature/API key",
        "100400": "Bad request",
        "100404": "Not found",
        "100412": "Precondition failed",
        "100413": "Insufficient margin",
        "100414": "Position not found",
        "100416": "Immediate trigger",
        "100417": "Reduce-only rejected",
        "100421": "Order not found",
        "100431": "Rate limit",
        "100500": "Server error",
        "100503": "Service unavailable",
        "-2015": "Invalid API key/IP",
        "-1021": "Timestamp ahead",
        "-1022": "Invalid signature",
    }

    RETRYABLE_CODES = {"100431", "100500", "100503", "-1021"}

    def __init__(self):
        cfg = get_config().exchange
        self.api_key = cfg.api_key
        self.api_secret = cfg.api_secret
        self.base_url = cfg.base_url.rstrip("/")
        self.recv_window = cfg.recv_window
        self.max_retries = cfg.max_retries
        self.retry_delay = cfg.retry_delay
        self.timeout = cfg.timeout

        # Session with connection pooling and retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.headers.update({
            "X-BX-APIKEY": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "CryptoBot/5.0"
        })

        self._last_request_time = 0.0
        self._min_interval = 1.0 / cfg.rate_limit_per_sec
        self._event_bus = get_event_bus()

        logger.info("BingXAPIClient v5.0 | base=%s pool=10", self.base_url)

    def _sign(self, params: Dict[str, Any]) -> str:
        query = urllib.parse.urlencode(sorted(params.items()))
        return hmac.new(
            self.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()

    def _build_params(self, extra: Optional[Dict] = None) -> Dict[str, Any]:
        params = {
            "timestamp": int(time.time() * 1000),
            "recvWindow": self.recv_window,
        }
        if extra:
            params.update({k: v for k, v in extra.items() if v is not None})
        return params

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                 signed: bool = True, retry: int = 0) -> APIResponse:
        self._rate_limit()
        start = time.time()
        url = f"{self.base_url}{endpoint}"
        req_params = self._build_params(params or {})

        if signed and self.api_secret:
            req_params["signature"] = self._sign(req_params)

        try:
            if method == "GET":
                resp = self.session.get(url, params=req_params, timeout=self.timeout)
            elif method == "POST":
                resp = self.session.post(url, params=req_params, timeout=self.timeout)
            elif method == "DELETE":
                resp = self.session.delete(url, params=req_params, timeout=self.timeout)
            else:
                return APIResponse(False, error_msg=f"Bad method: {method}")

            latency = (time.time() - start) * 1000

            try:
                data = resp.json()
            except json.JSONDecodeError:
                return APIResponse(False, error_msg=f"Bad JSON: {resp.text[:200]}", raw=resp, latency_ms=latency)

            if "code" in data and data["code"] != 0:
                code = str(data.get("code", ""))
                msg = data.get("msg", "Unknown")
                desc = self.ERROR_CODES.get(code, "Unknown")
                logger.warning("API error | code=%s | %s | %s", code, msg, desc)

                if code in self.RETRYABLE_CODES and retry < self.max_retries:
                    delay = self.retry_delay * (2 ** retry)
                    logger.info("Retry in %.1fs (%d/%d)", delay, retry + 1, self.max_retries)
                    time.sleep(delay)
                    return self._request(method, endpoint, params, signed, retry + 1)

                self._event_bus.emit_new(EventType.ERROR, {
                    "source": "api", "code": code, "msg": msg, "endpoint": endpoint
                })
                return APIResponse(False, error_code=code, error_msg=f"{msg} ({desc})", raw=resp, latency_ms=latency)

            return APIResponse(True, data=data.get("data", data), raw=resp, latency_ms=latency)

        except requests.exceptions.Timeout:
            if retry < self.max_retries:
                time.sleep(self.retry_delay * (2 ** retry))
                return self._request(method, endpoint, params, signed, retry + 1)
            return APIResponse(False, error_msg="Timeout after retries")
        except requests.exceptions.ConnectionError as e:
            if retry < self.max_retries:
                time.sleep(self.retry_delay * (2 ** retry))
                return self._request(method, endpoint, params, signed, retry + 1)
            return APIResponse(False, error_msg=f"Connection error: {e}")
        except Exception as e:
            logger.exception("API request failed")
            return APIResponse(False, error_msg=f"Error: {e}")

    # Public
    def get_server_time(self) -> APIResponse:
        return self._request("GET", "/openApi/swap/v2/server/time", signed=False)

    def get_symbols(self) -> APIResponse:
        return self._request("GET", "/openApi/swap/v2/quote/contracts", signed=False)

    def get_ticker(self, symbol: str) -> APIResponse:
        return self._request("GET", "/openApi/swap/v2/quote/ticker", {"symbol": symbol}, signed=False)

    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> APIResponse:
        return self._request("GET", "/openApi/swap/v3/quote/klines",
                            {"symbol": symbol, "interval": interval, "limit": limit}, signed=False)

    def get_depth(self, symbol: str, limit: int = 20) -> APIResponse:
        return self._request("GET", "/openApi/swap/v2/quote/depth",
                            {"symbol": symbol, "limit": limit}, signed=False)

    def get_funding_rate(self, symbol: str) -> APIResponse:
        return self._request("GET", "/openApi/swap/v2/quote/premiumIndex",
                            {"symbol": symbol}, signed=False)

    def get_open_interest(self, symbol: str) -> APIResponse:
        return self._request("GET", "/openApi/swap/v2/quote/openInterest",
                            {"symbol": symbol}, signed=False)

    # Private
    def get_balance(self) -> APIResponse:
        return self._request("GET", "/openApi/swap/v3/user/balance")

    def get_positions(self, symbol: Optional[str] = None) -> APIResponse:
        params = {"symbol": symbol} if symbol else {}
        return self._request("GET", "/openApi/swap/v2/user/positions", params)

    def set_leverage(self, symbol: str, leverage: int, side: str = "LONG") -> APIResponse:
        return self._request("POST", "/openApi/swap/v2/trade/leverage",
                            {"symbol": symbol, "leverage": leverage, "side": side})

    def set_margin_mode(self, symbol: str, margin_mode: str) -> APIResponse:
        return self._request("POST", "/openApi/swap/v2/trade/marginType",
                            {"symbol": symbol, "marginType": margin_mode})

    def place_order(self, symbol: str, side: str, position_side: str,
                    order_type: str, quantity: float, price: Optional[float] = None,
                    stop_price: Optional[float] = None, reduce_only: bool = False,
                    time_in_force: str = "GTC") -> APIResponse:
        params = {
            "symbol": symbol, "side": side, "positionSide": position_side,
            "type": order_type, "quantity": quantity,
            "reduceOnly": "true" if reduce_only else "false",
        }
        if order_type == "LIMIT":
            if price is None:
                return APIResponse(False, error_msg="Price required for LIMIT")
            params["price"] = price
            params["timeInForce"] = time_in_force
        if stop_price:
            params["stopPrice"] = stop_price

        logger.trade(f"ORDER | {symbol} {side} {position_side} {order_type} qty={quantity}")
        return self._request("POST", "/openApi/swap/v2/trade/order", params)

    def place_market_order(self, symbol: str, side: str, position_side: str, quantity: float) -> APIResponse:
        return self.place_order(symbol, side, position_side, "MARKET", quantity)

    def close_position(self, symbol: str, position_side: str) -> APIResponse:
        resp = self.get_positions(symbol)
        if not resp.is_ok:
            return resp
        positions = resp.data or []
        for pos in positions:
            if pos.get("positionSide") == position_side:
                qty = abs(float(pos.get("positionAmt", 0)))
                if qty > 0:
                    side = "SELL" if position_side == "LONG" else "BUY"
                    return self.place_market_order(symbol, side, position_side, qty)
        return APIResponse(False, error_msg=f"No {position_side} position for {symbol}")

    def cancel_order(self, symbol: str, order_id: str) -> APIResponse:
        return self._request("DELETE", "/openApi/swap/v2/trade/order",
                            {"symbol": symbol, "orderId": order_id})

    def get_open_orders(self, symbol: Optional[str] = None) -> APIResponse:
        params = {"symbol": symbol} if symbol else {}
        return self._request("GET", "/openApi/swap/v2/trade/openOrders", params)

    def get_order_history(self, symbol: Optional[str] = None, limit: int = 100) -> APIResponse:
        params = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/openApi/swap/v2/trade/allOrders", params)

    def get_income_history(self, symbol: Optional[str] = None, limit: int = 100) -> APIResponse:
        params = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/openApi/swap/v2/trade/income", params)
