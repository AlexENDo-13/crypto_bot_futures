#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Offline Cache v1.0
Локальное хранение свечей и сигналов при отсутствии интернета.
Интеграция с Database.offline_cache.
"""
import logging
import json
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class OfflineCache:
    """
    Кеш данных для оффлайн-режима.
    Использует SQLite (через Database) или JSON fallback.
    """

    def __init__(self, database=None, json_path: str = "data/offline_cache.json"):
        self.db = database
        self.json_path = json_path
        self._memory_cache: Dict[str, Any] = {}
        self._default_ttl_hours = 24

    def store_candles(self, symbol: str, timeframe: str, candles: List[Dict]):
        """Сохранить свечи в кеш."""
        if self.db:
            try:
                self.db.cache_candles(symbol, timeframe, candles)
                return
            except Exception as e:
                logger.error(f"DB cache failed, falling back to JSON: {e}")

        # JSON fallback
        key = f"{symbol}_{timeframe}"
        self._memory_cache[key] = {
            "candles": candles,
            "stored_at": datetime.now().isoformat(),
        }
        self._persist_json()

    def get_candles(self, symbol: str, timeframe: str) -> Optional[List[Dict]]:
        """Получить свечи из кеша если они не устарели."""
        if self.db:
            try:
                cached = self.db.get_cached_candles(symbol, timeframe)
                if cached:
                    logger.debug(f"Cache hit for {symbol} {timeframe}")
                    return cached
            except Exception as e:
                logger.error(f"DB cache read failed: {e}")

        # JSON fallback
        key = f"{symbol}_{timeframe}"
        if key in self._memory_cache:
            data = self._memory_cache[key]
            stored = datetime.fromisoformat(data["stored_at"])
            if datetime.now() - stored < timedelta(hours=self._default_ttl_hours):
                return data["candles"]

        return None

    def store_signal_queue(self, signals: List[Dict]):
        """Сохранить очередь сигналов для исполнения при восстановлении связи."""
        self._memory_cache["signal_queue"] = {
            "signals": signals,
            "stored_at": datetime.now().isoformat(),
        }
        self._persist_json()

    def get_signal_queue(self) -> List[Dict]:
        """Получить очередь сигналов."""
        if "signal_queue" in self._memory_cache:
            return self._memory_cache["signal_queue"]["signals"]
        return []

    def clear_signal_queue(self):
        """Очистить очередь после исполнения."""
        self._memory_cache.pop("signal_queue", None)
        self._persist_json()

    def _persist_json(self):
        """Сохранить в JSON файл."""
        try:
            import json
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(self._memory_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist offline cache: {e}")

    def load_json(self):
        """Загрузить из JSON файла."""
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self._memory_cache = json.load(f)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(f"Failed to load offline cache: {e}")
