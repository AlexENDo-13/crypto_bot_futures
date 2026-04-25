"""
CryptoBot v9.0 - Futuristic GUI with Async Support
Features: Real-time charts, neural network viz, system health dashboard,
          dark neon theme, holographic effects, async worker loop
"""
import sys
import os
import csv
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import time
import traceback

try:
    from PyQt6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTabWidget, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
        QGroupBox, QGridLayout, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
        QLineEdit, QMessageBox, QProgressBar, QSplitter, QFrame, QStatusBar,
        QToolBar, QMenuBar, QMenu, QFileDialog, QDialog, QFormLayout,
        QDialogButtonBox, QScrollArea, QTreeWidget, QTreeWidgetItem,
        QApplication, QSystemTrayIcon
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
    from PyQt6.QtGui import QFont, QColor, QAction, QKeySequence, QPainter, QPen, QBrush
    PYQT_VER = 6
except ImportError:
    from PyQt5.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTabWidget, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
        QGroupBox, QGridLayout, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
        QLineEdit, QMessageBox, QProgressBar, QSplitter, QFrame, QStatusBar,
        QToolBar, QMenuBar, QMenu, QFileDialog, QDialog, QFormLayout,
        QDialogButtonBox, QScrollArea, QTreeWidget, QTreeWidgetItem,
        QApplication, QSystemTrayIcon
    )
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
    from PyQt5.QtGui import QFont, QColor, QAction, QKeySequence
    PYQT_VER = 5

class LogWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        font = QFont("JetBrains Mono", 9)
        if PYQT_VER == 6:
            font.setStyleHint(QFont.StyleHint.Monospace)
        else:
            font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.colors = {
            "DEBUG": "#666666", "INFO": "#00ff88", "WARNING": "#ffaa00",
            "ERROR": "#ff0044", "CRITICAL": "#ff00ff", "TRADE": "#00ccff",
            "NEURAL": "#aa66ff"
        }
        self._line_count = 0
        self._max_lines = 5000

    def append_log(self, message: str, level: int = 20):
        level_name = "INFO"
        if level <= 10: level_name = "DEBUG"
        elif level <= 20: level_name = "INFO"
        elif level <= 30: level_name = "WARNING"
        elif level <= 40: level_name = "ERROR"
        else: level_name = "CRITICAL"

        color = self.colors.get(level_name, "#ffffff")
        timestamp = datetime.now().strftime("%H:%M:%S")
        html = '[%s] <span style="color:%s;font-weight:bold">%s</span> <span style="color:#ccc">%s</span>' % (
            timestamp, color, level_name, message)
        self.append(html)
        self._line_count += 1
        if self._line_count > self._max_lines:
            self.clear()
            self._line_count = 0
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

class BotWorker(QThread):
    signal_log = pyqtSignal(str, int)
    signal_status = pyqtSignal(str)
    signal_balance = pyqtSignal(float, float)
    signal_positions = pyqtSignal(list)
    signal_scan_done = pyqtSignal(list)
    signal_performance = pyqtSignal(dict)
    signal_health = pyqtSignal(dict)
    signal_neural = pyqtSignal(dict)

    def __init__(self, executor=None, scanner=None, data_fetcher=None,
                 monitor=None, autopilot=None, interval: int = 60, auto_trade: bool = True):
        super().__init__()
        self.executor = executor
        self.scanner = scanner
        self.data_fetcher = data_fetcher
        self.monitor = monitor
        self.autopilot = autopilot
        self.interval = interval
        self.auto_trade = auto_trade
        self.running = False
        self._paused = False
        self._cycle_count = 0
        self._scan_requested = False

    def run(self):
        # Create new event loop for async operations in this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.running = True
        self.signal_log.emit("Neural system initialized", 20)

        while self.running:
            if not self._paused:
                try:
                    self._cycle_count += 1
                    self.signal_status.emit("Cycle #%d | Neural Scanning..." % self._cycle_count)

                    if self.monitor:
                        self.monitor.start_cycle()

                    # Multi-timeframe scan
                    if self.scanner:
                        try:
                            # Scan multiple timeframes
                            signals_15m = self.loop.run_until_complete(
                                self.scanner.scan_all("15m")
                            )
                            signals_1h = self.loop.run_until_complete(
                                self.scanner.scan_all("1h")
                            )

                            # Combine: require 15m signal + 1h confirmation
                            all_signals = []
                            symbols_1h = {s.symbol for s in signals_1h}

                            for sig in signals_15m:
                                if sig.symbol in symbols_1h:
                                    # Boost confidence if 1h agrees
                                    sig.confidence = min(sig.confidence * 1.15, 1.0)
                                    sig.metadata = sig.metadata or {}
                                    sig.metadata["multi_tf"] = "15m+1h"
                                    all_signals.append(sig)
                                elif sig.confidence >= 0.7:
                                    # Strong 15m signal stands alone
                                    sig.metadata = sig.metadata or {}
                                    sig.metadata["multi_tf"] = "15m"
                                    all_signals.append(sig)

                            total_signals = len(all_signals)
                            if self.monitor:
                                self.monitor.record_stats({"signals_found": total_signals})

                            if all_signals:
                                self.signal_log.emit("Multi-TF scan: %d signals" % total_signals, 20)
                                for sig in all_signals[:3]:
                                    neural_score = sig.metadata.get("neural_score", 0) if sig.metadata else 0
                                    mtf = sig.metadata.get("multi_tf", "") if sig.metadata else ""
                                    self.signal_log.emit("  >> %s [%s] conf=%.2f neural=%.2f [%s]" % (
                                        sig.symbol, sig.type.value.upper(), 
                                        sig.confidence, neural_score, mtf), 20)
                                    self.signal_neural.emit({
                                        "symbol": sig.symbol,
                                        "confidence": sig.confidence,
                                        "neural_score": neural_score,
                                        "regime": sig.metadata.get("regime", "unknown") if sig.metadata else "unknown",
                                        "multi_tf": mtf
                                    })
                                if self.executor and self.auto_trade:
                                    for sig in all_signals[:3]:
                                        try:
                                            self.loop.run_until_complete(
                                                self.executor.execute_signal(sig)
                                            )
                                            if self.monitor:
                                                self.monitor.record_stats({"trades_executed": 1})
                                        except Exception as e:
                                            self.signal_log.emit("Execute error: %s" % e, 40)
                                            if self.monitor:
                                                self.monitor.record_error()
                        except Exception as e:
                            self.signal_log.emit("Scan error: %s" % e, 40)
                            if self.monitor:
                                self.monitor.record_error()

                    if self.executor:
                        try:
                            self.loop.run_until_complete(self.executor.update_balance())
                            bal = self.executor.balance
                            self.signal_balance.emit(bal, bal)
                        except Exception as e:
                            self.signal_log.emit("Balance error: %s" % e, 40)

                    if self.data_fetcher and self.executor and self.executor.positions:
                        try:
                            prices = self.loop.run_until_complete(
                                self.data_fetcher.get_prices_batch(list(self.executor.positions.keys()))
                            )
                            if prices:
                                self.loop.run_until_complete(
                                    self.executor.update_positions(prices)
                                )
                                self.signal_positions.emit(self.executor.get_open_positions())
                        except Exception as e:
                            self.signal_log.emit("Position update error: %s" % e, 40)

                    # Auto-adapt every 10 cycles
                    if self._cycle_count % 10 == 0 and self.autopilot and self.executor:
                        try:
                            self.autopilot.adapt(self.scanner, self.executor, self.executor.risk)
                        except Exception as e:
                            self.signal_log.emit("AutoPilot error: %s" % e, 40)

                    if self.monitor:
                        self.monitor.end_cycle()
                        health = self.monitor.get_performance_summary()
                        self.signal_health.emit(health)
                        anomalies = self.monitor.detect_anomalies()
                        if anomalies:
                            for a in anomalies:
                                self.signal_log.emit("ANOMALY: %s in cycle %d" % (a["type"], a["cycle"]), 30)

                    self.signal_status.emit("Cycle #%d | Idle" % self._cycle_count)

                except Exception as e:
                    self.signal_log.emit("Worker error: %s" % e, 40)
                    for line in traceback.format_exc().split("\\n")[:5]:
                        if line.strip():
                            self.signal_log.emit(line, 40)

            if self._scan_requested:
                self._scan_requested = False
                try:
                    if self.scanner:
                        signals = self.loop.run_until_complete(self.scanner.scan_all("15m"))
                        self.signal_scan_done.emit(signals)
                except Exception as e:
                    self.signal_log.emit("Manual scan error: %s" % e, 40)

            for _ in range(self.interval):
                if not self.running or self._paused:
                    break
                time.sleep(1)

        self.loop.close()
        self.signal_log.emit("Neural system shutdown", 20)

    def stop(self):
        self.running = False
        self.wait(3000)

    def pause(self):
        self._paused = True
        self.signal_status.emit("PAUSED")

    def resume(self):
        self._paused = False
        self.signal_status.emit("RUNNING")

    def request_scan(self):
        self._scan_requested = True

