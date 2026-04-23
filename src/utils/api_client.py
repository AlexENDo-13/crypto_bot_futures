#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AsyncBingXClient v3.0 — улучшенный клиент BingX API.
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
    BASE_URL = "https://open-api.bingx.com"
    DEMO_URL = "https://open-api-vst.bingx.com"

    ERROR_CODES = {
        100001: "API key не действителен", 100002: "Ошибка подписи",
        100003: "Неверный timestamp", 100004: "Нет разрешения",
        100005: "Слишком много запросов", 100100: "Недостаточно средств",
        100101: "Недостаточно маржи", 100112: "Неверный символ",
        100114: "Неверный размер позиции", 100115: "Превышен лимит позиций",
        100116: "Неверное плечо", 100117: "Неверный тип ордера",
        100400: "Неверные параметры", 100412: "Неверный символ",
        100413: "Контракт не существует", 100414: "Неверный объём",
        100415: "Неверная цена", 100416: "Недостаточно баланса",
        100417: "Позиция не существует", 100418: "Ордер не существует",
        100419: "Неверный статус", 100420: "Ордер уже исполнен",
        100421: "Слишком много ордеров", 100422: "Нарушение лимита позиций",
        100423: "Неверный тип позиции", 100424: "Неверный режим маржи",
        100425: "Неверный режим позиции", 80001: "Система занята",
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
        self._last_request_time = 0
        self._rate_limit_delay = 0.05
        self._request_count = 0
        self._error_count = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            async with self._session_lock:
                if self._session is None or self._session.closed:
                    timeout = aiohttp.ClientTimeout(total=30, connect=15, sock_read=30)
                    connector = aiohttp.TCPConnector(limit=100, limit_per_host=20, ttl_dns_cache=300, enable_cleanup_closed=True)
                    self._session = aiohttp.ClientSession(timeout=timeout, connector=connector, headers={"X-BX-APIKEY": self.api_key})
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _sync_server_time(self, force: bool = False):
        if not force and self._server_time_offset != 0:
            return
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/openApi/swap/v2/server/time") as resp:
                data = await resp.json()
                if data and data.get("code") == 0:
                    server_time = data.get("data", {}).get("serverTime", 0)
                    self._server_time_offset = server_time - int(time.time() * 1000)
                    logger.info(f"Время сервера синхронизировано. Offset: {self._server_time_offset}ms")
        except Exception as e:
            logger.warning(f"Не удалось синхронизировать время: {e}")
            self._server_time_offset = 0

    def _get_timestamp(self) -> int:
        return int(time.time() * 1000) + self._server_time_offset

    def _sign(self, query_string: str) -> str:
        return hmac.new(self.api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

    async def _request(self, method: str, path: str, params: dict = None, signed: bool = False,
                        retries: int = 3, retry_delay: float = 1.0) -> Optional[Dict]:
        session = await self._get_session()
        params = params or {}
        headers = {"X-BX-APIKEY": self.api_key}

        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = time.time()

        last_error = None
        for attempt in range(retries):
            try:
                if signed:
                    params["timestamp"] = self._get_timestamp()
                    params["recvWindow"] = 5000
                    sorted_params = sorted(params.items())
                    query_string = urlencode(sorted_params)
                    signature = self._sign(query_string)
                    full_query = f"{query_string}&signature={signature}"
                    request_url = f"{self.base_url}{path}?{full_query}"
                    if method.upper() == "GET":
                        async with session.get(request_url, headers=headers) as resp:
                            text = await resp.text()
                    elif method.upper() == "POST":
                        async with session.post(request_url, headers=headers) as resp:
                            text = await resp.text()
                    elif method.upper() == "DELETE":
                        async with session.delete(request_url, headers=headers) as resp:
                            text = await resp.text()
                    else:
                        raise ValueError(f"Unsupported method: {method}")
                else:
                    request_url = f"{self.base_url}{path}"
                    if method.upper() == "GET":
                        async with session.get(request_url, params=params, headers=headers) as resp:
                            text = await resp.text()
                    elif method.upper() == "POST":
                        async with session.post(request_url, data=params, headers=headers) as resp:
                            text = await resp.text()
                    elif method.upper() == "DELETE":
                        async with session.delete(request_url, params=params, headers=headers) as resp:
                            text = await resp.text()
                    else:
                        raise ValueError(f"Unsupported method: {method}")

                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    logger.error(f"Невалидный JSON: {text[:200]}")
                    return None

                self._request_count += 1
                if data and data.get("code") != 0:
                    code = data.get("code")
                    msg = data.get("msg", "Unknown")
                    desc = self.ERROR_CODES.get(code, "Unknown")
                    logger.warning(f"BingX API Error {code}: {msg} ({desc})")
                    self._error_count += 1
                    if code in (100001, 100002, 100003, 100005, 80001) and attempt < retries - 1:
                        await self._sync_server_time(force=True)
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
                    return data
                return data
            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"Сетевой сбой ({attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
            except asyncio.TimeoutError:
                last_error = "Timeout"
                logger.warning(f"Таймаут ({attempt+1}/{retries})")
                if attempt < retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
            except Exception as e:
                last_error = e
                logger.error(f"Ошибка запроса: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))

        logger.error(f"Все попытки исчерпаны: {last_error}")
        return None

    def _safe_float(self, val, default=0.0):
        try:
            if val is None:
                return default
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                val = val.strip()
                if val == "" or val.lower() == "null":
                    return default
                return float(val)
            return default
        except (TypeError, ValueError):
            return default

    def _extract_balance(self, obj: Any) -> Optional[Dict]:
        if not isinstance(obj, dict):
            return None
        return {
            "balance": self._safe_float(obj.get("balance")),
            "available": self._safe_float(obj.get("availableMargin") or obj.get("available") or obj.get("balance")),
            "used": self._safe_float(obj.get("usedMargin") or obj.get("freeze") or obj.get("locked")),
            "equity": self._safe_float(obj.get("equity") or obj.get("balance")),
            "unrealizedProfit": self._safe_float(obj.get("unrealizedProfit") or obj.get("unRealizedProfit")),
            "realisedProfit": self._safe_float(obj.get("realisedProfit") or obj.get("realizedProfit")),
            "asset": str(obj.get("asset", "USDT")),
        }

    # Public methods
    async def get_server_time(self) -> Optional[Dict]:
        return await self._request("GET", "/openApi/swap/v2/server/time", signed=False)

    async def get_symbol_info(self, symbol: str = None) -> Optional[Dict]:
        cache_ttl = 300
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
        result = await self._request("GET", "/openApi/swap/v2/quote/ticker", params={"symbol": symbol}, signed=False)
        if result and result.get("code") == 0:
            data = result.get("data", [])
            if data:
                ticker = data[0] if isinstance(data, list) else data
                def sf(val, d=0.0):
                    try:
                        return float(val) if val is not None else d
                    except:
                        return d
                return {
                    "symbol": ticker.get("symbol", symbol),
                    "lastPrice": sf(ticker.get("lastPrice") or ticker.get("close")),
                    "volume24h": sf(ticker.get("volume") or ticker.get("quoteVolume") or ticker.get("volume24h")),
                    "high24h": sf(ticker.get("highPrice") or ticker.get("high")),
                    "low24h": sf(ticker.get("lowPrice") or ticker.get("low")),
                    "markPrice": sf(ticker.get("markPrice") or ticker.get("lastPrice")),
                    "bid": sf(ticker.get("bidPrice")),
                    "ask": sf(ticker.get("askPrice")),
                    "fundingRate": sf(ticker.get("fundingRate")),
                }
        return None

    async def get_all_tickers(self) -> List[Dict]:
        result = await self._request("GET", "/openApi/swap/v2/quote/ticker", signed=False)
        tickers = []
        if result and result.get("code") == 0:
            data = result.get("data", [])
            def sf(val, d=0.0):
                try:
                    return float(val) if val is not None else d
                except:
                    return d
            for t in (data if isinstance(data, list) else [data]):
                if t:
                    tickers.append({
                        "symbol": t.get("symbol", ""),
                        "lastPrice": sf(t.get("lastPrice") or t.get("close")),
                        "volume24h": sf(t.get("volume") or t.get("quoteVolume") or t.get("volume24h")),
                        "markPrice": sf(t.get("markPrice") or t.get("lastPrice")),
                        "fundingRate": sf(t.get("fundingRate")),
                    })
        return tickers

    async def get_klines(self, symbol: str, interval: str = "15m", limit: int = 100) -> List[Dict]:
        result = await self._request("GET", "/openApi/swap/v3/quote/klines",
                                      params={"symbol": symbol, "interval": interval, "limit": limit}, signed=False)
        if result and result.get("code") == 0:
            data = result.get("data", [])
            klines = []
            for k in data:
                if isinstance(k, list) and len(k) >= 6:
                    klines.append({"timestamp": int(k[0]), "open": float(k[1]), "high": float(k[2]),
                                   "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])})
                elif isinstance(k, dict):
                    klines.append({"timestamp": int(k.get("time", k.get("timestamp", 0))),
                                   "open": float(k.get("open", 0)), "high": float(k.get("high", 0)),
                                   "low": float(k.get("low", 0)), "close": float(k.get("close", 0)),
                                   "volume": float(k.get("volume", 0))})
            return klines
        return []

    async def get_funding_rate(self, symbol: str) -> Optional[Dict]:
        result = await self._request("GET", "/openApi/swap/v2/quote/premiumIndex", params={"symbol": symbol}, signed=False)
        if result and result.get("code") == 0:
            data = result.get("data", {})
            if isinstance(data, list) and data:
                data = data[0]
            return {"fundingRate": self._safe_float(data.get("lastFundingRate") or data.get("fundingRate"))}
        return {"fundingRate": 0.0}

    # Private methods
    async def get_account_info(self) -> Optional[Dict]:
        result = await self._request("GET", "/openApi/swap/v2/user/balance", signed=True)
        if not result or result.get("code") != 0:
            return None
        data = result.get("data", {})
        balance_data = data.get("balance")
        if isinstance(balance_data, dict):
            extracted = self._extract_balance(balance_data)
            if extracted and extracted["balance"] > 0:
                return extracted
            for key, val in balance_data.items():
                if isinstance(val, dict):
                    extracted = self._extract_balance(val)
                    if extracted and extracted["asset"].upper() == "USDT":
                        return extracted
        if isinstance(balance_data, list):
            for bal in balance_data:
                extracted = self._extract_balance(bal)
                if extracted and extracted["asset"].upper() == "USDT":
                    return extracted
        if balance_data:
            extracted = self._extract_balance(balance_data[0])
            if extracted:
                return extracted
        if isinstance(data, dict):
            extracted = self._extract_balance(data)
            if extracted and extracted["balance"] > 0:
                return extracted
        assets = data.get("assets") or data.get("balances")
        if isinstance(assets, list):
            for asset in assets:
                extracted = self._extract_balance(asset)
                if extracted and extracted["asset"].upper() == "USDT":
                    return extracted
        logger.error(f"❌ Не удалось распарсить баланс: {json.dumps(result, ensure_ascii=False)[:500]}")
        return None

    async def get_positions(self, symbol: str = None) -> List[Dict]:
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
                if not p:
                    continue
                amt = self._safe_float(p.get("positionAmt"))
                if amt == 0:
                    continue
                positions.append({
                    "symbol": str(p.get("symbol", "")),
                    "positionAmt": amt,
                    "avgPrice": self._safe_float(p.get("avgPrice") or p.get("entryPrice")),
                    "positionSide": str(p.get("positionSide", "LONG" if amt > 0 else "SHORT")),
                    "leverage": int(self._safe_float(p.get("leverage", 1))),
                    "unrealizedProfit": self._safe_float(p.get("unrealizedProfit") or p.get("unRealizedProfit")),
                    "markPrice": self._safe_float(p.get("markPrice")),
                    "lastPrice": self._safe_float(p.get("lastPrice") or p.get("markPrice")),
                    "liquidationPrice": self._safe_float(p.get("liquidationPrice")),
                })
        return positions

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        result = await self._request("POST", "/openApi/swap/v2/trade/leverage",
                                      params={"symbol": symbol, "leverage": str(leverage), "side": "BOTH"}, signed=True)
        if result and result.get("code") == 0:
            logger.info(f"Плечо {leverage}x для {symbol} установлено")
            return True
        msg = result.get("msg", "Unknown") if result else "No response"
        logger.warning(f"Не удалось установить плечо {symbol}: {msg}")
        return False

    async def set_margin_mode(self, symbol: str, margin_mode: str = "CROSSED") -> bool:
        result = await self._request("POST", "/openApi/swap/v2/trade/marginType",
                                      params={"symbol": symbol, "marginType": margin_mode}, signed=True)
        if result and result.get("code") == 0:
            logger.info(f"Режим маржи {margin_mode} для {symbol} установлен")
            return True
        msg = result.get("msg", "") if result else ""
        if "already" in msg.lower() or "repeat" in msg.lower():
            return True
        logger.warning(f"Ошибка установки маржи {margin_mode} для {symbol}: {msg}")
        return False

    async def place_order(self, symbol: str, side: str, quantity: float, order_type: str = "MARKET",
                           price: float = None, stop_price: float = None, leverage: int = None,
                           position_side: str = "BOTH", client_order_id: str = None) -> Optional[Dict]:
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

        result = await self._request("POST", "/openApi/swap/v2/trade/order", params=params, signed=True)
        if result is None:
            logger.error(f"Ордер {symbol} {side}: нет ответа")
            return None
        if result.get("code") != 0:
            code = result.get("code", -1)
            msg = result.get("msg", "Unknown")
            logger.error(f"Ордер отклонён {symbol} {side}: [{code}] {msg}")
            return {"error": True, "code": code, "msg": msg}
        data = result.get("data", {})
        return {
            "orderId": data.get("orderId", client_order_id or ""),
            "clientOrderId": data.get("clientOrderId", client_order_id or ""),
            "symbol": symbol, "side": side, "quantity": quantity,
            "price": self._safe_float(data.get("avgPrice") or price),
            "avgPrice": self._safe_float(data.get("avgPrice") or price),
            "status": data.get("status", "FILLED"),
        }

    async def place_stop_order(self, symbol: str, side: str, stop_price: float, quantity: float = None,
                                order_type: str = "STOP_MARKET", position_side: str = "BOTH",
                                close_position: bool = False) -> Optional[Dict]:
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "positionSide": position_side.upper(),
            "stopPrice": str(stop_price),
        }
        if close_position:
            params["closePosition"] = "true"
        elif quantity is not None:
            params["quantity"] = str(quantity)

        result = await self._request("POST", "/openApi/swap/v2/trade/order", params=params, signed=True)
        if result is None:
            logger.error(f"Стоп-ордер {symbol}: нет ответа")
            return None
        if result.get("code") != 0:
            code = result.get("code", -1)
            msg = result.get("msg", "Unknown")
            logger.error(f"Стоп-ордер отклонён {symbol}: [{code}] {msg}")
            return {"error": True, "code": code, "msg": msg}
        data = result.get("data", {})
        return {
            "orderId": data.get("orderId", ""),
            "symbol": symbol, "side": side, "stopPrice": stop_price,
            "status": data.get("status", "NEW"),
        }

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        result = await self._request("DELETE", "/openApi/swap/v2/trade/order",
                                      params={"symbol": symbol, "orderId": order_id}, signed=True)
        if result and result.get("code") == 0:
            logger.info(f"Ордер {order_id} отменён")
            return True
        msg = result.get("msg", "") if result else ""
        if "not exist" in msg.lower() or "cancelled" in msg.lower():
            return True
        logger.error(f"Ошибка отмены ордера {order_id}: {msg}")
        return False

    async def cancel_all_orders(self, symbol: str = None) -> bool:
        params = {}
        if symbol:
            params["symbol"] = symbol
        result = await self._request("DELETE", "/openApi/swap/v2/trade/allOpenOrders", params=params, signed=True)
        if result and result.get("code") == 0:
            logger.info(f"Все ордера отменены{' для ' + symbol if symbol else ''}")
            return True
        return False

    async def close_position(self, symbol: str, position_side: str = "BOTH") -> bool:
        positions = await self.get_positions(symbol)
        for pos in positions:
            if pos.get("symbol") == symbol:
                pos_side = pos.get("positionSide", "LONG")
                if position_side != "BOTH" and pos_side != position_side:
                    continue
                amt = abs(float(pos.get("positionAmt", 0)))
                if amt > 0:
                    close_side = "SELL" if pos_side == "LONG" else "BUY"
                    result = await self.place_order(symbol=symbol, side=close_side, quantity=amt,
                                                     order_type="MARKET", position_side=pos_side)
                    if result and not result.get("error") and result.get("orderId"):
                        logger.info(f"Позиция {symbol} закрыта")
                        return True
        return False

    def set_demo_mode(self, demo_mode: bool):
        if self.demo_mode == demo_mode:
            return
        self.demo_mode = demo_mode
        self.base_url = self.DEMO_URL if demo_mode else self.BASE_URL
        logger.info(f"Режим переключён на {'демо' if demo_mode else 'реальный'}")

    def get_symbol_specs(self, symbol: str) -> Optional[Dict]:
        info = self._symbol_info_cache.get(symbol)
        if info:
            return {
                "symbol": symbol,
                "stepSize": self._safe_float(info.get("quantityStep") or info.get("stepSize"), 0.001),
                "minNotional": self._safe_float(info.get("minNotional") or info.get("minQty"), 5.0),
                "maxLeverage": int(self._safe_float(info.get("maxLongLeverage") or info.get("maxLeverage"), 125)),
                "tickSize": self._safe_float(info.get("priceStep") or info.get("tickSize"), 0.01),
                "contractSize": self._safe_float(info.get("size"), 1.0),
            }
        return None

    def get_health(self) -> Dict[str, Any]:
        return {
            "requests": self._request_count,
            "errors": self._error_count,
            "error_rate": (self._error_count / max(self._request_count, 1)) * 100,
            "demo_mode": self.demo_mode,
        }
