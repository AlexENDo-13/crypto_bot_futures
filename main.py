#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Точка входа в торговый бот BingX Futures.
Полное управление через PyQt5 GUI с тёмной темой.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from src.config.settings import Settings
from src.ui.main_window import MainWindow, apply_dark_theme

def main():
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DisableWindowContextHelpButton)
    app.setApplicationName("Crypto Trading Bot")
    app.setApplicationVersion("2.0")
    apply_dark_theme(app)
    settings = Settings()
    window = MainWindow(settings)
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
