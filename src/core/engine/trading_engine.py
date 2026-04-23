#!/usr/bin/env python3
"""
Асинхронный торговый движок.
"""
import asyncio
from typing import Dict, Optional

class TradingEngine:
    def __init__(self, client, data_fetcher, scanner, executor, risk_manager, settings, logger):
        self.client = client
        self.data_fetcher = data_fetcher
        self.scanner = scanner
        self.executor = executor
        self.risk_manager = risk_manager
        self.settings = settings
        self.logger = logger

        self.open_positions: Dict[str, any] = {}  # symbol -> Position object
        self.balance = 0.0
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Запускает основной цикл движка."""
        self._running = True
        # Получаем начальный баланс
        account = await self.client.get_account_info()
        self.balance = float(account.get('balance', self.settings.get('virtual_balance', 100.0)))
        self.logger.info(f"Engine started. Balance: {self.balance:.2f} USDT")
        self._task = asyncio.create_task(self._async_main())

    async def stop(self):
        """Останавливает движок."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.client.close()
        self.logger.info("Engine stopped")

    async def _async_main(self):
        while self._running:
            try:
                await asyncio.wait_for(self._run_iteration_async(), timeout=300.0)
            except asyncio.TimeoutError:
                self.logger.error("Iteration timeout")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Engine error: {e}")
                await asyncio.sleep(10)

    async def _run_iteration_async(self):
        # Обновление баланса
        account = await self.client.get_account_info()
        self.balance = float(account.get('balance', self.balance))

        # Сканирование рынка
        contracts = await self.data_fetcher.get_all_usdt_contracts()
        candidates = await self.scanner.scan_async(contracts, self.balance)

        max_positions = self.settings.get('max_positions', 2)
        for cand in candidates:
            if len(self.open_positions) >= max_positions:
                break
            if cand['symbol'] in self.open_positions:
                continue

            self.logger.info(f"Attempting entry for {cand['symbol']}")
            pos = await self.executor.execute_trade_async(cand)
            if pos:
                self.open_positions[cand['symbol']] = pos

        # Синхронизация с биржей (удаление закрытых позиций)
        await self._sync_positions_with_exchange_async()

        # Пауза между итерациями
        interval = self.settings.get('scan_interval_minutes', 5) * 60
        await asyncio.sleep(interval)

    async def _sync_positions_with_exchange_async(self):
        """Обновляет self.open_positions на основе данных биржи."""
        try:
            exchange_positions = await self.client.get_positions()
            active_symbols = {p['symbol'].replace('-', '/') for p in exchange_positions if float(p.get('positionAmt', 0)) != 0}
            # Удаляем закрытые позиции
            closed = [sym for sym in self.open_positions if sym not in active_symbols]
            for sym in closed:
                del self.open_positions[sym]
                self.logger.info(f"Position {sym} closed")
        except Exception as e:
            self.logger.error(f"Sync positions error: {e}")
