"""BingX API Client v2 with fixed signature."""
import asyncio
import hashlib
import hmac
import json
import time
from typing import Dict, Any, Optional, List
import aiohttp


class BingXAPIClient:
    """BingX API клиент с исправленной подписью.

    Критическое исправление: apiKey только в заголовке X-BX-APIKEY,
    НЕ в query string и НЕ в подписи.
    """

    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://open-api.bingx.com"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    def _sign(self, payload: str) -> str:
        """Создаёт HMAC-SHA256 подпись."""
        return hmac.new(
            self.api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                       data: Optional[Dict] = None, signed: bool = False) -> Dict[str, Any]:
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        headers = {}

        if params is None:
            params = {}

        if signed and self.api_key:
            params["timestamp"] = int(time.time() * 1000)
            # Сортируем параметры для стабильной подписи
            sorted_params = sorted(params.items())
            query_string = "&".join([f"{k}={v}" for k, v in sorted_params])
            signature = self._sign(query_string)
            params["signature"] = signature
            headers["X-BX-APIKEY"] = self.api_key

        try:
            async with session.request(method, url, params=params, json=data, headers=headers, timeout=30) as resp:
                text = await resp.text()
                try:
                    result = json.loads(text)
                except json.JSONDecodeError:
                    result = {"code": -1, "msg": text}

                if result.get("code") not in (0, None, 200):
                    raise Exception(f"BingX API error {result.get('code')}: {result.get('msg')}")
                return result.get("data", result)
        except aiohttp.ClientError as e:
            raise Exception(f"Request failed: {e}")

    async def get_account_balance(self) -> Dict[str, Any]:
        return await self._request("GET", "/openApi/swap/v2/user/balance", signed=True)

    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if symbol:
            params["symbol"] = symbol
        result = await self._request("GET", "/openApi/swap/v2/user/positions", params=params, signed=True)
        # Handle nested dict response
        if isinstance(result, dict) and "positions" in result:
            return result["positions"]
        return result if isinstance(result, list) else []

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if symbol:
            params["symbol"] = symbol
        result = await self._request("GET", "/openApi/swap/v2/trade/openOrders", params=params, signed=True)
        return result if isinstance(result, list) else []

    async def place_order(self, symbol: str, side: str, order_type: str, quantity: float,
                          price: Optional[float] = None, stop_price: Optional[float] = None,
                          leverage: int = 1) -> Dict[str, Any]:
        data = {
            "symbol": symbol,
            "side": side,
            "positionSide": "LONG" if side == "BUY" else "SHORT",
            "type": order_type.upper(),
            "quantity": str(quantity),
        }
        if price is not None:
            data["price"] = str(price)
        if stop_price is not None:
            data["stopPrice"] = str(stop_price)
        return await self._request("POST", "/openApi/swap/v2/trade/order", data=data, signed=True)

    async def close_position(self, symbol: str, position_side: str) -> Dict[str, Any]:
        """Закрытие позиции через closePosition=true."""
        data = {
            "symbol": symbol,
            "side": "SELL" if position_side == "LONG" else "BUY",
            "positionSide": position_side,
            "type": "MARKET",
            "closePosition": "true"
        }
        try:
            return await self._request("POST", "/openApi/swap/v2/trade/order", data=data, signed=True)
        except Exception:
            # Fallback: close via market order
            pos = await self.get_positions(symbol)
            if pos:
                qty = abs(float(pos[0].get("positionAmt", 0)))
                if qty > 0:
                    return await self.place_order(
                        symbol=symbol,
                        side="SELL" if position_side == "LONG" else "BUY",
                        order_type="MARKET",
                        quantity=qty
                    )
            raise

    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        data = {"symbol": symbol, "orderId": order_id}
        return await self._request("DELETE", "/openApi/swap/v2/trade/order", data=data, signed=True)

    async def set_leverage(self, symbol: str, leverage: int, side: str = "BOTH") -> Dict[str, Any]:
        data = {"symbol": symbol, "leverage": leverage, "side": side}
        return await self._request("POST", "/openApi/swap/v2/trade/leverage", data=data, signed=True)

    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[list]:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        result = await self._request("GET", "/openApi/swap/v3/quote/klines", params=params)
        return result if isinstance(result, list) else []

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        params = {"symbol": symbol}
        result = await self._request("GET", "/openApi/swap/v2/quote/ticker", params=params)
        return result if isinstance(result, dict) else {}

    async def get_symbol_info(self) -> Dict[str, Any]:
        result = await self._request("GET", "/openApi/swap/v2/quote/contracts")
        return result if isinstance(result, dict) else {}

    async def get_symbol_specs(self, symbol: str) -> Dict[str, Any]:
        info = await self.get_symbol_info()
        if isinstance(info, dict) and "contracts" in info:
            for contract in info["contracts"]:
                if contract.get("symbol") == symbol:
                    return contract
        return {}

    async def get_health(self) -> Dict[str, Any]:
        try:
            await self.get_ticker("BTC-USDT")
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
