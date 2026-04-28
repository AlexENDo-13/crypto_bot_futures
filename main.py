#!/usr/bin/env python3
"""
CryptoBot v11.1 — Neural Adaptive Trading System (STABLE)
Fixed: Graceful shutdown, QThread API worker, memory monitor, offline guard.
"""
import sys
import asyncio
import logging
import signal
from pathlib import Path

import qasync
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, Qt

from src.exchange.api_client import BingXAPIClient
from src.config.settings import Settings
from src.core.engine.trading_engine import TradingEngine
from src.core.bot_logger import BotLogger
from src.ui.main_window import MainWindow
from src.core.stability.graceful_shutdown import ShutdownManager
from src.core.stability.memory_monitor import MemoryMonitor
from src.core.stability.offline_guard import OfflineGuard
from src.core.stability.watchdog import EngineWatchdog

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
    logger.info("Starting CryptoBot v11.1 (STABLE)")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Stability: Memory monitor
    mem_monitor = MemoryMonitor(max_mb=512, check_interval_sec=30)
    mem_monitor.start()

    # Stability: Offline guard
    offline_guard = OfflineGuard(check_interval_sec=10)
    offline_guard.start()

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
        msg.setText("LIVE MODE requires API keys.\\n\\nPlease enter your BingX API Key and Secret in the Config tab, then click Save Settings.")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.exec()

    # Stability: Watchdog — auto-restart engine if it hangs
    watchdog = EngineWatchdog(engine, api_client, restart_threshold_sec=60)
    watchdog.start()

    # Stability: Graceful shutdown manager
    shutdown_mgr = ShutdownManager(app, engine, api_client, mem_monitor, offline_guard, watchdog)

    # Handle Ctrl+C and system signals
    def signal_handler(signum, frame):
        logger.info(f"Signal {signum} received, initiating graceful shutdown...")
        asyncio.create_task(shutdown_mgr.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    future = asyncio.get_event_loop().create_future()

    def on_last_window_closed():
        if not future.done():
            logger.info("Last window closed, shutting down...")
            asyncio.create_task(shutdown_mgr.shutdown())
            if not future.done():
                future.set_result(0)

    app.lastWindowClosed.connect(on_last_window_closed)

    # Wait for shutdown
    try:
        await future
    except asyncio.CancelledError:
        pass

    logger.info("Application shutdown complete")
    app.quit()

if __name__ == "__main__":
    try:
        qasync.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
