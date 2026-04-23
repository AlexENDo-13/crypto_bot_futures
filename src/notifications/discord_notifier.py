"""
Discord Notifier – отправка уведомлений через Webhook.
"""

import requests
from datetime import datetime
from src.core.logger import BotLogger


class DiscordNotifier:
    def __init__(self, webhook_url: str, logger: BotLogger):
        self.webhook_url = webhook_url
        self.logger = logger
        self.enabled = bool(webhook_url)

    def send_message(self, content: str, title: str = None, color: int = 0x00ff00) -> bool:
        if not self.enabled:
            return False
        embed = None
        if title:
            embed = {
                "title": title,
                "description": content,
                "color": color,
                "timestamp": datetime.utcnow().isoformat()
            }
        payload = {"content": content if not embed else None, "embeds": [embed] if embed else None}
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=5)
            return resp.status_code == 204
        except Exception as e:
            self.logger.error(f"Discord error: {e}")
            return False

    def send_trade_open(self, symbol: str, side: str, price: float):
        color = 0x00ff00 if side == "BUY" else 0xff0000
        self.send_message(
            title="🚀 Новая позиция",
            content=f"{side} {symbol} @ {price:.4f}",
            color=color
        )

    def send_trade_close(self, symbol: str, pnl: float, reason: str):
        color = 0x00ff00 if pnl > 0 else 0xff0000
        self.send_message(
            title="📊 Позиция закрыта",
            content=f"{symbol} | PnL: {pnl:+.2f} USDT | {reason}",
            color=color
        )

    def send_daily_report(self, stats: dict):
        embed = {
            "title": "📈 Ежедневный отчёт",
            "fields": [
                {"name": "Баланс", "value": f"{stats['balance']:.2f} USDT", "inline": True},
                {"name": "PnL сегодня", "value": f"{stats['daily_pnl']:+.2f}%", "inline": True},
                {"name": "Win Rate", "value": f"{stats['win_rate']:.1f}%", "inline": True},
                {"name": "Сделок", "value": str(stats['trades']), "inline": True}
            ],
            "color": 0x3498db,
            "timestamp": datetime.utcnow().isoformat()
        }
        if self.enabled:
            requests.post(self.webhook_url, json={"embeds": [embed]}, timeout=5)