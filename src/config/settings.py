#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Settings — конфигурация бота (словарь + dataclass совместимость)
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict


logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    # === API ===
    "api_key": os.getenv("BINGX_API_KEY", ""),
    "api_secret": os.getenv("BINGX_API_SECRET", ""),
    "base_url": os.getenv("BINGX_BASE_URL", "https://open-api.bingx.com"),
    
    # === Режим ===
    "demo_mode": os.getenv("PAPER_TRADING", "true").lower() == "true",
    "virtual_balance": 100.0,
    
    # === Рынок ===
    "timeframe": os.getenv("TIMEFRAME", "15m"),
    "scan_interval_minutes": int(os.getenv("SCAN_INTERVAL", "5")),
    "max_positions": int(os.getenv("MAX_POSITIONS", "2")),
    
    # === Фильтры ===
    "min_adx": int(os.getenv("MIN_ADX", "10")),
    "min_atr_percent": float(os.getenv("MIN_ATR_PERCENT", "0.5")),
    "min_volume_24h_usdt": float(os.getenv("MIN_VOLUME", "50000")),
    "min_volume_ratio": float(os.getenv("MIN_VOLUME_RATIO", "0.8")),
    "max_funding_rate": 0.0,
    "use_spread_filter": True,
    "max_spread_percent": 0.3,
    
    # === Сигналы ===
    "min_signal_strength": float(os.getenv("MIN_SIGNAL_STRENGTH", "0.35")),
    "min_trend_score": float(os.getenv("MIN_TREND_SCORE", "1.5")),
    
    # === Риск-менеджмент ===
    "max_risk_per_trade": float(os.getenv("RISK_PER_TRADE_PCT", "1.0")),
    "max_total_risk_percent": float(os.getenv("MAX_RISK_PER_DAY_PCT", "5.0")),
    "max_leverage": int(os.getenv("LEVERAGE", "10")),
    "default_sl_pct": float(os.getenv("DEFAULT_SL_PCT", "1.5")),
    "default_tp_pct": float(os.getenv("DEFAULT_TP_PCT", "3.0")),
    "daily_loss_limit_percent": 8.0,
    "max_orders_per_hour": 6,
    "anti_chase_threshold_percent": 0.3,
    
    # === Трейлинг-стоп ===
    "trailing_stop_enabled": os.getenv("USE_TRAILING_STOP", "true").lower() == "true",
    "trailing_stop_distance_percent": 2.0,
    "trailing_activation": float(os.getenv("TRAILING_ACTIVATION", "1.5")),
    "trailing_callback": float(os.getenv("TRAILING_CALLBACK", "0.5")),
    
    # === Выходы ===
    "use_stepped_take_profit": True,
    "anti_chase_enabled": True,
    "dead_weight_exit_enabled": True,
    "adaptive_tp_enabled": True,
    "max_hold_time_minutes": int(os.getenv("MAX_HOLD_TIME_MINUTES", "240")),
    
    # === Индикаторы ===
    "use_multi_timeframe": True,
    "use_bollinger_filter": True,
    "use_candle_patterns": True,
    "use_macd_indicator": True,
    "use_ichimoku_indicator": True,
    
    # === Предиктивные ===
    "trap_detector_enabled": True,
    "predictive_entry_enabled": True,
    "use_neural_filter": True,
    "use_neural_predictor": False,
    
    # === Производительность ===
    "use_async_scan": True,
    "use_genetic_optimizer": True,
    "self_healing_enabled": True,
    
    # === Данные ===
    "export_trades_csv": True,
    "json_logging_enabled": True,
    
    # === Anti-martingale ===
    "anti_martingale_enabled": True,
    "anti_martingale_risk_reduction": 0.8,
    "reduce_risk_on_weekends": True,
    "weekend_risk_multiplier": 0.5,
    "correlation_limit_enabled": True,
    
    # === Telegram ===
    "telegram_enabled": False,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_commands_enabled": True,
    "telegram_daily_report_enabled": False,
    "telegram_proxy_url": "",
    "telegram_proxy_auto_rotate": False,
    
    # === Discord ===
    "discord_enabled": False,
    "discord_webhook_url": "",
    
    # === Web ===
    "web_interface_enabled": False,
    "web_interface_port": 5000,
    
    # === UI ===
    "sound_enabled": True,
    "voice_enabled": False,
    "dark_theme": True,
    
    # === Символы ===
    "symbols_whitelist": [
        "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT",
        "ADA-USDT", "AVAX-USDT", "LINK-USDT", "MATIC-USDT", "DOT-USDT",
        "LTC-USDT", "BCH-USDT", "ETC-USDT", "UNI-USDT", "ATOM-USDT"
    ],
    "blacklist": ["SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "BONK-USDT"],
    
    # === Дополнительно ===
    "max_daily_trades": 10,
    "daily_profit_target_percent": 5.0,
    "stop_on_daily_target": True,
    "force_ignore_session": False,
}


CONFIG_FILE = Path("config/bot_config.json")


