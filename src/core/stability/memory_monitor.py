"""
Memory Monitor — prevents RAM bloat by alerting when threshold exceeded.
"""
import threading
import time
import logging
import gc
import sys

logger = logging.getLogger("CryptoBot.Memory")

class MemoryMonitor:
    def __init__(self, max_mb: int = 512, check_interval_sec: int = 30):
        self.max_mb = max_mb
        self.check_interval_sec = check_interval_sec
        self._running = False
        self._thread = None
        self._peak_mb = 0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"Memory monitor started (threshold: {self.max_mb} MB, interval: {self.check_interval_sec}s)")

    def stop(self):
        self._running = False

    def _get_usage_mb(self) -> float:
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            # Fallback without psutil
            return 0.0

    def _loop(self):
        while self._running:
            try:
                usage = self._get_usage_mb()
                if usage > self._peak_mb:
                    self._peak_mb = usage

                if usage > self.max_mb:
                    logger.warning(f"MEMORY ALERT: {usage:.1f} MB exceeds threshold {self.max_mb} MB — forcing GC")
                    gc.collect()
                    # Double-check
                    usage_after = self._get_usage_mb()
                    if usage_after > self.max_mb * 1.2:
                        logger.error(f"CRITICAL MEMORY: {usage_after:.1f} MB — consider restarting bot")
                else:
                    logger.debug(f"Memory usage: {usage:.1f} MB (peak: {self._peak_mb:.1f} MB)")
            except Exception as e:
                logger.error(f"Memory monitor error: {e}")
            time.sleep(self.check_interval_sec)

    def get_stats(self) -> dict:
        return {
            "current_mb": self._get_usage_mb(),
            "peak_mb": self._peak_mb,
            "threshold_mb": self.max_mb,
        }
