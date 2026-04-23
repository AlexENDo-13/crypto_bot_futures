#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup.py — установка зависимостей и первичная настройка.
"""
import subprocess
import sys
import os
import json


def install_requirements():
    """Устанавливает зависимости."""
    print("📦 Установка зависимостей...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    print("✅ Зависимости установлены")


def create_config():
    """Создаёт конфигурационный файл."""
    config_dir = "config"
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, "bot_config.json")

    if os.path.exists(config_path):
        print(f"⚠️ Файл {config_path} уже существует")
        return

    default_config = {
        "demo_mode": True,
        "virtual_balance": 100.0,
        "api_key": "",
        "api_secret": "",
        "timeframe": "15m",
        "scan_interval_minutes": 5,
        "max_positions": 2,
        "max_risk_per_trade": 1.0,
        "max_leverage": 10,
        "default_sl_pct": 1.5,
        "default_tp_pct": 3.0,
        "daily_loss_limit_percent": 8.0,
        "trailing_stop_enabled": True,
        "trailing_stop_distance_percent": 2.0,
        "telegram_enabled": False,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "discord_enabled": False,
        "discord_webhook_url": "",
        "symbols_whitelist": [
            "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT"
        ],
        "blacklist": ["SHIB-USDT", "PEPE-USDT"],
        "log_level": "INFO",
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(default_config, f, indent=4, ensure_ascii=False)

    print(f"✅ Создан {config_path}")
    print("⚠️ ВАЖНО: Заполните api_key и api_secret для реального режима!")


def create_directories():
    """Создаёт необходимые директории."""
    dirs = ["data", "logs"]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    print("✅ Директории созданы")


if __name__ == "__main__":
    print("🚀 Настройка Crypto Trading Bot...")
    install_requirements()
    create_directories()
    create_config()
    print("\n✅ Настройка завершена!")
    print("Запуск: python main.py")
