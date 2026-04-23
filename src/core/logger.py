#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logger — рабочий логгер с BotLogger для UI
"""
import logging
import os
import sys
import queue
import threading
from datetime import datetime
from typing import Optional, Callable, List, Tuple

class BotLogger:
    """
    Логгер для бота с поддержкой UI-колбэков.
    Потокобезопасен, поддерживает очередь сообщений для GUI.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, name: str = "trading_bot", level: str = "INFO",
                 log_file: str = "logs/trading_bot.log"):
        if self._initialized:
            return

        self.name = name
        self.log_file = log_file
        self._callbacks: List[Callable[[str, str], None]] = []
        self._message_queue: queue.Queue = queue.Queue()
        self._handlers: List[logging.Handler] = []

        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self.logger.handlers.clear()

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        self.logger.addHandler(console)
        self._handlers.append(console)

        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            self._handlers.append(file_handler)

        ui_handler = _UIHandler(self._message_queue)
        ui_handler.setFormatter(formatter)
        self.logger.addHandler(ui_handler)
        self._handlers.append(ui_handler)

        self._initialized = True
        self.info("BotLogger инициализирован")

    def debug(self, msg: str):
        self.logger.debug(msg)
        self._notify("DEBUG", msg)

    def info(self, msg: str):
        self.logger.info(msg)
        self._notify("INFO", msg)

    def warning(self, msg: str):
        self.logger.warning(msg)
        self._notify("WARNING", msg)

    def error(self, msg: str):
        self.logger.error(msg)
        self._notify("ERROR", msg)

    def critical(self, msg: str):
        self.logger.critical(msg)
        self._notify("CRITICAL", msg)

    def exception(self, msg: str):
        self.logger.exception(msg)
        self._notify("ERROR", msg)

    def add_callback(self, callback: Callable[[str, str], None]):
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[str, str], None]):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify(self, level: str, msg: str):
        for cb in self._callbacks:
            try:
                cb(level, msg)
            except Exception:
                pass

    def get_queue(self) -> queue.Queue:
        return self._message_queue

    def get_recent_messages(self, count: int = 100) -> List[Tuple[str, str]]:
        messages = []
        temp = []
        while not self._message_queue.empty() and len(messages) < count:
            try:
                item = self._message_queue.get_nowait()
                messages.append(item)
                temp.append(item)
            except queue.Empty:
                break

        for item in temp:
            self._message_queue.put(item)

        return messages

    def set_level(self, level: str):
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))

class _UIHandler(logging.Handler):
    def __init__(self, message_queue: queue.Queue):
        super().__init__()
        self.queue = message_queue

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.queue.put((record.levelname, msg))
        except Exception:
            self.handleError(record)

def setup_logger(name: str = "trading_bot", level: str = "INFO",
                 log_file: str = "logs/trading_bot.log") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger

# Алиас для обратной совместимости
Logger = BotLogger

logger = setup_logger()
