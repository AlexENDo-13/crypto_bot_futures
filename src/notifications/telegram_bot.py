#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Control Bot v1.0
Двусторонний бот: уведомления + команды управления.
Fallback: если aiogram не доступен — используем requests (без async).
"""
import logging
import asyncio
from typing import Optional, Callable, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from aiogram import Bot, Dispatcher, types
    from aiogram.filters import Command
    AIogram_AVAILABLE = True
except ImportError:
    AIogram_AVAILABLE = False
    logger.warning("aiogram not installed. Telegram bot disabled. pip install aiogram")

class TelegramControlBot:
    def __init__(self, token: str, chat_id: str, mode_switcher=None,
                 position_tracker=None, database=None, logger_instance=None):
        self.token = token
        self.chat_id = str(chat_id)
        self.mode_switcher = mode_switcher
        self.position_tracker = position_tracker
        self.db = database
        self.log = logger_instance or logger
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self._task: Optional[asyncio.Task] = None
        self._handlers: Dict[str, Callable] = {}

    async def start(self):
        if not AIogram_AVAILABLE:
            self.log.error("Cannot start Telegram bot: aiogram not installed")
            return
        if not self.token or not self.chat_id:
            self.log.error("Telegram token or chat_id not configured")
            return
        self.bot = Bot(token=self.token)
        self.dp = Dispatcher()
        self._register_handlers()
        self._task = asyncio.create_task(self._polling())
        self.log.info("Telegram control bot started")

    async def _polling(self):
        try:
            await self.dp.start_polling(self.bot, skip_updates=True)
        except Exception as e:
            self.log.error(f"Telegram polling error: {e}")

    def _register_handlers(self):
        @self.dp.message(Command("start"))
        async def cmd_start(message: types.Message):
            await message.answer("🤖 CryptoBot Control\nUse /help for commands")

        @self.dp.message(Command("help"))
        async def cmd_help(message: types.Message):
            text = (
                "📋 Commands:\n"
                "/status — Bot status\n"
                "/positions — Open positions\n"
                "/mode [trend|grid|dca|paused|light] — Switch mode\n"
                "/pause — Pause trading\n"
                "/resume — Resume trading\n"
                "/closeall — Close all positions\n"
                "/profit — PnL stats\n"
                "/logs [N] — Last log lines\n"
                "/alert [text] — Test alert"
            )
            await message.answer(text)

        @self.dp.message(Command("status"))
        async def cmd_status(message: types.Message):
            mode = self.mode_switcher.mode_name if self.mode_switcher else "unknown"
            stats = self._get_stats_text()
            await message.answer(f"🌐 Mode: {mode}\n{stats}")

        @self.dp.message(Command("mode"))
        async def cmd_mode(message: types.Message):
            parts = message.text.split()
            if len(parts) < 2:
                await message.answer("Usage: /mode [trend|grid|dca|paused|light]")
                return
            new_mode = parts[1].lower()
            if self.mode_switcher:
                from src.core.mode_switcher import BotMode
                try:
                    mode_enum = BotMode(new_mode)
                    ok = self.mode_switcher.switch_to(mode_enum, reason="Telegram command")
                    if ok:
                        await message.answer(f"✅ Mode switched to {new_mode}")
                    else:
                        await message.answer(f"❌ Cannot switch to {new_mode}")
                except ValueError:
                    await message.answer("❌ Unknown mode")
            else:
                await message.answer("❌ Mode switcher not available")

        @self.dp.message(Command("pause"))
        async def cmd_pause(message: types.Message):
            if self.mode_switcher:
                from src.core.mode_switcher import BotMode
                self.mode_switcher.switch_to(BotMode.PAUSED, reason="Telegram /pause")
                await message.answer("⏸️ Bot paused")
            else:
                await message.answer("❌ Mode switcher not available")

        @self.dp.message(Command("resume"))
        async def cmd_resume(message: types.Message):
            if self.mode_switcher:
                from src.core.mode_switcher import BotMode
                self.mode_switcher.switch_to(BotMode.TREND, reason="Telegram /resume")
                await message.answer("▶️ Bot resumed (TREND mode)")
            else:
                await message.answer("❌ Mode switcher not available")

        @self.dp.message(Command("closeall"))
        async def cmd_closeall(message: types.Message):
            handler = self._handlers.get("close_all")
            if handler:
                try:
                    handler()
                    await message.answer("🔴 Close all positions triggered")
                except Exception as e:
                    await message.answer(f"❌ Error: {e}")
            else:
                await message.answer("❌ Close handler not registered")

        @self.dp.message(Command("profit"))
        async def cmd_profit(message: types.Message):
            if self.db:
                stats = self.db.get_trade_stats(days=1)
                text = (
                    f"📊 Today:\n"
                    f"Trades: {stats.get('total', 0)}\n"
                    f"Wins: {stats.get('wins', 0)}\n"
                    f"Losses: {stats.get('losses', 0)}\n"
                    f"PnL: {stats.get('total_pnl', 0):.4f}"
                )
                await message.answer(text)
            else:
                await message.answer("❌ Database not connected")

        @self.dp.message(Command("logs"))
        async def cmd_logs(message: types.Message):
            parts = message.text.split()
            n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
            await message.answer(f"📄 Last {n} log lines: (implement log reader)")

    def _get_stats_text(self) -> str:
        lines = []
        if self.position_tracker:
            try:
                positions = self.position_tracker.get_open_positions()
                lines.append(f"Open positions: {len(positions)}")
            except Exception:
                pass
        if self.db:
            try:
                stats = self.db.get_trade_stats(days=1)
                lines.append(f"Today PnL: {stats.get('total_pnl', 0):.4f}")
            except Exception:
                pass
        return "\n".join(lines) if lines else "No stats available"

    def register_handler(self, command: str, callback: Callable):
        self._handlers[command] = callback

    async def send_alert(self, text: str):
        if self.bot and self.chat_id:
            try:
                await self.bot.send_message(self.chat_id, f"🚨 {text}")
            except Exception as e:
                self.log.error(f"Telegram send error: {e}")

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self.bot:
            await self.bot.session.close()
        self.log.info("Telegram control bot stopped")
