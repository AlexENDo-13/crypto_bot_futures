"""
CryptoBot v9.1 - Advanced Logging System (FIXED)
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional, Callable

class CallbackLogHandler(logging.Handler):
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

        if not self.logger.handlers:
            console = logging.StreamHandler(sys.stdout)
            console.setLevel(level)
            console.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s | %(message)s",
                datefmt="%H:%M:%S"
            ))
            self.logger.addHandler(console)

            log_file = self.log_dir / ("bot_" + datetime.now().strftime("%Y%m%d") + ".log")
            file_h = RotatingFileHandler(
                log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
            )
            file_h.setLevel(logging.DEBUG)
            file_h.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s - %(filename)s:%(lineno)d | %(message)s"
            ))
            self.logger.addHandler(file_h)

        self.logger.info("BotLogger v9.1 initialized | log_dir=%s level=%s", log_dir, logging.getLevelName(level))

    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)

    def log(self, level, msg, *args, **kwargs):
        self.logger.log(level, msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self.logger.exception(msg, *args, **kwargs)

    def set_level(self, level: int):
        self.level = level
        self.logger.setLevel(level)
        for h in self.logger.handlers:
            h.setLevel(level)
        self.logger.info("Log level changed to %s", logging.getLevelName(level))

    def add_gui_handler(self, callback: Callable[[str, int], None]):
        if self._callback_handler:
            self.logger.removeHandler(self._callback_handler)
            self._callback_handler = None
        try:
            self._callback_handler = CallbackLogHandler(callback=callback)
            self._callback_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(self._callback_handler)
            self.logger.info("GUI log handler added")
        except Exception as e:
            self.logger.warning("GUI handler error: %s", e)

    def get_logger(self, name: str = "CryptoBot") -> logging.Logger:
        return logging.getLogger(name)

    def log_trade(self, **kwargs):
        msg = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.info("TRADE | %s", msg)

    def log_signal(self, **kwargs):
        msg = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.info("SIGNAL | %s", msg)

    def log_position_update(self, **kwargs):
        msg = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.info("POSITION | %s", msg)

    def log_state(self, component: str, data: dict):
        msg = f"{component} | " + " | ".join(f"{k}={v}" for k, v in data.items())
        self.logger.debug(msg)

    def log_decision(self, action: str, symbol, data: dict):
        msg = f"DECISION {action} | sym={symbol} | " + " | ".join(f"{k}={v}" for k, v in data.items())
        self.logger.info(msg)

def get_logger(name: str = "CryptoBot") -> logging.Logger:
    return BotLogger().get_logger(name)
