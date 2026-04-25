#!/usr/bin/env python3
"""
CryptoBot v9.1 - Neural Adaptive Trading System (FIXED)
Main entry point with qasync event loop integration.
"""
import sys
import asyncio
import logging
from pathlib import Path

import qasync
from PyQt6.QtWidgets import QApplication

from src.exchange.api_client import BingXAPIClient
from src.config.settings import Settings
from src.core.engine.trading_engine import TradingEngine
from src.core.logger import BotLogger
from src.ui.main_window import MainWindow


def setup_logging():
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger = logging.getLogger("CryptoBot")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s CryptoBot.%(name)s | %(message)s",
        datefmt="%H:%M:%S"
    )
    file_handler = logging.FileHandler(log_dir / "bot.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


async def main():
    logger = setup_logging()
    logger.info("Starting CryptoBot v9.1 (FIXED)")

    app = QApplication(sys.argv)

    # Загружаем настройки
    settings = Settings("config/bot_config.json")

    # API ключи из переменных окружения или из конфига
    import os
    api_key = os.getenv("BINGX_API_KEY", settings.get("api_key", ""))
    api_secret = os.getenv("BINGX_API_SECRET", settings.get("api_secret", ""))

    # РЕЖИМ ТОРГОВЛИ: demo_mode=false -> LIVE, demo_mode=true -> PAPER
    demo_mode = settings.get("demo_mode", True)
    testnet = demo_mode  # Если demo_mode=True, используем testnet/paper

    if not demo_mode:
        if not api_key or not api_secret:
            logger.error("!!! LIVE MODE ТРЕБУЕТ API КЛЮЧИ !!!")
            logger.error("Установите BINGX_API_KEY и BINGX_API_SECRET")
            # Можно показать QMessageBox здесь
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Ошибка", "Для live-торговли нужны API ключи BingX!")
            sys.exit(1)
        logger.warning("=" * 60)
        logger.warning("  LIVE TRADING MODE АКТИВИРОВАН")
        logger.warning("  Бот будет торговать РЕАЛЬНЫМИ средствами!")
        logger.warning("=" * 60)
    else:
        logger.info("PAPER / DEMO MODE — торговля виртуальными средствами")

    # Инициализация API клиента
    api_client = BingXAPIClient(
        api_key=api_key,
        api_secret=api_secret,
        base_url="https://open-api.bingx.com",
        testnet=testnet
    )

    # Логгер бота
    bot_logger = BotLogger()

    # Создаём торговый движок
    engine = TradingEngine(
        settings=settings,
        logger=bot_logger,
        api_client=api_client,
        telegram=None
    )

    # Создание и отображение главного окна
    window = MainWindow(api_client=api_client, engine=engine, settings=settings)
    window.show()

    logger.info("MainWindow displayed")

    # Запускаем движок
    await engine.start()

    # Запуск основного цикла событий PyQt6 через qasync
    await app.exec()

    # Корректное завершение
    await engine.stop()
    await api_client.close()
    logger.info("Application shutdown complete")


if __name__ == "__main__":
    qasync.run(main())
