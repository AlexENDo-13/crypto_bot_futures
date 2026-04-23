import aiohttp
import time
import hashlib
import hmac
import json
import logging

logger = logging.getLogger("AsyncBingXClient")

class AsyncBingXClient:
    BASE_URL = "https://open-api.bingx.com"          # Реальный сервер
    DEMO_URL = "https://open-api-vst.bingx.com"      # Тестовый сервер

    def __init__(self, api_key: str, api_secret: str, demo_mode: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.demo_mode = demo_mode
        self.base_url = self.DEMO_URL if demo_mode else self.BASE_URL
        self.session = None

    async def _get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = hmac.new(
            self.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    async def _request(self, method, path, params=None, signed=False):
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        headers = {"X-BX-APIKEY": self.api_key}
        if signed:
            params = self._sign(params or {})
        try:
            if method.upper() == "GET":
                async with session.get(url, params=params, headers=headers) as resp:
                    return await resp.json()
            elif method.upper() == "POST":
                async with session.post(url, json=params, headers=headers) as resp:
                    return await resp.json()
            elif method.upper() == "DELETE":
                async with session.delete(url, params=params, headers=headers) as resp:
                    return await resp.json()
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise

    # ---------- методы API ----------
    async def get_account_info(self):
        return await self._request("GET", "/openApi/swap/v3/user/balance", signed=True)

    async def get_positions(self):
        return await self._request("GET", "/openApi/swap/v3/user/positions", signed=True)

    async def place_order(self, **kwargs):
        return await self._request("POST", "/openApi/swap/v3/trade/order",
                                   params=kwargs, signed=True)

    async def cancel_order(self, symbol, order_id):
        return await self._request("DELETE", "/openApi/swap/v3/trade/order",
                                   params={"symbol": symbol, "orderId": order_id}, signed=True)

    async def set_leverage(self, symbol, leverage):
        return await self._request("POST", "/openApi/swap/v3/trade/leverage",
                                   params={"symbol": symbol, "leverage": leverage}, signed=True)

    async def get_symbol_info(self, symbol):
        return await self._request("GET", "/openApi/swap/v2/quote/contracts", signed=False)

    # ========== НОВЫЙ МЕТОД ==========
    def set_demo_mode(self, demo_mode: bool):
        """Мгновенно переключает клиент между реальным и тестовым окружением."""
        if self.demo_mode == demo_mode:
            return
        self.demo_mode = demo_mode
        self.base_url = self.DEMO_URL if demo_mode else self.BASE_URL
        logger.info(f"Режим переключён на {'демо' if demo_mode else 'реальный'}. Новый URL: {self.base_url}")
