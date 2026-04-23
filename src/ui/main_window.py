#!/usr/bin/env python3
"""
Главное окно приложения.
"""
import asyncio
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtCore import QTimer

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.engine = None
        # ... инициализация UI ...

    def closeEvent(self, event):
        """Корректное завершение приложения."""
        if self.engine and getattr(self.engine, '_running', False):
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Если цикл уже запущен, создаём задачу
                asyncio.create_task(self.engine.stop())
                # Даём немного времени на остановку
                QTimer.singleShot(500, event.accept)
            else:
                loop.run_until_complete(self.engine.stop())
                event.accept()
        else:
            event.accept()
