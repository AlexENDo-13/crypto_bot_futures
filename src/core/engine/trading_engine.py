#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TradingEngine — thread-safe торговый движок.
"""
import asyncio
import time
import logging
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.config.settings import Settings
from src.core.logger import BotLogger
from src.core.trading.position import Position, OrderSide
from src.core.market.data_fetcher import DataFetcher
from src.core.scanner.market_scanner import MarketScanner
from src.core.executor.trade_executor import TradeExecutor
from src.core.exit.exit_manager import ExitManager
from src.core.risk.risk_manager import RiskManager
from src.core.risk.risk_controller import RiskController
from src.core.trading.order_manager import OrderManager
from src.intelligence.strategy_engine import StrategyEngine

logger = logging.getLogger("TradingEngine")

class TradingEngine:
    def __init__(self, settings: Settings, logger: BotLogger, api_client, telegram=None):
        self.settings = settings
        self.logger = logger
        self.api_client = api_client
        self.telegram = telegram
        self.running = False
        self._task = None
        self._lock = threading.Lock()

        self.order_manager = OrderManager(api_client, logger)
        self.risk_manager = RiskManager(api_client, settings.to_dict())
        self.risk_controller = RiskController(logger, settings.to_dict())
        self.data_fetcher = DataFetcher(api_client, logger, settings.to_dict())
        self.strategy_engine = StrategyEngine(logger, settings)
        self.market_scanner = MarketScanner(settings, logger, self.data_fetcher, self.risk_controller, self.strategy_engine)
        self.trade_executor = TradeExecutor(settings, logger, self.order_manager, self.risk_manager, self.risk_controller)
        self.exit_manager = ExitManager(settings, logger, api_client, self.risk_manager)

        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Dict] = []
        self.balance = 0.0
        self.start_balance = 0.0
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.last_scan_time = 0
        self.scan_interval = settings.get("scan_interval_minutes", 5) * 60
        self._balance_fetch_failures = 0
        self._max_balance_failures = 5
        self._last_scan_result: List[Dict] = []
        self._api_latency_ms = 0.0
        self._last_error = ""
        self._total_trades = 0
        self._winning_trades = 0
        self._positions_hash = ""  # для отслеживания изменений
        self._history_hash = ""
        self._signals_hash = ""

    async def start(self):
        self.running = True
        self.logger.info("🚀 Запуск главного цикла...")

        for attempt in range(3):
            try:
                bal_info = await self.risk_manager.get_account_balance()
                self.balance = bal_info.get("total_equity", 0)
                self.start_balance = self.balance
                if self.balance > 0:
                    self.logger.info(f"💰 Баланс обновлён: {self.balance:.4f} USDT")
                    self.logger.log_state("balance", {
                        "total": self.balance, "available": bal_info.get("available_balance", self.balance),
                        "used": bal_info.get("used", 0), "equity": bal_info.get("equity", self.balance),
                        "unrealized": bal_info.get("unrealizedProfit", 0),
                    })
                    self._balance_fetch_failures = 0
                    break
                else:
                    self.logger.warning(f"⚠️ Баланс = 0 (попытка {attempt + 1}/3)")
                    if attempt < 2:
                        await asyncio.sleep(2)
            except Exception as e:
                self.logger.error(f"❌ Ошибка получения баланса (попытка {attempt + 1}/3): {e}")
                if attempt < 2:
                    await asyncio.sleep(2)

        if self.balance <= 0:
            self.logger.warning("⚠️ Баланс не получен. Бот продолжит работу и будет повторять попытки.")

        await self._sync_positions()
        self._task = asyncio.create_task(self._main_loop())

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.logger.info("⏹ Торговый движок остановлен")

    async def _main_loop(self):
        while self.running:
            try:
                loop_start = time.time()
                await self._update_balance()
                await self._sync_positions()
                await self._update_positions_pnl()
                await self.exit_manager.check_exits(self.positions, self._on_position_closed)

                now = time.time()
                if now - self.last_scan_time >= self.scan_interval:
                    self.last_scan_time = now
                    await self._scan_and_trade()

                self.logger.log_state("positions", {
                    "count": len(self.positions),
                    "symbols": list(self.positions.keys()),
                    "total_unrealized_pnl": sum(p.unrealized_pnl for p in self.positions.values()),
                })

                self._api_latency_ms = (time.time() - loop_start) * 1000
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._last_error = str(e)
                self.logger.error(f"Ошибка в главном цикле: {e}")
                await asyncio.sleep(10)

    async def _update_balance(self):
        try:
            bal_info = await self.risk_manager.get_account_balance()
            new_balance = bal_info.get("total_equity", self.balance)
            with self._lock:
                if new_balance > 0:
                    self.balance = new_balance
                    self._balance_fetch_failures = 0
                else:
                    self._balance_fetch_failures += 1
        except Exception as e:
            with self._lock:
                self._balance_fetch_failures += 1
            self.logger.error(f"Ошибка обновления баланса: {e}")

    async def _sync_positions(self):
        try:
            exchange_positions = await self.api_client.get_positions()
            current_symbols = {p["symbol"].replace("-", "/") for p in exchange_positions}

            with self._lock:
                for sym in list(self.positions.keys()):
                    if sym.replace("/", "-") not in {p["symbol"] for p in exchange_positions}:
                        pos = self.positions.pop(sym)
                        self.risk_manager.register_position_close(pos)
                        self.risk_controller.register_position_close(sym)
                        self._record_closed_position(pos, "EXCHANGE_CLOSE")
                        self.logger.info(f"📤 Позиция {sym} закрыта на бирже")

                for p in exchange_positions:
                    symbol = p["symbol"].replace("-", "/")
                    amt = float(p.get("positionAmt", 0))
                    if amt == 0:
                        continue
                    if symbol not in self.positions:
                        side = OrderSide.BUY if amt > 0 else OrderSide.SELL
                        qty = abs(amt)
                        entry_price = float(p.get("avgPrice", p.get("entryPrice", 0)))
                        leverage = int(p.get("leverage", 1))
                        if entry_price <= 0:
                            self.logger.warning(f"⚠️ {symbol}: entry_price=0 при восстановлении, пропускаем")
                            continue
                        try:
                            pos = Position(symbol=symbol, side=side, quantity=qty, entry_price=entry_price, leverage=leverage)
                            self.positions[symbol] = pos
                            self.risk_manager.register_position_open(pos)
                            self.risk_controller.register_position_open(symbol)
                            self.logger.info(f"📥 Позиция {symbol} восстановлена: {side.value} {qty} @ {entry_price}")
                        except Exception as e:
                            self.logger.error(f"❌ Ошибка восстановления {symbol}: {e}")
                    else:
                        pos = self.positions[symbol]
                        pos.quantity = abs(float(p.get("positionAmt", pos.quantity)))
                        pos.leverage = int(p.get("leverage", pos.leverage))
        except Exception as e:
            self.logger.error(f"Ошибка синхронизации позиций: {e}")

    async def _update_positions_pnl(self):
        for symbol, pos in list(self.positions.items()):
            try:
                ticker = await self.data_fetcher.get_ticker_data(symbol)
                if ticker:
                    mark_price = ticker.get("markPrice", ticker.get("lastPrice", 0))
                    if mark_price > 0:
                        pos.update_market_price(mark_price)
            except Exception as e:
                self.logger.debug(f"Ошибка обновления PnL {symbol}: {e}")

    def _on_position_closed(self, pos: Position):
        with self._lock:
            self._record_closed_position(pos, pos.exit_reason.value if pos.exit_reason else "UNKNOWN")
            self.risk_manager.update_pnl(pos.realized_pnl)
            if pos.realized_pnl > 0:
                self._winning_trades += 1
            self._total_trades += 1
            self.strategy_engine.record_trade_result(pos.realized_pnl)

    def _record_closed_position(self, pos: Position, reason: str):
        self.closed_positions.append({
            "symbol": pos.symbol, "side": pos.side.value,
            "entry_price": pos.entry_price, "exit_price": pos.exit_price,
            "quantity": pos.quantity, "leverage": pos.leverage,
            "realized_pnl": pos.realized_pnl,
            "realized_pnl_percent": getattr(pos, "realized_pnl_percent", 0.0),
            "exit_reason": reason,
            "entry_time": pos.entry_time.isoformat() if pos.entry_time else None,
            "exit_time": pos.exit_time.isoformat() if pos.exit_time else None,
            "strategy": pos.strategy,
        })
        if len(self.closed_positions) > 200:
            self.closed_positions = self.closed_positions[-200:]

    async def _scan_and_trade(self):
        self.logger.info("🔍 Запуск сканирования рынка...")
        self.logger.log_decision("scan_start", None, {"balance": self.balance, "positions": len(self.positions)})

        ok, reason = self.risk_manager.can_open_position(len(self.positions), self.balance)
        if not ok:
            self.logger.info(f"⛔ Сканирование пропущено: {reason}")
            return

        candidates = await self.market_scanner.scan_async(
            balance=self.balance, max_pairs=100,
            ignore_session_check=self.settings.get("force_ignore_session", True),
        )
        with self._lock:
            self._last_scan_result = candidates

        if not candidates:
            self.logger.info("📭 Подходящих сигналов не найдено")
            self.logger.log_decision("scan_empty", None, {"filters": "adx/atr/volume/signal"})
            return

        candidates = self.risk_controller.filter_signals(candidates, list(self.positions.values()), self.balance)
        if not candidates:
            self.logger.info("📭 Сигналы отфильтрованы риск-контроллером")
            return

        for candidate in candidates[:1]:
            try:
                pos = await self.trade_executor.execute_trade_async(
                    candidate=candidate, balance=self.balance, open_positions=self.positions,
                    trailing_enabled=self.settings.get("trailing_stop_enabled", True),
                    trailing_distance=self.settings.get("trailing_stop_distance_percent", 2.0),
                    telegram=self.telegram, daily_pnl=self.daily_pnl, weekly_pnl=self.weekly_pnl,
                    start_balance=self.start_balance,
                )
                if pos:
                    with self._lock:
                        self.positions[pos.symbol] = pos
                    self.risk_controller.register_position_open(pos.symbol)
            except Exception as e:
                self.logger.error(f"Ошибка исполнения сделки: {e}")

    def get_stats(self) -> dict:
        with self._lock:
            total_pnl = sum(p["realized_pnl"] for p in self.closed_positions)
            win_rate = (self._winning_trades / self._total_trades * 100) if self._total_trades > 0 else 0
            return {
                "balance": self.balance,
                "start_balance": self.start_balance,
                "positions_count": len(self.positions),
                "daily_pnl": self.daily_pnl,
                "weekly_pnl": self.weekly_pnl,
                "total_trades": self._total_trades,
                "winning_trades": self._winning_trades,
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "api_latency_ms": self._api_latency_ms,
                "last_error": self._last_error,
                "risk_stats": self.risk_manager.get_daily_stats(),
                "risk_controller_stats": self.risk_controller.get_stats(),
                "strategy_stats": self.strategy_engine.get_recent_performance(),
                "scan_result_count": len(self._last_scan_result),
                "positions_hash": hash(tuple(p.to_dict().get("current_price", 0) for p in self.positions.values())),
                "history_hash": hash(tuple(h.get("exit_time", "") for h in self.closed_positions[-10:])),
                "signals_hash": hash(tuple(s.get("symbol", "") for s in self._last_scan_result)),
            }

    def get_closed_positions(self) -> List[Dict]:
        with self._lock:
            return list(reversed(self.closed_positions))

    def get_open_positions(self) -> List[Dict]:
        with self._lock:
            return [p.to_dict() for p in self.positions.values()]

    def get_last_scan_signals(self) -> List[Dict]:
        with self._lock:
            return list(self._last_scan_result)
