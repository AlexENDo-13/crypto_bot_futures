"""
CryptoBot v7.0 - Notification System
Telegram, Discord, Email alerts with trade templates
"""
import logging
from typing import Dict, Optional
from dataclasses import dataclass

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False


@dataclass
class NotificationConfig:
    telegram_enabled: bool = False
    telegram_token: str = ""
    telegram_chat_id: str = ""
    discord_enabled: bool = False
    discord_webhook: str = ""
    email_enabled: bool = False
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_login: str = ""
    email_password: str = ""
    email_to: str = ""


class NotificationManager:
    """Multi-channel notification system."""

    def __init__(self, config: NotificationConfig = None):
        self.config = config or NotificationConfig()
        self.logger = logging.getLogger("CryptoBot.Notifications")

    def send(self, message: str, level: str = "INFO"):
        prefix = f"[{level}] "
        full_msg = prefix + message

        if self.config.telegram_enabled:
            self._send_telegram(full_msg)
        if self.config.discord_enabled:
            self._send_discord(full_msg)
        if self.config.email_enabled:
            self._send_email(full_msg, level)

    def _send_telegram(self, message: str):
        if not REQUESTS_OK or not self.config.telegram_token or not self.config.telegram_chat_id:
            return
        try:
            url = f"https://api.telegram.org/bot{self.config.telegram_token}/sendMessage"
            payload = {"chat_id": self.config.telegram_chat_id, "text": message, "parse_mode": "HTML"}
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                self.logger.warning(f"Telegram failed: {resp.status_code}")
        except Exception as e:
            self.logger.error(f"Telegram error: {e}")

    def _send_discord(self, message: str):
        if not REQUESTS_OK or not self.config.discord_webhook:
            return
        try:
            payload = {"content": message}
            resp = requests.post(self.config.discord_webhook, json=payload, timeout=10)
            if resp.status_code not in (200, 204):
                self.logger.warning(f"Discord failed: {resp.status_code}")
        except Exception as e:
            self.logger.error(f"Discord error: {e}")

    def _send_email(self, message: str, level: str):
        if not self.config.email_login or not self.config.email_password or not self.config.email_to:
            return
        try:
            import smtplib
            from email.mime.text import MIMEText
            msg = MIMEText(message)
            msg["Subject"] = f"CryptoBot: {level}"
            msg["From"] = self.config.email_login
            msg["To"] = self.config.email_to
            with smtplib.SMTP(self.config.email_smtp_host, self.config.email_smtp_port) as server:
                server.starttls()
                server.login(self.config.email_login, self.config.email_password)
                server.send_message(msg)
        except Exception as e:
            self.logger.error(f"Email error: {e}")

    def send_trade_open(self, symbol: str, side: str, price: float, size: float):
        msg = f"<b>OPEN</b> {symbol} {side} @ ${price:.4f} x {size:.4f}"
        self.send(msg, "TRADE")

    def send_trade_close(self, symbol: str, side: str, entry: float, exit_price: float, pnl: float):
        emoji = "+" if pnl >= 0 else "-"
        msg = f"<b>CLOSE</b> {symbol} {side} | Entry: ${entry:.4f} | Exit: ${exit_price:.4f} | P&L: {emoji}${abs(pnl):.2f}"
        self.send(msg, "TRADE")

    def send_alert(self, message: str):
        self.send(f"<b>ALERT</b> {message}", "ALERT")
