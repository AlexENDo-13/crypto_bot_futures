#!/usr/bin/env python3
"""
BingX Adaptive Trading Bot v5.0
Точка входа для GUI и консольного запуска
"""

import sys
import os
from pathlib import Path

# Добавляем корень проекта в sys.path для корректных импортов
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from src.ui.main_window import MainWindow
from src.config.settings import Settings
from src.core.logger import BotLogger

def main():
    # Включаем High DPI scaling для чёткого интерфейса
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("BingX Adaptive Trading Bot")
    app.setOrganizationName("BingXBot")

    # Загружаем настройки
    settings = Settings()
    logger = BotLogger(level=settings.get("log_level", "INFO"))

    # Создаём и показываем главное окно
    window = MainWindow(settings)
    window.show()

    logger.info("🚀 GUI запущен")
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
