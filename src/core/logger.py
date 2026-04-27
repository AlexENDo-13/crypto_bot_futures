#!/usr/bin/env python3
import logging
from pathlib import Path
from datetime import datetime

class BotLogger:
    def __init__(self, log_dir="logs", level=logging.INFO):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.level = level
        self.logger = logging.getLogger("CryptoBot")
        self.logger.setLevel(level)
        if not self.logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s %(levelname)s CryptoBot.%(name)s | %(message)s",
                datefmt="%H:%M:%S"
            )
            fh = logging.FileHandler(self.log_dir / "bot.log", encoding="utf-8")
            fh.setFormatter(formatter)
            ch = logging.StreamHandler()
            ch.setFormatter(formatter)
            self.logger.addHandler(fh)
            self.logger.addHandler(ch)
        self.logger.info(f"BotLogger v10.0 initialized | log_dir={log_dir} level={logging.getLevelName(level)}")

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def debug(self, msg):
        self.logger.debug(msg)

    def critical(self, msg):
        self.logger.critical(msg)
