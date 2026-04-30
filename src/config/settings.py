"""Settings manager with JSON config support."""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class Settings:
    """Управление настройками бота."""

    DEFAULT_CONFIG = {
        "api_key": "",
        "api_secret": "",
        "testnet": True,
        "demo_mode": True,
        "leverage": 5,
        "risk_per_trade": 2.0,
        "max_positions": 3,
        "timeframes": ["15m", "1h", "4h", "1d"],
        "min_adx": 15,
        "min_atr_percent": 0.5,
        "timeframe_agreement": 2,
        "symbols": ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT"],
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "auto_trading": False,
        "circuit_breaker_daily_loss": 10.0,
        "partial_tp_1": 50,
        "partial_tp_1_pct": 50,
        "partial_tp_2": 30,
        "partial_tp_2_pct": 80,
        "trailing_stop_activation": 1.5,
        "trailing_stop_distance": 1.0,
        "breakeven_after_tp1": True,
    }

    def __init__(self, config_path: str = "config/bot_config.json"):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Merge with defaults
                    config = dict(self.DEFAULT_CONFIG)
                    config.update(loaded)
                    return config
            except Exception:
                pass
        return dict(self.DEFAULT_CONFIG)

    def save(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        self._config[key] = value
        self.save()

    def all(self) -> Dict[str, Any]:
        return dict(self._config)
