"""Crypto Bot Futures — Main Entry Point."""
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
from src.ui.terminal_ui import TerminalUI

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

async def main():
    try:
        settings = Settings()
        bot_logger = BotLogger(log_dir=settings.get("log_dir", "logs"), level=getattr(logging, settings.get("log_level", "INFO").upper()))
        api_client = Exchange(api_key=settings.get("api_key", ""), api_secret=settings.get("api_secret", ""), testnet=settings.get("testnet", False))
        engine = TradingEngine(settings, bot_logger, api_client)

        # Start TerminalUI in background thread
        ui = TerminalUI(
            mode_switcher=engine.mode_switcher,
            position_tracker=engine,
            database=None,
            performance_profile=engine.performance_profile
        )
        ui_thread = threading.Thread(target=ui.start, daemon=True)
        ui_thread.start()

        bot_logger.info("Crypto Bot Futures v10.0 — Fixed Edition")
        await engine.start()
        while engine.is_running():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
    finally:
        if 'ui' in locals():
            ui.stop()
        if 'engine' in locals():
            await engine.stop()
        if 'api_client' in locals():
            await api_client.close()
        logger.info("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main())
