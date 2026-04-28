#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proxy Manager v1.0
Авто-подбор рабочих прокси для API BingX из РФ.
Поддержка HTTP/HTTPS/SOCKS5. Кеширование + health-check.
"""
import logging
import time
import requests
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class Proxy:
    url: str
    protocol: str = "http"
    latency: float = 999.0
    last_check: Optional[datetime] = None
    failures: int = 0
    working: bool = False

class ProxyManager:
    """
    Управление прокси для обхода блокировок.

    Usage:
        pm = ProxyManager()
        pm.add_proxy("http://user:pass@host:port")
        proxy = pm.get_best_proxy()
        requests.get(url, proxies=proxy)
    """

    DEFAULT_PROXIES = [
        # Публичные прокси (замени на свои приватные)
        "http://proxy.example.com:8080",
    ]

    def __init__(self, test_url: str = "https://open-api.bingx.com/openApi/swap/v2/server/time"):
        self.proxies: List[Proxy] = []
        self.test_url = test_url
        self._current_index = 0
        self._cache_valid_minutes = 5
        self._max_failures = 3

    def add_proxy(self, proxy_url: str):
        """Добавить прокси в пул."""
        protocol = proxy_url.split("://")[0] if "://" in proxy_url else "http"
        self.proxies.append(Proxy(url=proxy_url, protocol=protocol))
        logger.info(f"Added proxy: {proxy_url}")

    def add_proxies_from_file(self, filepath: str):
        """Загрузить список прокси из файла (один на строку)."""
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.add_proxy(line)
        except FileNotFoundError:
            logger.warning(f"Proxy file not found: {filepath}")

    def _check_proxy(self, proxy: Proxy) -> Tuple[bool, float]:
        """Проверить прокси на работоспособность. Возвращает (working, latency_ms)."""
        proxies = {
            "http": proxy.url,
            "https": proxy.url,
        }
        start = time.time()
        try:
            response = requests.get(
                self.test_url,
                proxies=proxies,
                timeout=10,
                verify=False
            )
            latency = (time.time() - start) * 1000
            if response.status_code == 200:
                return True, latency
        except Exception as e:
            logger.debug(f"Proxy {proxy.url} failed: {e}")
        return False, 9999.0

    def health_check_all(self):
        """Проверить все прокси и отсортировать по скорости."""
        logger.info("Running proxy health check...")
        for proxy in self.proxies:
            working, latency = self._check_proxy(proxy)
            proxy.working = working
            proxy.latency = latency
            proxy.last_check = datetime.now()
            if working:
                proxy.failures = 0
                logger.info(f"  ✓ {proxy.url} — {latency:.0f}ms")
            else:
                proxy.failures += 1
                logger.warning(f"  ✗ {proxy.url} — failed ({proxy.failures}x)")

        # Сортировка: рабочие первые, по latency
        self.proxies.sort(key=lambda p: (not p.working, p.latency))
        working_count = sum(1 for p in self.proxies if p.working)
        logger.info(f"Proxy check complete: {working_count}/{len(self.proxies)} working")

    def get_best_proxy(self) -> Optional[Dict[str, str]]:
        """Получить лучший прокси для requests."""
        if not self.proxies:
            return None

        # Проверить, не устарел ли кеш
        if self.proxies[0].last_check:
            age = datetime.now() - self.proxies[0].last_check
            if age > timedelta(minutes=self._cache_valid_minutes):
                self.health_check_all()

        # Найти первый рабочий
        for proxy in self.proxies:
            if proxy.working and proxy.failures < self._max_failures:
                return {"http": proxy.url, "https": proxy.url}

        # Если нет рабочих — перепроверить
        logger.warning("No working proxies! Retrying health check...")
        self.health_check_all()
        for proxy in self.proxies:
            if proxy.working:
                return {"http": proxy.url, "https": proxy.url}

        return None

    def report_failure(self, proxy_url: str):
        """Сообщить о неудачном запросе через прокси."""
        for proxy in self.proxies:
            if proxy.url == proxy_url:
                proxy.failures += 1
                if proxy.failures >= self._max_failures:
                    proxy.working = False
                    logger.warning(f"Proxy {proxy_url} marked as dead")
                break

    def get_stats(self) -> Dict:
        return {
            "total": len(self.proxies),
            "working": sum(1 for p in self.proxies if p.working),
            "best_latency": min((p.latency for p in self.proxies if p.working), default=0),
        }
