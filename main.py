"""
CryptoBot v7.1 - Main Entry Point
"""
import sys
import os
import traceback
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.logger import BotLogger, get_logger

try:
    from PyQt6.QtWidgets import QApplication
    PYQT = "PyQt6"
except ImportError:
    try:
        from PyQt5.QtWidgets import QApplication
        PYQT = "PyQt5"
    except ImportError:
        print("ERROR: Install PyQt6: pip install PyQt6")
        sys.exit(1)


def ensure_directories():
    for d in ["logs", "data/state", "data/cache", "config", "backtests"]:
        Path(d).mkdir(parents=True, exist_ok=True)


def run_gui():
    log = get_logger("CryptoBot")
    log.info("Starting CryptoBot v7.1 GUI | Qt=%s", PYQT)

    app = QApplication(sys.argv)
    app.setApplicationName("CryptoBot v7.1")

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    log.info("MainWindow displayed")

    if hasattr(app, 'exec'):
        sys.exit(app.exec())
    else:
        sys.exit(app.exec_())


def main():
    ensure_directories()
    logger = BotLogger(log_dir="logs", level=20)
    log = logger.get_logger("CryptoBot")

    log.info("=" * 60)
    log.info("CryptoBot v7.1 - Professional Futures Trading Bot")
    log.info("=" * 60)

    try:
        run_gui()
    except Exception as e:
        log.error("Fatal: %s", e, exc_info=True)
        print("\nFATAL ERROR: %s" % e)
        print(traceback.format_exc())
        input("\nPress Enter to exit...")
        raise


if __name__ == "__main__":
    main()
