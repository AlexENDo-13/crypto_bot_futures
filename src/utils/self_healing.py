#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SelfHealingMonitor v4.0 — мониторинг здоровья с реальными проверками."""
import threading, time, logging
from typing import Dict, Any

class SelfHealingMonitor:
    def __init__(self, check_interval: int = 30, logger=None):
        self.check_interval = check_interval
        self.logger = logger
        self._running = False
        self._thread = None
        self._checks = []
        self._last_health = {}
        self._recovery_actions = 0

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        if self.logger: self.logger.info("🩺 SelfHealingMonitor запущен")
        else: logging.getLogger("SelfHealing").info("🩺 SelfHealingMonitor запущен")

    def stop(self):
        self._running = False
        if self._thread: self._thread.join(timeout=5)

    def _monitor_loop(self):
        while self._running:
            time.sleep(self.check_interval)
            self._run_checks()

    def _run_checks(self):
        for name, check_fn in self._checks:
            try:
                ok, msg = check_fn()
                self._last_health[name] = {"ok": ok, "msg": msg, "time": time.time()}
                if not ok:
                    self._recovery_actions += 1
                    if self.logger: self.logger.warning(f"🩺 SelfHealing [{name}]: {msg}")
            except Exception as e:
                if self.logger: self.logger.error(f"🩺 Ошибка проверки {name}: {e}")

    def register_check(self, name: str, check_fn):
        self._checks.append((name, check_fn))

    def get_health(self) -> Dict[str, Any]:
        return {
            "status": "running" if self._running else "stopped",
            "checks": len(self._checks), "recovery_actions": self._recovery_actions,
            "last_health": self._last_health,
        }
