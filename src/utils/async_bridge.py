"""
Async Bridge Utility
Provides AsyncExecutor for running coroutines from synchronous PyQt code.
"""
import asyncio
import threading
import logging
from typing import Coroutine, Any
from concurrent.futures import Future


class AsyncExecutor:
    """
    Runs an asyncio event loop in a dedicated daemon thread,
    allowing synchronous code to submit coroutines and retrieve results.
    """

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._started = False
        self._lock = threading.Lock()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def start(self):
        with self._lock:
            if not self._started:
                self._thread.start()
                self._started = True
                logging.getLogger("CryptoBot.Async").info("AsyncExecutor started")

    def run_coroutine(self, coro: Coroutine) -> Future:
        """
        Schedule a coroutine in the dedicated event loop.
        Returns a concurrent.futures.Future that can be awaited or polled.
        """
        if not self._started:
            self.start()
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    async def _shutdown_loop(self):
        """Stop the loop from inside the loop thread."""
        tasks = [t for t in asyncio.all_tasks(self._loop) if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._loop.stop()

    def stop(self):
        """Gracefully stop the event loop and wait for the thread."""
        if not self._started:
            return
        future = asyncio.run_coroutine_threadsafe(self._shutdown_loop(), self._loop)
        try:
            future.result(timeout=5)
        except Exception:
            pass
        self._thread.join(timeout=5)
        self._loop.close()
        self._started = False
        logging.getLogger("CryptoBot.Async").info("AsyncExecutor stopped")
