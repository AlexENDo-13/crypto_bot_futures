"""Crypto Bot Futures — Main Entry Point WITH GUI."""
import asyncio
import logging
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config.settings import Settings
from src.core.bot_logger import BotLogger
from src.exchange.exchange import Exchange
from src.core.engine.trading_engine import TradingEngine

# GUI imports
try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt
    GUI_AVAILABLE = True
except ImportError:
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        GUI_AVAILABLE = True
    except ImportError:
        GUI_AVAILABLE = False
        print("WARNING: PyQt not installed. GUI unavailable.")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def main():
    try:
        logger.info("=== MAIN START ===")
        settings = Settings()
        bot_logger = BotLogger(
            log_dir=settings.get("log_dir", "logs"),
            level=getattr(logging, settings.get("log_level", "INFO").upper())
        )
        api_client = Exchange(
            api_key=settings.get("api_key", ""),
            api_secret=settings.get("api_secret", ""),
            testnet=settings.get("testnet", False)
        )
        engine = TradingEngine(settings, bot_logger, api_client)
        logger.info("TradingEngine created")

        # Start engine in background thread (GUI runs in main thread)
        async def run_engine():
            bot_logger.info("Crypto Bot Futures v10.0 — GUI Mode")
            await engine.start()
            while engine.is_running():
                await asyncio.sleep(1)

        engine_thread = threading.Thread(target=lambda: asyncio.run(run_engine()), daemon=True)
        engine_thread.start()
        logger.info("Engine thread started")

        # Start GUI in main thread
        if GUI_AVAILABLE:
            logger.info("Starting GUI...")
            app = QApplication(sys.argv)
            app.setQuitOnLastWindowClosed(True)

            try:
                from src.ui.main_window import MainWindow
                window = MainWindow(engine=engine)
                window.show()
                logger.info("GUI window shown")
                app.exec_()  # PyQt5
            except Exception as e:
                logger.error(f"GUI error: {e}", exc_info=True)
                # Fallback: terminal mode
                logger.info("Falling back to terminal mode...")
                while engine.is_running():
                    await asyncio.sleep(1)
        else:
            logger.info("No GUI available, running in terminal mode...")
            while engine.is_running():
                await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
    finally:
        if 'engine' in locals():
            await engine.stop()
        if 'api_client' in locals():
            await api_client.close()
        logger.info("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main())
