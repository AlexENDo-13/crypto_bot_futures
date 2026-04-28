#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance Profile v1.0
Авто-определение режима работы по железу.
light / standard / full — переключает функции бота.
"""
import logging
import psutil
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class ProfileMode(Enum):
    LIGHT = "light"       # Слабое железо / батарея
    STANDARD = "standard" # Среднее
    FULL = "full"         # Мощное железо

@dataclass
class ProfileConfig:
    mode: ProfileMode
    enable_ml: bool
    enable_realtime_charts: bool
    enable_correlation_matrix: bool
    scan_interval_seconds: int
    max_concurrent_pairs: int
    log_level: str
    memory_limit_mb: int

class PerformanceProfile:
    """
    Управление производительностью бота.

    Usage:
        profile = PerformanceProfile()
        profile.auto_detect()  # Определить по железу
        # или
        profile.set_mode(ProfileMode.LIGHT)  # Принудительно
    """

    PROFILES = {
        ProfileMode.LIGHT: ProfileConfig(
            mode=ProfileMode.LIGHT,
            enable_ml=False,
            enable_realtime_charts=False,
            enable_correlation_matrix=False,
            scan_interval_seconds=60,
            max_concurrent_pairs=5,
            log_level="INFO",
            memory_limit_mb=300,
        ),
        ProfileMode.STANDARD: ProfileConfig(
            mode=ProfileMode.STANDARD,
            enable_ml=True,
            enable_realtime_charts=False,
            enable_correlation_matrix=True,
            scan_interval_seconds=30,
            max_concurrent_pairs=10,
            log_level="INFO",
            memory_limit_mb=500,
        ),
        ProfileMode.FULL: ProfileConfig(
            mode=ProfileMode.FULL,
            enable_ml=True,
            enable_realtime_charts=True,
            enable_correlation_matrix=True,
            scan_interval_seconds=15,
            max_concurrent_pairs=20,
            log_level="DEBUG",
            memory_limit_mb=800,
        ),
    }

    def __init__(self, mode_switcher=None):
        self._mode = ProfileMode.STANDARD
        self._config = self.PROFILES[ProfileMode.STANDARD]
        self._listeners: List[Callable] = []
        self._mode_switcher = mode_switcher

    @property
    def mode(self) -> ProfileMode:
        return self._mode

    @property
    def config(self) -> ProfileConfig:
        return self._config

    def auto_detect(self) -> ProfileMode:
        """Авто-определение режима по железу."""
        try:
            ram_gb = psutil.virtual_memory().total / (1024**3)
            cpu_count = psutil.cpu_count(logical=True)

            logger.info(f"Hardware detect: RAM={ram_gb:.1f}GB, CPUs={cpu_count}")

            if ram_gb < 8 or cpu_count <= 4:
                detected = ProfileMode.LIGHT
            elif ram_gb < 16 or cpu_count <= 8:
                detected = ProfileMode.STANDARD
            else:
                detected = ProfileMode.FULL

            self.set_mode(detected, reason="auto_detect")
            return detected

        except Exception as e:
            logger.error(f"Auto-detect failed: {e}, using STANDARD")
            self.set_mode(ProfileMode.STANDARD, reason="fallback")
            return ProfileMode.STANDARD

    def set_mode(self, mode: ProfileMode, reason: str = "manual"):
        """Установить режим вручную."""
        old_mode = self._mode
        self._mode = mode
        self._config = self.PROFILES[mode]

        logger.info(f"Performance profile: {old_mode.value} → {mode.value} ({reason})")

        # Синхронизация с ModeSwitcher
        if self._mode_switcher and mode == ProfileMode.LIGHT:
            from src.core.mode_switcher import BotMode
            self._mode_switcher.switch_to(BotMode.LIGHT, reason=f"performance_profile:{reason}")

        for listener in self._listeners:
            try:
                listener(old_mode, mode, self._config)
            except Exception as e:
                logger.error(f"Profile listener error: {e}")

    def add_listener(self, callback: Callable):
        self._listeners.append(callback)

    def get_memory_usage_mb(self) -> float:
        """Текущее потребление RAM процессом."""
        try:
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0

    def is_memory_critical(self) -> bool:
        """Память критически заполнена?"""
        usage = self.get_memory_usage_mb()
        return usage > self._config.memory_limit_mb * 1.2

    def get_stats(self) -> Dict[str, Any]:
        return {
            "profile": self._mode.value,
            "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
            "ram_used_percent": psutil.virtual_memory().percent,
            "process_memory_mb": round(self.get_memory_usage_mb(), 1),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "config": {
                "ml": self._config.enable_ml,
                "charts": self._config.enable_realtime_charts,
                "correlation": self._config.enable_correlation_matrix,
                "interval": self._config.scan_interval_seconds,
                "max_pairs": self._config.max_concurrent_pairs,
            }
        }