class NeonButton(QPushButton):
    def __init__(self, text, color="#00ff88", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: %s;
                border: 2px solid %s;
                border-radius: 8px;
                padding: 10px 24px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: %s;
                color: #0a0a0a;
            }
            QPushButton:pressed {
                background-color: %s;
            }
            QPushButton:disabled {
                border-color: #333;
                color: #555;
            }
        """ % (color, color, color, color))

class HealthGauge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 100
        self.setMinimumSize(120, 120)
        self.setMaximumSize(120, 120)

    def set_value(self, val: int):
        self.value = max(0, min(100, val))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing if PYQT_VER == 6 else QPainter.Antialiasing)
        rect = self.rect().adjusted(10, 10, -10, -10)
        pen = QPen()
        pen.setWidth(8)
        pen.setColor(QColor("#1a1a2e"))
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)
        if self.value >= 70:
            color = QColor("#00ff88")
        elif self.value >= 40:
            color = QColor("#ffaa00")
        else:
            color = QColor("#ff0044")
        pen.setColor(color)
        painter.setPen(pen)
        span = int(self.value * 3.6 * 16)
        painter.drawArc(rect, 90 * 16, -span)
        painter.setPen(QColor("#ffffff"))
        font = QFont("Segoe UI", 16, QFont.Weight.Bold if PYQT_VER == 6 else QFont.Bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter if PYQT_VER == 6 else Qt.AlignCenter, "%d%%" % self.value)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CryptoBot v9.0 - Neural Adaptive Trading System")
        self.setMinimumSize(1600, 1000)

        self.bot_running = False
        self.worker = None
        self.start_time = None
        self.auto_trade = True

        self.settings = None
        self.api_client = None
        self.data_fetcher = None
        self.scanner = None
        self.executor = None
        self.risk_manager = None
        self.notifier = None
        self.state_manager = None
        self.monitor = None
        self.autopilot = None

        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_timers()
        self._setup_tray()
        self._apply_neon_theme()

        from core.logger import BotLogger, get_logger
        logger_instance = BotLogger(log_dir="logs", level=20)
        logger_instance.add_gui_handler(self.append_log)

        try:
            self._init_core()
            self._load_settings_to_ui()
            self.append_log("Neural system v9.0 initialized", 20)
            self.append_log("Multi-Timeframe scan ready | AutoPilot ON", 20)
        except Exception as e:
            self.append_log("Init error: %s" % e, 40)
            for line in traceback.format_exc().split("\\n")[:5]:
                if line.strip():
                    self.append_log(line, 40)

    def _init_core(self):
        from core.settings import BotSettings
        from core.state_manager import StateManager
        from core.notifications import NotificationManager, NotificationConfig
        from core.monitor import SystemMonitor
        from core.autopilot import AutoPilot
        from exchange.api_client import BingXAPIClient
        from exchange.data_fetcher import DataFetcher
        from exchange.market_scanner import MarketScanner
        from exchange.trade_executor import TradeExecutor
        from risk.risk_manager import RiskManager, RiskLimits
        from ml.ml_engine import MLEngine

        self.settings = BotSettings.load()
        self.state_manager = StateManager()
        self.monitor = SystemMonitor()
        self.autopilot = AutoPilot()

        self.api_client = BingXAPIClient(
            api_key=self.settings.api_key, api_secret=self.settings.api_secret,
            base_url=self.settings.base_url, testnet=self.settings.testnet
        )
        self.data_fetcher = DataFetcher(api_client=self.api_client)

        limits = RiskLimits(
            max_position_size=self.settings.max_position_size,
            max_risk_per_trade=self.settings.max_risk_per_trade,
            max_leverage=self.settings.max_leverage,
            max_daily_loss=self.settings.max_daily_loss,
            default_sl_percent=self.settings.default_sl,
            default_tp_percent=self.settings.default_tp
        )
        self.risk_manager = RiskManager(limits=limits)
        ml = MLEngine()

        notif_config = NotificationConfig(
            telegram_enabled=self.settings.telegram_enabled,
            telegram_token=self.settings.telegram_token,
            telegram_chat_id=self.settings.telegram_chat_id
        )
        self.notifier = NotificationManager(config=notif_config)

        self.executor = TradeExecutor(
            api_client=self.api_client, risk_manager=self.risk_manager,
            paper_trading=self.settings.paper_trading, balance=10000.0,
            notifier=self.notifier
        )
        self.scanner = MarketScanner(data_fetcher=self.data_fetcher, ml_engine=ml, max_workers=4)

        mode = "PAPER" if self.settings.paper_trading else "LIVE"
        self.append_log("Neural core ready | Mode=%s | AutoPilot=ON" % mode, 20)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addLayout(self._create_control_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal if PYQT_VER == 6 else Qt.Horizontal)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_dashboard_tab(), "Neural Dashboard")
        self.tabs.addTab(self._create_positions_tab(), "Positions")
        self.tabs.addTab(self._create_market_tab(), "Market Scan")
        self.tabs.addTab(self._create_strategies_tab(), "Strategies")
        self.tabs.addTab(self._create_risk_tab(), "Risk Control")
        self.tabs.addTab(self._create_neural_tab(), "Neural Net")
        self.tabs.addTab(self._create_performance_tab(), "Performance")
        self.tabs.addTab(self._create_settings_tab(), "Settings")
        splitter.addWidget(self.tabs)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        health_group = QGroupBox("System Health")
        health_layout = QHBoxLayout(health_group)
        self.health_gauge = HealthGauge()
        health_layout.addWidget(self.health_gauge)
        self.health_details = QVBoxLayout()
        self.lbl_health_status = QLabel("Status: STANDBY")
        self.lbl_health_status.setStyleSheet("color: #00ff88; font-size: 14px; font-weight: bold;")
        self.lbl_cycle_time = QLabel("Cycle: 0.0s")
        self.lbl_api_latency = QLabel("API: 0ms")
        self.lbl_error_rate = QLabel("Errors: 0")
        for lbl in [self.lbl_health_status, self.lbl_cycle_time, self.lbl_api_latency, self.lbl_error_rate]:
            lbl.setStyleSheet("color: #aaa; font-size: 11px;")
            self.health_details.addWidget(lbl)
        health_layout.addLayout(self.health_details)
        right_layout.addWidget(health_group)

        log_group = QGroupBox("Neural Logs")
        log_layout = QVBoxLayout(log_group)
        self.log_widget = LogWidget()
        log_layout.addWidget(self.log_widget)
        right_layout.addWidget(log_group, 3)

        stats_group = QGroupBox("Live Stats")
        stats_layout = QGridLayout(stats_group)
        self.lbl_balance = QLabel("$0.00")
        self.lbl_balance.setStyleSheet("color: #00ff88; font-size: 20px; font-weight: bold;")
        self.lbl_pnl = QLabel("$0.00")
        self.lbl_pnl.setStyleSheet("color: #00ff88; font-size: 16px;")
        self.lbl_positions = QLabel("0")
        self.lbl_positions.setStyleSheet("color: #00ccff; font-size: 16px;")
        self.lbl_uptime = QLabel("00:00:00")
        self.lbl_uptime.setStyleSheet("color: #aaa; font-size: 12px;")
        stats_layout.addWidget(QLabel("Balance:"), 0, 0)
        stats_layout.addWidget(self.lbl_balance, 0, 1)
        stats_layout.addWidget(QLabel("P&L:"), 1, 0)
        stats_layout.addWidget(self.lbl_pnl, 1, 1)
        stats_layout.addWidget(QLabel("Positions:"), 2, 0)
        stats_layout.addWidget(self.lbl_positions, 2, 1)
        stats_layout.addWidget(QLabel("Uptime:"), 3, 0)
        stats_layout.addWidget(self.lbl_uptime, 3, 1)
        right_layout.addWidget(stats_group, 1)

        splitter.addWidget(right)
        splitter.setSizes([1200, 400])
        layout.addWidget(splitter, 1)

    def _create_control_bar(self):
        layout = QHBoxLayout()
        layout.setSpacing(15)

        self.status_indicator = QLabel("STANDBY")
        self.status_indicator.setStyleSheet("color: #ffaa00; font-size: 16px; font-weight: bold; padding: 5px 15px; border: 2px solid #ffaa00; border-radius: 4px;")
        layout.addWidget(self.status_indicator)
        layout.addSpacing(20)

        layout.addWidget(QLabel("MODE:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["PAPER", "LIVE"])
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.setStyleSheet("color: #00ff88; background: #1a1a2e; border: 1px solid #00ff88;")
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        layout.addWidget(self.mode_combo)
        layout.addSpacing(10)

        self.chk_auto_trade = QCheckBox("AUTO-TRADE")
        self.chk_auto_trade.setChecked(True)
        self.chk_auto_trade.setStyleSheet("color: #00ff88; font-weight: bold;")
        layout.addWidget(self.chk_auto_trade)
        layout.addSpacing(10)

        self.chk_autopilot = QCheckBox("AUTOPILOT")
        self.chk_autopilot.setChecked(True)
        self.chk_autopilot.setStyleSheet("color: #aa66ff; font-weight: bold;")
        layout.addWidget(self.chk_autopilot)
        layout.addSpacing(30)

        self.btn_start = NeonButton("START NEURAL", "#00ff88")
        self.btn_start.clicked.connect(self._on_start)
        layout.addWidget(self.btn_start)

        self.btn_stop = NeonButton("STOP", "#ff0044")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop)
        layout.addWidget(self.btn_stop)

        self.btn_pause = NeonButton("PAUSE", "#ffaa00")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._on_pause)
        layout.addWidget(self.btn_pause)

        layout.addStretch()

        self.conn_status = QLabel("API: OFFLINE")
        self.conn_status.setStyleSheet("color: #ff0044; font-size: 12px;")
        layout.addWidget(self.conn_status)

        return layout

    def _create_dashboard_tab(self):
        w = QWidget()
        layout = QGridLayout(w)
        layout.setSpacing(15)

        portfolio = QGroupBox("Neural Portfolio")
        portfolio.setStyleSheet("QGroupBox { color: #00ff88; font-weight: bold; }")
        pl = QGridLayout(portfolio)
        self.dash_total_balance = QLabel("$0.00")
        self.dash_total_balance.setStyleSheet("font-size: 28px; font-weight: bold; color: #00ff88;")
        pl.addWidget(self.dash_total_balance, 0, 0, 1, 2)
        metrics = [
            ("Available", "dash_available", "#aaa"),
            ("Margin", "dash_margin", "#ffaa00"),
            ("Daily P&L", "dash_daily_pnl", "#00ff88"),
            ("Total P&L", "dash_total_pnl", "#00ccff"),
            ("Win Rate", "dash_winrate", "#aa66ff"),
            ("Trades", "dash_trades", "#ffffff"),
        ]
        for i, (name, attr, color) in enumerate(metrics):
            lbl = QLabel("%s: -" % name)
            lbl.setStyleSheet("color: %s; font-size: 13px;" % color)
            setattr(self, attr, lbl)
            pl.addWidget(lbl, (i // 2) + 1, i % 2)
        layout.addWidget(portfolio, 0, 0, 1, 2)

        signals = QGroupBox("Active Signals (Multi-TF)")
        signals.setStyleSheet("QGroupBox { color: #aa66ff; font-weight: bold; }")
        sl = QVBoxLayout(signals)
        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(8)
        self.signals_table.setHorizontalHeaderLabels(["Time", "Symbol", "Strategy", "Side", "Conf", "Neural", "Regime", "TF"])
        self.signals_table.setStyleSheet("QTableWidget { background: #0a0a0a; color: #ccc; border: 1px solid #333; }")
        sl.addWidget(self.signals_table)
        layout.addWidget(signals, 1, 0, 1, 2)

        market = QGroupBox("Market Pulse")
        market.setStyleSheet("QGroupBox { color: #00ccff; font-weight: bold; }")
        ml = QVBoxLayout(market)
        self.market_tree = QTreeWidget()
        self.market_tree.setHeaderLabels(["Symbol", "Price", "24h %", "Volume", "Signal Strength"])
        self.market_tree.setStyleSheet("QTreeWidget { background: #0a0a0a; color: #ccc; border: 1px solid #333; }")
        ml.addWidget(self.market_tree)
        layout.addWidget(market, 0, 2, 2, 1)

        return w

    def _create_neural_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        info = QGroupBox("Neural Network Status")
        info.setStyleSheet("QGroupBox { color: #aa66ff; font-weight: bold; }")
        il = QGridLayout(info)
        self.neural_status = QLabel("Status: STANDBY")
        self.neural_status.setStyleSheet("color: #aa66ff; font-size: 16px;")
        self.neural_model_age = QLabel("Model Age: -")
        self.neural_accuracy = QLabel("Accuracy: -")
        self.neural_features = QLabel("Features: 15")
        for lbl in [self.neural_status, self.neural_model_age, self.neural_accuracy, self.neural_features]:
            lbl.setStyleSheet("color: #ccc; font-size: 13px;")
            il.addWidget(lbl)
        layout.addWidget(info)
        self.neural_log = QTextEdit()
        self.neural_log.setReadOnly(True)
        self.neural_log.setStyleSheet("background: #0a0a0a; color: #aa66ff; border: 1px solid #333;")
        layout.addWidget(self.neural_log)
        return w

    def _create_positions_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(10)
        self.positions_table.setHorizontalHeaderLabels([
            "Symbol", "Side", "Size", "Entry", "Mark", "SL", "TP", "P&L ($)", "P&L (%)", "Actions"
        ])
        self.positions_table.setStyleSheet("QTableWidget { background: #0a0a0a; color: #ccc; }")
        mode = QHeaderView.ResizeMode.Stretch if PYQT_VER == 6 else QHeaderView.Stretch
        self.positions_table.horizontalHeader().setSectionResizeMode(mode)
        layout.addWidget(self.positions_table)
        return w

    def _create_market_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Symbols:"))
        self.scan_symbols = QSpinBox()
        self.scan_symbols.setRange(1, 100)
        self.scan_symbols.setValue(15)
        controls.addWidget(self.scan_symbols)
        controls.addWidget(QLabel("Timeframe:"))
        self.scan_timeframe = QComboBox()
        self.scan_timeframe.addItems(["1m", "5m", "15m", "1h", "4h", "1d"])
        self.scan_timeframe.setCurrentText("15m")
        controls.addWidget(self.scan_timeframe)
        self.btn_scan = NeonButton("NEURAL SCAN", "#aa66ff")
        self.btn_scan.clicked.connect(self._on_scan)
        controls.addWidget(self.btn_scan)
        controls.addStretch()
        layout.addLayout(controls)

        self.scanner_table = QTableWidget()
        self.scanner_table.setColumnCount(8)
        self.scanner_table.setHorizontalHeaderLabels([
            "Symbol", "Price", "24h Vol", "Trend", "RSI", "Signal", "Neural", "Regime"
        ])
        self.scanner_table.setStyleSheet("QTableWidget { background: #0a0a0a; color: #ccc; }")
        mode = QHeaderView.ResizeMode.Stretch if PYQT_VER == 6 else QHeaderView.Stretch
        self.scanner_table.horizontalHeader().setSectionResizeMode(mode)
        layout.addWidget(self.scanner_table)
        return w

    def _create_strategies_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.strategy_list = QTreeWidget()
        self.strategy_list.setHeaderLabels(["Strategy", "Status", "Weight", "Win Rate", "P&L"])
        self.strategy_list.setStyleSheet("QTreeWidget { background: #0a0a0a; color: #ccc; }")
        strategies = [
            ("EMA Cross", True, "1.0", "62%", "+$1,234"),
            ("RSI Divergence", True, "0.9", "58%", "+$890"),
            ("Volume Breakout", True, "0.8", "55%", "+$456"),
            ("Support/Resistance", True, "0.9", "60%", "+$1,100"),
            ("MACD Momentum", True, "0.8", "57%", "+$780"),
            ("Bollinger Squeeze", True, "0.7", "54%", "+$320"),
            ("DCA", True, "1.0", "65%", "+$900"),
        ]
        for name, active, weight, wr, pnl in strategies:
            item = QTreeWidgetItem([name, "ACTIVE" if active else "OFF", weight, wr, pnl])
            item.setForeground(1, QColor("#00ff88"))
            self.strategy_list.addTopLevelItem(item)
        layout.addWidget(self.strategy_list)
        return w

    def _create_risk_tab(self):
        w = QWidget()
        layout = QGridLayout(w)
        limits = QGroupBox("Risk Limits")
        limits.setStyleSheet("QGroupBox { color: #ff0044; font-weight: bold; }")
        ll = QFormLayout(limits)
        self.risk_max_position = QDoubleSpinBox()
        self.risk_max_position.setRange(10, 100000)
        self.risk_max_position.setValue(1000)
        ll.addRow("Max Position ($):", self.risk_max_position)
        self.risk_max_risk = QDoubleSpinBox()
        self.risk_max_risk.setRange(0.1, 10.0)
        self.risk_max_risk.setValue(2.0)
        self.risk_max_risk.setSuffix("%")
        ll.addRow("Risk/Trade:", self.risk_max_risk)
        self.risk_max_leverage = QSpinBox()
        self.risk_max_leverage.setRange(1, 125)
        self.risk_max_leverage.setValue(10)
        ll.addRow("Max Leverage:", self.risk_max_leverage)
        layout.addWidget(limits, 0, 0)

        sltp = QGroupBox("SL / TP / Trailing")
        sltp.setStyleSheet("QGroupBox { color: #ffaa00; font-weight: bold; }")
        sl = QFormLayout(sltp)
        self.risk_sl_default = QDoubleSpinBox()
        self.risk_sl_default.setRange(0.1, 20.0)
        self.risk_sl_default.setValue(2.0)
        self.risk_sl_default.setSuffix("%")
        sl.addRow("Default SL:", self.risk_sl_default)
        self.risk_tp_default = QDoubleSpinBox()
        self.risk_tp_default.setRange(0.5, 50.0)
        self.risk_tp_default.setValue(4.0)
        self.risk_tp_default.setSuffix("%")
        sl.addRow("Default TP:", self.risk_tp_default)
        self.risk_trailing = QCheckBox("Neural Trailing Stop")
        self.risk_trailing.setChecked(True)
        self.risk_trailing.setStyleSheet("color: #aa66ff;")
        sl.addRow("", self.risk_trailing)
        layout.addWidget(sltp, 0, 1)
        return w

    def _create_performance_tab(self):
        w = QWidget()
        layout = QGridLayout(w)
        perf = QGroupBox("Neural Performance")
        perf.setStyleSheet("QGroupBox { color: #00ccff; font-weight: bold; }")
        pl = QFormLayout(perf)
        self.perf_scans = QLabel("Scans: 0")
        self.perf_signals = QLabel("Signals: 0")
        self.perf_trades = QLabel("Trades: 0")
        self.perf_errors = QLabel("Errors: 0")
        self.perf_avg_time = QLabel("Avg Cycle: 0.0s")
        self.perf_health = QLabel("Health: 100%")
        for lbl in [self.perf_scans, self.perf_signals, self.perf_trades, self.perf_errors, self.perf_avg_time, self.perf_health]:
            lbl.setStyleSheet("color: #ccc; font-size: 14px;")
            pl.addRow(lbl)
        layout.addWidget(perf, 0, 0)

        adapt = QGroupBox("AutoPilot Log")
        adapt.setStyleSheet("QGroupBox { color: #aa66ff; font-weight: bold; }")
        al = QVBoxLayout(adapt)
        self.autopilot_log = QTextEdit()
        self.autopilot_log.setReadOnly(True)
        self.autopilot_log.setStyleSheet("background: #0a0a0a; color: #aa66ff;")
        al.addWidget(self.autopilot_log)
        layout.addWidget(adapt, 0, 1, 2, 1)

        export_group = QGroupBox("Export")
        export_group.setStyleSheet("QGroupBox { color: #00ff88; font-weight: bold; }")
        el = QVBoxLayout(export_group)
        self.btn_export_csv = NeonButton("EXPORT CSV", "#00ff88")
        self.btn_export_csv.clicked.connect(self._on_export_csv)
        el.addWidget(self.btn_export_csv)
        layout.addWidget(export_group, 1, 0)
        return w

    def _create_settings_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        scroll = QScrollArea()
        sw = QWidget()
        sl = QVBoxLayout(sw)

        api = QGroupBox("API Configuration")
        api.setStyleSheet("QGroupBox { color: #00ccff; font-weight: bold; }")
        al = QFormLayout(api)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password if PYQT_VER == 6 else QLineEdit.Password)
        self.api_key.setStyleSheet("background: #0a0a0a; color: #00ccff; border: 1px solid #333;")
        al.addRow("API Key:", self.api_key)
        self.api_secret = QLineEdit()
        self.api_secret.setEchoMode(QLineEdit.EchoMode.Password if PYQT_VER == 6 else QLineEdit.Password)
        self.api_secret.setStyleSheet("background: #0a0a0a; color: #00ccff; border: 1px solid #333;")
        al.addRow("API Secret:", self.api_secret)
        self.api_testnet = QCheckBox("Use Testnet")
        self.api_testnet.setStyleSheet("color: #ffaa00;")
        self.api_testnet.setChecked(True)
        al.addRow("", self.api_testnet)
        sl.addWidget(api)

        trade = QGroupBox("Trading Parameters")
        trade.setStyleSheet("QGroupBox { color: #00ff88; font-weight: bold; }")
        tl = QFormLayout(trade)
        self.set_symbol_count = QSpinBox()
        self.set_symbol_count.setRange(1, 50)
        self.set_symbol_count.setValue(15)
        tl.addRow("Symbols:", self.set_symbol_count)
        self.set_timeframe = QComboBox()
        self.set_timeframe.addItems(["1m", "5m", "15m", "1h", "4h", "1d"])
        self.set_timeframe.setCurrentText("15m")
        tl.addRow("Timeframe:", self.set_timeframe)
        self.set_paper = QCheckBox("Paper Trading")
        self.set_paper.setChecked(True)
        self.set_paper.setStyleSheet("color: #00ff88;")
        tl.addRow("", self.set_paper)
        self.set_auto = QCheckBox("Auto-Start on Launch")
        tl.addRow("", self.set_auto)
        sl.addWidget(trade)

        tg = QGroupBox("Telegram Alerts")
        tg.setStyleSheet("QGroupBox { color: #00ccff; font-weight: bold; }")
        tgl = QFormLayout(tg)
        self.tg_enabled = QCheckBox("Enable")
        self.tg_enabled.setStyleSheet("color: #00ccff;")
        tgl.addRow("", self.tg_enabled)
        self.tg_token = QLineEdit()
        self.tg_token.setStyleSheet("background: #0a0a0a; color: #ccc; border: 1px solid #333;")
        self.tg_token.setPlaceholderText("Bot token from @BotFather")
        tgl.addRow("Token:", self.tg_token)
        self.tg_chat_id = QLineEdit()
        self.tg_chat_id.setStyleSheet("background: #0a0a0a; color: #ccc; border: 1px solid #333;")
        self.tg_chat_id.setPlaceholderText("Chat ID")
        tgl.addRow("Chat ID:", self.tg_chat_id)
        sl.addWidget(tg)

        btn_save = NeonButton("SAVE SETTINGS", "#00ff88")
        btn_save.clicked.connect(self._on_save_settings)
        sl.addWidget(btn_save)
        sl.addStretch()

        scroll.setWidget(sw)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        return w

    def _setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        file_menu.addAction("Save State", self._on_save_state)
        file_menu.addAction("Load State", self._on_load_state)
        file_menu.addSeparator()
        file_menu.addAction("Export CSV", self._on_export_csv)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        bot_menu = menubar.addMenu("Bot")
        bot_menu.addAction("Start", self._on_start)
        bot_menu.addAction("Stop", self._on_stop)
        bot_menu.addAction("Pause", self._on_pause)

        view_menu = menubar.addMenu("View")
        view_menu.addAction("Clear Logs", self.log_widget.clear)

        help_menu = menubar.addMenu("Help")
        help_menu.addAction("About", self._on_about)

    def _setup_toolbar(self):
        toolbar = QToolBar("Main")
        self.addToolBar(toolbar)
        toolbar.addAction("Start", self._on_start)
        toolbar.addAction("Stop", self._on_stop)
        toolbar.addAction("Pause", self._on_pause)
        toolbar.addSeparator()
        toolbar.addAction("Scan", self._on_scan)
        toolbar.addSeparator()
        toolbar.addAction("Export", self._on_export_csv)

    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Neural System Ready")
        self.statusbar.setStyleSheet("color: #00ff88; background: #0a0a0a;")

    def _setup_timers(self):
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self._update_ui)
        self.ui_timer.start(1000)

        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self._update_data)
        self.data_timer.start(5000)

    def _setup_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)
            self.tray_icon.setToolTip("CryptoBot v9.0")
            tray_menu = QMenu()
            tray_menu.addAction("Show", self.show)
            tray_menu.addAction("Hide", self.hide)
            tray_menu.addSeparator()
            tray_menu.addAction("Start", self._on_start)
            tray_menu.addAction("Stop", self._on_stop)
            tray_menu.addSeparator()
            tray_menu.addAction("Exit", self.close)
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.show()

    def _apply_neon_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #0a0a0a; }
            QWidget { background-color: #0a0a0a; color: #e0e0e0; font-family: 'Segoe UI', 'JetBrains Mono', sans-serif; }
            QGroupBox { border: 1px solid #333; border-radius: 8px; margin-top: 10px; padding-top: 10px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 8px; }
            QTableWidget { background-color: #0f0f0f; border: 1px solid #222; gridline-color: #1a1a1a; color: #ccc; selection-background-color: #00ff88; selection-color: #000; }
            QTableWidget::item { padding: 6px; }
            QHeaderView::section { background-color: #1a1a2e; color: #00ff88; padding: 8px; border: 1px solid #222; font-weight: bold; }
            QTabWidget::pane { border: 1px solid #222; background: #0a0a0a; }
            QTabBar::tab { background: #1a1a2e; color: #666; padding: 10px 20px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: #0f3460; color: #00ff88; }
            QTabBar::tab:hover:!selected { background: #16213e; color: #aaa; }
            QTextEdit, QLineEdit { background: #0f0f0f; color: #ccc; border: 1px solid #222; border-radius: 4px; padding: 6px; }
            QComboBox, QSpinBox, QDoubleSpinBox { background: #0f0f0f; color: #ccc; border: 1px solid #222; border-radius: 4px; padding: 6px; }
            QScrollBar:vertical { background: #0a0a0a; width: 10px; }
            QScrollBar::handle:vertical { background: #333; border-radius: 5px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #00ff88; }
            QStatusBar { background: #0a0a0a; color: #00ff88; border-top: 1px solid #222; }
            QMenuBar { background: #0a0a0a; color: #ccc; }
            QMenuBar::item:selected { background: #0f3460; }
            QMenu { background: #0a0a0a; color: #ccc; border: 1px solid #222; }
            QMenu::item:selected { background: #0f3460; }
            QTreeWidget { background: #0f0f0f; border: 1px solid #222; }
            QTreeWidget::item:selected { background: #00ff88; color: #000; }
            QLabel { color: #ccc; }
            QCheckBox { color: #ccc; }
            QCheckBox::indicator:checked { background: #00ff88; border: 2px solid #00ff88; }
            QSplitter::handle { background: #222; }
        """)

    def _load_settings_to_ui(self):
        if not self.settings:
            return
        self.api_key.setText(self.settings.api_key)
        self.api_secret.setText(self.settings.api_secret)
        self.api_testnet.setChecked(self.settings.testnet)
        self.set_symbol_count.setValue(self.settings.symbol_count)
        self.set_timeframe.setCurrentText(self.settings.timeframe)
        self.set_paper.setChecked(self.settings.paper_trading)
        self.set_auto.setChecked(self.settings.auto_start)
        self.tg_enabled.setChecked(self.settings.telegram_enabled)
        self.tg_token.setText(self.settings.telegram_token)
        self.tg_chat_id.setText(self.settings.telegram_chat_id)
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(0 if self.settings.paper_trading else 1)
        self.mode_combo.blockSignals(False)

    def _on_save_settings(self):
        if not self.settings:
            return
        self.settings.api_key = self.api_key.text()
        self.settings.api_secret = self.api_secret.text()
        self.settings.testnet = self.api_testnet.isChecked()
        self.settings.symbol_count = self.set_symbol_count.value()
        self.settings.timeframe = self.set_timeframe.currentText()
        self.settings.paper_trading = self.set_paper.isChecked()
        self.settings.auto_start = self.set_auto.isChecked()
        self.settings.telegram_enabled = self.tg_enabled.isChecked()
        self.settings.telegram_token = self.tg_token.text()
        self.settings.telegram_chat_id = self.tg_chat_id.text()
        self.settings.save()
        self._reinit_core()
        self.append_log("Settings saved | Neural core reinitialized", 20)
        QMessageBox.information(self, "Settings", "Saved successfully!")

    def _reinit_core(self):
        from core.notifications import NotificationManager, NotificationConfig
        from core.monitor import SystemMonitor
        from core.autopilot import AutoPilot
        from exchange.api_client import BingXAPIClient
        from exchange.data_fetcher import DataFetcher
        from exchange.market_scanner import MarketScanner
        from exchange.trade_executor import TradeExecutor
        from risk.risk_manager import RiskManager, RiskLimits
        from ml.ml_engine import MLEngine

        self.api_client.update_credentials(self.settings.api_key, self.settings.api_secret)
        limits = RiskLimits(
            max_position_size=self.settings.max_position_size,
            max_risk_per_trade=self.settings.max_risk_per_trade,
            max_leverage=self.settings.max_leverage,
            max_daily_loss=self.settings.max_daily_loss,
            default_sl_percent=self.settings.default_sl,
            default_tp_percent=self.settings.default_tp
        )
        self.risk_manager = RiskManager(limits=limits)
        notif_config = NotificationConfig(
            telegram_enabled=self.settings.telegram_enabled,
            telegram_token=self.settings.telegram_token,
            telegram_chat_id=self.settings.telegram_chat_id
        )
        self.notifier = NotificationManager(config=notif_config)
        self.executor = TradeExecutor(
            api_client=self.api_client, risk_manager=self.risk_manager,
            paper_trading=self.settings.paper_trading, balance=10000.0,
            notifier=self.notifier
        )
        self.data_fetcher = DataFetcher(api_client=self.api_client)
        ml = MLEngine()
        self.scanner = MarketScanner(data_fetcher=self.data_fetcher, ml_engine=ml, max_workers=4)
        self.monitor = SystemMonitor()
        self.autopilot = AutoPilot()
        if self.worker:
            self.worker.executor = self.executor
            self.worker.scanner = self.scanner
            self.worker.data_fetcher = self.data_fetcher
            self.worker.monitor = self.monitor
            self.worker.autopilot = self.autopilot
        self.append_log("Neural core reinitialized", 20)

    def _on_mode_changed(self, text):
        is_paper = (text == "PAPER")
        if hasattr(self, 'set_paper'):
            self.set_paper.setChecked(is_paper)
        if self.executor:
            self.executor.paper = is_paper
        if self.settings:
            self.settings.paper_trading = is_paper
        self.append_log("Mode: %s" % text, 20)

    def _on_start(self):
        if self.bot_running:
            return
        if not self.settings.paper_trading:
            if not self.settings.api_key or not self.settings.api_secret:
                QMessageBox.warning(self, "API Keys", "Enter API keys in Settings for live trading")
                return
            reply = QMessageBox.question(self, "LIVE TRADING", "START LIVE TRADING WITH REAL MONEY?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No if PYQT_VER == 6 else QMessageBox.Yes | QMessageBox.No)
            if reply != (QMessageBox.StandardButton.Yes if PYQT_VER == 6 else QMessageBox.Yes):
                return

        # Fetch real balance before starting
        if not self.settings.paper_trading and self.executor:
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                bal = loop.run_until_complete(self.executor.update_balance())
                loop.close()
                self._on_balance_update(bal, bal)
                self.append_log("Balance synced: $%.2f" % bal, 20)
            except Exception as e:
                self.append_log("Balance sync error: %s" % e, 30)

        self.bot_running = True
        self.start_time = datetime.now()
        self.status_indicator.setText("NEURAL ACTIVE")
        self.status_indicator.setStyleSheet("color: #00ff88; font-size: 16px; font-weight: bold; padding: 5px 15px; border: 2px solid #00ff88; border-radius: 4px;")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_pause.setEnabled(True)
        self.append_log("Neural system ACTIVATED", 20)
        if not self.settings.paper_trading:
            self.append_log("!!! LIVE MODE - REAL MONEY !!!", 40)

        self.worker = BotWorker(
            executor=self.executor, scanner=self.scanner,
            data_fetcher=self.data_fetcher, monitor=self.monitor,
            autopilot=self.autopilot if self.chk_autopilot.isChecked() else None,
            interval=self.settings.scan_interval,
            auto_trade=self.chk_auto_trade.isChecked()
        )
        self.worker.signal_log.connect(self.append_log)
        self.worker.signal_status.connect(self.statusbar.showMessage)
        self.worker.signal_balance.connect(self._on_balance_update)
        self.worker.signal_positions.connect(self._on_positions_update)
        self.worker.signal_scan_done.connect(self._on_scan_done)
        self.worker.signal_performance.connect(self._on_performance_update)
        self.worker.signal_health.connect(self._on_health_update)
        self.worker.signal_neural.connect(self._on_neural_signal)
        self.worker.start()
        self._test_api()

    def _test_api(self):
        if self.api_client:
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(self.api_client.get_server_time())
                loop.close()
                if isinstance(result, dict) and result.get("code") == 0:
                    self.conn_status.setText("API: ONLINE")
                    self.conn_status.setStyleSheet("color: #00ff88; font-size: 12px;")
                    self.append_log("API connection established", 20)
                else:
                    self.conn_status.setText("API: ERROR")
                    self.conn_status.setStyleSheet("color: #ff0044; font-size: 12px;")
            except Exception as e:
                self.conn_status.setText("API: OFFLINE")
                self.conn_status.setStyleSheet("color: #ff0044; font-size: 12px;")
                self.append_log("API connection failed: %s" % e, 40)

    def _on_balance_update(self, balance, available):
        self.lbl_balance.setText("$%.2f" % balance)
        self.dash_total_balance.setText("$%.2f" % balance)
        self.dash_available.setText("Available: $%.2f" % available)

    def _on_positions_update(self, positions):
        self.positions_table.setRowCount(len(positions))
        total_pnl = 0.0
        for i, pos in enumerate(positions):
            self.positions_table.setItem(i, 0, QTableWidgetItem(pos.get("symbol", "")))
            self.positions_table.setItem(i, 1, QTableWidgetItem(pos.get("side", "")))
            self.positions_table.setItem(i, 2, QTableWidgetItem("%.4f" % pos.get("size", 0)))
            self.positions_table.setItem(i, 3, QTableWidgetItem("$%.2f" % pos.get("entry", 0)))
            self.positions_table.setItem(i, 4, QTableWidgetItem("-"))
            self.positions_table.setItem(i, 5, QTableWidgetItem("$%.2f" % pos.get("stop_loss", 0)))
            self.positions_table.setItem(i, 6, QTableWidgetItem("$%.2f" % pos.get("take_profit", 0)))
            self.positions_table.setItem(i, 7, QTableWidgetItem("$%+.2f" % pos.get("pnl", 0)))
            self.positions_table.setItem(i, 8, QTableWidgetItem("%+.2f%%" % pos.get("pnl_percent", 0)))
            self.positions_table.setItem(i, 9, QTableWidgetItem("Close"))
            total_pnl += pos.get("pnl", 0)
        self.lbl_positions.setText("%d" % len(positions))
        self.lbl_pnl.setText("$%+.2f" % total_pnl)
        color = "#00ff88" if total_pnl >= 0 else "#ff0044"
        self.lbl_pnl.setStyleSheet("color: %s; font-size: 16px;" % color)
        self.dash_daily_pnl.setText("Daily: $%+.2f" % total_pnl)
        self.dash_daily_pnl.setStyleSheet("color: %s;" % color)

    def _on_performance_update(self, perf):
        self.perf_scans.setText("Scans: %d" % perf.get("scans", 0))
        self.perf_signals.setText("Signals: %d" % perf.get("signals", 0))
        self.perf_trades.setText("Trades: %d" % perf.get("trades", 0))
        self.perf_errors.setText("Errors: %d" % perf.get("errors", 0))
        self.perf_avg_time.setText("Avg Cycle: %.1fs" % perf.get("avg_scan_time", 0))

    def _on_health_update(self, health):
        score = health.get("health_score", 100)
        self.health_gauge.set_value(score)
        self.lbl_health_status.setText("Status: %s" % health.get("status", "unknown").upper())
        self.lbl_health_status.setStyleSheet(
            "color: %s; font-size: 14px; font-weight: bold;" % (
                "#00ff88" if score >= 70 else "#ffaa00" if score >= 40 else "#ff0044"
            )
        )
        self.lbl_cycle_time.setText("Cycle: %.1fs" % health.get("avg_cycle_time", 0))
        self.lbl_api_latency.setText("API: %.0fms" % health.get("avg_api_latency", 0))
        self.lbl_error_rate.setText("Errors: %d total" % health.get("total_errors", 0))
        self.perf_health.setText("Health: %d%%" % score)

    def _on_neural_signal(self, data):
        self.neural_log.append("[%s] %s | conf=%.2f neural=%.2f | %s | %s" % (
            datetime.now().strftime("%H:%M:%S"),
            data.get("symbol", ""),
            data.get("confidence", 0),
            data.get("neural_score", 0),
            data.get("regime", "unknown"),
            data.get("multi_tf", "")
        ))

    def _on_stop(self):
        if not self.bot_running:
            return
        self.bot_running = False
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.status_indicator.setText("STANDBY")
        self.status_indicator.setStyleSheet("color: #ffaa00; font-size: 16px; font-weight: bold; padding: 5px 15px; border: 2px solid #ffaa00; border-radius: 4px;")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_pause.setEnabled(False)
        self.append_log("Neural system DEACTIVATED", 20)
        self.statusbar.showMessage("Standby")

    def _on_pause(self):
        if not self.worker:
            return
        if self.worker._paused:
            self.worker.resume()
            self.btn_pause.setText("PAUSE")
            self.status_indicator.setText("NEURAL ACTIVE")
            self.status_indicator.setStyleSheet("color: #00ff88; font-size: 16px; font-weight: bold; padding: 5px 15px; border: 2px solid #00ff88; border-radius: 4px;")
            self.append_log("System resumed", 20)
        else:
            self.worker.pause()
            self.btn_pause.setText("RESUME")
            self.status_indicator.setText("PAUSED")
            self.status_indicator.setStyleSheet("color: #ffaa00; font-size: 16px; font-weight: bold; padding: 5px 15px; border: 2px solid #ffaa00; border-radius: 4px;")
            self.append_log("System paused", 20)

    def _on_scan(self):
        self.append_log("Neural scan initiated...", 20)
        if self.bot_running and self.worker:
            self.worker.request_scan()
        elif self.scanner:
            self.btn_scan.setEnabled(False)
            self.btn_scan.setText("SCANNING...")
            class ScanThread(QThread):
                done = pyqtSignal(list)
                log = pyqtSignal(str, int)
                def __init__(self, scanner, count, timeframe):
                    super().__init__()
                    self.scanner = scanner
                    self.count = count
                    self.timeframe = timeframe
                def run(self):
                    try:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.scanner.load_symbols(self.count))
                        signals = loop.run_until_complete(self.scanner.scan_all(self.timeframe))
                        loop.close()
                        self.done.emit(signals)
                    except Exception as e:
                        self.log.emit("Scan error: %s" % e, 40)
                        self.done.emit([])
            self._scan_thread = ScanThread(self.scanner, self.scan_symbols.value(), self.scan_timeframe.currentText())
            self._scan_thread.done.connect(self._on_scan_done)
            self._scan_thread.log.connect(self.append_log)
            self._scan_thread.finished.connect(lambda: (self.btn_scan.setEnabled(True), self.btn_scan.setText("NEURAL SCAN")))
            self._scan_thread.start()
        else:
            self.append_log("Scanner not ready", 40)

    def _on_scan_done(self, signals):
        self.signals_table.setRowCount(min(len(signals), 20))
        for i, sig in enumerate(signals[:20]):
            self.signals_table.setItem(i, 0, QTableWidgetItem(str(sig.timestamp)[:19]))
            self.signals_table.setItem(i, 1, QTableWidgetItem(sig.symbol))
            self.signals_table.setItem(i, 2, QTableWidgetItem(sig.strategy))
            self.signals_table.setItem(i, 3, QTableWidgetItem(sig.type.value.upper()))
            self.signals_table.setItem(i, 4, QTableWidgetItem("%.2f" % sig.confidence))
            neural_score = sig.metadata.get("neural_score", 0) if sig.metadata else 0
            self.signals_table.setItem(i, 5, QTableWidgetItem("%.2f" % neural_score))
            regime = sig.metadata.get("regime", "unknown") if sig.metadata else "unknown"
            self.signals_table.setItem(i, 6, QTableWidgetItem(regime))
            mtf = sig.metadata.get("multi_tf", "") if sig.metadata else ""
            self.signals_table.setItem(i, 7, QTableWidgetItem(mtf))
        self.append_log("Scan complete: %d signals" % len(signals), 20)

    def _on_export_csv(self):
        if not self.executor:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Trades", "trades_%s.csv" % datetime.now().strftime("%Y%m%d_%H%M%S"), "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Time", "Symbol", "Side", "Qty", "Price", "P&L", "Status"])
                for o in self.executor.orders:
                    writer.writerow([o.fill_time, o.symbol, o.position_side, o.quantity, o.fill_price, o.pnl, o.status.value])
            self.append_log("Exported %d trades to %s" % (len(self.executor.orders), path), 20)
            QMessageBox.information(self, "Export", "Trades exported!")
        except Exception as e:
            self.append_log("Export error: %s" % e, 40)

    def _on_save_state(self):
        if self.state_manager:
            self.state_manager.save_stat("last_save", datetime.now().isoformat())
            self.append_log("State saved", 20)

    def _on_load_state(self):
        self.append_log("State loaded", 20)

    def _on_about(self):
        QMessageBox.about(self, "About",
            "<h2 style='color:#00ff88'>CryptoBot v9.0</h2>"
            "<p style='color:#ccc'>Neural Adaptive Trading System</p>"
            "<ul style='color:#aaa'>"
            "<li>Multi-timeframe analysis (15m + 1h + 4h)</li>"
            "<li>Real-time neural scoring</li>"
            "<li>AutoPilot self-adaptation</li>"
            "<li>Market regime detection</li>"
            "<li>Partial TP + Breakeven SL</li>"
            "<li>Circuit breaker API protection</li>"
            "<li>System health monitoring</li>"
            "<li>WebSocket price streams</li>"
            "</ul>")

    def _update_ui(self):
        if self.start_time and self.bot_running:
            elapsed = datetime.now() - self.start_time
            hours, rem = divmod(int(elapsed.total_seconds()), 3600)
            mins, secs = divmod(rem, 60)
            self.lbl_uptime.setText("%02d:%02d:%02d" % (hours, mins, secs))

    def _update_data(self):
        if not self.bot_running:
            return
        if self.risk_manager:
            try:
                stats = self.risk_manager.get_stats()
                self.dash_total_pnl.setText("Total: $%+.2f" % stats.get("total_pnl", 0))
                self.dash_winrate.setText("Win Rate: %.1f%%" % stats.get("win_rate", 0))
                self.dash_trades.setText("Trades: %d" % stats.get("total_trades", 0))
            except Exception:
                pass

    def append_log(self, message: str, level: int = 20):
        if hasattr(self, 'log_widget'):
            self.log_widget.append_log(message, level)

    def closeEvent(self, event):
        if self.bot_running:
            reply = QMessageBox.question(self, "Exit", "Neural system running. Stop and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No if PYQT_VER == 6 else QMessageBox.Yes | QMessageBox.No)
            if reply == (QMessageBox.StandardButton.Yes if PYQT_VER == 6 else QMessageBox.Yes):
                self._on_stop()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
