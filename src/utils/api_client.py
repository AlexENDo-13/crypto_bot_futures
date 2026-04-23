#!/usr/bin/env python3
"""
BingX Native API Client (без CCXT)
Полностью асинхронный, с синхронизацией времени, корректной подписью и rate limiting.
Исправлено: get_all_contracts всегда возвращает список, даже если ответ упакован иначе.
"""
import time
import hmac
import hashlib
import aiohttp
import asyncio
from typing import Dict, Any, Optional


class AsyncBingXClient:
    BASE_URL = "https://open-api.bingx.com"
    DEMO_URL = "https://open-api-vst.bingx.com"

    def __init__(self, api_key: str, api_secret: str, demo_mode: bool = True, settings: dict = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.demo_mode = demo_mode
        self.base_url = self.DEMO_URL if demo_mode else self.BASE_URL
        self.settings = settings or {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._time_offset = 0
        self._semaphore = asyncio.Semaphore(5)
        self._last_request_time = 0
        self._min_interval = 0.05

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _sync_time(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/openApi/swap/v2/server/time") as resp:
                    data = await resp.json()
                    if data.get('code') == 0:
                        server_time = int(data['data']['serverTime'])
                        local_time = int(time.time() * 1000)
                        self._time_offset = server_time - local_time
        except Exception:
            self._time_offset = 0

    def _get_timestamp(self) -> int:
        return int(time.time() * 1000) + self._time_offset

    def _sign(self, params: Dict[str, Any]) -> str:
        query = '&'.join(f"{k}={v}" for k, v in sorted(params.items()))
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _request(
        self, endpoint: str, params: Dict[str, Any] = None,
        method: str = 'GET', signed: bool = True
    ) -> Dict:
        if params is None:
            params = {}

        async with self._semaphore:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_time = time.time()

        if signed:
            if self._time_offset == 0:
                await self._sync_time()
            params['timestamp'] = self._get_timestamp()
            params['apiKey'] = self.api_key
            sign = self._sign(params)
            params['sign'] = sign

        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"

        try:
            if method == 'GET':
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    data = await resp.json()
            elif method == 'DELETE':
                async with session.delete(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    data = await resp.json()
            else:
                async with session.post(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    data = await resp.json()

            if data.get('code') != 0:
                raise Exception(f"API error {data.get('code')}: {data.get('msg')}")
            return data.get('data', {})
        except aiohttp.ClientError as e:
            raise Exception(f"Network error: {e}")

    # ---------- Публичные методы ----------
    async def get_ticker(self, symbol: str) -> Dict:
        symbol = symbol.replace('/', '-')
        return await self._request('/openApi/swap/v2/quote/ticker', {'symbol': symbol}, signed=False)

    async def get_order_book(self, symbol: str, limit: int = 5) -> Dict:
        symbol = symbol.replace('/', '-')
        return await self._request('/openApi/swap/v2/quote/depth', {'symbol': symbol, 'limit': limit}, signed=False)

    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> list:
        symbol = symbol.replace('/', '-')
        data = await self._request('/openApi/swap/v3/quote/klines', {
            'symbol': symbol, 'interval': interval, 'limit': limit
        }, signed=False)
        return data if isinstance(data, list) else []

    async def get_funding_rate(self, symbol: str) -> Dict:
        symbol = symbol.replace('/', '-')
        return await self._request('/openApi/swap/v2/quote/premiumIndex', {'symbol': symbol}, signed=False)

    async def get_all_contracts(self) -> list:
        """
        Получить список всех фьючерсных контрактов.
        Устойчиво извлекает список независимо от того, упакован ли ответ в data/contracts.
        """
        data = await self._request('/openApi/swap/v2/quote/contracts', {}, signed=False)
        # data может быть списком или словарём с ключом 'contracts' или 'data'
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ('contracts', 'data', 'symbols'):
                if key in data and isinstance(data[key], list):
                    return data[key]
        return []

    # ---------- Приватные методы ----------
    async def get_account_info(self) -> Dict:
        return await self._request('/openApi/swap/v2/user/account', {}, signed=True)

    async def get_positions(self) -> list:
        data = await self._request('/openApi/swap/v2/user/positions', {}, signed=True)
        return data if isinstance(data, list) else []

    async def place_order(
        self, symbol: str, side: str, quantity: float,
        leverage: int = 3, order_type: str = 'MARKET',
        price: float = None, position_side: str = None
    ) -> Dict:
        symbol = symbol.replace('/', '-')
        if position_side is None:
            position_side = 'LONG' if side.upper() == 'BUY' else 'SHORT'

        params = {
            'symbol': symbol,
            'side': side.upper(),
            'positionSide': position_side,
            'type': order_type.upper(),
            'quantity': str(quantity),
            'leverage': str(leverage),
        }
        if price is not None and order_type.upper() == 'LIMIT':
            params['price'] = str(price)

        return await self._request('/openApi/swap/v2/trade/order', params, method='POST', signed=True)

    async def cancel_order(self, symbol: str, order_id: str) -> Dict:
        symbol = symbol.replace('/', '-')
        params = {
            'symbol': symbol,
            'orderId': order_id,
        }
        return await self._request('/openApi/swap/v2/trade/order', params, method='DELETE', signed=True)

    async def get_all_tickers(self) -> Dict[str, Dict]:
        contracts = await self.get_all_contracts()

        async def fetch_one(contract):
            sym = contract.get('symbol', '').replace('-', '/')
            if not sym:
                return None, None
            try:
                ticker = await self.get_ticker(sym)
                return sym, ticker
            except Exception:
                return None, None

        tasks = [fetch_one(c) for c in contracts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        tickers = {}
        for res in results:
            if isinstance(res, tuple) and res[0] and res[1]:
                tickers[res[0]] = res[1]
        return tickers
