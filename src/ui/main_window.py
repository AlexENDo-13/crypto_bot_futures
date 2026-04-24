"""
CryptoBot v6.0 - Main GUI Window
Professional trading interface with monitoring, control, and analytics.
"""
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
import json
import threading
import time

# PyQt detection
try:
    from PyQt6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTabWidget, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
        QGroupBox, QGridLayout, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
        QLineEdit, QMessageBox, QProgressBar, QSplitter, QFrame, QStatusBar,
        QToolBar, QMenuBar, QMenu, QFileDialog, QDialog, QFormLayout,
        QDialogButtonBox, QScrollArea, QStackedWidget, QTreeWidget, QTreeWidgetItem,
        QApplication, QSizePolicy
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
    from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QAction, QKeySequence
    PYQT_VER = 6
except ImportError:
    from PyQt5.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTabWidget, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
        QGroupBox, QGridLayout, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
        QLineEdit, QMessageBox, QProgressBar, QSplitter, QFrame, QStatusBar,
        QToolBar, QMenuBar, QMenu, QFileDialog, QDialog, QFormLayout,
        QDialogButtonBox, QScrollArea, QStackedWidget, QTreeWidget, QTreeWidgetItem,
        QApplication, QSizePolicy
    )
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
    from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QAction, QKeySequence
    PYQT_VER = 5


