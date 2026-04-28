"""
Graceful Shutdown Manager — ensures clean exit without hanging.
"""
import asyncio
import logging

logger = logging.getLogger("CryptoBot.Shutdown")

class ShutdownManager:
    def __init__(self, app, engine, api_client, mem_monitor=None, offline_guard=None, watchdog=None):
        self.app = app
        self.engine = engine
        self.api_client = api_client
        self.mem_monitor = mem_monitor
        self.offline_guard = offline_guard
        self.watchdog = watchdog
        self._shutting_down = False

    async def shutdown(self):
        if self._shutting_down:
            return
        self._shutting_down = True
        logger.info("=== GRACEFUL SHUTDOWN INITIATED ===")

        # 1. Stop watchdog first (so it doesn't restart engine)
        if self.watchdog:
            try:
                self.watchdog.stop()
                logger.info("Watchdog stopped")
            except Exception as e:
                logger.warning(f"Watchdog stop error: {e}")

        # 2. Stop engine (cancel positions, close orders)
        if self.engine and self.engine.running:
            try:
                await asyncio.wait_for(self.engine.stop(), timeout=15)
                logger.info("Engine stopped")
            except asyncio.TimeoutError:
                logger.warning("Engine stop timed out — forcing cancel")
            except Exception as e:
                logger.error(f"Engine stop error: {e}")

        # 3. Close API client sessions
        if self.api_client:
            try:
                await asyncio.wait_for(self.api_client.close(), timeout=10)
                logger.info("API client closed")
            except Exception as e:
                logger.warning(f"API client close error: {e}")

        # 4. Stop monitors
        if self.mem_monitor:
            try:
                self.mem_monitor.stop()
                logger.info("Memory monitor stopped")
            except Exception as e:
                logger.warning(f"Memory monitor stop error: {e}")

        if self.offline_guard:
            try:
                self.offline_guard.stop()
                logger.info("Offline guard stopped")
            except Exception as e:
                logger.warning(f"Offline guard stop error: {e}")

        # 5. Quit application
        logger.info("=== SHUTDOWN COMPLETE ===")
        self.app.quit()
