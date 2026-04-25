#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TradingEngine v5.1 — Self-healing adaptive engine. Never stops, auto-recovers."""
import asyncio
import time
import logging
import threading
import csv
import os
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
        self._stop_event = asyncio.Event()

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
        self._loop_count = 0
        self._start_time = time.time()
        self._health_status = "OK"
        self._emergency = False
        self._csv_path = os.path.join("logs", "trades.csv")
        self._ensure_csv()

        # Adaptive parameters
        self._adaptive_scan_interval = self.scan_interval
        self._consecutive_scan_errors = 0
        self._consecutive_empty_scans = 0
        self._api_error_streak = 0
        self._last_successful_scan = time.time()
        self._market_volatility = 0.5  # 0-1 scale
        self._recovery_mode = False

    def _ensure_csv(self):
        if not os.path.exists(self._csv_path):
            os.makedirs("logs", exist_ok=True)
            with open(self._csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["time", "symbol", "side", "entry", "exit", "qty", "leverage", "pnl", "pnl_pct", "reason"])

    async def start(self):
        self.running = True
        self._stop_event.clear()
        self.logger.info("Starting TradingEngine v5.1 (Self-Healing)...")

        # Try to get balance with multiple attempts and fallbacks
        for attempt in range(5):
            try:
                bal_info = await self.risk_manager.get_account_balance()
                self.balance = bal_info.get("total_equity", 0)
                self.start_balance = self.balance
                if self.balance > 0:
                    self.logger.info(f"Balance: {self.balance:.4f} USDT")
                    self._balance_fetch_failures = 0
                    break
                else:
                    self.logger.warning(f"Balance = 0 (attempt {attempt + 1}/5)")
                    if attempt < 4:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
            except Exception as e:
                self.logger.error(f"Balance error (attempt {attempt + 1}/5): {e}")
                if attempt < 4:
                    await asyncio.sleep(2 ** attempt)

        if self.balance <= 0:
            self.logger.warning("Balance not received. Running in monitoring mode.")
            # Don't stop - continue in monitoring mode

        await self._sync_positions()
        self._task = asyncio.create_task(self._main_loop())
        self.logger.info("Engine started - self-healing active")

    async def stop(self):
        self.running = False
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.logger.info("TradingEngine stopped")

    async def emergency_stop(self):
        self._emergency = True
        self.running = False
        self._stop_event.set()
        self.logger.critical("EMERGENCY STOP: Closing all positions...")
        for symbol, pos in list(self.positions.items()):
            try:
                await self.trade_executor.close_position_async(symbol, pos.side, pos.quantity)
                pos.close(pos.current_price if pos.current_price > 0 else pos.entry_price, "EMERGENCY")
                self._record_closed_position(pos, "EMERGENCY")
                self.risk_manager.update_pnl(pos.realized_pnl)
            except Exception as e:
                self.logger.error(f"Emergency close error {symbol}: {e}")
        self.positions.clear()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.logger.critical("EMERGENCY STOP completed")

    async def _main_loop(self):
        while self.running and not self._stop_event.is_set():
            try:
                loop_start = time.time()
                self._loop_count += 1

                # Core operations with individual error handling
                try:
                    await self._update_balance()
                except Exception as e:
                    self.logger.error(f"Balance update error (non-critical): {e}")

                try:
                    await self._sync_positions()
                except Exception as e:
                    self.logger.error(f"Position sync error (non-critical): {e}")

                try:
                    await self._update_positions_pnl()
                except Exception as e:
                    self.logger.error(f"PnL update error (non-critical): {e}")

                try:
                    await self.exit_manager.check_exits(self.positions, self._on_position_closed)
                except Exception as e:
                    self.logger.error(f"Exit check error (non-critical): {e}")

                # Adaptive scan interval
                now = time.time()
                self._adapt_scan_interval()

                if now - self.last_scan_time >= self._adaptive_scan_interval:
                    self.last_scan_time = now
                    try:
                        await self._scan_and_trade()
                        self._consecutive_scan_errors = 0
                        self._api_error_streak = max(0, self._api_error_streak - 1)
                    except Exception as e:
                        self._consecutive_scan_errors += 1
                        self._api_error_streak += 1
                        self.logger.error(f"Scan error (non-critical, streak={self._api_error_streak}): {e}")
                        # Increase interval on errors
                        self._adaptive_scan_interval = min(300, self._adaptive_scan_interval * 1.5)

                # Log state
                try:
                    self.logger.log_state("positions", {
                        "count": len(self.positions),
                        "symbols": list(self.positions.keys()),
                        "total_unrealized_pnl": sum(p.unrealized_pnl for p in self.positions.values()),
                        "loop": self._loop_count,
                        "uptime": time.time() - self._start_time,
                        "scan_interval": self._adaptive_scan_interval,
                        "api_health": self.api_client.get_health(),
                    })
                except Exception:
                    pass

                self._api_latency_ms = (time.time() - loop_start) * 1000
                self._health_status = "OK" if self._api_error_streak < 3 else f"DEGRADED (errors: {self._api_error_streak})"

                # Sleep with early wake on stop
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._last_error = str(e)
                self._health_status = f"ERROR: {str(e)[:50]}"
                self.logger.error(f"Main loop error (recovering): {e}")
                # NEVER STOP - just sleep and continue
                await asyncio.sleep(10)

    def _adapt_scan_interval(self):
        """Adapt scan interval based on market conditions and errors."""
        base = self.scan_interval

        # More positions = slower scanning
        pos_count = len(self.positions)
        if pos_count >= self.settings.get("max_positions", 3):
            base *= 2.0
        elif pos_count > 0:
            base *= 1.3

        # API errors = slower scanning
        if self._api_error_streak > 0:
            base *= (1 + self._api_error_streak * 0.5)

        # Empty scans = faster scanning (market is quiet)
        if self._consecutive_empty_scans > 2:
            base *= 0.7

        # High volatility = faster scanning
        if self._market_volatility > 0.7:
            base *= 0.8

        self._adaptive_scan_interval = max(15, min(300, base))

    async def _update_balance(self):
        try:
            bal_info = await self.risk_manager.get_account_balance()
            new_balance = bal_info.get("total_equity", self.balance)
            with self._lock:
                if new_balance > 0:
                    self.balance = new_balance
                    self._balance_fetch_failures = 0
                    # Adapt risk based on balance
                    self._adapt_to_balance(new_balance)
                else:
                    self._balance_fetch_failures += 1
        except Exception as e:
            with self._lock:
                self._balance_fetch_failures += 1
            self.logger.error(f"Balance update error: {e}")

    def _adapt_to_balance(self, balance: float):
        """Adapt trading parameters based on balance size."""
        if balance < 50:
            # Micro account - minimal risk
            self.risk_manager.risk_per_trade = 0.5
            self.risk_manager.max_positions = 1
        elif balance < 200:
            # Small account
            self.risk_manager.risk_per_trade = 0.8
            self.risk_manager.max_positions = 2
        elif balance < 1000:
            # Medium account
            self.risk_manager.risk_per_trade = 1.0
            self.risk_manager.max_positions = 3
        elif balance < 5000:
            # Large account
            self.risk_manager.risk_per_trade = 1.5
            self.risk_manager.max_positions = 5
        else:
            # Whale account
            self.risk_manager.risk_per_trade = 2.0
            self.risk_manager.max_positions = 7

    async def _sync_positions(self):
        try:
            exchange_positions = await self.api_client.get_positions()
            current_symbols = {p.get("symbol", "").replace("-", "/") for p in exchange_positions if p.get("positionAmt", 0) != 0}

            with self._lock:
                # Remove closed positions
                for sym in list(self.positions.keys()):
                    if sym not in current_symbols:
                        pos = self.positions.pop(sym)
                        self.risk_manager.register_position_close(pos)
                        self.risk_controller.register_position_close(sym)
                        self._record_closed_position(pos, "EXCHANGE_CLOSE")
                        self.logger.info(f"Position {sym} closed on exchange")

                # Add new positions
                for p in exchange_positions:
                    symbol = p.get("symbol", "").replace("-", "/")
                    amt = float(p.get("positionAmt", 0))
                    if amt == 0:
                        continue
                    if symbol not in self.positions:
                        side = OrderSide.BUY if amt > 0 else OrderSide.SELL
                        qty = abs(amt)
                        entry_price = float(p.get("avgPrice", p.get("entryPrice", 0)))
                        leverage = int(p.get("leverage", 1))
                        if entry_price <= 0:
                            self.logger.warning(f"{symbol}: entry_price=0, skipping")
                            continue
                        try:
                            pos = Position(symbol=symbol, side=side, quantity=qty, entry_price=entry_price, leverage=leverage)
                            self.positions[symbol] = pos
                            self.risk_manager.register_position_open(pos)
                            self.risk_controller.register_position_open(symbol)
                            self.logger.info(f"Position {symbol} restored: {side.value} {qty} @ {entry_price}")
                        except Exception as e:
                            self.logger.error(f"Restore error {symbol}: {e}")
                    else:
                        pos = self.positions[symbol]
                        pos.quantity = abs(float(p.get("positionAmt", pos.quantity)))
                        pos.leverage = int(p.get("leverage", pos.leverage))
        except Exception as e:
            self.logger.error(f"Sync positions error: {e}")

    async def _update_positions_pnl(self):
        for symbol, pos in list(self.positions.items()):
            try:
                ticker = await self.data_fetcher.get_ticker_data(symbol)
                if ticker:
                    mark_price = ticker.get("markPrice", ticker.get("lastPrice", 0))
                    if mark_price > 0:
                        pos.update_market_price(mark_price)
            except Exception as e:
                self.logger.debug(f"PnL update error {symbol}: {e}")

    def _on_position_closed(self, pos: Position):
        with self._lock:
            self._record_closed_position(pos, pos.exit_reason.value if pos.exit_reason else "UNKNOWN")
            self.risk_manager.update_pnl(pos.realized_pnl)
            self.risk_controller.add_pnl(pos.realized_pnl)
            if pos.realized_pnl > 0:
                self._winning_trades += 1
            self._total_trades += 1
            self.strategy_engine.record_trade_result(pos.realized_pnl)
            self._append_csv(pos)

    def _append_csv(self, pos: Position):
        try:
            with open(self._csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.utcnow().isoformat(),
                    pos.symbol,
                    pos.side.value,
                    pos.entry_price,
                    pos.exit_price,
                    pos.initial_quantity,
                    pos.leverage,
                    pos.realized_pnl,
                    pos.realized_pnl_percent,
                    pos.exit_reason.value if pos.exit_reason else "",
                ])
        except Exception as e:
            self.logger.debug(f"CSV write error: {e}")

    def _record_closed_position(self, pos: Position, reason: str):
        self.closed_positions.append({
            "symbol": pos.symbol,
            "side": pos.side.value,
            "entry_price": pos.entry_price,
            "exit_price": pos.exit_price,
            "quantity": pos.quantity if pos.quantity > 0 else pos.initial_quantity,
            "leverage": pos.leverage,
            "realized_pnl": pos.realized_pnl,
            "realized_pnl_percent": getattr(pos, "realized_pnl_percent", 0.0),
            "exit_reason": reason,
            "entry_time": pos.entry_time.isoformat() if pos.entry_time else None,
            "exit_time": pos.exit_time.isoformat() if pos.exit_time else None,
            "strategy": pos.strategy,
            "partial_closes": pos.partial_closes,
        })
        if len(self.closed_positions) > 500:
            self.closed_positions = self.closed_positions[-500:]

    async def _scan_and_trade(self):
        self.logger.info("Starting market scan...")
        self.logger.log_decision("scan_start", None, {"balance": self.balance, "positions": len(self.positions)})

        ok, reason = self.risk_manager.can_open_position(len(self.positions), self.balance)
        if not ok:
            self.logger.info(f"Scan skipped: {reason}")
            return

        candidates = await self.market_scanner.scan_async(
            balance=self.balance, max_pairs=100,
            ignore_session_check=self.settings.get("force_ignore_session", True),
        )

        with self._lock:
            self._last_scan_result = candidates

        if not candidates:
            self._consecutive_empty_scans += 1
            self.logger.info(f"No signals found (empty streak: {self._consecutive_empty_scans})")
            self.logger.log_decision("scan_empty", None, {"filters": "adx/atr/volume/signal"})
            return

        self._consecutive_empty_scans = 0
        self._last_successful_scan = time.time()

        candidates = self.risk_controller.filter_signals(candidates, list(self.positions.values()), self.balance)
        if not candidates:
            self.logger.info("Signals filtered by risk controller")
            return

        for candidate in candidates:
            if len(self.positions) >= self.risk_manager.max_positions:
                self.logger.info("Max positions reached")
                break
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
                self.logger.error(f"Trade execution error (non-critical): {e}")

    def get_stats(self) -> dict:
        with self._lock:
            total_pnl = sum(p["realized_pnl"] for p in self.closed_positions)
            win_rate = (self._winning_trades / self._total_trades * 100) if self._total_trades > 0 else 0
            uptime = time.time() - self._start_time
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
                "health_status": self._health_status,
                "uptime_seconds": uptime,
                "loop_count": self._loop_count,
                "risk_stats": self.risk_manager.get_daily_stats(),
                "risk_controller_stats": self.risk_controller.get_stats(),
                "strategy_stats": self.strategy_engine.get_recent_performance(),
                "scan_result_count": len(self._last_scan_result),
                "scan_stats": self.market_scanner.get_scan_stats(),
                "fetch_health": self.data_fetcher.get_fetch_health(),
                "adaptive_interval": self._adaptive_scan_interval,
                "api_health": self.api_client.get_health(),
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

    def get_health(self) -> Dict[str, Any]:
        return {
            "status": self._health_status,
            "running": self.running,
            "uptime": time.time() - self._start_time,
            "loop_count": self._loop_count,
            "balance_failures": self._balance_fetch_failures,
            "positions": len(self.positions),
            "api_errors": self._api_error_streak,
            "adaptive_interval": self._adaptive_scan_interval,
        }
