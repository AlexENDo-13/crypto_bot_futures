#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BotLogger — логгер с поддержкой callback для UI.
"""
import logging
import sys
from datetime import datetime


class BotLogger:
    """Кастомный логгер с callback для UI."""

    def __init__(self, name="BotLogger", level="INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))

        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self._callbacks: list = []

    def add_callback(self, callback):
        """Добавляет callback для UI обновлений."""
        self._callbacks.append(callback)

    def _notify(self, msg: str):
        for cb in self._callbacks:
            try:
                cb(msg)
            except Exception:
                pass

    def debug(self, msg: str):
        self.logger.debug(msg)

    def info(self, msg: str):
        self.logger.info(msg)
        self._notify(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)
        self._notify(msg)

    def error(self, msg: str):
        self.logger.error(msg)
        self._notify(msg)

    def critical(self, msg: str):
        self.logger.critical(msg)
        self._notify(msg)
