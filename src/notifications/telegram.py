"""
Telegram Notifications - Send trade alerts and status updates.
"""
import requests
from typing import Optional
from src.core.config import get_config
from src.core.logger import get_logger

logger = get_logger()

class TelegramNotifier:
    def __init__(self):
        cfg = get_config().notifications
        self.enabled = cfg.telegram_enabled
        self.token = cfg.telegram_bot_token
        self.chat_id = cfg.telegram_chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send(self, message: str, parse_mode: str = "HTML"):
        if not self.enabled or not self.token or not self.chat_id:
            return
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                logger.error("Telegram send failed: %s", resp.text)
        except Exception as e:
            logger.error("Telegram error: %s", e)

    def send_trade(self, symbol: str, side: str, pnl: float, reason: str):
        emoji = "🟢" if pnl >= 0 else "🔴"
        msg = f"{emoji} <b>{symbol}</b> {side} closed\n"
        msg += f"PnL: <b>{pnl:+.2f}</b> USDT\n"
        msg += f"Reason: {reason}"
        self.send(msg)

    def send_signal(self, symbol: str, direction: str, confidence: float, strategy: str):
        emoji = "🚀" if direction == "LONG" else "🔻"
        msg = f"{emoji} <b>Signal</b>: {symbol} {direction}\n"
        msg += f"Confidence: {confidence:.2f}\n"
        msg += f"Strategy: {strategy}"
        self.send(msg)

    def send_alert(self, title: str, message: str):
        msg = f"⚠️ <b>{title}</b>\n{message}"
        self.send(msg)
