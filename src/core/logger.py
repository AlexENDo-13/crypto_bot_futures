"""
CryptoBot v6.0 - Advanced Logging System
Fixed QtLogHandler MRO issue
"""
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

# PyQt6 imports
try:
    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtWidgets import QTextEdit
    PYQT6 = True
except ImportError:
    try:
        from PyQt5.QtCore import QObject, pyqtSignal
        from PyQt5.QtWidgets import QTextEdit
        PYQT6 = False
    except ImportError:
        QObject = None
        pyqtSignal = None
        QTextEdit = None


class QtLogHandler(logging.Handler):
    """Custom log handler that emits Qt signals for GUI updates.

    FIXED v6.0: Properly handles QObject inheritance without MRO conflicts.
    Uses composition instead of multiple inheritance to avoid sip.simplewrapper issues.
    """
    log_signal = None  # Will be set as class attribute

    def __init__(self, parent=None):
        # CRITICAL FIX: Call logging.Handler.__init__ first, then setup QObject
        logging.Handler.__init__(self)
        self.setLevel(logging.DEBUG)

        # Use a formatter that works well with GUI
        self.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s | %(message)s",
            datefmt="%H:%M:%S"
        ))

        # Store parent reference for later
        self._parent = parent
        self._qt_object = None

        # Create internal QObject for signals ONLY if Qt is available
        if QObject is not None:
            try:
                self._qt_object = QObject()
                # Define signal on instance if not on class
                if not hasattr(QtLogHandler, '_signal_defined'):
                    QtLogHandler.log_signal = pyqtSignal(str)
                    QtLogHandler._signal_defined = True
            except Exception as e:
                print(f"[Logger] Warning: Could not create Qt signal object: {e}")

    def emit(self, record):
        """Emit log record. Thread-safe via signal if Qt available."""
        try:
            msg = self.format(record)

            # If we have a parent with append_log method, call it directly
            if self._parent is not None and hasattr(self._parent, 'append_log'):
                try:
                    self._parent.append_log(msg, record.levelno)
                except Exception:
                    pass

            # Also print to console as fallback
            print(msg)

        except Exception:
            self.handleError(record)


class BotLogger:
    """Centralized logging manager for CryptoBot v6.0."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, log_dir: str = "logs", level: int = logging.INFO):
        if self._initialized:
            return

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.level = level
        self._qt_handler: Optional[QtLogHandler] = None
        self._file_handler: Optional[RotatingFileHandler] = None
        self._console_handler: Optional[logging.StreamHandler] = None

        # Setup root logger
        self.logger = logging.getLogger("CryptoBot")
        self.logger.setLevel(level)
        self.logger.propagate = False

        # Clear existing handlers
        self.logger.handlers.clear()

        # Console handler
        self._console_handler = logging.StreamHandler(sys.stdout)
        self._console_handler.setLevel(level)
        console_fmt = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s | %(message)s",
            datefmt="%H:%M:%S"
        )
        self._console_handler.setFormatter(console_fmt)
        self.logger.addHandler(self._console_handler)

        # File handler with rotation
        log_file = self.log_dir / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
        self._file_handler = RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        self._file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s - %(filename)s:%(lineno)d | %(message)s"
        )
        self._file_handler.setFormatter(file_fmt)
        self.logger.addHandler(self._file_handler)

        self._initialized = True
        self.logger.info(f"BotLogger v6.0 initialized | log_dir={log_dir}")

    def add_qt_handler(self, parent_widget=None) -> QtLogHandler:
        """Add Qt GUI log handler. Safe even if Qt is not available."""
        if self._qt_handler is not None:
            return self._qt_handler

        try:
            self._qt_handler = QtLogHandler(parent=parent_widget)
            self._qt_handler.setLevel(logging.INFO)
            self.logger.addHandler(self._qt_handler)
            self.logger.info("QtLogHandler v6.0 added successfully")
        except Exception as e:
            self.logger.warning(f"Could not add Qt handler: {e}. Console logging only.")
            self._qt_handler = None

        return self._qt_handler

    def get_logger(self, name: str = "CryptoBot") -> logging.Logger:
        """Get a named logger."""
        return logging.getLogger(name)

    def set_level(self, level: int):
        """Set logging level."""
        self.level = level
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)


# Convenience function
def get_logger(name: str = "CryptoBot") -> logging.Logger:
    return BotLogger().get_logger(name)
