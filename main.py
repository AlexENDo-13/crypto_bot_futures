#!/usr/bin/env python3
"""
CryptoBot v9.1 - Neural Adaptive Trading System (FIXED)
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
    settings = Settings("config/bot_config.json")

    import os
    api_key = os.getenv("BINGX_API_KEY", settings.get("api_key", ""))
    api_secret = os.getenv("BINGX_API_SECRET", settings.get("api_secret", ""))

    demo_mode = settings.get("demo_mode", True)
    testnet = demo_mode

    if not demo_mode:
        if not api_key or not api_secret:
            logger.error("!!! LIVE MODE REQUIRES API KEYS !!!")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Error", "API keys required for live trading!")
            sys.exit(1)
        logger.warning("LIVE TRADING MODE ACTIVE")
    else:
        logger.info("PAPER / DEMO MODE")

    api_client = BingXAPIClient(
        api_key=api_key,
        api_secret=api_secret,
        base_url="https://open-api.bingx.com",
        testnet=testnet
    )

    bot_logger = BotLogger()

    engine = TradingEngine(
        settings=settings,
        logger=bot_logger,
        api_client=api_client,
        telegram=None
    )

    window = MainWindow(api_client=api_client, engine=engine, settings=settings)
    window.show()

    logger.info("MainWindow displayed")

    await app.exec()

    if engine.running:
        await engine.stop()
    await api_client.close()
    logger.info("Application shutdown complete")


if __name__ == "__main__":
    qasync.run(main())