class Settings:
    """
    Настройки бота — словарь с load/save/update.
    Совместим с ConfigPanel (data, update, load).
    """
    
    def __init__(self, config_file: Optional[str] = None):
        self._config_file = Path(config_file) if config_file else CONFIG_FILE
        self._data: Dict[str, Any] = {}
        self.load()
    
    @property
    def data(self) -> Dict[str, Any]:
        """Вернуть текущий конфиг (для ConfigPanel)"""
        return self._data.copy()
    
    def load(self) -> Dict[str, Any]:
        """Загрузить конфиг из файла или создать дефолтный"""
        if self._config_file.exists():
            try:
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                self._data = {**DEFAULT_CONFIG, **loaded}
                logger.info(f"Конфиг загружен из {self._config_file}")
            except Exception as e:
                logger.warning(f"Ошибка загрузки конфига: {e}, используем дефолт")
                self._data = DEFAULT_CONFIG.copy()
        else:
            self._data = DEFAULT_CONFIG.copy()
            self.save()
            logger.info(f"Создан дефолтный конфиг: {self._config_file}")
        
        return self._data.copy()
    
    def save(self):
        """Сохранить конфиг в файл"""
        try:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=4, ensure_ascii=False)
            logger.info(f"Конфиг сохранён в {self._config_file}")
        except Exception as e:
            logger.error(f"Ошибка сохранения конфига: {e}")
    
    def update(self, updates: Dict[str, Any]):
        """Обновить настройки (вызывается из ConfigPanel.save_settings)"""
        self._data.update(updates)
        self.save()
        logger.info("Настройки обновлены")
    
    def get(self, key: str, default=None):
        """Получить значение по ключу"""
        return self._data.get(key, default)
    
    def __getattr__(self, name: str):
        """
        Доступ к настройкам как к атрибутам (для совместимости с dataclass).
        Например: settings.API_KEY → settings._data["api_key"]
        """
        # Сначала проверить верхний регистр (старые имена)
        upper_name = name.upper()
        for key in self._data:
            if key.upper() == upper_name or key == name:
                return self._data[key]
        
        # Дефолтные значения для старых имен
        mapping = {
            'TIMEFRAME': 'timeframe',
            'SCAN_INTERVAL': 'scan_interval_minutes',
            'MAX_POSITIONS': 'max_positions',
            'MIN_ADX': 'min_adx',
            'MIN_ATR_PERCENT': 'min_atr_percent',
            'MIN_VOLUME': 'min_volume_24h_usdt',
            'MIN_VOLUME_RATIO': 'min_volume_ratio',
            'MIN_SIGNAL_STRENGTH': 'min_signal_strength',
            'MIN_TREND_SCORE': 'min_trend_score',
            'RISK_PER_TRADE_PCT': 'max_risk_per_trade',
            'MAX_RISK_PER_DAY_PCT': 'max_total_risk_percent',
            'LEVERAGE': 'max_leverage',
            'DEFAULT_SL_PCT': 'default_sl_pct',
            'DEFAULT_TP_PCT': 'default_tp_pct',
            'USE_TRAILING_STOP': 'trailing_stop_enabled',
            'TRAILING_ACTIVATION': 'trailing_activation',
            'TRAILING_CALLBACK': 'trailing_callback',
            'MAX_HOLD_TIME_MINUTES': 'max_hold_time_minutes',
            'SYMBOLS_WHITELIST': 'symbols_whitelist',
            'BLACKLIST': 'blacklist',
            'LOG_LEVEL': 'log_level',
            'LOG_FILE': 'log_file',
            'API_KEY': 'api_key',
            'API_SECRET': 'api_secret',
            'BASE_URL': 'base_url',
            'PAPER_TRADING': 'demo_mode',
        }
        
        if name in mapping:
            return self._data.get(mapping[name], default)
        
        raise AttributeError(f"'Settings' object has no attribute '{name}'")
    
    @property
    def QTY_STEP(self) -> Dict[str, float]:
        """Совместимость с TradeExecutor"""
        return {
            "BTC-USDT": 0.001,
            "ETH-USDT": 0.001,
            "default": 0.001
        }
    
    @property
    def MIN_QTY(self) -> Dict[str, float]:
        """Совместимость с TradeExecutor"""
        return {
            "BTC-USDT": 0.001,
            "ETH-USDT": 0.001,
            "default": 0.001
        }


# Для обратной совместимости с dataclass
@dataclass
class SettingsLegacy:
    """Старый dataclass (если где-то используется явно)"""
    API_KEY: str = ""
    API_SECRET: str = ""
    BASE_URL: str = "https://open-api.bingx.com"
    PAPER_TRADING: bool = True
    TIMEFRAME: str = "15m"
    SCAN_INTERVAL: int = 60
    MAX_POSITIONS: int = 3
    MIN_ADX: float = 10.0
    MIN_ATR_PERCENT: float = 0.5
    MIN_VOLUME: float = 50000.0
    MIN_VOLUME_RATIO: float = 0.8
    MIN_SIGNAL_STRENGTH: float = 0.35
    MIN_TREND_SCORE: float = 1.5
    RISK_PER_TRADE_PCT: float = 1.0
    MAX_RISK_PER_DAY_PCT: float = 5.0
    LEVERAGE: int = 10
    DEFAULT_SL_PCT: float = 1.5
    DEFAULT_TP_PCT: float = 3.0
    USE_TRAILING_STOP: bool = True
    TRAILING_ACTIVATION: float = 1.5
    TRAILING_CALLBACK: float = 0.5
    MAX_HOLD_TIME_MINUTES: int = 240
    SYMBOLS_WHITELIST: List[str] = field(default_factory=lambda: [
        "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT"
    ])
    BLACKLIST: List[str] = field(default_factory=lambda: [
        "SHIB-USDT", "PEPE-USDT"
    ])
    QTY_STEP: Dict[str, float] = field(default_factory=lambda: {
        "BTC-USDT": 0.001,
        "ETH-USDT": 0.001,
        "default": 0.001
    })
    MIN_QTY: Dict[str, float] = field(default_factory=lambda: {
        "BTC-USDT": 0.001,
        "ETH-USDT": 0.001,
        "default": 0.001
    })
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/trading_bot.log"
