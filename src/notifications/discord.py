"""
Discord Webhook Notifications
"""
import requests
import json
from src.core.config import get_config
from src.core.logger import get_logger

logger = get_logger()

class DiscordNotifier:
    def __init__(self):
        cfg = get_config().notifications
        self.enabled = cfg.discord_enabled
        self.webhook_url = cfg.discord_webhook_url

    def send(self, content: str, embeds: list = None):
        if not self.enabled or not self.webhook_url:
            return
        try:
            payload = {"content": content}
            if embeds:
                payload["embeds"] = embeds
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code not in [200, 204]:
                logger.error("Discord send failed: %s", resp.text)
        except Exception as e:
            logger.error("Discord error: %s", e)

    def send_trade(self, symbol: str, side: str, pnl: float, reason: str):
        color = 0x00ff00 if pnl >= 0 else 0xff0000
        embed = {
            "title": f"{symbol} {side} Closed",
            "color": color,
            "fields": [
                {"name": "PnL", "value": f"{pnl:+.2f} USDT", "inline": True},
                {"name": "Reason", "value": reason, "inline": True}
            ]
        }
        self.send("", [embed])
