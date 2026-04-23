#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AsyncBingXClient — полностью исправленный клиент BingX API.
Правильные эндпоинты v2, обработка ошибок, retry, синхронизация времени.
"""
import aiohttp
import asyncio
import time
import hashlib
import hmac
import json
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

logger = logging.getLogger("AsyncBingXClient")


class AsyncBingXClient:
    """Асинхронный клиент BingX Futures API v2 с полной обработкой ошибок."""

    BASE_URL = "https://open-api.bingx.com"
    DEMO_URL = "https://open-api-vst.bingx.com"

    # BingX error codes
    ERROR_CODES = {
        100001: "API key не действителен",
        100002: "Ошибка подписи",
        100003: "Неверный timestamp",
        100004: "Нет разрешения",
        100005: "Слишком много запросов",
        100100: "Недостаточно средств",
        100101: "Недостаточно маржи",
        100112: "Неверный символ",
        100114: "Неверный размер позиции",
        100115: "Превышен лимит позиций",
        100116: "Неверное плечо",
        100117: "Неверный тип ордера",
        100400: "Неверные параметры",
        100412: "Неверный символ или параметры контракта",
        100413: "Контракт не существует",
        100414: "Неверный объём (quantity)",
        100415: "Неверная цена",
        100416: "Недостаточно баланса для ордера",
        100417: "Позиция не существует",
        100418: "Ордер не существует",
        100419: "Неверный статус ордера",
        100420: "Ордер уже исполнен",
        100421: "Слишком много открытых ордеров",
        100422: "Нарушение лимита позиций",
        100423: "Неверный тип позиции",
        100424: "Неверный режим маржи",
        100425: "Неверный режим позиции",
        100426: "Неверный trigger price",
        100427: "Неверный clientOrderId",
        100428: "Ордер уже отменён",
        100429: "Ордер в процессе отмены",
        100430: "Неверный timeInForce",
        100431: "Неверный workingType",
        100432: "Неверный priceProtect",
        100433: "Неверный newClientOrderId",
        100434: "Неверный stopPrice",
        100435: "Неверный icebergQty",
        100436: "Неверный recvWindow",
        100437: "Неверный positionSide",
        100438: "Неверный closePosition",
        100439: "Неверный activationPrice",
        100440: "Неверный callbackRate",
        100441: "Неверный priceRate",
        100442: "Неверный trailingStop",
        100443: "Неверный triggerDirection",
        100444: "Неверный marginType",
        100445: "Неверный autoAddMargin",
        80001: "Система занята, повторите позже",
        80016: "Неверный период свечей",
    }

    def __init__(self, api_key: str, api_secret: str, demo_mode: bool = True, settings: Dict = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.demo_mode = demo_mode
        self.settings = settings or {}
        self.base_url = self.DEMO_URL if demo_mode else self.BASE_URL
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
        self._server_time_offset = 0
        self._symbol_info_cache: Dict[str, Dict] = {}
        self._last_symbol_info_update = 0
        self._request_count = 0
        self._last_request_time = 0
        self._rate_limit_delay = 0.05  # 50ms между запросами

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            async with self._session_lock:
                if self._session is None or self._session.closed:
                    timeout = aiohttp.ClientTimeout(total=30, connect=15, sock_read=30)
                    connector = aiohttp.TCPConnector(
                        limit=100, limit_per_host=20, ttl_dns_cache=300, enable_cleanup_closed=True
                    )
                    self._session = aiohttp.ClientSession(
                        timeout=timeout, connector=connector,
                        headers={"X-BX-APIKEY": self.api_key}
                    )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _sync_server_time(self, force: bool = False):
        """Синхронизация времени с сервером BingX."""
        if not force and self._server_time_offset != 0:
            return
        try:
            session = await self._get_session()
            url = f"{self.base_url}/openApi/swap/v2/server/time"
            async with session.get(url) as resp:
                data = await resp.json()
                if data and data.get("code") == 0:
                    server_time = data.get("data", {}).get("serverTime", 0)
                    local_time = int(time.time() * 1000)
                    self._server_time_offset = server_time - local_time
                    logger.info(f"Время сервера синхронизировано. Offset: {self._server_time_offset}ms")
        except Exception as e:
            logger.warning(f"Не удалось синхронизировать время: {e}")
            self._server_time_offset = 0

    def _get_timestamp(self) -> int:
        """Возвращает timestamp с учётом смещения сервера."""
        return int(time.time() * 1000) + self._server_time_offset

    def _sign(self, params: dict) -> str:
        """Создаёт подпись HMAC-SHA256."""
        query = urlencode(sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def _request(
        self,
        method: str,
        path: str,
        params: dict = None,
        signed: bool = False,
        retries: int = 3,
        retry_delay: float = 1.0
    ) -> Optional[Dict]:
        """Универсальный запрос с retry-логикой и rate limiting."""
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        params = params or {}

        # Rate limiting
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = time.time()

        if signed:
            params["timestamp"] = self._get_timestamp()
            params["recvWindow"] = 5000
            signature = self._sign(params)
            params["signature"] = signature

        headers = {"X-BX-APIKEY": self.api_key}

        last_error = None
        for attempt in range(retries):
            try:
                if method.upper() == "GET":
                    async with session.get(url, params=params, headers=headers) as resp:
                        text = await resp.text()
                        try:
                            data = json.loads(text)
                        except json.JSONDecodeError:
                            logger.error(f"Невалидный JSON ответ: {text[:200]}")
                            return None
                elif method.upper() == "POST":
                    async with session.post(url, data=params, headers=headers) as resp:
                        text = await resp.text()
                        try:
                            data = json.loads(text)
                        except json.JSONDecodeError:
                            logger.error(f"Невалидный JSON ответ: {text[:200]}")
                            return None
                elif method.upper() == "DELETE":
                    async with session.delete(url, params=params, headers=headers) as resp:
                        text = await resp.text()
                        try:
                            data = json.loads(text)
                        except json.JSONDecodeError:
                            logger.error(f"Невалидный JSON ответ: {text[:200]}")
                            return None
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Check for BingX errors
                if data and data.get("code") != 0:
                    code = data.get("code")
                    msg = data.get("msg", "Unknown error")
                    error_desc = self.ERROR_CODES.get(code, "Unknown error")
                    logger.warning(f"BingX API Error {code}: {msg} ({error_desc})")

                    # Retryable errors
                    if code in (100003, 100005, 80001, 100002):
                        if attempt < retries - 1:
                            await self._sync_server_time(force=True)
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                    return data  # Return error response for caller to handle

                return data

            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"Сетевой сбой (попытка {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
            except asyncio.TimeoutError:
                last_error = "Timeout"
                logger.warning(f"Таймаут запроса (попытка {attempt + 1}/{retries})")
                if attempt < retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
            except Exception as e:
                last_error = e
                logger.error(f"Неожиданная ошибка запроса: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))

        logger.error(f"Все попытки запроса исчерпаны. Последняя ошибка: {last_error}")
        return None

    # ========== PUBLIC API METHODS ==========

    async def get_server_time(self) -> Optional[Dict]:
        return await self._request("GET", "/openApi/swap/v2/server/time", signed=False)

    async def get_symbol_info(self, symbol: str = None) -> Optional[Dict]:
        """Получает информацию о торговых парах (stepSize, minNotional и т.д.)."""
        cache_ttl = 300  # 5 minutes
        now = time.time()

        if symbol and symbol in self._symbol_info_cache:
            if now - self._last_symbol_info_update < cache_ttl:
                return {"code": 0, "data": [self._symbol_info_cache[symbol]]}

        params = {}
        if symbol:
            params["symbol"] = symbol

        result = await self._request("GET", "/openApi/swap/v2/quote/contracts", params=params, signed=False)

        if result and result.get("code") == 0:
            self._last_symbol_info_update = now
            for contract in result.get("data", []):
                sym = contract.get("symbol", "")
                if sym:
                    self._symbol_info_cache[sym] = contract

        return result

    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Получает текущую цену и объём."""
        result = await self._request(
            "GET", "/openApi/swap/v2/quote/ticker",
            params={"symbol": symbol}, signed=False
        )
        if result and result.get("code") == 0:
            data = result.get("data", [])
            if data:
                ticker = data[0] if isinstance(data, list) else data
                return {
                    "symbol": ticker.get("symbol", symbol),
                    "lastPrice": float(ticker.get("lastPrice", 0) or ticker.get("close", 0)),
                    "volume24h": float(ticker.get("volume", 0) or ticker.get("quoteVolume", 0)),
                    "high24h": float(ticker.get("highPrice", 0) or ticker.get("high", 0)),
                    "low24h": float(ticker.get("lowPrice", 0) or ticker.get("low", 0)),
                    "markPrice": float(ticker.get("markPrice", 0) or ticker.get("lastPrice", 0)),
                    "bid": float(ticker.get("bidPrice", 0)),
                    "ask": float(ticker.get("askPrice", 0)),
                    "fundingRate": float(ticker.get("fundingRate", 0)),
                }
        return None

    async def get_all_tickers(self) -> List[Dict]:
        """Получает все тикеры."""
        result = await self._request("GET", "/openApi/swap/v2/quote/ticker", signed=False)
        tickers = []
        if result and result.get("code") == 0:
            data = result.get("data", [])
            for t in (data if isinstance(data, list) else [data]):
                if t:
                    tickers.append({
                        "symbol": t.get("symbol", ""),
                        "lastPrice": float(t.get("lastPrice", 0) or t.get("close", 0)),
                        "volume24h": float(t.get("volume", 0) or t.get("quoteVolume", 0)),
                        "markPrice": float(t.get("markPrice", 0) or t.get("lastPrice", 0)),
                        "fundingRate": float(t.get("fundingRate", 0)),
                    })
        return tickers

    async def get_klines(self, symbol: str, interval: str = "15m", limit: int = 100) -> List[Dict]:
        """Получает свечи (OHLCV)."""
        result = await self._request(
            "GET", "/openApi/swap/v3/quote/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            signed=False
        )
        if result and result.get("code") == 0:
            data = result.get("data", [])
            klines = []
            for k in data:
                if isinstance(k, list) and len(k) >= 6:
                    klines.append({
                        "timestamp": int(k[0]),
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5]),
                    })
                elif isinstance(k, dict):
                    klines.append({
                        "timestamp": int(k.get("time", k.get("timestamp", 0))),
                        "open": float(k.get("open", 0)),
                        "high": float(k.get("high", 0)),
                        "low": float(k.get("low", 0)),
                        "close": float(k.get("close", 0)),
                        "volume": float(k.get("volume", 0)),
                    })
            return klines
        return []

    async def get_funding_rate(self, symbol: str) -> Optional[Dict]:
        """Получает текущую ставку фандинга."""
        result = await self._request(
            "GET", "/openApi/swap/v2/quote/premiumIndex",
            params={"symbol": symbol}, signed=False
        )
        if result and result.get("code") == 0:
            data = result.get("data", {})
            if isinstance(data, list) and data:
                data = data[0]
            return {"fundingRate": float(data.get("lastFundingRate", 0) or data.get("fundingRate", 0))}
        return {"fundingRate": 0.0}

    async def get_order_book(self, symbol: str, limit: int = 5) -> Optional[Dict]:
        """Получает стакан ордеров."""
        result = await self._request(
            "GET", "/openApi/swap/v2/quote/depth",
            params={"symbol": symbol, "limit": limit}, signed=False
        )
        if result and result.get("code") == 0:
            data = result.get("data", {})
            return {
                "bids": [[float(b[0]), float(b[1])] for b in data.get("bids", [])],
                "asks": [[float(a[0]), float(a[1])] for a in data.get("asks", [])],
            }
        return {"bids": [], "asks": []}

    # ========== PRIVATE API METHODS ==========

    async def get_account_info(self) -> Optional[Dict]:
        """Получает баланс счёта."""
        result = await self._request("GET", "/openApi/swap/v2/user/balance", signed=True)
        if result and result.get("code") == 0:
            data = result.get("data", {})
            # BingX returns balance in nested structure
            balances = data.get("balance", []) if isinstance(data.get("balance"), list) else []
            if not balances and isinstance(data, dict):
                # Try direct access
                usdt_balance = data.get("availableMargin", data.get("balance", 0))
                if isinstance(usdt_balance, (int, float, str)):
                    return {
                        "balance": float(usdt_balance),
                        "available": float(data.get("availableMargin", usdt_balance)),
                        "used": float(data.get("usedMargin", 0)),
                    }
            for bal in balances:
                if bal.get("asset", "").upper() == "USDT":
                    return {
                        "balance": float(bal.get("balance", 0)),
                        "available": float(bal.get("availableBalance", bal.get("balance", 0))),
                        "used": float(bal.get("usedMargin", 0)),
                    }
            # Fallback: return total if we can't find USDT
            if isinstance(data, dict):
                return {
                    "balance": float(data.get("balance", 0)),
                    "available": float(data.get("availableMargin", data.get("balance", 0))),
                    "used": float(data.get("usedMargin", 0)),
                }
        return None

    async def get_positions(self, symbol: str = None) -> List[Dict]:
        """Получает открытые позиции."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        result = await self._request("GET", "/openApi/swap/v2/user/positions", params=params, signed=True)
        positions = []
        if result and result.get("code") == 0:
            data = result.get("data", [])
            if isinstance(data, dict):
                data = data.get("positions", [data])
            for p in (data if isinstance(data, list) else [data]):
                if p and float(p.get("positionAmt", 0)) != 0:
                    positions.append({
                        "symbol": p.get("symbol", ""),
                        "positionAmt": float(p.get("positionAmt", 0)),
                        "avgPrice": float(p.get("avgPrice", p.get("entryPrice", 0))),
                        "positionSide": p.get("positionSide", "LONG" if float(p.get("positionAmt", 0)) > 0 else "SHORT"),
                        "leverage": int(p.get("leverage", 1)),
                        "unrealizedProfit": float(p.get("unrealizedProfit", p.get("unRealizedProfit", 0))),
                        "markPrice": float(p.get("markPrice", 0)),
                        "lastPrice": float(p.get("lastPrice", p.get("markPrice", 0))),
                        "liquidationPrice": float(p.get("liquidationPrice", 0)),
                    })
        return positions

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Устанавливает плечо."""
        result = await self._request(
            "POST", "/openApi/swap/v2/trade/leverage",
            params={"symbol": symbol, "leverage": str(leverage), "side": "BOTH"}, signed=True
        )
        if result and result.get("code") == 0:
            logger.info(f"Плечо {leverage}x для {symbol} установлено")
            return True
        else:
            msg = result.get("msg", "Unknown") if result else "No response"
            logger.warning(f"Не удалось установить плечо {symbol}: {msg}")
            return False

    async def set_margin_mode(self, symbol: str, margin_mode: str = "CROSSED") -> bool:
        """Устанавливает режим маржи (ISOLATED или CROSSED)."""
        result = await self._request(
            "POST", "/openApi/swap/v2/trade/marginType",
            params={"symbol": symbol, "marginType": margin_mode}, signed=True
        )
        if result and result.get("code") == 0:
            logger.info(f"Режим маржи {margin_mode} для {symbol} установлен")
            return True
        msg = result.get("msg", "") if result else ""
        if "already" in msg.lower() or "repeat" in msg.lower():
            return True
        logger.warning(f"Ошибка установки маржи {margin_mode} для {symbol}: {msg}")
        return False

    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: float = None,
        stop_price: float = None,
        leverage: int = None,
        position_side: str = "BOTH",
        stop_loss: float = None,
        take_profit: float = None,
        client_order_id: str = None,
    ) -> Optional[Dict]:
        """Размещает ордер."""
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "positionSide": position_side.upper(),
            "quantity": str(quantity),
        }

        if price is not None and order_type.upper() != "MARKET":
            params["price"] = str(price)
        if stop_price is not None:
            params["stopPrice"] = str(stop_price)
        if client_order_id:
            params["newClientOrderId"] = client_order_id

        # Attach SL/TP if provided
        if stop_loss is not None:
            params["stopLoss"] = json.dumps({"stopPrice": str(stop_loss), "type": "STOP_MARKET", "workingType": "MARK_PRICE"})
        if take_profit is not None:
            params["takeProfit"] = json.dumps({"stopPrice": str(take_profit), "type": "TAKE_PROFIT_MARKET", "workingType": "MARK_PRICE"})

        result = await self._request("POST", "/openApi/swap/v2/trade/order", params=params, signed=True)

        if result and result.get("code") == 0:
            data = result.get("data", {})
            logger.info(f"Ордер размещён: {symbol} {side} {quantity} @ {order_type}, ID: {data.get('orderId')}")
            return {
                "orderId": data.get("orderId", client_order_id or ""),
                "clientOrderId": data.get("clientOrderId", client_order_id or ""),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": float(data.get("avgPrice", price or 0)),
                "avgPrice": float(data.get("avgPrice", price or 0)),
                "status": data.get("status", "FILLED"),
            }
        else:
            msg = result.get("msg", "Unknown") if result else "No response"
            code = result.get("code", -1) if result else -1
            logger.error(f"Ошибка ордера {symbol}: [{code}] {msg}")
            return None

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Отменяет ордер."""
        result = await self._request(
            "DELETE", "/openApi/swap/v2/trade/order",
            params={"symbol": symbol, "orderId": order_id}, signed=True
        )
        if result and result.get("code") == 0:
            logger.info(f"Ордер {order_id} отменён")
            return True
        msg = result.get("msg", "") if result else ""
        if "not exist" in msg.lower() or "cancelled" in msg.lower():
            return True
        logger.error(f"Ошибка отмены ордера {order_id}: {msg}")
        return False

    async def cancel_all_orders(self, symbol: str = None) -> bool:
        """Отменяет все ордера."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        result = await self._request(
            "DELETE", "/openApi/swap/v2/trade/allOpenOrders",
            params=params, signed=True
        )
        if result and result.get("code") == 0:
            logger.info(f"Все ордера отменены{' для ' + symbol if symbol else ''}")
            return True
        return False

    async def close_position(self, symbol: str, position_side: str = "BOTH") -> bool:
        """Закрывает позицию рыночным ордером."""
        positions = await self.get_positions(symbol)
        for pos in positions:
            if pos.get("symbol") == symbol:
                pos_side = pos.get("positionSide", "LONG")
                if position_side != "BOTH" and pos_side != position_side:
                    continue
                amt = abs(float(pos.get("positionAmt", 0)))
                if amt > 0:
                    close_side = "SELL" if pos_side == "LONG" else "BUY"
                    result = await self.place_order(
                        symbol=symbol, side=close_side, quantity=amt,
                        order_type="MARKET", position_side=pos_side
                    )
                    if result and result.get("orderId"):
                        logger.info(f"Позиция {symbol} закрыта")
                        return True
        return False

    def set_demo_mode(self, demo_mode: bool):
        """Переключает режим."""
        if self.demo_mode == demo_mode:
            return
        self.demo_mode = demo_mode
        self.base_url = self.DEMO_URL if demo_mode else self.BASE_URL
        logger.info(f"Режим переключён на {'демо' if demo_mode else 'реальный'}")

    def get_symbol_specs(self, symbol: str) -> Optional[Dict]:
        """Возвращает спецификации символа (stepSize, minNotional)."""
        info = self._symbol_info_cache.get(symbol)
        if info:
            return {
                "symbol": symbol,
                "stepSize": float(info.get("quantityStep", info.get("stepSize", 0.001))),
                "minNotional": float(info.get("minNotional", info.get("minQty", 5.0))),
                "maxLeverage": int(info.get("maxLongLeverage", info.get("maxLeverage", 125))),
                "tickSize": float(info.get("priceStep", info.get("tickSize", 0.01))),
                "contractSize": float(info.get("size", 1.0)),
            }
        return None
