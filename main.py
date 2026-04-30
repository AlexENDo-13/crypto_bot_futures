#!/usr/bin/env python3
import sys
import os
import asyncio
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config.settings import Settings
from src.exchange.exchange import Exchange
from src.core.bot_logger import BotLogger
from src.core.engine.trading_engine import TradingEngine
from src.ui.main_window import MainWindow

def run_engine_in_thread(engine: TradingEngine):
    """Запускает TradingEngine в отдельном потоке с собственным event loop."""
    def thread_target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(engine.start())
            loop.run_forever()
        except Exception as e:
            print(f"Engine thread error: {e}")
        finally:
            loop.close()
    
    thread = threading.Thread(target=thread_target, daemon=True)
    thread.start()
    return thread

def main():
    print("=== MAIN START ===")
    
    # Инициализация логгера
    logger = BotLogger(log_dir="logs", level="INFO")
    
    # Загрузка настроек
    settings = Settings()
    
    # === ИСПРАВЛЕНО: правильные аргументы для Exchange ===
    api_key = settings.get("api_key", "")
    api_secret = settings.get("api_secret", "")
    testnet = settings.get("testnet", False)
    
    exchange = Exchange(
        api_key=api_key,
        api_secret=api_secret,
        testnet=testnet
    )
    logger.info("Exchange initialized")
    
    # Создание движка
    engine = TradingEngine(
        settings=settings,
        logger=logger,
        api_client=exchange.client,  # ИСПРАВЛЕНО: exchange.client, не exchange.api_client
        telegram=None
    )
    
    logger.info("TradingEngine created")
    
    # Запуск движка в ОТДЕЛЬНОМ потоке
    engine_thread = run_engine_in_thread(engine)
    logger.info("Engine thread started")
    
    # Запуск GUI в главном потоке
    logger.info("Starting GUI...")
    try:
        import PyQt5.QtWidgets as QtWidgets
        
        app = QtWidgets.QApplication(sys.argv)
        
        # Передаём правильные аргументы
        window = MainWindow(
            api_client=exchange.client,  # ИСПРАВЛЕНО
            settings=settings,
            engine=engine
        )
        window.show()
        
        logger.info("GUI started successfully")
        sys.exit(app.exec_())
        
    except Exception as e:
        logger.error(f"GUI error: {e}", exc_info=True)
        logger.info("Falling back to terminal mode...")
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(engine.start())
            loop.run_forever()
        except KeyboardInterrupt:
            print("\nShutdown requested...")
            loop = asyncio.get_event_loop()
            asyncio.run_coroutine_threadsafe(engine.stop(), loop)

if __name__ == "__main__":
    main()
