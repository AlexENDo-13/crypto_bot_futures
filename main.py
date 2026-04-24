"""
CryptoBot v6.0 - Main Entry Point
Professional automated futures trading bot with GUI.
"""
import sys
import os
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
        print("ERROR: PyQt5 or PyQt6 is required. Install with: pip install PyQt6")
        sys.exit(1)


def ensure_directories():
    """Create required directories."""
    dirs = ["logs", "data/state", "data/history", "config", "backtests"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)


def run_gui():
    """Run the GUI application."""
    log = get_logger("CryptoBot")
    log.info(f"Starting CryptoBot v6.0 GUI | Qt={PYQT}")

    app = QApplication(sys.argv)
    app.setApplicationName("CryptoBot v6.0")

    # Import and create main window
    from ui.main_window import MainWindow

    window = MainWindow()
    window.show()

    log.info("MainWindow displayed successfully")

    # PyQt6 has exec(), PyQt5 has exec_()
    if hasattr(app, 'exec'):
        sys.exit(app.exec())
    else:
        sys.exit(app.exec_())


def main():
    """Main entry point."""
    ensure_directories()

    # Initialize logger
    logger = BotLogger(log_dir="logs", level=20)
    log = logger.get_logger("CryptoBot")

    log.info("=" * 60)
    log.info("CryptoBot v6.0 - Professional Futures Trading Bot")
    log.info("=" * 60)

    try:
        run_gui()
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
