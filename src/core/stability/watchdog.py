"""
Engine Watchdog — monitors engine health and auto-restarts if frozen.
"""
import threading
import time
import logging
import asyncio

logger = logging.getLogger("CryptoBot.Watchdog")

class EngineWatchdog:
    def __init__(self, engine, api_client, restart_threshold_sec: int = 60):
        self.engine = engine
        self.api_client = api_client
        self.restart_threshold_sec = restart_threshold_sec
        self._running = False
        self._thread = None
        self._last_heartbeat = time.time()
        self._restart_count = 0
        self._max_restarts = 5

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"Engine watchdog started (threshold: {self.restart_threshold_sec}s)")

    def stop(self):
        self._running = False

    def heartbeat(self):
        self._last_heartbeat = time.time()

    def _loop(self):
        while self._running:
            try:
                time.sleep(self.restart_threshold_sec // 2)

                if not self.engine.running:
                    continue

                elapsed = time.time() - self._last_heartbeat
                # Update heartbeat from engine stats
                try:
                    stats = self.engine.get_health()
                    if stats.get("running"):
                        self._last_heartbeat = time.time()
                        elapsed = 0
                except Exception:
                    pass

                if elapsed > self.restart_threshold_sec:
                    self._restart_count += 1
                    if self._restart_count > self._max_restarts:
                        logger.error(f"Watchdog: max restarts ({self._max_restarts}) reached — giving up")
                        self._running = False
                        break

                    logger.warning(f"Watchdog: engine appears frozen ({elapsed:.0f}s) — auto-restarting (attempt {self._restart_count}/{self._max_restarts})")
                    try:
                        # Schedule restart in event loop
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.run_coroutine_threadsafe(self._restart_engine(), loop)
                        else:
                            loop.run_until_complete(self._restart_engine())
                    except Exception as e:
                        logger.error(f"Watchdog restart failed: {e}")
            except Exception as e:
                logger.error(f"Watchdog error: {e}")

    async def _restart_engine(self):
        try:
            if self.engine.running:
                await self.engine.stop()
            await asyncio.sleep(2)
            await self.engine.start()
            self._last_heartbeat = time.time()
            logger.info("Watchdog: engine restarted successfully")
        except Exception as e:
            logger.error(f"Watchdog restart error: {e}")

    def get_stats(self) -> dict:
        return {
            "restarts": self._restart_count,
            "max_restarts": self._max_restarts,
            "last_heartbeat_ago": time.time() - self._last_heartbeat,
        }
