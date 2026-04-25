"""
Main Window for CryptoBot v9.1 (FIXED)
Neural Adaptive GUI with TradingEngine integration.
"""
import logging
import sys
import asyncio
import time
from datetime import datetime
from typing import Optional, List, Dict

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QTableWidget, QTableWidgetItem,
    QTextEdit, QSplitter, QStatusBar, QMessageBox
)

from src.exchange.api_client import BingXAPIClient
from src.config.settings import Settings
from src.core.engine.trading_engine import TradingEngine
from src.utils.async_bridge import AsyncExecutor


class MainWindow(QMainWindow):
    log_signal = pyqtSignal(str)
    stats_signal = pyqtSignal(dict)

    def __init__(self, api_client: BingXAPIClient, engine: TradingEngine, settings: Settings):
        super().__init__()
        self.api_client = api_client
        self.engine = engine
        self.settings = settings
        self.logger = logging.getLogger("CryptoBot")
        self.setWindowTitle("CryptoBot v9.1 - Neural Adaptive GUI [FIXED]")
        self.resize(1280, 800)

        self.async_executor = AsyncExecutor()
        self.async_executor.start()

        self.symbols = settings.get("symbols_whitelist", [
            "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "ADA-USDT",
            "AVAX-USDT", "DOGE-USDT", "LINK-USDT", "MATIC-USDT", "LTC-USDT"
        ])

        self._init_ui()
        self._connect_signals()
        self._restore_window_state()

        # Periodic UI update (every 2 seconds)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_stats)
        self.update_timer.start(2000)

        # Periodic auto-scan (every 60 seconds)
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.run_scan)
        self.scan_timer.start(60000)

        self.logger.info("MainWindow initialized with TradingEngine")

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Control panel
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel)

        # Stats panel
        stats_panel = self._create_stats_panel()
        main_layout.addWidget(stats_panel)

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

        self.scan_btn = QPushButton("Scan Now")
        self.scan_btn.clicked.connect(self.run_scan)
        layout.addWidget(self.scan_btn)

        layout.addWidget(QLabel("Timeframe:"))
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(["1m", "5m", "15m", "30m", "1h", "4h", "1d"])
        self.timeframe_combo.setCurrentText("15m")
        layout.addWidget(self.timeframe_combo)

        layout.addWidget(QLabel("Min Confidence:"))
        self.conf_spin = QComboBox()
        self.conf_spin.addItems(["0.1", "0.2", "0.25", "0.3", "0.4", "0.5", "0.7"])
        self.conf_spin.setCurrentText("0.25")
        layout.addWidget(self.conf_spin)

        self.engine_btn = QPushButton("Start Engine")
        self.engine_btn.setCheckable(True)
        self.engine_btn.toggled.connect(self.toggle_engine)
        layout.addWidget(self.engine_btn)

        self.autopilot_btn = QPushButton("AutoPilot OFF")
        self.autopilot_btn.setCheckable(True)
        self.autopilot_btn.toggled.connect(self.toggle_autopilot)
        layout.addWidget(self.autopilot_btn)

        # Mode indicator
        demo = self.settings.get("demo_mode", True)
        self.mode_label = QLabel("MODE: PAPER" if demo else "MODE: LIVE")
        self.mode_label.setStyleSheet("color: green;" if demo else "color: red; font-weight: bold;")
        layout.addWidget(self.mode_label)

        layout.addStretch()
        return panel

    def _create_stats_panel(self) -> QWidget:
        panel = QWidget()
        layout = QHBoxLayout(panel)
        self.balance_label = QLabel("Balance: --")
        self.positions_label = QLabel("Positions: 0")
        self.pnl_label = QLabel("Daily PnL: 0.00")
        self.winrate_label = QLabel("Win Rate: --")
        self.health_label = QLabel("Health: OK")
        layout.addWidget(self.balance_label)
        layout.addWidget(self.positions_label)
        layout.addWidget(self.pnl_label)
        layout.addWidget(self.winrate_label)
        layout.addWidget(self.health_label)
        layout.addStretch()
        return panel

    def _connect_signals(self):
        self.log_signal.connect(self._append_log)
        self.stats_signal.connect(self._update_ui_stats)
        gui_handler = GuiLogHandler(self.log_signal)
        logging.getLogger("CryptoBot").addHandler(gui_handler)

    def _update_stats(self):
        if self.engine and self.engine.running:
            stats = self.engine.get_stats()
            self.stats_signal.emit(stats)

    def _update_ui_stats(self, stats: dict):
        self.balance_label.setText(f"Balance: {stats.get('balance', 0):.2f} USDT")
        self.positions_label.setText(f"Positions: {stats.get('positions_count', 0)}")
        self.pnl_label.setText(f"Daily PnL: {stats.get('daily_pnl', 0):.2f}")
        win_rate = stats.get('win_rate', 0)
        self.winrate_label.setText(f"Win Rate: {win_rate:.1f}%")
        health = stats.get('health_status', 'OK')
        self.health_label.setText(f"Health: {health}")
        if "ERROR" in str(health):
            self.health_label.setStyleSheet("color: red;")
        else:
            self.health_label.setStyleSheet("color: green;")

    def run_scan(self):
        self.status_label.setText("Scanning...")
        self.scan_btn.setEnabled(False)
        # Use engine's scanner if engine is running
        if self.engine and self.engine.running:
            async def do_scan():
                try:
                    await self.engine._scan_and_trade()
                    signals = self.engine.get_last_scan_signals()
                    self.on_scan_results(signals)
                except Exception as e:
                    self.logger.error(f"Scan error: {e}")
                    self.on_scan_results([])
            self.async_executor.run_coroutine(do_scan())
        else:
            self.status_label.setText("Engine not running")
            self.scan_btn.setEnabled(True)

    def on_scan_results(self, signals: List[Dict]):
        self.scan_btn.setEnabled(True)
        self.status_label.setText(f"Last scan: {datetime.now().strftime('%H:%M:%S')} | Signals: {len(signals)}")
        self._update_signals_table(signals)
        if self.autopilot_btn.isChecked() and signals:
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
        self.logger.info(f"AutoPilot executing {len(signals)} signals via TradingEngine")
        # Engine already handles execution in _scan_and_trade if running

    def toggle_engine(self, checked):
        if checked:
            self.engine_btn.setText("Stop Engine")
            self.async_executor.run_coroutine(self.engine.start())
            self.logger.info("TradingEngine START requested")
        else:
            self.engine_btn.setText("Start Engine")
            self.async_executor.run_coroutine(self.engine.stop())
            self.logger.info("TradingEngine STOP requested")

    def toggle_autopilot(self, checked):
        self.autopilot_btn.setText("AutoPilot ON" if checked else "AutoPilot OFF")
        status = "ACTIVE" if checked else "STANDBY"
        self.logger.info(f"AutoPilot {status}")

    def _append_log(self, text: str):
        self.log_console.append(text)

    def _restore_window_state(self):
        pass

    def closeEvent(self, event):
        self.logger.info("Shutting down application...")
        self.update_timer.stop()
        self.scan_timer.stop()
        if self.engine:
            asyncio.ensure_future(self.engine.stop())
        self.async_executor.stop()
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
    def __init__(self, signal):
        super().__init__()
        self.signal = signal
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s | %(message)s", "%H:%M:%S"))

    def emit(self, record):
        msg = self.format(record)
        self.signal.emit(msg)
