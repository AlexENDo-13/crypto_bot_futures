#!/usr/bin/env python3
"""Settings — configuration loader."""
import json
import os
from pathlib import Path
from typing import Any, Dict

class Settings:
    def __init__(self, config_path: str = "config/bot_config.json"):
        self.config_path = Path(config_path)
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self):
        defaults = {
            "api_key": os.getenv("BINGX_API_KEY", ""),
            "api_secret": os.getenv("BINGX_API_SECRET", ""),
            "testnet": os.getenv("BINGX_TESTNET", "false").lower() == "true",
            "scan_interval_minutes": 3,
            "timeframe": "15m",
            "mtf_timeframes": ["1h", "4h", "1d"],
            "use_multi_timeframe": True,
            "mtf_required_agreement": 2,
            "min_adx": 12,
            "min_atr_percent": 0.3,
            "min_volume_24h_usdt": 30000,
            "min_signal_strength": 0.25,
            "use_spread_filter": True,
            "max_spread_percent": 0.8,
            "max_funding_rate": 0.0,
            "default_sl_pct": 1.5,
            "default_tp_pct": 3.0,
            "auto_optimize_sl_tp": True,
            "trailing_stop_enabled": True,
            "trailing_stop_distance_percent": 2.0,
            "learning_enabled": True,
            "force_ignore_session": True,
            "correlation_filter_enabled": True,
            "cache_ttl_seconds": 60,
            "telegram_token": os.getenv("TELEGRAM_TOKEN", ""),
            "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
            "max_open_positions": 5,
            "risk_per_trade_percent": 1.0,
            "max_daily_loss_percent": 5.0,
            "max_weekly_loss_percent": 10.0,
            "leverage": 1,
            "log_level": "INFO",
            "log_dir": "logs",
        }
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    defaults.update(json.load(f))
            except Exception:
                pass
        self._data = defaults

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return self._data.copy()
