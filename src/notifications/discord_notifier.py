#!/usr/bin/env python3
import logging, json, aiohttp
logger = logging.getLogger("DiscordNotifier")

class DiscordNotifier:
    def __init__(self, webhook_url): self.webhook_url = webhook_url
    async def send(self, message):
        if not self.webhook_url: return
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json={"content": message}) as resp:
                    if resp.status != 204: logger.warning(f"Discord webhook status: {resp.status}")
        except Exception as e: logger.error(f"Ошибка Discord: {e}")
