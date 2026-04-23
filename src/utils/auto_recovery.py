#!/usr/bin/env python3
import os
import sys
import time
import threading
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, List
import psutil
from src.core.logger import BotLogger

class SelfHealingWatchdog:
    def __init__(self, logger: BotLogger, restart_callback: Optional[Callable] = None):
        self.logger = logger
        self.restart_callback = restart_callback
        self.running = False
        self.crash_count = 0
        self.last_crash_time = 0
        self.crash_history: list = []
        self.max_crashes_per_hour = 5
        self.repair_actions: dict = {}
        
    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        self.logger.info("🛡️ Watchdog запущен")
    
    def stop(self):
        self.running = False
        self.logger.info("Watchdog остановлен")
    
    def _monitor_loop(self):
        while self.running:
            self._check_health()
            time.sleep(30)
    
    def _check_health(self):
        try:
            if self._is_stalled():
                self.logger.warning("⚠️ Обнаружено зависание бота, выполняется перезапуск...")
                self._perform_restart(reason="stall")
            if self._memory_leak_detected():
                self.logger.warning("⚠️ Обнаружена утечка памяти, перезапуск...")
                self._perform_restart(reason="memory_leak")
        except Exception as e:
            self.logger.error(f"Ошибка в watchdog: {e}")
    
    def _is_stalled(self) -> bool:
        try:
            heartbeat_file = Path("data/heartbeat.txt")
            if heartbeat_file.exists():
                mtime = datetime.fromtimestamp(heartbeat_file.stat().st_mtime)
                if (datetime.now() - mtime).total_seconds() > 7200:
                    hour = datetime.now().hour
                    if 10 <= hour <= 22:
                        return True
                return False
            log_dir = Path("data/logs")
            if not log_dir.exists():
                return False
            latest_log = sorted(log_dir.glob("*_bot.log"), reverse=True)
            if not latest_log:
                return False
            mtime = datetime.fromtimestamp(latest_log[0].stat().st_mtime)
            if (datetime.now() - mtime).total_seconds() > 7200:
                hour = datetime.now().hour
                if 10 <= hour <= 22:
                    return True
        except Exception:
            pass
        return False
    
    def _memory_leak_detected(self) -> bool:
        try:
            process = psutil.Process()
            mem_mb = process.memory_info().rss / 1024 / 1024
            return mem_mb > 1500
        except Exception:
            return False
    
    def record_crash(self, error: Exception, context: dict = None):
        now = time.time()
        self.crash_count += 1
        self.last_crash_time = now
        crash_info = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context or {},
        }
        self.crash_history.append(crash_info)
        crash_file = Path("data/crashes.jsonl")
        crash_file.parent.mkdir(parents=True, exist_ok=True)
        import json
        with open(crash_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(crash_info, ensure_ascii=False) + "\n")
        self._analyze_and_repair(crash_info)
        if self.crash_count > self.max_crashes_per_hour:
            self.logger.critical("🚨 Слишком много сбоев, требуется ручное вмешательство!")
            return
        self._perform_restart(reason=f"crash_{type(error).__name__}")
    
    def _analyze_and_repair(self, crash_info: dict):
        error_msg = crash_info["error_message"].lower()
        if "timestamp" in error_msg or "100400" in error_msg:
            self.logger.info("🔧 Обнаружена ошибка синхронизации времени, сброс offset...")
        elif "connection" in error_msg or "timeout" in error_msg:
            self.logger.info("🔧 Проблемы с соединением, увеличиваем таймауты...")
        elif "memory" in error_msg or "killed" in error_msg:
            self.logger.info("🔧 Нехватка памяти, очистка кэша...")
            self._clear_cache()
    
    def _clear_cache(self):
        try:
            cache_dir = Path("data/cache")
            if cache_dir.exists():
                import shutil
                shutil.rmtree(cache_dir)
                cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    
    def _perform_restart(self, reason: str = "unknown"):
        self.logger.warning(f"🔄 Перезапуск бота, причина: {reason}")
        if self.restart_callback:
            try:
                self.restart_callback()
            except Exception as e:
                self.logger.error(f"Ошибка при перезапуске: {e}")
                self._hard_restart()
        else:
            self._hard_restart()
    
    def _hard_restart(self):
        self.logger.warning("Выполняется жёсткий перезапуск процесса...")
        time.sleep(2)
        # Пытаемся использовать callback для корректного перезапуска движка
        if self.restart_callback:
            try:
                self.restart_callback()
            except Exception as e:
                self.logger.error(f"Ошибка при перезапуске через callback: {e}")
                os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            os.execv(sys.executable, [sys.executable] + sys.argv)

class ProxyListUpdater:
    PROXY_SOURCES = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://www.proxy-list.download/api/v1/get?type=socks5",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    ]
    def __init__(self, logger: BotLogger):
        self.logger = logger
        self.proxy_file = Path("data/proxies.txt")
        self.last_update = 0
        self.update_interval = 3600
    def get_proxies(self) -> list:
        now = time.time()
        if self.proxy_file.exists() and (now - self.last_update) < self.update_interval:
            return self._read_proxy_file()
        proxies = self._fetch_from_sources()
        if proxies:
            self._save_proxy_file(proxies)
            self.last_update = now
        return proxies
    def _fetch_from_sources(self) -> list:
        import requests
        all_proxies = []
        for source in self.PROXY_SOURCES:
            try:
                resp = requests.get(source, timeout=10)
                if resp.status_code == 200:
                    proxies = [line.strip() for line in resp.text.splitlines() if line.strip() and not line.startswith('#')]
                    all_proxies.extend(proxies)
                    self.logger.debug(f"Загружено {len(proxies)} прокси из {source}")
            except Exception as e:
                self.logger.debug(f"Ошибка загрузки прокси {source}: {e}")
        return list(set(all_proxies))
    def _save_proxy_file(self, proxies: list):
        self.proxy_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.proxy_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(proxies))
        self.logger.info(f"💾 Сохранено {len(proxies)} прокси")
    def _read_proxy_file(self) -> list:
        try:
            with open(self.proxy_file, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception:
            return []