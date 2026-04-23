"""
Cache Manager – файловый кэш.
"""

import json
import time
import hashlib
import pandas as pd
from pathlib import Path
from typing import Any, Optional


class CacheManager:
    def __init__(self, ttl_minutes: int = 15):
        self.ttl = ttl_minutes * 60
        self.dir = Path("data/cache")
        self.dir.mkdir(parents=True, exist_ok=True)

    def _key(self, *args) -> str:
        return hashlib.md5(":".join(str(a) for a in args).encode()).hexdigest()

    def get(self, *args) -> Optional[Any]:
        path = self.dir / f"{self._key(*args)}.json"
        if not path.exists() or time.time() - path.stat().st_mtime > self.ttl:
            return None
        with open(path) as f:
            data = json.load(f)['value']
            if isinstance(data, dict) and data.get('__df__'):
                return pd.read_json(data['data'], orient='split')
            return data

    def set(self, *args, value: Any):
        path = self.dir / f"{self._key(*args)}.json"
        if isinstance(value, pd.DataFrame):
            value = {'__df__': True, 'data': value.to_json(orient='split', date_format='iso')}
        with open(path, 'w') as f:
            json.dump({'value': value}, f)