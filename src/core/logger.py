"""
Advanced Logging v5.0 - Structured logging, Qt signals, file rotation,
remote forwarding, and performance metrics.
"""
import logging
import logging.handlers
import sys
import os
import json
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

try:
    from PyQt5.QtCore import QObject, pyqtSignal
    HAS_QT = True
except ImportError:
    try:
        from PyQt6.QtCore import QObject, pyqtSignal
        HAS_QT = True
    except ImportError:
        HAS_QT = False
        class QObject:
            pass
        def pyqtSignal(*args, **kwargs):
            return None


class ColorCodes:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    ORANGE = "\033[38;5;208m"


class ColoredFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: ColorCodes.GRAY,
        logging.INFO: ColorCodes.GREEN,
        logging.WARNING: ColorCodes.YELLOW,
        logging.ERROR: ColorCodes.RED,
        logging.CRITICAL: ColorCodes.MAGENTA + ColorCodes.BOLD,
    }

    MSG_COLORS = {
        "PROFIT": ColorCodes.GREEN + ColorCodes.BOLD,
        "WIN": ColorCodes.GREEN + ColorCodes.BOLD,
        "LOSS": ColorCodes.RED + ColorCodes.BOLD,
        "STOP": ColorCodes.RED + ColorCodes.BOLD,
        "SIGNAL": ColorCodes.CYAN + ColorCodes.BOLD,
        "ERROR": ColorCodes.RED,
        "FAILED": ColorCodes.RED,
        "OPEN": ColorCodes.BLUE + ColorCodes.BOLD,
        "CLOSE": ColorCodes.ORANGE + ColorCodes.BOLD,
        "RISK": ColorCodes.YELLOW + ColorCodes.BOLD,
        "WS": ColorCodes.MAGENTA,
    }

    def __init__(self, fmt: str = None, datefmt: str = None, use_colors: bool = True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and (sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ)

    def format(self, record: logging.LogRecord) -> str:
        original_levelname = record.levelname
        original_msg = record.msg

        if self.use_colors:
            color = self.LEVEL_COLORS.get(record.levelno, ColorCodes.WHITE)
            record.levelname = f"{color}{record.levelname}{ColorCodes.RESET}"

            msg_upper = str(record.msg).upper()
            for keyword, msg_color in self.MSG_COLORS.items():
                if keyword in msg_upper:
                    record.msg = f"{msg_color}{record.msg}{ColorCodes.RESET}"
                    break

        result = super().format(record)
        record.levelname = original_levelname
        record.msg = original_msg
        return result


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            data.update(record.extra)
        return json.dumps(data, default=str)


class QtLogHandler(logging.Handler):
    if HAS_QT:
        log_signal = pyqtSignal(str, str, str)
    else:
        log_signal = None

    def __init__(self, parent: Optional[QObject] = None):
        if HAS_QT:
            super().__init__()
            QObject.__init__(self, parent)
        else:
            super().__init__()
        self.setLevel(logging.DEBUG)

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            level = record.levelname
            category = getattr(record, "category", "general")
            if HAS_QT and self.log_signal is not None:
                self.log_signal.emit(level, msg, category)
        except Exception:
            self.handleError(record)


class BotLogger:
    _instance: Optional["BotLogger"] = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, name: str = "CryptoBot", log_dir: str = "logs",
                 console_level: int = logging.INFO, file_level: int = logging.DEBUG,
                 max_bytes: int = 10 * 1024 * 1024, backup_count: int = 10):
        if BotLogger._initialized:
            return

        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        self.logger.handlers.clear()

        # Console
        console_fmt = "%(asctime)s %(levelname)s %(name)s | %(message)s"
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(ColoredFormatter(console_fmt, datefmt="%H:%M:%S"))
        self.logger.addHandler(console_handler)
        self._console_handler = console_handler

        # Main log file
        log_file = self.log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setLevel(file_level)
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d)\n%(message)s\n",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # JSON structured log
        json_file = self.log_dir / f"{name}_structured_{datetime.now().strftime('%Y%m%d')}.jsonl"
        json_handler = logging.handlers.RotatingFileHandler(
            json_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        json_handler.setLevel(file_level)
        json_handler.setFormatter(JsonFormatter())
        self.logger.addHandler(json_handler)

        # Error log
        error_file = self.log_dir / f"{name}_errors_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        self.logger.addHandler(error_handler)

        self._qt_handler: Optional[QtLogHandler] = None
        BotLogger._initialized = True
        self.logger.info("BotLogger v5.0 initialized | log_dir=%s", self.log_dir)

    def add_qt_handler(self, parent=None) -> Optional[QtLogHandler]:
        if not HAS_QT:
            self.logger.warning("Qt not available")
            return None
        if self._qt_handler:
            return self._qt_handler
        self._qt_handler = QtLogHandler(parent)
        self._qt_handler.setLevel(logging.INFO)
        self._qt_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        self.logger.addHandler(self._qt_handler)
        self.logger.info("QtLogHandler attached")
        return self._qt_handler

    def remove_qt_handler(self):
        if self._qt_handler and self._qt_handler in self.logger.handlers:
            self.logger.removeHandler(self._qt_handler)
            self._qt_handler = None

    def set_level(self, level: int):
        self._console_handler.setLevel(level)

    def debug(self, msg: str, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)
    def info(self, msg: str, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)
    def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)
    def error(self, msg: str, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)
    def critical(self, msg: str, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)
    def exception(self, msg: str, *args, **kwargs):
        self.logger.exception(msg, *args, **kwargs)

    def trade(self, msg: str, **kwargs):
        extra = logging.LoggerAdapter(self.logger, {"category": "trade"})
        extra.info(f"[TRADE] {msg}", **kwargs)
    def signal(self, msg: str, **kwargs):
        extra = logging.LoggerAdapter(self.logger, {"category": "signal"})
        extra.info(f"[SIGNAL] {msg}", **kwargs)
    def pnl(self, msg: str, **kwargs):
        extra = logging.LoggerAdapter(self.logger, {"category": "pnl"})
        extra.info(f"[PnL] {msg}", **kwargs)
    def risk(self, msg: str, **kwargs):
        extra = logging.LoggerAdapter(self.logger, {"category": "risk"})
        extra.warning(f"[RISK] {msg}", **kwargs)
    def ws(self, msg: str, **kwargs):
        extra = logging.LoggerAdapter(self.logger, {"category": "websocket"})
        extra.debug(f"[WS] {msg}", **kwargs)


_log: Optional[BotLogger] = None

def get_logger() -> BotLogger:
    global _log
    if _log is None:
        _log = BotLogger()
    return _log

def setup_logging(log_dir: str = "logs", console_level: int = logging.INFO, file_level: int = logging.DEBUG) -> BotLogger:
    global _log
    _log = BotLogger(log_dir=log_dir, console_level=console_level, file_level=file_level)
    return _log
