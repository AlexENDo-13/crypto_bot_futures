#!/usr/bin/env python3
import logging, asyncio
try:
    from telegram import Bot
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False

logger = logging.getLogger("TelegramNotifier")

class TelegramNotifier:
    def __init__(self, token, chat_id, proxy=None):
        self.token = token; self.chat_id = chat_id; self.proxy = proxy; self.bot = None
        if HAS_TELEGRAM and token:
            try: self.bot = Bot(token=token)
            except Exception as e: logger.error(f"Ошибка Telegram: {e}")
    async def send(self, message):
        if not self.bot or not self.chat_id: return
        try: await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode="Markdown")
        except Exception as e: logger.error(f"Ошибка отправки Telegram: {e}")
    def send_sync(self, message):
        if not self.bot or not self.chat_id: return
        try: asyncio.create_task(self.send(message))
        except Exception: pass
