"""
Offline Guard — pauses API requests when internet is down, resumes when back.
"""
import threading
import time
import logging
import socket

logger = logging.getLogger("CryptoBot.Offline")

class OfflineGuard:
    def __init__(self, check_interval_sec: int = 10, test_host: str = ("8.8.8.8", 53)):
        self.check_interval_sec = check_interval_sec
        self.test_host = test_host
        self._running = False
        self._thread = None
        self._online = True
        self._offline_since = None
        self._callbacks = []

    def add_callback(self, callback):
        self._callbacks.append(callback)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"Offline guard started (interval: {self.check_interval_sec}s)")

    def stop(self):
        self._running = False

    def is_online(self) -> bool:
        return self._online

    def _check_internet(self) -> bool:
        try:
            socket.setdefaulttimeout(3)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(self.test_host)
            return True
        except Exception:
            return False
        finally:
            socket.setdefaulttimeout(None)

    def _loop(self):
        while self._running:
            try:
                was_online = self._online
                self._online = self._check_internet()

                if was_online and not self._online:
                    self._offline_since = time.time()
                    logger.warning("INTERNET LOST — pausing API requests")
                    for cb in self._callbacks:
                        try:
                            cb(False)
                        except Exception:
                            pass
                elif not was_online and self._online:
                    offline_duration = time.time() - (self._offline_since or time.time())
                    logger.info(f"INTERNET RESTORED after {offline_duration:.0f}s — resuming API requests")
                    self._offline_since = None
                    for cb in self._callbacks:
                        try:
                            cb(True)
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Offline guard error: {e}")
            time.sleep(self.check_interval_sec)

    def get_status(self) -> dict:
        return {
            "online": self._online,
            "offline_since": self._offline_since,
        }
