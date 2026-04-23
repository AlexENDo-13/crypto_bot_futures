#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Settings — расширенный менеджер настроек с полными дефолтами.
"""
import os
import json


class Settings:
    """Управление настройками бота с валидацией."""

    DEFAULTS = {
        "demo_mode": True,
        "virtual_balance": 100.0,
        "api_key": "",
        "api_secret": "",
        "base_url": "https://open-api.bingx.com",
        "timeframe": "15m",
        "scan_interval_minutes": 5,
        "max_positions": 2,
        "min_adx": 15,
        "min_atr_percent": 1.0,
        "min_volume_24h_usdt": 100000.0,
        "min_volume_ratio": 0.8,
        "max_funding_rate": 0.0,
        "use_spread_filter": True,
        "max_spread_percent": 0.3,
        "min_signal_strength": 0.35,
        "min_trend_score": 1.5,
        "max_risk_per_trade": 1.0,
        "max_total_risk_percent": 5.0,
        "max_leverage": 10,
        "default_sl_pct": 1.5,
        "default_tp_pct": 3.0,
        "daily_loss_limit_percent": 8.0,
        "max_orders_per_hour": 6,
        "anti_chase_threshold_percent": 0.3,
        "trailing_stop_enabled": True,
        "trailing_stop_distance_percent": 2.0,
        "trailing_activation": 1.5,
        "trailing_callback": 0.5,
        "use_stepped_take_profit": True,
        "anti_chase_enabled": True,
        "dead_weight_exit_enabled": True,
        "adaptive_tp_enabled": True,
        "max_hold_time_minutes": 240,
        "use_multi_timeframe": True,
        "use_bollinger_filter": True,
        "use_candle_patterns": True,
        "use_macd_indicator": True,
        "use_ichimoku_indicator": True,
        "trap_detector_enabled": True,
        "predictive_entry_enabled": True,
        "use_neural_filter": True,
        "use_neural_predictor": False,
        "use_async_scan": True,
        "use_genetic_optimizer": True,
        "self_healing_enabled": True,
        "export_trades_csv": True,
        "json_logging_enabled": True,
        "anti_martingale_enabled": True,
        "anti_martingale_risk_reduction": 0.8,
        "reduce_risk_on_weekends": True,
        "weekend_risk_multiplier": 0.5,
        "correlation_limit_enabled": True,
        "telegram_enabled": False,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_commands_enabled": True,
        "telegram_daily_report_enabled": False,
        "telegram_proxy_url": "",
        "telegram_proxy_auto_rotate": False,
        "discord_enabled": False,
        "discord_webhook_url": "",
        "web_interface_enabled": False,
        "web_interface_port": 5000,
        "sound_enabled": True,
        "voice_enabled": False,
        "dark_theme": True,
        "symbols_whitelist": [
            "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT",
            "ADA-USDT", "AVAX-USDT", "LINK-USDT", "MATIC-USDT", "DOT-USDT",
            "LTC-USDT", "BCH-USDT", "ETC-USDT", "UNI-USDT", "ATOM-USDT"
        ],
        "blacklist": ["SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "BONK-USDT"],
        "max_daily_trades": 10,
        "daily_profit_target_percent": 5.0,
        "stop_on_daily_target": False,
        "force_ignore_session": True,
        "log_level": "INFO",
    }

    def __init__(self, config_path="config/bot_config.json"):
        self.config_path = config_path
        self._data = dict(self.DEFAULTS)
        self.load()

    @property
    def data(self):
        return self._data

    def load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                try:
                    file_data = json.load(f)
                    self._data.update(file_data)
                except json.JSONDecodeError:
                    pass
        # Ensure all defaults exist
        for key, val in self.DEFAULTS.items():
            if key not in self._data:
                self._data[key] = val

    def save(self):
        os.makedirs(os.path.dirname(self.config_path) or ".", exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=4, ensure_ascii=False)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def update(self, new_data: dict):
        self._data.update(new_data)
        self.save()

    def to_dict(self):
        return dict(self._data)
