"""
BotLogger v9.0
Centralized logging configuration with file and console handlers.
"""
import logging
import sys
from pathlib import Path
from datetime import datetime


class BotLogger:
    """Configures root logger for the bot with consistent formatting."""

    _initialized = False

    @classmethod
    def setup(cls, log_dir: str = "logs", level: int = logging.INFO) -> logging.Logger:
        if cls._initialized:
            return logging.getLogger("CryptoBot")

        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Root logger for CryptoBot
        logger = logging.getLogger("CryptoBot")
        logger.setLevel(level)

        # Clear any existing handlers to avoid duplication
        logger.handlers.clear()

        # Formatter
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s CryptoBot.%(name)s | %(message)s",
            datefmt="%H:%M:%S"
        )

        # File handler
        log_file = log_path / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        cls._initialized = True
        return logger

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """Return a child logger for a specific module."""
        return logging.getLogger(f"CryptoBot.{name}")
