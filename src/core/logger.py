"""
CryptoBot v6.0 - Advanced Logging System
Fixed: убран конфликтный QtLogHandler, используем callback-логгер
"""
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional, Callable, List


class CallbackLogHandler(logging.Handler):
    """Простой обработчик, который вызывает callback-функцию.
    Не зависит от Qt, работает через функцию-прослойку.
    """

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
            # Также пишем в консоль
            print(msg)
        except Exception:
            self.handleError(record)


class BotLogger:
    """Centralized logging manager for CryptoBot v6.0."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, log_dir: str = "logs", level: int = logging.INFO):
        if self._initialized:
            return

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.level = level
        self._callback_handler: Optional[CallbackLogHandler] = None
        self._file_handler: Optional[RotatingFileHandler] = None
        self._console_handler: Optional[logging.StreamHandler] = None

        # Setup root logger
        self.logger = logging.getLogger("CryptoBot")
        self.logger.setLevel(level)
        self.logger.propagate = False

        # Clear existing handlers
        self.logger.handlers.clear()

        # Console handler
        self._console_handler = logging.StreamHandler(sys.stdout)
        self._console_handler.setLevel(level)
        console_fmt = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s | %(message)s",
            datefmt="%H:%M:%S"
        )
        self._console_handler.setFormatter(console_fmt)
        self.logger.addHandler(self._console_handler)

        # File handler with rotation
        log_file = self.log_dir / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
        self._file_handler = RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        self._file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s - %(filename)s:%(lineno)d | %(message)s"
        )
        self._file_handler.setFormatter(file_fmt)
        self.logger.addHandler(self._file_handler)

        self._initialized = True
        self.logger.info(f"BotLogger v6.0 initialized | log_dir={log_dir}")

    def add_gui_handler(self, callback: Callable[[str, int], None]):
        """Add GUI callback log handler."""
        if self._callback_handler is not None:
            self._callback_handler.callback = callback
            return

        try:
            self._callback_handler = CallbackLogHandler(callback=callback)
            self._callback_handler.setLevel(logging.INFO)
            self.logger.addHandler(self._callback_handler)
            self.logger.info("GUI log handler added successfully")
        except Exception as e:
            self.logger.warning(f"Could not add GUI handler: {e}")

    def get_logger(self, name: str = "CryptoBot") -> logging.Logger:
        """Get a named logger."""
        return logging.getLogger(name)

    def set_level(self, level: int):
        """Set logging level."""
        self.level = level
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)


def get_logger(name: str = "CryptoBot") -> logging.Logger:
    return BotLogger().get_logger(name)
