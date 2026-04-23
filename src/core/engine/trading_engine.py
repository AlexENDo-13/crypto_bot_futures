#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TradingEngine — полностью автономный торговый движок.
Адаптация под депозит, самовосстановление, детальное логирование.
"""
import asyncio
import threading
import time
import traceback
import random
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from src.core.logger import BotLogger
from src.core.market.data_fetcher import DataFetcher
from src.core.trading.order_manager import OrderManager
from src.core.trading.position import Position, OrderSide, ExitReason
from src.core.risk.risk_manager import RiskManager
from src.core.risk.risk_controller import RiskController
from src.intelligence.strategy_engine import StrategyEngine
from src.utils.api_client import AsyncBingXClient
from src.core.scanner.market_scanner import MarketScanner
from src.core.executor.trade_executor import TradeExecutor
from src.core.exit.exit_manager import ExitManager
from src.config.settings import Settings


class TradingEngine:
    """Полностью автономный торговый движок с адаптивностью."""

    def __init__(self, settings: Settings, logger: BotLogger = None):
        self.settings = settings
        self.logger = logger or BotLogger("TradingEngine")
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()
        self._paused = False
        self._state = "STOPPED"
        self._update_callbacks: List[callable] = []
        self._start_time = None
        self._iteration_count = 0
        self._error_count = 0
        self._last_successful_scan = 0
        self._consecutive_api_errors = 0
        self._api_backoff_until = 0

        # API Client
        self.client = AsyncBingXClient(
            api_key=settings.get("api_key", ""),
            api_secret=settings.get("api_secret", ""),
            demo_mode=settings.get("demo_mode", True),
            settings=settings.data,
        )
        self.logger.info(f"🔑 API клиент инициализирован (Demo: {settings.get('demo_mode', True)})")
        self.logger.log_state("api_client", {"demo_mode": settings.get("demo_mode", True), "base_url": self.client.base_url})

        # Components
        self.data_fetcher = DataFetcher(self.client, self.logger, settings.data)
        self.risk_manager = RiskManager(self.client, settings.data)
        self.order_manager = OrderManager(self.client, settings, self.logger)
        self.risk_controller = RiskController(self.logger, settings.data)
        self.strategy_engine = StrategyEngine(self.logger, settings)
        self.scanner = MarketScanner(settings, self.logger, self.data_fetcher, self.risk_controller, self.strategy_engine)
        self.executor = TradeExecutor(settings, self.logger, self.order_manager, self.risk_manager, self.risk_controller)
        self.exit_manager = ExitManager(
            settings=settings, logger=self.logger, data_fetcher=self.data_fetcher,
            risk_manager=self.risk_manager, risk_controller=self.risk_controller,
            strategy_engine=self.strategy_engine, order_manager=self.order_manager,
            sqlite_history=None,
        )

        # Notifiers
        self.telegram = None
        self.discord = None
        self._init_notifiers()

        # Balances
        self.balance = float(settings.get("virtual_balance", 100.0))
        self.real_balance = 0.0
        self._last_balance_update = 0

        self.open_positions: Dict[str, Position] = {}
        self.last_prices: Dict[str, float] = {}

        self.scan_interval = int(settings.get("scan_interval_minutes", 5)) * 60
        self.last_scan_time = 0.0
        self.force_scan = False
        self.max_positions = int(settings.get("max_positions", 2))

        self.daily_profit_target = float(settings.get("daily_profit_target_percent", 5.0))
        self.daily_target_reached = False

        self._force_scan_event = asyncio.Event()
        self.consecutive_losses = 0
        self._last_status_update = 0

        # Adaptive parameters
        self._adaptive_leverage = int(settings.get("max_leverage", 10))
        self._adaptive_risk = float(settings.get("max_risk_per_trade", 1.0))
        self._adaptive_scan_interval = self.scan_interval

        self.logger.info("✅ Движок инициализирован")

    def _init_notifiers(self):
        """Инициализирует уведомления."""
        if self.settings.get("telegram_enabled"):
            try:
                from src.notifications.telegram_notifier import TelegramNotifier
                self.telegram = TelegramNotifier(
                    bot_token=self.settings.get("telegram_bot_token", ""),
                    chat_id=self.settings.get("telegram_chat_id", ""),
                    logger=self.logger,
                )
                self.logger.info("📱 Telegram уведомления активны")
            except Exception as e:
                self.logger.warning(f"Telegram не инициализирован: {e}")

        if self.settings.get("discord_enabled"):
            try:
                from src.notifications.discord_notifier import DiscordNotifier
                self.discord = DiscordNotifier(
                    webhook_url=self.settings.get("discord_webhook_url", ""),
                    logger=self.logger,
                )
                self.logger.info("💬 Discord уведомления активны")
            except Exception as e:
                self.logger.warning(f"Discord не инициализирован: {e}")

    @property
    def running(self) -> bool:
        return self._running

    def is_running(self) -> bool:
        return self._running and not self._paused

    def get_status(self) -> dict:
        total_pnl = sum(p.unrealized_pnl for p in self.open_positions.values())
        uptime = 0
        if self._start_time:
            uptime = (datetime.now() - self._start_time).total_seconds()
        return {
            "state": self._state,
            "running": self._running,
            "paused": self._paused,
            "balance": self.balance,
            "real_balance": self.real_balance,
            "positions": len(self.open_positions),
            "pnl": total_pnl,
            "daily_pnl": getattr(self.risk_manager, "daily_pnl", 0),
            "consecutive_losses": getattr(self.risk_manager, "consecutive_losses", 0),
            "uptime_seconds": uptime,
            "iterations": self._iteration_count,
            "errors": self._error_count,
            "adaptive_leverage": self._adaptive_leverage,
            "adaptive_risk": self._adaptive_risk,
            "last_scan": self.last_scan_time,
        }

    def set_ui_callback(self, callback: callable):
        self._update_callbacks.append(callback)

    def set_update_callback(self, callback: callable):
        self._update_callbacks.append(callback)

    def _notify_update(self, data: dict):
        for cb in self._update_callbacks:
            try:
                cb(data)
            except Exception as e:
                self.logger.debug(f"UI callback error: {e}")

    def start(self):
        if self._thread and self._thread.is_alive():
            self.logger.warning("Движок уже запущен")
            return
        self._running = True
        self._paused = False
        self._state = "RUNNING"
        self._stop_event.clear()
        self._start_time = datetime.now()
        self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._thread.start()
        self.logger.info("▶ Асинхронный торговый движок запущен")

    def stop(self):
        self._running = False
        self._paused = False
        self._state = "STOPPED"
        self._stop_event.set()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        self.logger.info("⏹ Торговый движок остановлен")

    def pause(self):
        self._paused = True
        self._state = "PAUSED"
        self.logger.info("⏸ Движок на паузе")

    def resume(self):
        self._paused = False
        self._state = "RUNNING"
        self.logger.info("▶ Движок возобновлён")

    def scan_now(self):
        self.force_scan = True
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._force_scan_event.set)

    def _run_async_loop(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self._loop = asyncio.get_event_loop()
        try:
            self._loop.run_until_complete(self._async_main())
        except Exception as e:
            if "Event loop stopped" not in str(e):
                self.logger.error(f"Критическая ошибка в event loop: {e}")
                self.logger.error(traceback.format_exc())

    async def _async_main(self):
        self.logger.info("🚀 Запуск главного цикла...")

        # Initial balance sync
        await self._update_real_balance_async()
        self._adapt_to_balance()

        if not self.settings.get("demo_mode"):
            if self.real_balance <= 0:
                self.logger.critical(
                    "❌ Реальный режим включен, но баланс фьючерсов = 0 USDT. "
                    "Переведите USDT на фьючерсный счёт BingX. "
                    "Бот не будет торговать."
                )
                if self.telegram:
                    self.telegram.send_sync("🚨 Бот остановлен: баланс фьючерсов = 0 USDT. Переведите средства на фьючерсный счёт.")
                self._running = False
                return
            else:
                self.logger.info(f"✅ Реальный баланс фьючерсов: {self.real_balance:.4f} USDT. Бот готов к торговле.")

        self.risk_controller.daily_start_balance = self.balance

        while self._running:
            try:
                if self._paused:
                    await asyncio.sleep(1)
                    continue

                # API backoff check
                if time.time() < self._api_backoff_until:
                    wait = self._api_backoff_until - time.time()
                    self.logger.info(f"⏳ API backoff: ожидание {wait:.0f}с")
                    await asyncio.sleep(min(wait, 10))
                    continue

                await asyncio.wait_for(self._run_iteration_async(), timeout=300.0)
                self._iteration_count += 1
                self._consecutive_api_errors = 0

            except asyncio.TimeoutError:
                self.logger.error("⏱ Итерация превысила таймаут (5 мин)")
                self._error_count += 1
            except Exception as e:
                self.logger.error(f"💥 Ошибка в главном цикле: {e}")
                self.logger.error(traceback.format_exc())
                self._error_count += 1
                await asyncio.sleep(10)

    async def _run_iteration_async(self):
        self.logger.debug(f"--- Итерация #{self._iteration_count} ---")

        # 1. Sync with exchange
        self.logger.debug("Синхронизация с биржей...")
        try:
            await self._sync_positions_with_exchange()
            await self._update_positions_prices_async()
            self.logger.log_state("positions", {
                "count": len(self.open_positions),
                "symbols": list(self.open_positions.keys()),
                "total_unrealized_pnl": sum(p.unrealized_pnl for p in self.open_positions.values()),
            })
        except Exception as e:
            self.logger.error(f"Ошибка синхронизации позиций: {e}")

        # 2. Update balance
        try:
            await self._update_real_balance_async()
        except Exception as e:
            self.logger.warning(f"Ошибка обновления баланса: {e}")

        # 3. Check exits
        self.logger.debug("Проверка условий выхода...")
        try:
            await self.exit_manager.check_all_positions(
                self.open_positions,
                get_ticker_func=self._sync_get_ticker,
                update_balance_func=self._update_virtual_balance_sync,
                save_history=True,
                telegram_notifier=self.telegram,
                discord_notifier=self.discord,
                current_balance=self.balance,
            )
        except Exception as e:
            self.logger.error(f"Ошибка проверки выходов: {e}")

        # 4. Check circuit breaker / drawdown
        if self.balance > 0:
            drawdown = self.risk_manager.daily_loss / self.balance * 100 if hasattr(self.risk_manager, "daily_loss") else 0
            if drawdown >= 20:
                self.logger.critical(f"🚨 АВАРИЙНАЯ ОСТАНОВКА! Просадка {drawdown:.1f}%")
                if self.telegram:
                    self.telegram.send_sync(f"🚨 АВАРИЙНАЯ ОСТАНОВКА! Просадка {drawdown:.1f}%")
                await self.emergency_close_all_async()
                self._running = False
                return

        # 5. Adaptive parameters
        self._adapt_to_market()

        # 6. Market scan
        now = time.time()
        if not self.force_scan and (now - self.last_scan_time < self._adaptive_scan_interval):
            await asyncio.sleep(5)
            return

        self.force_scan = False
        self.last_scan_time = now
        self._last_successful_scan = now

        can_scan, reason = self.risk_controller.check_circuit_breaker(self.balance)
        if not can_scan:
            self.logger.warning(f"⛔ Сканирование пропущено: {reason}")
            return

        if len(self.open_positions) >= self.max_positions:
            self.logger.debug("Лимит позиций достигнут, пропуск сканирования")
            return

        if self.daily_target_reached:
            self.logger.info("🎯 Дневная цель достигнута, торговля приостановлена")
            return

        self.logger.info("🔍 Запуск сканирования рынка...")
        self.logger.log_decision("scan_start", data={"balance": self.balance, "positions": len(self.open_positions)})

        candidates = await self.scanner.scan_async(
            self.balance,
            max_pairs=100,
            max_asset_price_ratio=0.5,
            ignore_session_check=True,
        )

        if not candidates:
            self.logger.info("📭 Подходящих сигналов не найдено")
            self.logger.log_decision("scan_empty", data={"filters": "adx/atr/volume/signal"})
            return

        self.logger.info(f"✅ Найдено {len(candidates)} кандидатов")

        for c in candidates:
            if len(self.open_positions) >= self.max_positions:
                break

            symbol = c.get("symbol", "")
            self.logger.info(f"📊 Рассмотрение: {symbol}")

            can_trade, reason = self.risk_manager.can_open_position(len(self.open_positions), self.balance)
            if not can_trade:
                self.logger.info(f"⛔ Торговля запрещена: {reason}")
                self.logger.log_decision("trade_rejected", symbol, {"reason": reason})
                continue

            # Execute trade
            pos = await self.executor.execute_trade_async(
                c, self.balance, self.open_positions,
                self.settings.get("trailing_stop_enabled", True),
                self.settings.get("trailing_stop_distance_percent", 1.5),
                self.telegram,
                0, 0, self.balance,
            )

            if pos:
                self.open_positions[pos.symbol] = pos
                self.risk_controller.register_position_open(pos.symbol)
                self.strategy_engine.last_trade_time = time.time()
                self.logger.log_decision("trade_opened", pos.symbol, pos.to_dict())
                self._notify_update({"type": "new_position", "data": pos.to_dict()})
                self.logger.info(
                    f"🟢 Позиция открыта: {pos.symbol} {pos.side.value} | "
                    f"Вход: {pos.entry_price:.4f} | Qty: {pos.quantity:.6f} | "
                    f"SL: {pos.stop_loss_price:.4f} | TP: {pos.take_profit_price:.4f}"
                )
            else:
                self.logger.log_decision("trade_failed", symbol, {"reason": "executor returned None"})

        self._notify_update({"type": "status", "data": self.get_status()})

    def _adapt_to_balance(self):
        """Адаптирует параметры под размер депозита."""
        balance = self.real_balance if not self.settings.get("demo_mode") else self.balance
        if balance <= 0:
            return

        old_lev = self._adaptive_leverage
        old_risk = self._adaptive_risk
        old_atr = getattr(self.scanner, "current_min_atr", 1.0)

        # Micro accounts (< $100)
        if balance < 100:
            self._adaptive_leverage = min(20, int(self.settings.get("max_leverage", 10)))
            self._adaptive_risk = min(2.0, float(self.settings.get("max_risk_per_trade", 1.0)))
            self._adaptive_scan_interval = max(60, self.scan_interval // 2)
            # Lower ATR for micro accounts to find more opportunities
            self.scanner.current_min_atr = max(0.15, float(self.settings.get("min_atr_percent", 0.5)) * 0.5)
            self.scanner.current_min_adx = max(8.0, float(self.settings.get("min_adx", 10)) * 0.8)
            self.scanner.current_min_signal = max(0.15, float(self.settings.get("min_signal_strength", 0.25)) * 0.7)
            self.scanner.current_min_volume = max(20000, float(self.settings.get("min_volume_24h_usdt", 50000)) * 0.5)
        # Small accounts ($100 - $1000)
        elif balance < 1000:
            self._adaptive_leverage = min(15, int(self.settings.get("max_leverage", 10)))
            self._adaptive_risk = float(self.settings.get("max_risk_per_trade", 1.0))
            self._adaptive_scan_interval = self.scan_interval
            self.scanner.current_min_atr = max(0.3, float(self.settings.get("min_atr_percent", 0.5)) * 0.8)
            self.scanner.current_min_adx = max(10.0, float(self.settings.get("min_adx", 10)) * 0.9)
            self.scanner.current_min_signal = max(0.2, float(self.settings.get("min_signal_strength", 0.25)) * 0.85)
            self.scanner.current_min_volume = max(30000, float(self.settings.get("min_volume_24h_usdt", 50000)) * 0.7)
        # Medium accounts ($1000 - $10000)
        elif balance < 10000:
            self._adaptive_leverage = min(10, int(self.settings.get("max_leverage", 10)))
            self._adaptive_risk = min(1.5, float(self.settings.get("max_risk_per_trade", 1.0)))
            self._adaptive_scan_interval = self.scan_interval
            self.scanner.current_min_atr = float(self.settings.get("min_atr_percent", 0.5))
            self.scanner.current_min_adx = float(self.settings.get("min_adx", 10))
            self.scanner.current_min_signal = float(self.settings.get("min_signal_strength", 0.25))
            self.scanner.current_min_volume = float(self.settings.get("min_volume_24h_usdt", 50000))
        # Large accounts (>$10000)
        else:
            self._adaptive_leverage = min(5, int(self.settings.get("max_leverage", 10)))
            self._adaptive_risk = min(1.0, float(self.settings.get("max_risk_per_trade", 1.0)))
            self._adaptive_scan_interval = self.scan_interval * 2
            self.scanner.current_min_atr = float(self.settings.get("min_atr_percent", 0.5)) * 1.2
            self.scanner.current_min_adx = float(self.settings.get("min_adx", 10)) * 1.1
            self.scanner.current_min_signal = float(self.settings.get("min_signal_strength", 0.25)) * 1.1
            self.scanner.current_min_volume = float(self.settings.get("min_volume_24h_usdt", 50000)) * 1.5

        if (old_lev != self._adaptive_leverage or old_risk != self._adaptive_risk or 
            old_atr != self.scanner.current_min_atr):
            self.logger.info(
                f"🔄 Адаптация под депозит ${balance:.2f}: "
                f"плечо {old_lev}x → {self._adaptive_leverage}x, "
                f"риск {old_risk}% → {self._adaptive_risk}%, "
                f"ATR {old_atr:.2f}% → {self.scanner.current_min_atr:.2f}%, "
                f"ADX {self.scanner.current_min_adx:.1f}, "
                f"Signal {self.scanner.current_min_signal:.2f}, "
                f"Vol {self.scanner.current_min_volume:,.0f}"
            )
            self.logger.log_state("adaptive_params", {
                "balance": balance,
                "leverage": self._adaptive_leverage,
                "risk": self._adaptive_risk,
                "atr": self.scanner.current_min_atr,
                "adx": self.scanner.current_min_adx,
                "signal": self.scanner.current_min_signal,
                "volume": self.scanner.current_min_volume,
            })

    def _adapt_to_market(self):
        """Адаптирует параметры под рыночные условия."""
        # If many consecutive empty scans, relax filters
        if hasattr(self.scanner, "empty_scans_count"):
            if self.scanner.empty_scans_count >= 5:
                self.logger.info("📉 Рынок спокойный — параметры адаптированы")

    async def _update_real_balance_async(self):
        """Обновляет реальный баланс с обработкой ошибок."""
        try:
            account = await self.client.get_account_info()
            if account and "balance" in account:
                self.real_balance = float(account["balance"])
                if not self.settings.get("demo_mode"):
                    self.balance = self.real_balance
                self._last_balance_update = time.time()
                self.logger.info(
                    f"💰 Баланс обновлён: {self.real_balance:.4f} USDT "
                    f"(available: {account.get('available', 0):.4f}, "
                    f"used: {account.get('used', 0):.4f}, "
                    f"equity: {account.get('equity', 0):.4f})"
                )
                self.logger.log_state("balance", {
                    "total": self.real_balance,
                    "available": account.get("available", 0),
                    "used": account.get("used", 0),
                    "equity": account.get("equity", 0),
                    "unrealized": account.get("unrealizedProfit", 0),
                })
            else:
                if not self.settings.get("demo_mode"):
                    self.logger.warning(f"⚠️ Не удалось получить баланс: {account}")
                    self._consecutive_api_errors += 1
        except Exception as e:
            self._consecutive_api_errors += 1
            self.logger.error(f"❌ Ошибка получения баланса: {e}")
            if self._consecutive_api_errors >= 5:
                self.logger.critical("🚨 Слишком много ошибок API — активация backoff")
                self._api_backoff_until = time.time() + 60
                self._consecutive_api_errors = 0

    async def _sync_positions_with_exchange(self):
        """Сверяет позиции с биржей."""
        if self.settings.get("demo_mode"):
            return

        try:
            exchange_positions = await self.client.get_positions()
        except Exception as e:
            self.logger.error(f"Ошибка получения позиций с биржи: {e}")
            return

        exchange_symbols = set()
        for p in exchange_positions:
            amt = float(p.get("positionAmt", 0))
            if amt != 0:
                sym = p.get("symbol", "").replace("-USDT", "/USDT")
                exchange_symbols.add(sym)

        for sym in list(self.open_positions.keys()):
            if sym not in exchange_symbols:
                pos = self.open_positions[sym]
                self.logger.info(f"🏁 Позиция {sym} закрыта на бирже (возможно SL/TP)")
                self.exit_manager.record_exchange_tp_close(sym, pos, pos.current_price, 0.0)
                del self.open_positions[sym]
                self.risk_controller.register_position_close(sym)
                self._notify_update({"type": "position_closed", "data": pos.to_dict()})

    async def _update_positions_prices_async(self):
        """Обновляет цены для открытых позиций."""
        if not self.open_positions:
            return

        tasks = []
        for symbol, pos in self.open_positions.items():
            tasks.append(self._fetch_price_update(symbol, pos))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _fetch_price_update(self, symbol: str, pos: Position):
        try:
            ticker = await self.client.get_ticker(symbol.replace("/", "-"))
            if ticker and "lastPrice" in ticker:
                price = float(ticker["lastPrice"])
                self.last_prices[symbol] = price
                pos.update_market_price(price)
        except Exception as e:
            self.logger.debug(f"Ошибка обновления цены {symbol}: {e}")

    def _sync_get_ticker(self, symbol: str) -> Dict:
        if symbol in self.last_prices:
            return {"lastPrice": self.last_prices[symbol]}
        return {}

    def _update_virtual_balance_sync(self, pnl: float, strategy_type: str = None):
        if self.settings.get("demo_mode"):
            self.balance += pnl
            self.settings.set("virtual_balance", self.balance)

        if hasattr(self.risk_controller, "add_pnl"):
            self.risk_controller.add_pnl(pnl)
        if hasattr(self.risk_manager, "update_pnl"):
            self.risk_manager.update_pnl(pnl)
        if hasattr(self.strategy_engine, "record_trade_result"):
            self.strategy_engine.record_trade_result(pnl)

        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        # Re-adapt after significant PnL change
        if abs(pnl) > self.balance * 0.05:
            self._adapt_to_balance()

    async def emergency_close_all_async(self):
        """Экстренное закрытие всех позиций."""
        self.logger.critical("🛑 ЗАПУЩЕНО ЭКСТРЕННОЕ ЗАКРЫТИЕ ПОЗИЦИЙ!")
        for sym, pos in list(self.open_positions.items()):
            try:
                success = await self.executor.close_position_async(sym, pos.side, pos.quantity)
                if success:
                    del self.open_positions[sym]
                    self.logger.info(f"✅ Экстренно закрыт {sym}")
            except Exception as e:
                self.logger.error(f"❌ Ошибка закрытия {sym}: {e}")
