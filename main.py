#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Точка входа в торговый бот BingX Futures.
Запускает PyQt5 GUI с тёмной темой.
"""
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from src.config.settings import Settings
from src.ui.main_window import MainWindow, apply_dark_theme


def main():
    # Создаём приложение
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DisableWindowContextHelpButton)  # убираем знак вопроса в окнах

    # Применяем глобальную тёмную тему
    apply_dark_theme(app)

    # Загружаем настройки
    settings = Settings()
    # Если файл конфига не найден, будет создан стандартный (демо‑режим)

    # Создаём и показываем главное окно
    window = MainWindow(settings)
    window.show()

    # Запускаем главный цикл
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
