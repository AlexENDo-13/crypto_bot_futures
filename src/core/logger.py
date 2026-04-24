"""
CryptoBot v7.1 - Advanced Logging System
"""
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional, Callable

class CallbackLogHandler(logging.Handler):
    """GUI callback handler - no Qt dependencies."""

    def __init__(self, callback: Callable[[str, int], None] = None):
        super().__init__()
        self.callback = callback
        self.setLevel(logging.DEBUG)
        self.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s | %(message)s",
            datefmt="%H:%M:%S"
        ))

    def emit(self, record):
        try:
            msg = self.format(record)
            if self.callback:
                try:
                    self.callback(msg, record.levelno)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)

class BotLogger:
    """Centralized logging manager - proper singleton."""

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_dir: str = "logs", level: int = logging.INFO):
        if BotLogger._initialized:
            return
        BotLogger._initialized = True

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.level = level
        self._callback_handler = None

        self.logger = logging.getLogger("CryptoBot")
        self.logger.setLevel(level)
        self.logger.propagate = False

        # Only add handlers if none exist
        if not self.logger.handlers:
            # Console handler
            console = logging.StreamHandler(sys.stdout)
            console.setLevel(level)
            console.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s | %(message)s",
                datefmt="%H:%M:%S"
            ))
            self.logger.addHandler(console)

            # File handler
            log_file = self.log_dir / ("bot_" + datetime.now().strftime("%Y%m%d") + ".log")
            file_h = RotatingFileHandler(
                log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
            )
            file_h.setLevel(logging.DEBUG)
            file_h.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s - %(filename)s:%(lineno)d | %(message)s"
            ))
            self.logger.addHandler(file_h)

        self.logger.info("BotLogger v7.1 initialized | log_dir=%s", log_dir)

    def add_gui_handler(self, callback: Callable[[str, int], None]):
        """Add GUI callback - replaces existing if any."""
        if self._callback_handler:
            self.logger.removeHandler(self._callback_handler)
            self._callback_handler = None

        try:
            self._callback_handler = CallbackLogHandler(callback=callback)
            self._callback_handler.setLevel(logging.INFO)
            self.logger.addHandler(self._callback_handler)
            self.logger.info("GUI log handler added")
        except Exception as e:
            self.logger.warning("GUI handler error: %s", e)

    def get_logger(self, name: str = "CryptoBot") -> logging.Logger:
        return logging.getLogger(name)

def get_logger(name: str = "CryptoBot") -> logging.Logger:
    return BotLogger().get_logger(name)
