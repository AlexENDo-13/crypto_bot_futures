#!/usr/bin/env python3
"""
🧹 cleanup_and_fix.py — Очистка кэша и исправление конфигурации BingX Bot

Запускать после применения патчей для сброса старых настроек.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")

def backup_and_remove(path: Path, description: str):
    """Создает бэкап и удаляет файл/папку"""
    if not path.exists():
        print(f"  ℹ️  {description}: не найдено")
        return

    # Создаем бэкап с timestamp
    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{path.name}_{timestamp}.bak"
    backup_path = backup_dir / backup_name

    try:
        if path.is_file():
            shutil.copy2(path, backup_path)
            path.unlink()
        else:
            shutil.copytree(path, backup_path)
            shutil.rmtree(path)
        print(f"  ✅ {description}: удалено (бэкап: {backup_path})")
    except Exception as e:
        print(f"  ❌ {description}: ошибка — {e}")

def reset_config_to_defaults():
    """Сбрасывает user_config.json к дефолтным значениям с исправлениями"""
    print_header("📝 Сброс конфигурации")

    config_path = Path("src/config/user_config.json")

    # Исправленные дефолтные значения
    fixed_defaults = {
        "_config_version": 7,
        # API — оставляем пустые, пользователь заполнит
        "api_key": "",
        "api_secret": "",
        "demo_mode": True,
        "virtual_balance": 21.0,

        # === ИСПРАВЛЕННЫЕ РИСК-ПАРАМЕТРЫ ===
        "max_risk_per_trade": 2.0,
        "max_leverage": 3,
        "max_positions": 2,
        "max_total_risk_percent": 30.0,
        "daily_loss_limit_percent": 10.0,
        "max_orders_per_hour": 8,
        "min_position_notional": 5.0,
        "unrealized_drawdown_limit_percent": 15.0,
        "max_margin_percent": 80.0,

        # === ИСПРАВЛЕННЫЕ ПАРАМЕТРЫ СКАНИРОВАНИЯ ===
        "scan_interval_minutes": 2,
        "min_volume_24h_usdt": 100000,  # ← Снижено с 200000
        "min_atr_percent": 1.0,  # ← Снижено с 1.5
        "max_funding_rate": 0.001,  # ← ИСПРАВЛЕНО: 0.0 → 0.001 (0.1%)
        "min_adx": 15,  # ← Снижено с 20
        "force_ignore_session": True,

        # Фичи
        "use_genetic_optimizer": True,
        "self_healing_enabled": True,
        "trailing_stop_enabled": True,
        "trailing_stop_distance_percent": 1.5,
        "use_multi_timeframe": True,
        "use_stepped_take_profit": True,
        "stepped_tp_levels": [
            {"profit_percent": 2.5, "close_ratio": 0.5},
            {"profit_percent": 5.0, "close_ratio": 0.3},
            {"profit_percent": 10.0, "close_ratio": 0.2}
        ],
        "anti_chase_enabled": True,
        "adaptive_tp_enabled": True,
        "dead_weight_exit_enabled": True,
        "predictive_entry_enabled": True,
        "trap_detector_enabled": True,
        "use_neural_filter": False,
        "use_neural_predictor": False,
        "neural_confidence_threshold": 0.55,

        # Веса ТФ
        "tf_weight_15m": 0.2,
        "tf_weight_1h": 0.3,
        "tf_weight_4h": 0.3,
        "tf_weight_1d": 0.2,

        # Уведомления
        "telegram_enabled": False,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_commands_enabled": True,
        "discord_enabled": False,
        "discord_webhook_url": "",

        # Веб
        "web_interface_enabled": False,
        "web_interface_port": 5000,

        # Система
        "log_level": "DEBUG",
        "json_logging_enabled": True,
        "export_trades_csv": True,
        "cache_klines": False,
        "cache_ttl_minutes": 30,
        "use_async_scan": True,
        "async_concurrency": 10,
        "keep_top_weights": 3,
        "weekend_trading": False,
        "reduce_risk_on_weekends": True,
        "weekend_risk_multiplier": 0.5,

        # Стадии роста
        "staged_risk": True,
        "stages": [
            {"balance_up_to": 30, "risk_percent": 3.0, "leverage": 3},
            {"balance_up_to": 100, "risk_percent": 2.0, "leverage": 3},
            {"balance_up_to": 500, "risk_percent": 1.0, "leverage": 2}
        ],

        # Корреляции
        "correlation_limit_enabled": True,
        "correlation_groups": {
            "btc_eth": ["BTC/USDT", "ETH/USDT"],
            "layer1": ["BNB/USDT", "SOL/USDT", "AVAX/USDT"],
            "meme": ["DOGE/USDT", "SHIB/USDT", "PEPE/USDT"]
        },

        # Цели
        "daily_profit_target_percent": 20.0,
        "stop_on_daily_target": False,
        "max_daily_trades": 8,
        "health_score_threshold": 0.3,

        # Доп. фильтры
        "use_spread_filter": True,
        "max_spread_percent": 0.3,
        "anti_martingale_enabled": True,
        "anti_martingale_risk_reduction": 0.8,
        "anti_chase_threshold_percent": 0.3,
        "use_bollinger_filter": True,
        "use_candle_patterns": True,
        "use_macd_indicator": True,
        "use_ichimoku_indicator": True,
        "telegram_daily_report_enabled": False,
        "sound_enabled": True,
        "voice_enabled": False,
        "smart_growth_enabled": True,
        "growth_compound_rate": 0.5,
        "max_risk_boost_on_growth": 1.5,
        "recovery_mode_enabled": True,
        "dark_theme": True
    }

    try:
        # Создаем бэкап старого конфига если есть
        if config_path.exists():
            backup_and_remove(config_path, "Старый user_config.json")

        # Пишем новый конфиг
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(fixed_defaults, f, indent=4, ensure_ascii=False)

        print(f"  ✅ Новый конфиг создан: {config_path}")
        print(f"     Ключевые изменения:")
        print(f"       • max_funding_rate: 0.0 → 0.001 (разрешает фандинг до 0.1%)")
        print(f"       • min_adx: 20 → 15")
        print(f"       • min_atr_percent: 1.5 → 1.0")
        print(f"       • min_volume_24h_usdt: 200000 → 100000")

    except Exception as e:
        print(f"  ❌ Ошибка создания конфига: {e}")
        return False

    return True

def clean_cache():
    """Очищает все кэши"""
    print_header("🗑️  Очистка кэша")

    cache_paths = [
        (Path("data/cache"), "Кэш индикаторов"),
        (Path("data/models/strategy_weights.json"), "Веса стратегии"),
        (Path("data/models/thresholds.json"), "Генетические пороги"),
        (Path("data/ml_models"), "ML модели"),
    ]

    for path, desc in cache_paths:
        backup_and_remove(path, desc)

    # Очищаем кэш Python
    pycache_dirs = list(Path("src").rglob("__pycache__"))
    print(f"  🐍 Найдено {len(pycache_dirs)} папок __pycache__")
    for pycache in pycache_dirs:
        try:
            shutil.rmtree(pycache)
            print(f"    Удалено: {pycache}")
        except Exception as e:
            print(f"    Ошибка {pycache}: {e}")

def clean_logs(keep_last: int = 3):
    """Оставляет только последние N файлов логов"""
    print_header("📋 Очистка логов")

    log_dir = Path("data/logs")
    if not log_dir.exists():
        print("  ℹ️  Папка логов не найдена")
        return

    log_files = sorted(log_dir.glob("*_bot.log"), key=lambda x: x.stat().st_mtime, reverse=True)

    if len(log_files) <= keep_last:
        print(f"  ℹ️  Логов {len(log_files)}, оставляем все")
        return

    for old_log in log_files[keep_last:]:
        try:
            old_log.unlink()
            print(f"  🗑️  Удалён старый лог: {old_log.name}")
        except Exception as e:
            print(f"  ❌ Ошибка удаления {old_log.name}: {e}")

    print(f"  ✅ Оставлено последних {keep_last} логов")

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║     🧹 ОЧИСТКА И СБРОС BINGX TRADING BOT                 ║
║         v1.0 — Исправление критических фильтров          ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Проверяем что мы в корне проекта
    if not Path("src").exists():
        print("❌ Ошибка: запускайте из корня проекта (где папка src/)")
        sys.exit(1)

    clean_cache()
    reset_config_to_defaults()
    clean_logs(keep_last=3)

    print_header("✅ ГОТОВО")
    print("""
Сделано:
  • Кэш индикаторов и моделей удалён
  • user_config.json сброшен с ИСПРАВЛЕННЫМИ значениями
  • Старые логи удалены

Теперь:
  1. Примените патчи для market_scanner.py (если ещё не)
  2. Запустите бота — он создаст новый кэш с правильными параметрами
  3. Проверьте логи на наличие сигналов

Важно: API ключи нужно будет ввести заново в настройках!
    """)

if __name__ == "__main__":
    main()
