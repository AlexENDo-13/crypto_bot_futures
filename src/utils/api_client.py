#!/usr/bin/env python3
"""
BingX Native API Client (без CCXT)
Полностью асинхронный, с синхронизацией времени и корректной подписью.
"""
import time
import hmac
import hashlib
import aiohttp
import asyncio
from typing import Dict, Any, Optional

class AsyncBingXClient:
    BASE_URL = "https://open-api.bingx.com"

    def __init__(self, api_key: str, api_secret: str, demo_mode: bool = True, settings: dict = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.demo_mode = demo_mode
        self.settings = settings or {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._time_offset = 0  # коррекция времени в миллисекундах

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _sync_time(self):
        """Синхронизирует локальное время с сервером BingX."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}/openApi/swap/v2/server/time") as resp:
                    data = await resp.json()
                    if data['code'] == 0:
                        server_time = int(data['data']['serverTime'])
                        local_time = int(time.time() * 1000)
                        self._time_offset = server_time - local_time
        except Exception:
            self._time_offset = 0

    def _get_timestamp(self) -> int:
        return int(time.time() * 1000) + self._time_offset

    def _sign(self, params: Dict[str, Any]) -> str:
        # Сортируем ключи и формируем строку запроса
        query = '&'.join(f"{k}={v}" for k, v in sorted(params.items()))
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _request(self, endpoint: str, params: Dict[str, Any], method: str = 'GET') -> Dict:
        if self._time_offset == 0:
            await self._sync_time()

        params['timestamp'] = self._get_timestamp()
        params['apiKey'] = self.api_key
        params['sign'] = self._sign(params)

        session = await self._get_session()
        url = f"{self.BASE_URL}{endpoint}"

        if method == 'GET':
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                data = await resp.json()
        else:
            async with session.post(url, data=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                data = await resp.json()

        if data.get('code') != 0:
            raise Exception(f"API error {data.get('code')}: {data.get('msg')}")
        return data.get('data', {})

    # ---------- Публичные методы ----------
    async def get_ticker(self, symbol: str) -> Dict:
        symbol = symbol.replace('/', '-')
        return await self._request('/openApi/swap/v2/quote/ticker', {'symbol': symbol})

    async def get_order_book(self, symbol: str, limit: int = 5) -> Dict:
        symbol = symbol.replace('/', '-')
        return await self._request('/openApi/swap/v2/quote/depth', {'symbol': symbol, 'limit': limit})

    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> list:
        symbol = symbol.replace('/', '-')
        data = await self._request('/openApi/swap/v3/quote/klines', {
            'symbol': symbol, 'interval': interval, 'limit': limit
        })
        return data  # возвращает список свечей

    async def get_funding_rate(self, symbol: str) -> Dict:
        symbol = symbol.replace('/', '-')
        return await self._request('/openApi/swap/v2/quote/premiumIndex', {'symbol': symbol})

    async def get_account_info(self) -> Dict:
        return await self._request('/openApi/swap/v2/user/account', {})

    async def get_positions(self) -> list:
        data = await self._request('/openApi/swap/v2/user/positions', {})
        return data if isinstance(data, list) else []

    async def place_order(self, symbol: str, side: str, quantity: float, leverage: int = 3) -> Dict:
        symbol = symbol.replace('/', '-')
        return await self._request('/openApi/swap/v2/trade/order', {
            'symbol': symbol,
            'side': side.upper(),
            'positionSide': 'LONG' if side.upper() == 'BUY' else 'SHORT',
            'type': 'MARKET',
            'quantity': str(quantity),
            'leverage': str(leverage)
        }, method='POST')

    async def get_all_tickers(self) -> Dict[str, Dict]:
        """Возвращает словарь {symbol: ticker_data} для всех активных контрактов."""
        contracts = await self._request('/openApi/swap/v2/quote/contracts', {})
        tickers = {}
        for c in contracts:
            sym = c['symbol'].replace('-', '/')
            try:
                ticker = await self.get_ticker(sym)
                tickers[sym] = ticker
            except Exception:
                continue
        return tickers
