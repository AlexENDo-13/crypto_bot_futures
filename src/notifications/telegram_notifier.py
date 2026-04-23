class TelegramNotifier:
    def __init__(self, bot_token, chat_id, logger=None, commands_enabled=True):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.logger = logger
        self.commands_enabled = commands_enabled
        self._engine = None

    def set_engine(self, engine):
        self._engine = engine

    def send_sync(self, message: str):
        if self.logger:
            self.logger.info(f"[TELEGRAM] {message[:100]}")

    def send_async(self, message: str):
        self.send_sync(message)