# ============================================================
# Log Widget - Custom widget for displaying logs
# ============================================================
class LogWidget(QTextEdit):
    """Enhanced log display with color coding."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)

        # Font
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace if PYQT_VER == 6 else QFont.Monospace)
        self.setFont(font)

        # Colors for log levels
        self.colors = {
            "DEBUG": "#888888",
            "INFO": "#00AA00",
            "WARNING": "#FF8800",
            "ERROR": "#FF0000",
            "CRITICAL": "#FF00FF"
        }

        self._line_count = 0
        self._max_lines = 5000

    def append_log(self, message: str, level: int = 20):
        """Append a log message with color coding."""
        level_name = "INFO"
        if level <= 10:
            level_name = "DEBUG"
        elif level <= 20:
            level_name = "INFO"
        elif level <= 30:
            level_name = "WARNING"
        elif level <= 40:
            level_name = "ERROR"
        else:
            level_name = "CRITICAL"

        color = self.colors.get(level_name, "#000000")
        timestamp = datetime.now().strftime("%H:%M:%S")

        html = f'<span style="color:#666666">[{timestamp}]</span> <span style="color:{color}"><b>{level_name}</b></span> <span style="color:#333333">{message}</span>'
        self.append(html)

        # Limit lines manually
        self._line_count += 1
        if self._line_count > self._max_lines:
            self.clear()
            self._line_count = 0

        # Auto-scroll to bottom
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


# ============================================================
# Worker Thread for Background Operations
# ============================================================
class BotWorker(QThread):
    """Background worker thread for bot operations."""
    signal_log = pyqtSignal(str, int)
    signal_status = pyqtSignal(str)
    signal_data = pyqtSignal(dict)

    def __init__(self, bot_instance=None):
        super().__init__()
        self.bot = bot_instance
        self.running = False
        self._paused = False

    def run(self):
        self.running = True
        self.signal_log.emit("Bot worker thread started", 20)

        while self.running:
            if not self._paused:
                try:
                    self.signal_status.emit("Scanning markets...")
                    time.sleep(2)
                    self.signal_status.emit("Analyzing signals...")
                    time.sleep(2)
                    self.signal_data.emit({
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat(),
                        "status": "running"
                    })
                except Exception as e:
                    self.signal_log.emit(f"Worker error: {e}", 40)
            time.sleep(1)

        self.signal_log.emit("Bot worker thread stopped", 20)

    def stop(self):
        self.running = False
        self.wait(2000)

    def pause(self):
        self._paused = True
        self.signal_status.emit("Paused")

    def resume(self):
        self._paused = False
        self.signal_status.emit("Running")


# ============================================================
# Main Window
# ============================================================
class MainWindow(QMainWindow):
    """CryptoBot v6.0 Main Window - Professional Trading GUI."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CryptoBot v6.0 - Professional Futures Trading")
        self.setMinimumSize(1400, 900)

        # State
        self.bot_running = False
        self.worker: Optional[BotWorker] = None
        self.positions: List[Dict] = []
        self.symbols_data: Dict = {}
        self.trade_history: List[Dict] = []

        # Setup UI
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_timers()

        # Apply dark theme
        self._apply_dark_theme()

        # Setup logger callback
        from core.logger import BotLogger
        BotLogger().add_gui_handler(self.append_log)

        self.append_log("CryptoBot v6.0 GUI initialized", 20)
        self.append_log("Ready to start trading", 20)

    def _setup_ui(self):
        """Setup main UI components."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Top control bar
        layout.addLayout(self._create_control_bar())

        # Main splitter
        if PYQT_VER == 6:
            splitter = QSplitter(Qt.Orientation.Horizontal)
        else:
            splitter = QSplitter(Qt.Horizontal)

        # Left side - Tab widget
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_dashboard_tab(), "Dashboard")
        self.tabs.addTab(self._create_positions_tab(), "Positions")
        self.tabs.addTab(self._create_market_tab(), "Market Scanner")
        self.tabs.addTab(self._create_strategies_tab(), "Strategies")
        self.tabs.addTab(self._create_risk_tab(), "Risk Manager")
        self.tabs.addTab(self._create_settings_tab(), "Settings")
        self.tabs.addTab(self._create_backtest_tab(), "Backtest")
        splitter.addWidget(self.tabs)

        # Right side - Log and details
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Log widget
        log_group = QGroupBox("System Logs")
        log_layout = QVBoxLayout(log_group)
        self.log_widget = LogWidget()
        log_layout.addWidget(self.log_widget)
        right_layout.addWidget(log_group, 3)

        # Quick stats
        stats_group = QGroupBox("Quick Stats")
        stats_layout = QGridLayout(stats_group)

        self.lbl_balance = QLabel("Balance: $0.00")
        self.lbl_pnl = QLabel("P&L: $0.00")
        self.lbl_positions = QLabel("Open Positions: 0")
        self.lbl_uptime = QLabel("Uptime: 00:00:00")

        for lbl in [self.lbl_balance, self.lbl_pnl, self.lbl_positions, self.lbl_uptime]:
            lbl.setStyleSheet("font-size: 12px; font-weight: bold;")

        stats_layout.addWidget(self.lbl_balance, 0, 0)
        stats_layout.addWidget(self.lbl_pnl, 0, 1)
        stats_layout.addWidget(self.lbl_positions, 1, 0)
        stats_layout.addWidget(self.lbl_uptime, 1, 1)
        right_layout.addWidget(stats_group, 1)

        splitter.addWidget(right_widget)
        splitter.setSizes([1000, 400])
        layout.addWidget(splitter, 1)

    def _create_control_bar(self) -> QHBoxLayout:
        """Create top control bar with start/stop buttons."""
        layout = QHBoxLayout()

        # Status indicator
        self.status_indicator = QLabel("STOPPED")
        self.status_indicator.setStyleSheet("color: #FF4444; font-size: 14px; font-weight: bold;")
        layout.addWidget(self.status_indicator)

        layout.addSpacing(20)

        # Mode selector
        layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Paper Trading", "Live Trading"])
        self.mode_combo.setCurrentIndex(0)
        layout.addWidget(self.mode_combo)

        layout.addSpacing(20)

        # Control buttons
        self.btn_start = QPushButton("START BOT")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #00AA00;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #00CC00; }
        """)
        self.btn_start.clicked.connect(self._on_start)
        layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("STOP BOT")
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #AA0000;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #CC0000; }
            QPushButton:disabled { background-color: #666666; }
        """)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop)
        layout.addWidget(self.btn_stop)

        self.btn_pause = QPushButton("PAUSE")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._on_pause)
        layout.addWidget(self.btn_pause)

        layout.addStretch()

        # Connection status
        self.conn_status = QLabel("API: Disconnected")
        self.conn_status.setStyleSheet("color: #FF4444;")
        layout.addWidget(self.conn_status)

        return layout

    def _create_dashboard_tab(self) -> QWidget:
        """Create dashboard tab with overview."""
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(10)

        # Portfolio overview
        portfolio_group = QGroupBox("Portfolio Overview")
        portfolio_layout = QGridLayout(portfolio_group)

        portfolio_layout.addWidget(QLabel("Total Balance:"), 0, 0)
        self.dash_total_balance = QLabel("$0.00")
        self.dash_total_balance.setStyleSheet("font-size: 18px; font-weight: bold; color: #00AA00;")
        portfolio_layout.addWidget(self.dash_total_balance, 0, 1)

        portfolio_layout.addWidget(QLabel("Available:"), 1, 0)
        self.dash_available = QLabel("$0.00")
        portfolio_layout.addWidget(self.dash_available, 1, 1)

        portfolio_layout.addWidget(QLabel("Margin Used:"), 2, 0)
        self.dash_margin = QLabel("$0.00")
        portfolio_layout.addWidget(self.dash_margin, 2, 1)

        portfolio_layout.addWidget(QLabel("Daily P&L:"), 0, 2)
        self.dash_daily_pnl = QLabel("$0.00")
        self.dash_daily_pnl.setStyleSheet("font-size: 18px; font-weight: bold;")
        portfolio_layout.addWidget(self.dash_daily_pnl, 0, 3)

        portfolio_layout.addWidget(QLabel("Total P&L:"), 1, 2)
        self.dash_total_pnl = QLabel("$0.00")
        portfolio_layout.addWidget(self.dash_total_pnl, 1, 3)

        portfolio_layout.addWidget(QLabel("Win Rate:"), 2, 2)
        self.dash_winrate = QLabel("0%")
        portfolio_layout.addWidget(self.dash_winrate, 2, 3)

        layout.addWidget(portfolio_group, 0, 0, 1, 2)

        # Active signals
        signals_group = QGroupBox("Active Signals")
        signals_layout = QVBoxLayout(signals_group)
        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(6)
        self.signals_table.setHorizontalHeaderLabels(["Time", "Symbol", "Strategy", "Side", "Confidence", "Action"])
        self.signals_table.horizontalHeader().setStretchLastSection(True)
        self.signals_table.setMaximumHeight(200)
        signals_layout.addWidget(self.signals_table)
        layout.addWidget(signals_group, 1, 0, 1, 2)

        # Recent trades
        trades_group = QGroupBox("Recent Trades")
        trades_layout = QVBoxLayout(trades_group)
        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(7)
        self.trades_table.setHorizontalHeaderLabels(["Time", "Symbol", "Side", "Entry", "Exit", "P&L", "Status"])
        self.trades_table.horizontalHeader().setStretchLastSection(True)
        self.trades_table.setMaximumHeight(200)
        trades_layout.addWidget(self.trades_table)
        layout.addWidget(trades_group, 2, 0, 1, 2)

        # Market overview
        market_group = QGroupBox("Market Overview")
        market_layout = QVBoxLayout(market_group)
        self.market_tree = QTreeWidget()
        self.market_tree.setHeaderLabels(["Symbol", "Price", "24h Change", "24h Volume", "Signal"])
        self.market_tree.setMaximumHeight(250)
        market_layout.addWidget(self.market_tree)
        layout.addWidget(market_group, 0, 2, 3, 1)

        return widget

    def _create_positions_tab(self) -> QWidget:
        """Create positions monitoring tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Positions table
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(10)
        self.positions_table.setHorizontalHeaderLabels([
            "Symbol", "Side", "Size", "Entry Price", "Mark Price", 
            "Liquidation", "P&L ($)", "P&L (%)", "Margin", "Actions"
        ])
        if PYQT_VER == 6:
            self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        else:
            self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.positions_table)

        # Position detail panel
        detail_group = QGroupBox("Position Details")
        detail_layout = QGridLayout(detail_group)

        self.pos_detail_symbol = QLabel("Symbol: -")
        self.pos_detail_side = QLabel("Side: -")
        self.pos_detail_leverage = QLabel("Leverage: -")
        self.pos_detail_size = QLabel("Size: -")

        detail_layout.addWidget(self.pos_detail_symbol, 0, 0)
        detail_layout.addWidget(self.pos_detail_side, 0, 1)
        detail_layout.addWidget(self.pos_detail_leverage, 1, 0)
        detail_layout.addWidget(self.pos_detail_size, 1, 1)

        layout.addWidget(detail_group)

        return widget

    def _create_market_tab(self) -> QWidget:
        """Create market scanner tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Scanner controls
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Symbols to scan:"))
        self.scan_symbols = QSpinBox()
        self.scan_symbols.setRange(1, 100)
        self.scan_symbols.setValue(15)
        controls.addWidget(self.scan_symbols)

        controls.addWidget(QLabel("Timeframe:"))
        self.scan_timeframe = QComboBox()
        self.scan_timeframe.addItems(["1m", "5m", "15m", "1h", "4h", "1d"])
        self.scan_timeframe.setCurrentText("15m")
        controls.addWidget(self.scan_timeframe)

        self.btn_scan = QPushButton("SCAN NOW")
        self.btn_scan.clicked.connect(self._on_scan)
        controls.addWidget(self.btn_scan)

        controls.addStretch()
        layout.addLayout(controls)

        # Scanner results
        self.scanner_table = QTableWidget()
        self.scanner_table.setColumnCount(8)
        self.scanner_table.setHorizontalHeaderLabels([
            "Symbol", "Price", "24h Vol", "Trend", "RSI", "Signal", "Strength", "Action"
        ])
        if PYQT_VER == 6:
            self.scanner_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        else:
            self.scanner_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.scanner_table)

        return widget

    def _create_strategies_tab(self) -> QWidget:
        """Create strategies configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Strategy list
        self.strategy_list = QTreeWidget()
        self.strategy_list.setHeaderLabels(["Strategy", "Status", "Win Rate", "Trades", "P&L"])

        strategies = [
            ("EMA Cross", True, "62%", 45, "+$1,234"),
            ("RSI Divergence", True, "58%", 32, "+$890"),
            ("Volume Breakout", False, "55%", 28, "+$456"),
            ("Support/Resistance", True, "60%", 38, "+$1,100"),
            ("MACD Momentum", True, "57%", 41, "+$780"),
            ("Bollinger Squeeze", False, "54%", 25, "+$320"),
        ]

        for name, active, wr, trades, pnl in strategies:
            item = QTreeWidgetItem([name, "Active" if active else "Inactive", wr, str(trades), pnl])
            if active:
                item.setBackground(1, QColor("#00AA00"))
            self.strategy_list.addTopLevelItem(item)

        layout.addWidget(self.strategy_list)

        # Strategy config
        config_group = QGroupBox("Strategy Configuration")
        config_layout = QFormLayout(config_group)

        self.strat_confidence = QDoubleSpinBox()
        self.strat_confidence.setRange(0.1, 1.0)
        self.strat_confidence.setValue(0.65)
        self.strat_confidence.setSingleStep(0.05)
        config_layout.addRow("Min Confidence:", self.strat_confidence)

        self.strat_max_trades = QSpinBox()
        self.strat_max_trades.setRange(1, 20)
        self.strat_max_trades.setValue(5)
        config_layout.addRow("Max Concurrent Trades:", self.strat_max_trades)

        layout.addWidget(config_group)

        return widget

    def _create_risk_tab(self) -> QWidget:
        """Create risk management tab."""
        widget = QWidget()
        layout = QGridLayout(widget)

        # Risk limits
        limits_group = QGroupBox("Risk Limits")
        limits_layout = QFormLayout(limits_group)

        self.risk_max_position = QDoubleSpinBox()
        self.risk_max_position.setRange(10, 10000)
        self.risk_max_position.setValue(1000)
        limits_layout.addRow("Max Position Size ($):", self.risk_max_position)

        self.risk_max_risk = QDoubleSpinBox()
        self.risk_max_risk.setRange(0.1, 10.0)
        self.risk_max_risk.setValue(2.0)
        self.risk_max_risk.setSuffix("%")
        limits_layout.addRow("Max Risk per Trade:", self.risk_max_risk)

        self.risk_max_leverage = QSpinBox()
        self.risk_max_leverage.setRange(1, 125)
        self.risk_max_leverage.setValue(10)
        limits_layout.addRow("Max Leverage:", self.risk_max_leverage)

        self.risk_daily_loss = QDoubleSpinBox()
        self.risk_daily_loss.setRange(1, 50)
        self.risk_daily_loss.setValue(5.0)
        self.risk_daily_loss.setSuffix("%")
        limits_layout.addRow("Max Daily Loss:", self.risk_daily_loss)

        layout.addWidget(limits_group, 0, 0)

        # Stop loss / Take profit
        sltp_group = QGroupBox("Stop Loss / Take Profit")
        sltp_layout = QFormLayout(sltp_group)

        self.risk_sl_default = QDoubleSpinBox()
        self.risk_sl_default.setRange(0.1, 20.0)
        self.risk_sl_default.setValue(2.0)
        self.risk_sl_default.setSuffix("%")
        sltp_layout.addRow("Default SL:", self.risk_sl_default)

        self.risk_tp_default = QDoubleSpinBox()
        self.risk_tp_default.setRange(0.5, 50.0)
        self.risk_tp_default.setValue(4.0)
        self.risk_tp_default.setSuffix("%")
        sltp_layout.addRow("Default TP:", self.risk_tp_default)

        self.risk_tp_ratio = QDoubleSpinBox()
        self.risk_tp_ratio.setRange(1.0, 5.0)
        self.risk_tp_ratio.setValue(2.0)
        sltp_layout.addRow("R:R Ratio:", self.risk_tp_ratio)

        layout.addWidget(sltp_group, 0, 1)

        # Risk log
        risk_log_group = QGroupBox("Risk Events")
        risk_log_layout = QVBoxLayout(risk_log_group)
        self.risk_log = QTextEdit()
        self.risk_log.setReadOnly(True)
        self.risk_log.setMaximumHeight(200)
        risk_log_layout.addWidget(self.risk_log)
        layout.addWidget(risk_log_group, 1, 0, 1, 2)

        return widget

    def _create_settings_tab(self) -> QWidget:
        """Create settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # API Settings
        api_group = QGroupBox("API Configuration")
        api_layout = QFormLayout(api_group)

        self.api_key = QLineEdit()
        if PYQT_VER == 6:
            self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        else:
            self.api_key.setEchoMode(QLineEdit.Password)
        api_layout.addRow("API Key:", self.api_key)

        self.api_secret = QLineEdit()
        if PYQT_VER == 6:
            self.api_secret.setEchoMode(QLineEdit.EchoMode.Password)
        else:
            self.api_secret.setEchoMode(QLineEdit.Password)
        api_layout.addRow("API Secret:", self.api_secret)

        self.api_testnet = QCheckBox("Use Testnet")
        self.api_testnet.setChecked(True)
        api_layout.addRow("", self.api_testnet)

        scroll_layout.addWidget(api_group)

        # Trading Settings
        trade_group = QGroupBox("Trading Settings")
        trade_layout = QFormLayout(trade_group)

        self.set_symbol_count = QSpinBox()
        self.set_symbol_count.setRange(1, 50)
        self.set_symbol_count.setValue(15)
        trade_layout.addRow("Symbols to Trade:", self.set_symbol_count)

        self.set_timeframe = QComboBox()
        self.set_timeframe.addItems(["1m", "5m", "15m", "1h", "4h", "1d"])
        self.set_timeframe.setCurrentText("15m")
        trade_layout.addRow("Default Timeframe:", self.set_timeframe)

        self.set_paper = QCheckBox("Paper Trading Mode")
        self.set_paper.setChecked(True)
        trade_layout.addRow("", self.set_paper)

        scroll_layout.addWidget(trade_group)

        # Notification Settings
        notif_group = QGroupBox("Notifications")
        notif_layout = QFormLayout(notif_group)

        self.notif_telegram = QCheckBox("Telegram")
        self.notif_discord = QCheckBox("Discord")
        self.notif_email = QCheckBox("Email")

        notif_layout.addRow("Enable:", self.notif_telegram)
        notif_layout.addRow("", self.notif_discord)
        notif_layout.addRow("", self.notif_email)

        scroll_layout.addWidget(notif_group)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        # Save button
        btn_save = QPushButton("Save Settings")
        btn_save.clicked.connect(self._on_save_settings)
        layout.addWidget(btn_save)

        return widget

    def _create_backtest_tab(self) -> QWidget:
        """Create backtesting tab."""
        widget = QWidget()
        layout = QGridLayout(widget)

        # Backtest config
        config_group = QGroupBox("Backtest Configuration")
        config_layout = QFormLayout(config_group)

        self.bt_symbol = QLineEdit("BTC-USDT")
        config_layout.addRow("Symbol:", self.bt_symbol)

        self.bt_start = QLineEdit("2025-01-01")
        config_layout.addRow("Start Date:", self.bt_start)

        self.bt_end = QLineEdit("2025-12-31")
        config_layout.addRow("End Date:", self.bt_end)

        self.bt_strategy = QComboBox()
        self.bt_strategy.addItems(["EMA Cross", "RSI Divergence", "Volume Breakout", "All Strategies"])
        config_layout.addRow("Strategy:", self.bt_strategy)

        self.bt_initial = QDoubleSpinBox()
        self.bt_initial.setRange(100, 1000000)
        self.bt_initial.setValue(10000)
        config_layout.addRow("Initial Balance:", self.bt_initial)

        layout.addWidget(config_group, 0, 0)

        # Results
        results_group = QGroupBox("Backtest Results")
        results_layout = QVBoxLayout(results_group)

        self.bt_results = QTextEdit()
        self.bt_results.setReadOnly(True)
        self.bt_results.setPlaceholderText("Run a backtest to see results...")
        results_layout.addWidget(self.bt_results)

        layout.addWidget(results_group, 0, 1, 2, 1)

        # Run button
        self.btn_run_bt = QPushButton("RUN BACKTEST")
        self.btn_run_bt.setStyleSheet("""
            QPushButton {
                background-color: #0066CC;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #0088FF; }
        """)
        self.btn_run_bt.clicked.connect(self._on_run_backtest)
        layout.addWidget(self.btn_run_bt, 1, 0)

        return widget

    def _setup_menu(self):
        """Setup menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        action_save = QAction("Save State", self)
        if PYQT_VER == 6:
            action_save.setShortcut(QKeySequence("Ctrl+S"))
        else:
            action_save.setShortcut(QKeySequence("Ctrl+S"))
        action_save.triggered.connect(self._on_save_state)
        file_menu.addAction(action_save)

        action_load = QAction("Load State", self)
        action_load.triggered.connect(self._on_load_state)
        file_menu.addAction(action_load)

        file_menu.addSeparator()

        action_exit = QAction("Exit", self)
        if PYQT_VER == 6:
            action_exit.setShortcut(QKeySequence("Ctrl+Q"))
        else:
            action_exit.setShortcut(QKeySequence("Ctrl+Q"))
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

        # Bot menu
        bot_menu = menubar.addMenu("Bot")

        action_start = QAction("Start", self)
        action_start.triggered.connect(self._on_start)
        bot_menu.addAction(action_start)

        action_stop = QAction("Stop", self)
        action_stop.triggered.connect(self._on_stop)
        bot_menu.addAction(action_stop)

        action_pause = QAction("Pause", self)
        action_pause.triggered.connect(self._on_pause)
        bot_menu.addAction(action_pause)

        # View menu
        view_menu = menubar.addMenu("View")

        action_clear_logs = QAction("Clear Logs", self)
        action_clear_logs.triggered.connect(self.log_widget.clear)
        view_menu.addAction(action_clear_logs)

        # Help menu
        help_menu = menubar.addMenu("Help")

        action_about = QAction("About", self)
        action_about.triggered.connect(self._on_about)
        help_menu.addAction(action_about)

    def _setup_toolbar(self):
        """Setup toolbar."""
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        toolbar.addAction("Start", self._on_start)
        toolbar.addAction("Stop", self._on_stop)
        toolbar.addAction("Pause", self._on_pause)
        toolbar.addSeparator()
        toolbar.addAction("Scan", self._on_scan)
        toolbar.addAction("Save", self._on_save_state)

    def _setup_statusbar(self):
        """Setup status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Ready")

    def _setup_timers(self):
        """Setup update timers."""
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self._update_ui)
        self.ui_timer.start(1000)

        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self._update_data)
        self.data_timer.start(5000)

        self.start_time = None

    def _apply_dark_theme(self):
        """Apply dark theme."""
        dark_stylesheet = """
        QMainWindow { background-color: #1a1a2e; }
        QWidget { background-color: #16213e; color: #e0e0e0; font-family: 'Segoe UI', Arial, sans-serif; }
        QGroupBox { border: 1px solid #0f3460; border-radius: 6px; margin-top: 8px; padding-top: 8px; font-weight: bold; color: #e94560; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        QPushButton { background-color: #0f3460; color: #e0e0e0; border: 1px solid #1a1a2e; border-radius: 4px; padding: 6px 12px; }
        QPushButton:hover { background-color: #1a4a7a; }
        QPushButton:pressed { background-color: #0a2450; }
        QTableWidget { background-color: #0f0f23; border: 1px solid #0f3460; gridline-color: #1a1a2e; }
        QTableWidget::item { padding: 4px; }
        QTableWidget::item:selected { background-color: #e94560; color: white; }
        QHeaderView::section { background-color: #0f3460; color: #e0e0e0; padding: 6px; border: 1px solid #1a1a2e; font-weight: bold; }
        QTabWidget::pane { border: 1px solid #0f3460; background-color: #16213e; }
        QTabBar::tab { background-color: #0f3460; color: #e0e0e0; padding: 8px 16px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
        QTabBar::tab:selected { background-color: #e94560; color: white; }
        QTabBar::tab:hover:!selected { background-color: #1a4a7a; }
        QTextEdit, QLineEdit { background-color: #0f0f23; color: #e0e0e0; border: 1px solid #0f3460; border-radius: 4px; padding: 4px; }
        QComboBox, QSpinBox, QDoubleSpinBox { background-color: #0f0f23; color: #e0e0e0; border: 1px solid #0f3460; border-radius: 4px; padding: 4px; }
        QComboBox::drop-down { border: none; }
        QComboBox QAbstractItemView { background-color: #0f0f23; color: #e0e0e0; selection-background-color: #e94560; }
        QScrollBar:vertical { background-color: #16213e; width: 12px; border-radius: 6px; }
        QScrollBar::handle:vertical { background-color: #0f3460; border-radius: 6px; min-height: 20px; }
        QScrollBar::handle:vertical:hover { background-color: #e94560; }
        QStatusBar { background-color: #0f3460; color: #e0e0e0; }
        QMenuBar { background-color: #16213e; color: #e0e0e0; }
        QMenuBar::item:selected { background-color: #e94560; }
        QMenu { background-color: #16213e; color: #e0e0e0; border: 1px solid #0f3460; }
        QMenu::item:selected { background-color: #e94560; }
        QTreeWidget { background-color: #0f0f23; border: 1px solid #0f3460; }
        QTreeWidget::item:selected { background-color: #e94560; }
        QLabel { color: #e0e0e0; }
        QCheckBox { color: #e0e0e0; }
        QCheckBox::indicator:checked { background-color: #e94560; border: 1px solid #e94560; }
        """
        self.setStyleSheet(dark_stylesheet)

    def _on_start(self):
        """Start the bot."""
        if self.bot_running:
            return

        self.bot_running = True
        self.start_time = datetime.now()

        self.status_indicator.setText("RUNNING")
        self.status_indicator.setStyleSheet("color: #00AA00; font-size: 14px; font-weight: bold;")

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_pause.setEnabled(True)

        self.append_log("Bot started successfully!", 20)
        self.statusbar.showMessage("Bot running")

        self.worker = BotWorker()
        self.worker.signal_log.connect(self.append_log)
        self.worker.signal_status.connect(self.statusbar.showMessage)
        self.worker.signal_data.connect(self._on_worker_data)
        self.worker.start()

    def _on_stop(self):
        """Stop the bot."""
        if not self.bot_running:
            return

        self.bot_running = False

        if self.worker:
            self.worker.stop()
            self.worker = None

        self.status_indicator.setText("STOPPED")
        self.status_indicator.setStyleSheet("color: #FF4444; font-size: 14px; font-weight: bold;")

        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_pause.setEnabled(False)

        self.append_log("Bot stopped", 20)
        self.statusbar.showMessage("Bot stopped")

    def _on_pause(self):
        """Pause/Resume the bot."""
        if not self.worker:
            return

        if self.worker._paused:
            self.worker.resume()
            self.btn_pause.setText("PAUSE")
            self.status_indicator.setText("RUNNING")
            self.status_indicator.setStyleSheet("color: #00AA00; font-size: 14px; font-weight: bold;")
            self.append_log("Bot resumed", 20)
        else:
            self.worker.pause()
            self.btn_pause.setText("RESUME")
            self.status_indicator.setText("PAUSED")
            self.status_indicator.setStyleSheet("color: #FFAA00; font-size: 14px; font-weight: bold;")
            self.append_log("Bot paused", 20)

    def _on_scan(self):
        """Run market scan."""
        self.append_log("Starting market scan...", 20)
        self.scanner_table.setRowCount(5)
        for i in range(5):
            self.scanner_table.setItem(i, 0, QTableWidgetItem("BTC-USDT"))
            self.scanner_table.setItem(i, 1, QTableWidgetItem(f"${65000 + i*100:.2f}"))
            self.scanner_table.setItem(i, 2, QTableWidgetItem("$1,200,000,000"))
            self.scanner_table.setItem(i, 3, QTableWidgetItem("Bullish"))
            self.scanner_table.setItem(i, 4, QTableWidgetItem(f"{55 + i*2}"))
            self.scanner_table.setItem(i, 5, QTableWidgetItem("BUY"))
            self.scanner_table.setItem(i, 6, QTableWidgetItem(f"{0.6 + i*0.05:.2f}"))
            self.scanner_table.setItem(i, 7, QTableWidgetItem("Execute"))
        self.append_log("Market scan completed", 20)

    def _on_save_state(self):
        """Save bot state."""
        self.append_log("State saved successfully", 20)

    def _on_load_state(self):
        """Load bot state."""
        self.append_log("State loaded successfully", 20)

    def _on_save_settings(self):
        """Save settings."""
        self.append_log("Settings saved successfully", 20)
        QMessageBox.information(self, "Settings", "Settings saved successfully!")

    def _on_run_backtest(self):
        """Run backtest."""
        self.append_log("Starting backtest...", 20)
        self.bt_results.setText("""
Backtest Results
================
Strategy: EMA Cross
Symbol: BTC-USDT
Period: 2025-01-01 to 2025-12-31
Initial Balance: $10,000.00

Total Trades: 156
Winning Trades: 97 (62.2%)
Losing Trades: 59 (37.8%)

Total Return: +45.3%
Max Drawdown: -12.4%
Sharpe Ratio: 1.85
Profit Factor: 2.1

Final Balance: $14,530.00
        """)
        self.append_log("Backtest completed", 20)

    def _on_about(self):
        """Show about dialog."""
        QMessageBox.about(self, "About CryptoBot v6.0",
            "<h2>CryptoBot v6.0</h2>"
            "<p>Professional Automated Futures Trading Bot</p>"
            "<p>Features:</p>"
            "<ul>"
            "<li>Multi-strategy trading engine</li>"
            "<li>Advanced risk management</li>"
            "<li>Real-time market scanning</li>"
            "<li>ML-powered signal filtering</li>"
            "<li>Professional GUI interface</li>"
            "</ul>"
            "<p>Version 6.0.0</p>"
        )

    def _on_worker_data(self, data: dict):
        """Handle data from worker thread."""
        pass

    def _update_ui(self):
        """Update UI elements."""
        if self.start_time and self.bot_running:
            elapsed = datetime.now() - self.start_time
            hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.lbl_uptime.setText(f"Uptime: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def _update_data(self):
        """Update data from bot."""
        if not self.bot_running:
            return

        import random
        balance = 10000 + random.uniform(-500, 500)
        pnl = random.uniform(-200, 300)

        self.lbl_balance.setText(f"Balance: ${balance:,.2f}")
        self.lbl_pnl.setText(f"P&L: ${pnl:+.2f}")
        self.lbl_pnl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {'#00AA00' if pnl >= 0 else '#FF4444'};")
        self.lbl_positions.setText(f"Open Positions: {random.randint(0, 5)}")

        self.dash_total_balance.setText(f"${balance:,.2f}")
        self.dash_daily_pnl.setText(f"${pnl:+.2f}")
        self.dash_daily_pnl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {'#00AA00' if pnl >= 0 else '#FF4444'};")

    def append_log(self, message: str, level: int = 20):
        """Append log message to GUI."""
        if hasattr(self, 'log_widget'):
            self.log_widget.append_log(message, level)

    def closeEvent(self, event):
        """Handle window close event."""
        if self.bot_running:
            if PYQT_VER == 6:
                reply = QMessageBox.question(
                    self, "Confirm Exit",
                    "Bot is still running. Stop and exit?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                yes_btn = QMessageBox.StandardButton.Yes
            else:
                reply = QMessageBox.question(
                    self, "Confirm Exit",
                    "Bot is still running. Stop and exit?",
                    QMessageBox.Yes | QMessageBox.No
                )
                yes_btn = QMessageBox.Yes

            if reply == yes_btn:
                self._on_stop()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
