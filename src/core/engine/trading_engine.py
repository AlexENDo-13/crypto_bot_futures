"""
Торговый движок — ядро системы, управляющее циклом сканирования и исполнения сделок
"""
import asyncio
import time
import threading
from typing import Optional, Dict, List, Callable
from enum import Enum

from src.utils.api_client import AsyncBingXClient
from src.core.market.data_fetcher import MarketDataFetcher
from src.core.scanner.market_scanner import MarketScanner
from src.core.executor.trade_executor import TradeExecutor
from src.core.risk.risk_manager import RiskManager
from src.config.settings import Settings
from src.core.logger import BotLogger

class EngineState(Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"

class TradingEngine:
    """Главный торговый движок, управляющий жизненным циклом бота"""

    def __init__(
        self,
        client: AsyncBingXClient,
        data_fetcher: MarketDataFetcher,
        scanner: MarketScanner,
        executor: TradeExecutor,
        risk_manager: RiskManager,
        settings: Settings,
        logger: BotLogger
    ):
        self.client = client
        self.data_fetcher = data_fetcher
        self.scanner = scanner
        self.executor = executor
        self.risk_manager = risk_manager
        self.settings = settings
        self.logger = logger

        self.state = EngineState.STOPPED
        self._stop_event: Optional[asyncio.Event] = None
        self._pause_event: Optional[asyncio.Event] = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._update_callback: Optional[Callable] = None

        self._stats = {
            "balance": 0.0,
            "positions": 0,
            "pnl": 0.0,
            "signals_found": 0,
            "trades_executed": 0,
            "errors": 0,
            "last_scan_time": None,
        }

        self.logger.info("Торговый движок инициализирован")

    def set_update_callback(self, callback: Callable[[Dict], None]):
        """Установка колбэка для обновления UI"""
        self._update_callback = callback

    def _notify_ui(self, data: Dict):
        """Отправка данных в UI"""
        if self._update_callback:
            try:
                self._update_callback(data)
            except Exception as e:
                self.logger.error(f"Ошибка вызова UI-колбэка: {e}")

    def start(self):
        """Запуск движка в отдельном потоке"""
        if self.state != EngineState.STOPPED:
            self.logger.warning(f"Невозможно запустить движок из состояния {self.state}")
            return

        self.state = EngineState.RUNNING
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.logger.info("Торговый движок запущен")

    def stop(self):
        """Остановка движка"""
        if self.state == EngineState.STOPPED:
            return
        self.logger.info("Остановка торгового движка...")
        self.state = EngineState.STOPPED
        if self._stop_event:
            self._stop_event.set()
        if self._pause_event:
            self._pause_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self.logger.info("Торговый движок остановлен")

    def pause(self):
        """Приостановка торговли"""
        if self.state == EngineState.RUNNING:
            self.state = EngineState.PAUSED
            if self._pause_event:
                self._pause_event.clear()
            self.logger.info("Торговый движок приостановлен")

    def resume(self):
        """Возобновление после паузы"""
        if self.state == EngineState.PAUSED:
            self.state = EngineState.RUNNING
            if self._pause_event:
                self._pause_event.set()
            self.logger.info("Торговый движок возобновлён")

    def is_running(self) -> bool:
        """Проверка активности движка"""
        return self.state == EngineState.RUNNING

    def get_status(self) -> Dict:
        """Получение текущего статуса"""
        return {
            "state": self.state.value,
            "balance": self._stats.get("balance", 0.0),
            "positions": self._stats.get("positions", 0),
            "pnl": self._stats.get("pnl", 0.0),
            "signals_found": self._stats.get("signals_found", 0),
            "trades_executed": self._stats.get("trades_executed", 0),
            "last_scan": self._stats.get("last_scan_time"),
        }

    def _run_loop(self):
        """Точка входа для потока: создаёт event loop и запускает основной цикл"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        # Создаём события внутри event loop
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Изначально не на паузе
        try:
            self._loop.run_until_complete(self._main_loop())
        except Exception as e:
            self.logger.error(f"Критическая ошибка в главном цикле: {e}")
            self.state = EngineState.ERROR
        finally:
            self._loop.close()

    async def _main_loop(self):
        """Главный асинхронный цикл движка"""
        self.logger.info("Основной торговый цикл запущен")

        await self._update_account_info()

        # ИСПРАВЛЕНО: scan_interval_minutes в минутах
        scan_interval = getattr(self.settings, 'scan_interval_minutes', 5) * 60

        while not self._stop_event.is_set():
            await self._pause_event.wait()

            cycle_start = time.time()
            try:
                await self._update_account_info()

                signals = await self.scanner.scan_all()
                self._stats["signals_found"] = len(signals)
                self._stats["last_scan_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

                self._notify_ui({"type": "signals", "data": signals})

                for signal in signals:
                    if self.state != EngineState.RUNNING or self._stop_event.is_set():
                        break
                    await self._process_signal(signal)

                await self._manage_positions()

                self._notify_ui({"type": "status", "data": self.get_status()})

            except Exception as e:
                self.logger.error(f"Ошибка в цикле сканирования: {e}")
                self._stats["errors"] += 1
                await asyncio.sleep(5)
                continue

            elapsed = time.time() - cycle_start
            sleep_time = max(0, scan_interval - elapsed)
            while sleep_time > 0 and not self._stop_event.is_set() and self.state == EngineState.RUNNING:
                chunk = min(1.0, sleep_time)
                await asyncio.sleep(chunk)
                sleep_time -= chunk

    async def _update_account_info(self):
        """Обновление информации о балансе и открытых позициях"""
        try:
            balance_info = await self.risk_manager.get_account_balance()
            if balance_info:
                self._stats["balance"] = balance_info.get("total_equity", 0.0)
                self._stats["pnl"] = balance_info.get("unrealized_pnl", 0.0)

            positions = await self.executor.get_open_positions()
            self._stats["positions"] = len(positions) if positions else 0

        except Exception as e:
            self.logger.error(f"Ошибка обновления информации о счёте: {e}")

    async def _process_signal(self, signal: Dict):
        symbol = signal.get("symbol")
        direction = signal.get("direction")
        confidence = signal.get("confidence", 0.5)
        price = signal.get("price", 0.0)

        if not symbol or not direction:
            return

        allowed, reason = await self.risk_manager.check_new_position_allowed(
            symbol=symbol, direction=direction, confidence=confidence
        )
        if not allowed:
            self.logger.info(f"Сигнал {symbol} {direction} отклонён риск-менеджером: {reason}")
            return

        position_size = await self.risk_manager.calculate_position_size(
            symbol=symbol, price=price, confidence=confidence
        )
        if position_size <= 0:
            self.logger.warning(f"Нулевой размер позиции для {symbol}")
            return

        self.logger.info(f"Открытие позиции {direction} {symbol} размером {position_size}")
        result = await self.executor.open_position(
            symbol=symbol,
            side=direction,
            quantity=position_size,
            price=price if getattr(self.settings, "use_limit_orders", False) else None,
        )

        if result and result.get("success"):
            self._stats["trades_executed"] += 1
            self.logger.info(f"Позиция {symbol} {direction} открыта, ордер: {result.get('order_id')}")
        else:
            self.logger.error(f"Не удалось открыть позицию {symbol}: {result}")

    async def _manage_positions(self):
        """Управление открытыми позициями"""
        positions = await self.executor.get_open_positions()
        if not positions:
            return

        for pos in positions:
            try:
                await self.risk_manager.manage_position_risk(pos)
            except Exception as e:
                self.logger.error(f"Ошибка управления позицией {pos.get('symbol')}: {e}")

    def start_async(self):
        self.start()

    def stop_async(self):
        self.stop()
