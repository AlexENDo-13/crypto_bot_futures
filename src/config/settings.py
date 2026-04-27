#!/usr/bin/env python3
"""Settings manager with defaults."""
import json
from pathlib import Path
from typing import Any, Dict

class Settings:
    DEFAULTS = {
        "api_key": "",
        "api_secret": "",
        "demo_mode": True,
        "timeframe": "15m",
        "mtf_timeframes": ["1h", "4h", "1d"],
        "use_multi_timeframe": True,
        "mtf_required_agreement": 2,
        "min_adx": 15,
        "min_atr_percent": 0.5,
        "min_volume_24h_usdt": 50000,
        "min_signal_strength": 0.35,
        "max_positions": 3,
        "max_risk_per_trade": 1.0,
        "max_total_risk_percent": 5.0,
        "max_leverage": 10,
        "default_sl_pct": 1.5,
        "default_tp_pct": 3.0,
        "daily_loss_limit_percent": 8.0,
        "trailing_stop_enabled": True,
        "trailing_stop_distance_percent": 2.0,
        "trailing_activation": 1.5,
        "trailing_callback": 0.5,
        "max_hold_time_minutes": 240,
        "anti_martingale_enabled": True,
        "anti_martingale_risk_reduction": 0.8,
        "reduce_risk_on_weekends": True,
        "weekend_risk_multiplier": 0.5,
        "daily_profit_target_percent": 5.0,
        "stop_on_daily_target": False,
        "max_orders_per_hour": 6,
        "scan_interval_minutes": 5,
        "cache_ttl_seconds": 60,
        "use_spread_filter": True,
        "max_spread_percent": 0.5,
        "max_funding_rate": 0.0,
        "correlation_limit_enabled": True,
        "max_daily_trades": 15,
        "partial_close_enabled": True,
        "partial_close_at_tp1": 0.50,
        "partial_close_at_tp2": 0.30,
        "breakeven_after_tp1": True,
        "dynamic_sl_enabled": True,
        "dynamic_tp_enabled": True,
        "dead_weight_exit_enabled": True,
        "trap_detector_enabled": True,
        "aggressive_adaptation": True,
        "fast_mode_empty_scans": True,
        "force_ignore_session": True,
        "symbols_whitelist": [],
        "blacklist": ["SHIB-USDT","PEPE-USDT","FLOKI-USDT","BONK-USDT","DOGE-USDT"],
    }

    def __init__(self, path: str):
        self._path = Path(path)
        self._data: Dict[str, Any] = dict(self.DEFAULTS)
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self._data.update(loaded)
            except Exception:
                pass

    def get(self, key: str, default=None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data)

    def save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
