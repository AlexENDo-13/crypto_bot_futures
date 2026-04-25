"""
Main Window for CryptoBot v9.0
Neural Adaptive GUI with real-time monitoring and manual controls.
"""
import logging
import sys
import time
from datetime import datetime
from typing import Optional, List, Dict

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QTableWidget, QTableWidgetItem,
    QTextEdit, QSplitter, QStatusBar, QMessageBox, QApplication,
    QDoubleSpinBox, QGroupBox, QGridLayout
)

from src.exchange.api_client import BingXAPIClient
from src.exchange.market_scanner import MarketScanner
from src.utils.async_bridge import AsyncExecutor
from src.utils.logger import BotLogger  # Assuming BotLogger is a custom handler


class MainWindow(QMainWindow):
    log_signal = pyqtSignal(str)

    def __init__(self, api_client: BingXAPIClient):
        super().__init__()
        self.api_client = api_client
        self.logger = logging.getLogger("CryptoBot")
        self.setWindowTitle("CryptoBot v9.0 - Neural Adaptive GUI")
        self.resize(1280, 800)

        # Async bridge
        self.async_executor = AsyncExecutor()
        self.async_executor.start()

        # Data models
        self.symbols = [
            "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "ADA-USDT",
            "AVAX-USDT", "DOGE-USDT", "LINK-USDT", "MATIC-USDT", "LTC-USDT",
            "DOT-USDT", "BCH-USDT", "UNI-USDT", "ETC-USDT", "FIL-USDT"
        ]
        self.scanner = MarketScanner(api_client, self.symbols, async_executor=self.async_executor)
        # Register strategies (example)
        self.scanner.strategies = {
            "ema_cross": DummyStrategy("EMA Cross"),
            "rsi_divergence": DummyStrategy("RSI Divergence"),
            "volume_breakout": DummyStrategy("Volume Breakout"),
            "support_resistance": DummyStrategy("Support Resistance"),
            "macd_momentum": DummyStrategy("MACD Momentum"),
            "bollinger_squeeze": DummyStrategy("Bollinger Squeeze"),
            "dca": DummyStrategy("DCA")
        }

        self._init_ui()
        self._connect_signals()
        self._restore_window_state()

        # Periodic auto-scan (every 60 seconds)
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.run_scan)
        self.scan_timer.start(60000)  # 1 min

        self.logger.info("MainWindow initialized with AsyncExecutor")

    # ---------- UI Setup ----------
    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Control panel
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel)

        # Splitter for signals table and log
        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter, stretch=1)

        # Signals table
        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(7)
        self.signals_table.setHorizontalHeaderLabels([
            "Time", "Symbol", "Strategy", "Direction", "Confidence", "Price", "Reason"
        ])
        self.signals_table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self.signals_table)

        # Log console
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumBlockCount(1000)
        splitter.addWidget(self.log_console)

        splitter.setSizes([400, 200])

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addPermanentWidget(self.status_label)

    def _create_control_panel(self) -> QWidget:
        panel = QWidget()
        layout = QHBoxLayout(panel)

        # Scan button
        self.scan_btn = QPushButton("Scan Now")
        self.scan_btn.clicked.connect(self.run_scan)
        layout.addWidget(self.scan_btn)

        # Timeframe selector
        layout.addWidget(QLabel("Timeframe:"))
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(["1m", "5m", "15m", "30m", "1h", "4h", "1d"])
        self.timeframe_combo.setCurrentText("15m")
        layout.addWidget(self.timeframe_combo)

        # Confidence threshold
        layout.addWidget(QLabel("Min Confidence:"))
        self.conf_spin = QDoubleSpinBox()
        self.conf_spin.setRange(0.0, 1.0)
        self.conf_spin.setSingleStep(0.05)
        self.conf_spin.setValue(0.3)
        layout.addWidget(self.conf_spin)

        # Auto-pilot toggle
        self.autopilot_btn = QPushButton("AutoPilot OFF")
        self.autopilot_btn.setCheckable(True)
        self.autopilot_btn.toggled.connect(self.toggle_autopilot)
        layout.addWidget(self.autopilot_btn)

        layout.addStretch()
        return panel

    def _connect_signals(self):
        # Connect custom log signal to console
        self.log_signal.connect(self._append_log)
        # Redirect Python logging to GUI
        gui_handler = GuiLogHandler(self.log_signal)
        logging.getLogger("CryptoBot").addHandler(gui_handler)

    # ---------- Core Actions ----------
    def run_scan(self):
        """Initiate a scan in async executor and update table."""
        self.status_label.setText("Scanning...")
        self.scan_btn.setEnabled(False)
        tf = self.timeframe_combo.currentText()
        min_conf = self.conf_spin.value()
        # All strategies enabled (for now)
        self.scanner.start_scan(
            callback=self.on_scan_results,
            timeframe=tf,
            min_confidence=min_conf,
            enabled_strategies=None
        )

    def on_scan_results(self, signals: List[Dict]):
        """Slot called when scan results are ready (in GUI thread)."""
        self.scan_btn.setEnabled(True)
        self.status_label.setText(f"Last scan: {datetime.now().strftime('%H:%M:%S')} | Signals: {len(signals)}")
        self._update_signals_table(signals)
        # If autopilot is ON, execute trade decisions
        if self.autopilot_btn.isChecked():
            self._execute_trades(signals)

    def _update_signals_table(self, signals):
        self.signals_table.setRowCount(0)
        for i, sig in enumerate(signals):
            self.signals_table.insertRow(i)
            now = datetime.now().strftime("%H:%M:%S")
            self.signals_table.setItem(i, 0, QTableWidgetItem(now))
            self.signals_table.setItem(i, 1, QTableWidgetItem(sig.get("symbol", "")))
            self.signals_table.setItem(i, 2, QTableWidgetItem(sig.get("strategy", "")))
            direction = sig.get("direction", "LONG")
            item_dir = QTableWidgetItem(direction)
            if direction == "LONG":
                item_dir.setForeground(Qt.GlobalColor.green)
            elif direction == "SHORT":
                item_dir.setForeground(Qt.GlobalColor.red)
            self.signals_table.setItem(i, 3, item_dir)
            conf = sig.get("confidence", 0)
            self.signals_table.setItem(i, 4, QTableWidgetItem(f"{conf:.2f}"))
            price = sig.get("price", 0)
            self.signals_table.setItem(i, 5, QTableWidgetItem(f"{price:.4f}"))
            self.signals_table.setItem(i, 6, QTableWidgetItem(sig.get("reason", "")))
        self.signals_table.resizeColumnsToContents()

    def _execute_trades(self, signals):
        # Placeholder for trade execution logic
        self.logger.info(f"AutoPilot would execute {len(signals)} trades")

    def toggle_autopilot(self, checked):
        self.autopilot_btn.setText("AutoPilot ON" if checked else "AutoPilot OFF")
        status = "ACTIVE" if checked else "STANDBY"
        self.logger.info(f"AutoPilot {status}")

    # ---------- Logging ----------
    def _append_log(self, text: str):
        self.log_console.append(text)

    # ---------- Window State & Shutdown ----------
    def _restore_window_state(self):
        # Could load QSettings, skip for brevity
        pass

    def closeEvent(self, event):
        self.logger.info("Shutting down application...")
        # Stop timer
        self.scan_timer.stop()
        # Cancel pending scans
        self.async_executor.stop()
        # Close API client (it's asynchronous, run in temporary loop)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.api_client.close())
            else:
                asyncio.run(self.api_client.close())
        except Exception as e:
            self.logger.error(f"Error during API close: {e}")
        event.accept()


class GuiLogHandler(logging.Handler):
    """Redirects logging messages to the GUI console via PyQt signal."""
    def __init__(self, signal):
        super().__init__()
        self.signal = signal
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s | %(message)s", "%H:%M:%S"))

    def emit(self, record):
        msg = self.format(record)
        self.signal.emit(msg)


# Dummy strategy for demonstration (replace with real strategies)
class DummyStrategy:
    def __init__(self, name):
        self.name = name

    def analyze(self, symbol, candles, timeframe):
        # return a dummy signal 10% of the time
        import random
        if random.random() < 0.1:
            return {
                "direction": random.choice(["LONG", "SHORT"]),
                "confidence": random.uniform(0.3, 0.9),
                "price": random.uniform(0.5, 500),
                "reason": f"{self.name} signal"
            }
        return None
