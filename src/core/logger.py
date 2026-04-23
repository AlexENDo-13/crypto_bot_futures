#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BotLogger — полноценный логгер: консоль, файл, JSON, UI callback.
"""
import logging
import logging.handlers
import sys
import os
import json
import traceback
from datetime import datetime
from typing import List, Callable, Optional
from queue import Queue

class JSONFormatter(logging.Formatter):
    """Форматтер для JSON-логов."""
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_entry["exception"] = traceback.format_exception(*record.exc_info)
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data
        return json.dumps(log_entry, ensure_ascii=False)

class QTextHandler(logging.Handler):
    """Handler для отправки логов в PyQt QTextEdit через callback."""
    def __init__(self, callback: Callable):
        super().__init__()
        self.callback = callback
        self.setFormatter(logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%H:%M:%S"
        ))
    def emit(self, record):
        try:
            msg = self.format(record)
            self.callback(msg, record.levelno)
        except Exception:
            pass

class BotLogger:
    """Полноценный логгер бота с мультиканальным выводом."""
    LEVEL_COLORS = {
        logging.DEBUG: "#888888",
        logging.INFO: "#E0E0E0",
        logging.WARNING: "#FFA500",
        logging.ERROR: "#FF4444",
        logging.CRITICAL: "#FF0000",
    }
    def __init__(self, name: str = "BotLogger", level: str = "INFO",
                 log_dir: str = "logs", max_bytes: int = 5 * 1024 * 1024,
                 backup_count: int = 5):
        self.name = name
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self.logger.handlers = []
        # Console
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.DEBUG)
        console_fmt = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console.setFormatter(console_fmt)
        self.logger.addHandler(console)
        # File
        log_file = os.path.join(log_dir, f"{name.lower()}.log")
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(console_fmt)
        self.logger.addHandler(file_handler)
        # JSON
        json_file = os.path.join(log_dir, f"{name.lower()}.jsonl")
        json_handler = logging.handlers.RotatingFileHandler(
            json_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        json_handler.setLevel(logging.DEBUG)
        json_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(json_handler)
        # UI callback
        self._ui_callbacks: List[Callable] = []
        self._ui_handler = None
        # Decision log
        decision_file = os.path.join(log_dir, "decisions.jsonl")
        self._decision_handler = logging.handlers.RotatingFileHandler(
            decision_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        self._decision_handler.setLevel(logging.INFO)
        self._decision_handler.setFormatter(JSONFormatter())
        self._decision_logger = logging.getLogger(f"{name}.decisions")
        self._decision_logger.setLevel(logging.INFO)
        self._decision_logger.handlers = []
        self._decision_logger.addHandler(self._decision_handler)
        self.info(f"📝 Логгер инициализирован. Логи: {log_dir}/")

    def set_ui_callback(self, callback: Callable):
        self._ui_callbacks.append(callback)
        if self._ui_handler is None:
            self._ui_handler = QTextHandler(callback)
            self._ui_handler.setLevel(logging.INFO)
            self.logger.addHandler(self._ui_handler)

    def debug(self, msg: str, extra: dict = None):
        if extra:
            self.logger.debug(msg, extra={"extra_data": extra})
        else:
            self.logger.debug(msg)
    def info(self, msg: str, extra: dict = None):
        if extra:
            self.logger.info(msg, extra={"extra_data": extra})
        else:
            self.logger.info(msg)
    def warning(self, msg: str, extra: dict = None):
        if extra:
            self.logger.warning(msg, extra={"extra_data": extra})
        else:
            self.logger.warning(msg)
    def error(self, msg: str, exc_info: bool = False, extra: dict = None):
        if extra:
            self.logger.error(msg, exc_info=exc_info, extra={"extra_data": extra})
        else:
            self.logger.error(msg, exc_info=exc_info)
    def critical(self, msg: str, exc_info: bool = False, extra: dict = None):
        if extra:
            self.logger.critical(msg, exc_info=exc_info, extra={"extra_data": extra})
        else:
            self.logger.critical(msg, exc_info=exc_info)

    def log_decision(self, decision_type: str, symbol: str = None, data: dict = None):
        entry = {
            "type": decision_type,
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": data or {},
        }
        self._decision_logger.info(json.dumps(entry, ensure_ascii=False))

    def log_state(self, component: str, state: dict):
        entry = {
            "type": "state",
            "component": component,
            "state": state,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self._decision_logger.info(json.dumps(entry, ensure_ascii=False))
