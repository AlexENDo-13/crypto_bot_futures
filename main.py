#!/usr/bin/env python3
"""
CryptoBot v9.0 - Neural Adaptive Trading System
Main entry point with qasync event loop integration.
"""
import sys
import asyncio
import logging
from pathlib import Path

import qasync
from PyQt6.QtWidgets import QApplication

from src.exchange.api_client import BingXAPIClient
from src.ui.main_window import MainWindow
from src.utils.logger import BotLogger


def setup_logging():
    """Configure root logger and bot-specific logger"""
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
    # Инициализация логирования
    logger = setup_logging()
    logger.info("Starting CryptoBot v9.0 GUI")
    
    # Создаём приложение Qt
    app = QApplication(sys.argv)
    
    # Загружаем конфигурацию (предположим, из переменных окружения или файла)
    import os
    api_key = os.getenv("BINGX_API_KEY", "")
    api_secret = os.getenv("BINGX_API_SECRET", "")
    testnet = os.getenv("BINGX_TESTNET", "true").lower() == "true"
    
    # Инициализация API клиента
    api_client = BingXAPIClient(
        api_key=api_key,
        api_secret=api_secret,
        base_url="https://open-api.bingx.com",
        testnet=testnet
    )
    
    # Создание и отображение главного окна
    window = MainWindow(api_client=api_client)
    window.show()
    
    logger.info("MainWindow displayed")
    
    # Запуск основного цикла событий PyQt6 через qasync
    await app.exec()
    
    # Корректное завершение всех асинхронных ресурсов
    await api_client.close()
    logger.info("Application shutdown complete")


if __name__ == "__main__":
    qasync.run(main())
