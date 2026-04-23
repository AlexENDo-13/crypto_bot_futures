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
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DisableWindowContextHelpButton)

    # Apply dark theme
    apply_dark_theme(app)

    # Load settings
    settings = Settings()

    # Create and show main window
    window = MainWindow(settings)
    window.show()

    # Run main loop
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
