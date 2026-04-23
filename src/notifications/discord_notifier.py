class DiscordNotifier:
    def __init__(self, webhook_url, logger=None):
        self.webhook_url = webhook_url
        self.logger = logger

    def send_sync(self, message: str):
        if self.logger:
            self.logger.info(f"[DISCORD] {message[:100]}")
