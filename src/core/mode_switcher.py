#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mode Switcher v1.0
Управление режимами: TREND, GRID, DCA, PAUSED, EMERGENCY, LIGHT.
"""
import logging
from enum import Enum, auto
from typing import Optional, Callable, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

class BotMode(Enum):
    TREND = "trend"
    GRID = "grid"
    DCA = "dca"
    PAUSED = "paused"
    EMERGENCY = "emergency"
    LIGHT = "light"  # Энергосберегающий режим

@dataclass
class ModeTransition:
    from_mode: BotMode
    to_mode: BotMode
    timestamp: datetime
    reason: str

class ModeSwitcher:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, state_manager=None):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._mode = BotMode.TREND
        self._state = state_manager
        self._history: List[ModeTransition] = []
        self._listeners: List[Callable] = []
        self._load_state()

    @property
    def mode(self) -> BotMode:
        return self._mode

    @property
    def mode_name(self) -> str:
        return self._mode.value

    def switch_to(self, new_mode: BotMode, reason: str = "manual") -> bool:
        if new_mode == self._mode:
            return True
        old_mode = self._mode
        if old_mode == BotMode.EMERGENCY and new_mode != BotMode.PAUSED:
            logger.warning("Cannot exit EMERGENCY except to PAUSED")
            return False
        self._mode = new_mode
        transition = ModeTransition(
            from_mode=old_mode,
            to_mode=new_mode,
            timestamp=datetime.now(),
            reason=reason
        )
        self._history.append(transition)
        logger.info(f"Mode switched: {old_mode.value} → {new_mode.value} ({reason})")
        self._persist_state()
        for listener in self._listeners:
            try:
                listener(old_mode, new_mode, reason)
            except Exception as e:
                logger.error(f"Mode listener error: {e}")
        return True

    def can_trade(self) -> bool:
        return self._mode in (BotMode.TREND, BotMode.GRID, BotMode.DCA)

    def is_light_mode(self) -> bool:
        return self._mode == BotMode.LIGHT

    def is_paused(self) -> bool:
        return self._mode == BotMode.PAUSED

    def is_emergency(self) -> bool:
        return self._mode == BotMode.EMERGENCY

    def add_listener(self, callback: Callable):
        self._listeners.append(callback)

    def get_history(self, limit: int = 10) -> List[ModeTransition]:
        return self._history[-limit:]

    def _persist_state(self):
        if self._state:
            self._state.save("mode_switcher", {
                "mode": self._mode.value,
                "history": [
                    {"from": t.from_mode.value, "to": t.to_mode.value,
                     "time": t.timestamp.isoformat(), "reason": t.reason}
                    for t in self._history[-50:]
                ]
            })

    def _load_state(self):
        if self._state:
            data = self._state.load("mode_switcher")
            if data:
                try:
                    self._mode = BotMode(data.get("mode", "trend"))
                except ValueError:
                    self._mode = BotMode.TREND
