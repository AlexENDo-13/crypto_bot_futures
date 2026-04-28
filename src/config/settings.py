#!/usr/bin/env python3
"""Settings v11.2 — Added Session #2 learning parameters."""
import json
import os
from typing import Any, Dict

DEFAULT_CONFIG = {
    "api_key": "",
    "api_secret": "",
    "demo_mode": True,
    "scan_interval_minutes": 3,
    "max_positions": 3,
    "max_risk_per_trade": 2.0,
    "max_total_risk_percent": 10.0,
    "max_leverage": 10,
    "default_sl_pct": 1.5,
    "default_tp_pct": 3.0,
    "daily_loss_limit_percent": 8.0,
    "anti_chase_threshold_percent": 0.3,
    "trailing_stop_enabled": True,
    "trailing_stop_distance_percent": 2.0,
    "trailing_activation": 1.5,
    "trailing_callback": 0.5,
    "max_hold_time_minutes": 240,
    "anti_martingale_enabled": True,
    "anti_martingale_risk_reduction": 0.8,
    "weekend_risk_multiplier": 0.5,
    "reduce_risk_on_weekends": True,
    "daily_profit_target_percent": 5.0,
    "stop_on_daily_target": False,
    "max_orders_per_hour": 8,
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
    "trap_detector_enabled": True,
    "aggressive_adaptation": True,
    "fast_mode_empty_scans": True,
    "force_ignore_session": True,
    "symbols_whitelist": [],
    "blacklist": ["SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "BONK-USDT"],
    "cache_ttl_seconds": 60,
    "partial_close_enabled": True,
    "partial_close_at_tp1": 0.50,
    "partial_close_at_tp2": 0.30,
    "breakeven_after_tp1": True,
    "dynamic_sl_enabled": True,
    "dynamic_tp_enabled": True,
    "dead_weight_exit_enabled": True,
    # Session #2: Learning parameters
    "learning_enabled": True,
    "min_confidence_threshold": 45.0,
    "auto_optimize_sl_tp": True,
    "time_filter_enabled": True,
    "regime_filter_enabled": True,
    "error_pattern_pause": True,
    "max_loss_streak": 3,
    "cooldown_minutes": 30,
    "overtrade_threshold": 6,
}

class Settings:
    def __init__(self, config_path: str = "config/bot_config.json"):
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self._config = dict(DEFAULT_CONFIG)
                    self._config.update(loaded)
            except Exception as e:
                print(f"Config load error: {e}, using defaults")
                self._config = dict(DEFAULT_CONFIG)
        else:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            self._config = dict(DEFAULT_CONFIG)
            self.save()

    def get(self, key: str, default=None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        self._config[key] = value

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Config save error: {e}")

    def to_dict(self) -> dict:
        return dict(self._config)
