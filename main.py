#!/usr/bin/env python3
"""
CryptoBot v10.0 — Neural Adaptive Trading System (PRODUCTION READY)
Fixed: Real trading execution, proper position sizing, enhanced strategy engine.
"""
import sys
import asyncio
import logging
from pathlib import Path

import qasync
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from src.exchange.api_client import BingXAPIClient
from src.config.settings import Settings
from src.core.engine.trading_engine import TradingEngine
from src.core.bot_logger import BotLogger
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
    logger.info("Starting CryptoBot v10.0 (PRODUCTION READY)")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    settings = Settings("config/bot_config.json")

    import os
    api_key = os.getenv("BINGX_API_KEY", settings.get("api_key", ""))
    api_secret = os.getenv("BINGX_API_SECRET", settings.get("api_secret", ""))

    demo_mode = settings.get("demo_mode", True)
    testnet = demo_mode

    if not demo_mode:
        if not api_key or not api_secret:
            logger.warning("LIVE MODE selected but API keys missing — GUI will load, enter keys in Config tab")
        else:
            logger.warning("LIVE TRADING MODE ACTIVE — REAL MONEY AT RISK")
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

    if not demo_mode and (not api_key or not api_secret):
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(window)
        msg.setWindowTitle("API Keys Required")
        msg.setText("LIVE MODE requires API keys.\n\nPlease enter your BingX API Key and Secret in the Config tab, then click Save Settings.")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.exec()

    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    future = asyncio.get_event_loop().create_future()

    def on_last_window_closed():
        if not future.done():
            future.set_result(0)

    app.lastWindowClosed.connect(on_last_window_closed)

    await future

    logger.info("Shutting down application...")
    if engine.running:
        await engine.stop()
    await api_client.close()
    logger.info("Application shutdown complete")

    app.quit()

if __name__ == "__main__":
    try:
        qasync.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
