"""
QThread API Worker — runs heavy API operations in separate thread to keep GUI responsive.
"""
from PyQt6.QtCore import QThread, pyqtSignal
import logging

logger = logging.getLogger("CryptoBot.QThread")

class APIWorker(QThread):
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, coro_func, *args, **kwargs):
        super().__init__()
        self.coro_func = coro_func
        self.args = args
        self.kwargs = kwargs
        self._result = None

    def run(self):
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._result = loop.run_until_complete(self.coro_func(*self.args, **self.kwargs))
            self.result_ready.emit(self._result)
        except Exception as e:
            logger.error(f"APIWorker error: {e}")
            self.error_occurred.emit(str(e))
        finally:
            try:
                loop.close()
            except Exception:
                pass

class APIWorkerPool:
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self._workers = []

    def submit(self, coro_func, *args, **kwargs) -> APIWorker:
        worker = APIWorker(coro_func, *args, **kwargs)
        self._workers.append(worker)
        worker.finished.connect(lambda w=worker: self._cleanup(w))
        worker.start()
        return worker

    def _cleanup(self, worker):
        if worker in self._workers:
            self._workers.remove(worker)

    def stop_all(self):
        for w in self._workers:
            try:
                w.quit()
                w.wait(2000)
            except Exception:
                pass
        self._workers.clear()
