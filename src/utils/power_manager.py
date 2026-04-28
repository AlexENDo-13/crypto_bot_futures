#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Power Manager v1.0
Мониторинг батареи + авто-переключение в light-режим.
"""
import logging
import platform
from typing import Optional, Callable, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class BatteryState:
    percent: float
    is_plugged: bool
    secsleft: Optional[int] = None

class PowerManager:
    """
    Управление энергопотреблением.

    Usage:
        pm = PowerManager(performance_profile=profile)
        pm.start_monitoring()  # Запускает фоновый мониторинг
    """

    def __init__(self, performance_profile=None, mode_switcher=None, check_interval_sec: int = 60):
        self.profile = performance_profile
        self.mode_switcher = mode_switcher
        self.check_interval = check_interval_sec
        self._running = False
        self._listeners: List[Callable] = []
        self._last_state: Optional[BatteryState] = None

    def get_battery_state(self) -> Optional[BatteryState]:
        """Получить состояние батареи."""
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery is None:
                return None  # Нет батареи (десктоп)
            return BatteryState(
                percent=battery.percent,
                is_plugged=battery.power_plugged,
                secsleft=battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None
            )
        except Exception as e:
            logger.debug(f"Battery check failed: {e}")
            return None

    def check_and_adjust(self):
        """Проверить батарею и при необходимости переключить режим."""
        state = self.get_battery_state()
        if state is None:
            return  # Десктоп — нечего делать

        self._last_state = state

        # Логика переключения
        if not state.is_plugged:
            if state.percent <= 15:
                # Критический уровень — пауза торговли
                if self.mode_switcher:
                    from src.core.mode_switcher import BotMode
                    self.mode_switcher.switch_to(BotMode.PAUSED, 
                        reason=f"battery_critical_{state.percent}%")
                logger.warning(f"🔋 Battery critical ({state.percent}%) — PAUSED")

            elif state.percent <= 30:
                # Низкий уровень — light режим
                if self.profile:
                    from src.core.performance_profile import ProfileMode
                    self.profile.set_mode(ProfileMode.LIGHT, 
                        reason=f"battery_low_{state.percent}%")
                logger.info(f"🔋 Battery low ({state.percent}%) — LIGHT mode")

            elif state.percent <= 50:
                # Средний уровень — standard
                if self.profile:
                    from src.core.performance_profile import ProfileMode
                    self.profile.set_mode(ProfileMode.STANDARD,
                        reason=f"battery_medium_{state.percent}%")
        else:
            # На зарядке — можно full
            if self.profile:
                from src.core.performance_profile import ProfileMode
                self.profile.set_mode(ProfileMode.FULL, reason="ac_power")
            logger.debug("🔌 AC power — FULL mode")

        for listener in self._listeners:
            try:
                listener(state)
            except Exception as e:
                logger.error(f"Power listener error: {e}")

    def start_monitoring(self):
        """Запустить фоновый мониторинг (в отдельном потоке)."""
        import threading
        self._running = True

        def monitor_loop():
            import time
            while self._running:
                self.check_and_adjust()
                time.sleep(self.check_interval)

        thread = threading.Thread(target=monitor_loop, daemon=True, name="PowerMonitor")
        thread.start()
        logger.info("Power monitoring started")

    def stop_monitoring(self):
        self._running = False

    def add_listener(self, callback: Callable):
        self._listeners.append(callback)

    def get_status_text(self) -> str:
        state = self.get_battery_state()
        if state is None:
            return "🔌 Desktop (no battery)"
        status = "🔌 Charging" if state.is_plugged else "🔋 Battery"
        time_left = f" (~{state.secsleft//60}min)" if state.secsleft else ""
        return f"{status}: {state.percent}%{time_left}"
