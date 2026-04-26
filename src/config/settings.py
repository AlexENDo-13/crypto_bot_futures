#!/usr/bin/env python3
import os, json, threading
from typing import Any, Dict, List, Optional

class Settings:
    DEFAULTS: Dict[str, Any] = {
        "demo_mode": True, "virtual_balance": 100.0, "api_key": "", "api_secret": "",
        "base_url": "https://open-api.bingx.com", "timeframe": "15m",
        "scan_interval_minutes": 5, "max_positions": 3, "max_leverage": 10,
        "max_risk_per_trade": 1.0, "max_total_risk_percent": 5.0,
        "default_sl_pct": 1.5, "default_tp_pct": 3.0,
        "min_adx": 10.0, "min_atr_percent": 0.50, "min_volume_24h_usdt": 50000.0,
        "min_volume_ratio": 0.8, "max_funding_rate": 0.0,
        "use_spread_filter": True, "max_spread_percent": 0.5,
        "min_signal_strength": 0.25, "min_trend_score": 1.5,
        "daily_loss_limit_percent": 8.0, "max_orders_per_hour": 6,
        "anti_chase_threshold_percent": 0.3, "trailing_stop_enabled": True,
        "trailing_stop_distance_percent": 2.0, "trailing_activation": 1.5,
        "trailing_callback": 0.5, "use_stepped_take_profit": True,
        "anti_chase_enabled": True, "dead_weight_exit_enabled": True,
        "adaptive_tp_enabled": True, "max_hold_time_minutes": 240,
        "use_multi_timeframe": True, "mtf_timeframes": ["1h", "4h", "1d"],
        "mtf_required_agreement": 2, "use_bollinger_filter": True,
        "use_candle_patterns": True, "use_macd_indicator": True,
        "use_ichimoku_indicator": True, "use_vwap_indicator": True,
        "use_stochastic_indicator": True, "use_obv_indicator": True,
        "trap_detector_enabled": True, "predictive_entry_enabled": True,
        "use_neural_filter": True, "use_neural_predictor": False,
        "use_async_scan": True, "use_genetic_optimizer": False,
        "self_healing_enabled": True, "auto_recovery_enabled": True,
        "max_api_failures": 5, "export_trades_csv": True,
        "json_logging_enabled": True, "anti_martingale_enabled": True,
        "anti_martingale_risk_reduction": 0.8, "reduce_risk_on_weekends": True,
        "weekend_risk_multiplier": 0.5, "correlation_limit_enabled": True,
        "telegram_enabled": False, "telegram_bot_token": "",
        "telegram_chat_id": "", "telegram_commands_enabled": True,
        "telegram_daily_report_enabled": False, "telegram_proxy_url": "",
        "telegram_proxy_auto_rotate": False, "discord_enabled": False,
        "discord_webhook_url": "", "web_interface_enabled": False,
        "web_interface_port": 5000, "sound_enabled": True,
        "voice_enabled": False, "dark_theme": True, "show_charts": True,
        "symbols_whitelist": [],  # EMPTY = scan ALL available USDT pairs
        "blacklist": ["SHIB-USDT","PEPE-USDT","FLOKI-USDT","BONK-USDT","DOGE-USDT"],
        "max_daily_trades": 15, "daily_profit_target_percent": 5.0,
        "stop_on_daily_target": False, "force_ignore_session": True,
        "log_level": "INFO", "log_to_file": True, "log_max_mb": 10,
        "log_backup_count": 10, "partial_close_enabled": True,
        "partial_close_at_tp1": 0.50, "partial_close_at_tp2": 0.30,
        "breakeven_after_tp1": True, "dynamic_sl_enabled": True,
        "dynamic_tp_enabled": True, "volatility_adjustment": True,
        "liquidity_check_enabled": True, "min_liquidity_score": 0.3,
        "adaptive_scan_interval": True, "fast_mode_empty_scans": True,
        "aggressive_adaptation": True,
        "cache_ttl_seconds": 60,
        "position_mode": "HEDGE",  # HEDGE mode requires positionSide
    }

    def __init__(self, config_path: str = "config/bot_config.json"):
        self.config_path = config_path
        self._data = dict(self.DEFAULTS)
        self._lock = threading.RLock()
        self._callbacks = []
        self.load()

    def load(self):
        with self._lock:
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    self._data.update(loaded)
                except Exception as e:
                    print(f"Config load error: {e}")
            for k, v in self.DEFAULTS.items():
                if k not in self._data:
                    self._data[k] = v

    def save(self):
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self.config_path) or ".", exist_ok=True)
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Config save error: {e}")

    def get(self, key: str, default: Any = None):
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any):
        with self._lock:
            old = self._data.get(key)
            self._data[key] = value
            if old != value:
                self.save()

    def update(self, new_data: Dict[str, Any]):
        with self._lock:
            for k, v in new_data.items():
                if self._data.get(k) != v:
                    self._data[k] = v
            self.save()

    def to_dict(self):
        with self._lock:
            return dict(self._data)

    def reset_to_defaults(self):
        with self._lock:
            self._data = dict(self.DEFAULTS)
            self.save()

    def export(self, path: str) -> bool:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def import_from(self, path: str) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.update(json.load(f))
            return True
        except Exception:
            return False
