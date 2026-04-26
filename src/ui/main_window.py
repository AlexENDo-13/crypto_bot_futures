"""
Main Window for CryptoBot v9.3 (COMPLETE FIX)
Full GUI with pages: Dashboard, Positions, Config, Logs, Stats
Fixed: All imports, all settings fields, full debug logging
"""
import logging
import sys
import asyncio
from datetime import datetime
from typing import Optional, List, Dict

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QTableWidget, QTableWidgetItem,
    QPlainTextEdit, QStatusBar, QMessageBox,
    QStackedWidget, QFrame, QLineEdit, QGroupBox, QFormLayout,
    QSpinBox, QDoubleSpinBox, QCheckBox, QScrollArea, QSplitter,
    QTabWidget, QTextEdit, QProgressBar, QHeaderView
)

from src.exchange.api_client import BingXAPIClient
from src.config.settings import Settings
from src.core.engine.trading_engine import TradingEngine


class GuiLogHandler(logging.Handler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s | %(message)s", "%H:%M:%S"))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.signal.emit(msg)
        except Exception:
            pass


class MainWindow(QMainWindow):
    log_signal = pyqtSignal(str)
    stats_signal = pyqtSignal(dict)

    def __init__(self, api_client: BingXAPIClient, engine: TradingEngine, settings: Settings):
        super().__init__()
        self.api_client = api_client
        self.engine = engine
        self.settings = settings
        self.logger = logging.getLogger("CryptoBot")
        self.setWindowTitle("CryptoBot v9.3 - Neural Adaptive Trading System")
        self.resize(1500, 950)

        self._init_ui()
        self._connect_signals()
        self._load_settings()

        # Update timers
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_stats)
        self.update_timer.start(2000)

        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.run_scan)
        self.scan_timer.start(60000)

        self.logger.info("=" * 60)
        self.logger.info("MainWindow initialized - CryptoBot v9.3")
        self.logger.info("=" * 60)

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Left sidebar ---
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("""
            QFrame { background-color: #1a1a2e; border-right: 2px solid #16213e; }
            QPushButton {
                background-color: transparent; color: #e94560; border: none;
                padding: 14px; text-align: left; font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background-color: #16213e; color: #fff; }
            QPushButton:checked { background-color: #0f3460; border-left: 4px solid #e94560; color: #fff; }
            QLabel { color: #a0a0a0; font-size: 11px; padding: 8px; }
        """)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 15, 0, 15)
        sidebar_layout.setSpacing(3)

        # Title
        title = QLabel("CRYPTO BOT")
        title.setStyleSheet("color: #e94560; font-size: 18px; font-weight: bold; padding: 10px;")
        sidebar_layout.addWidget(title)

        demo = self.settings.get("demo_mode", True)
        self.mode_label = QLabel("MODE: PAPER" if demo else "MODE: LIVE")
        self.mode_label.setStyleSheet(
            "color: #4ecca3; font-weight: bold; font-size: 12px;" if demo else "color: #ff6b6b; font-weight: bold; font-size: 12px;"
        )
        sidebar_layout.addWidget(self.mode_label)
        sidebar_layout.addSpacing(15)

        # Nav buttons
        self.nav_buttons = {}
        pages = [
            ("dashboard", "Dashboard"),
            ("positions", "Positions"),
            ("config", "Config"),
            ("logs", "Logs"),
            ("stats", "Stats"),
        ]
        for key, label in pages:
            btn = QPushButton(f"  {label}")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._switch_page(k))
            sidebar_layout.addWidget(btn)
            self.nav_buttons[key] = btn

        sidebar_layout.addStretch()

        # Control buttons
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("QFrame { background-color: #16213e; border-radius: 8px; margin: 5px; }")
        ctrl_layout = QVBoxLayout(ctrl_frame)
        ctrl_layout.setSpacing(8)

        self.engine_btn = QPushButton("▶ Start Engine")
        self.engine_btn.setStyleSheet("""
            QPushButton { color: #4ecca3; font-weight: bold; font-size: 13px; padding: 10px; }
            QPushButton:hover { background-color: #0f3460; }
        """)
        self.engine_btn.clicked.connect(self.toggle_engine)
        ctrl_layout.addWidget(self.engine_btn)

        self.scan_btn = QPushButton("🔍 Scan Now")
        self.scan_btn.setStyleSheet("""
            QPushButton { color: #74b9ff; font-weight: bold; font-size: 13px; padding: 10px; }
            QPushButton:hover { background-color: #0f3460; }
        """)
        self.scan_btn.clicked.connect(self.run_scan)
        ctrl_layout.addWidget(self.scan_btn)

        self.autopilot_btn = QPushButton("🤖 AutoPilot OFF")
        self.autopilot_btn.setCheckable(True)
        self.autopilot_btn.setStyleSheet("""
            QPushButton { color: #a0a0a0; font-weight: bold; font-size: 13px; padding: 10px; }
            QPushButton:checked { color: #fdcb6e; }
            QPushButton:hover { background-color: #0f3460; }
        """)
        self.autopilot_btn.clicked.connect(self.toggle_autopilot)
        ctrl_layout.addWidget(self.autopilot_btn)

        sidebar_layout.addWidget(ctrl_frame)

        sidebar_layout.addSpacing(10)
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #74b9ff; font-size: 12px;")
        sidebar_layout.addWidget(self.status_label)

        # Health indicator
        self.health_label = QLabel("● Health: OK")
        self.health_label.setStyleSheet("color: #4ecca3; font-size: 11px;")
        sidebar_layout.addWidget(self.health_label)

        main_layout.addWidget(sidebar)

        # --- Main content ---
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: #1a1a2e;")

        self.page_dashboard = self._create_dashboard_page()
        self.stack.addWidget(self.page_dashboard)

        self.page_positions = self._create_positions_page()
        self.stack.addWidget(self.page_positions)

        self.page_config = self._create_config_page()
        self.stack.addWidget(self.page_config)

        self.page_logs = self._create_logs_page()
        self.stack.addWidget(self.page_logs)

        self.page_stats = self._create_stats_page()
        self.stack.addWidget(self.page_stats)

        main_layout.addWidget(self.stack, stretch=1)
        self._switch_page("dashboard")
        self.nav_buttons["dashboard"].setChecked(True)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("CryptoBot v9.3 Ready | Waiting for start...")
        self.status_bar.setStyleSheet("background-color: #16213e; color: #a0a0a0;")

    def _create_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Stats cards
        cards_widget = QWidget()
        cards_layout = QHBoxLayout(cards_widget)
        cards_layout.setSpacing(15)

        self.dash_cards = {}
        card_data = [
            ("balance", "💰 Balance", "-- USDT", "#4ecca3"),
            ("pnl", "📈 Daily PnL", "--", "#74b9ff"),
            ("positions", "📊 Positions", "0", "#fdcb6e"),
            ("winrate", "🎯 Win Rate", "--%", "#e94560"),
            ("trades", "🔄 Trades", "0", "#a29bfe"),
            ("latency", "⚡ Latency", "-- ms", "#55efc4"),
        ]
        for key, title, default, color in card_data:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{ background-color: #16213e; border-radius: 12px; border: 1px solid #0f3460; }}
            """)
            card.setMinimumHeight(100)
            card_layout = QVBoxLayout(card)
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet("color: #a0a0a0; font-size: 12px;")
            card_layout.addWidget(title_lbl)
            val_lbl = QLabel(default)
            val_lbl.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold;")
            val_lbl.setObjectName(f"dash_val_{key}")
            card_layout.addWidget(val_lbl)
            cards_layout.addWidget(card)
            self.dash_cards[key] = val_lbl

        layout.addWidget(cards_widget)

        # Signals table
        signals_group = QGroupBox("Latest Signals")
        signals_group.setStyleSheet("""
            QGroupBox { color: #e94560; font-size: 14px; font-weight: bold; border: 1px solid #16213e; border-radius: 8px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)
        signals_layout = QVBoxLayout(signals_group)

        self.dash_signals_table = QTableWidget()
        self.dash_signals_table.setColumnCount(7)
        self.dash_signals_table.setHorizontalHeaderLabels(["Symbol", "Direction", "Strength", "ADX", "ATR%", "Price", "Time"])
        self.dash_signals_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dash_signals_table.setStyleSheet("""
            QTableWidget { background-color: #16213e; color: #fff; gridline-color: #0f3460; border: none; border-radius: 8px; }
            QHeaderView::section { background-color: #0f3460; color: #fff; padding: 8px; border: none; font-weight: bold; }
            QTableWidget::item { padding: 6px; }
        """)
        signals_layout.addWidget(self.dash_signals_table)
        layout.addWidget(signals_group)

        # Mini log
        log_group = QGroupBox("Live Log")
        log_group.setStyleSheet(signals_group.styleSheet())
        log_layout = QVBoxLayout(log_group)
        self.dash_log = QPlainTextEdit()
        self.dash_log.setReadOnly(True)
        self.dash_log.setMaximumBlockCount(200)
        self.dash_log.setStyleSheet("background-color: #0d1b2a; color: #a0a0a0; border-radius: 8px; padding: 5px;")
        log_layout.addWidget(self.dash_log)
        layout.addWidget(log_group)

        return page

    def _create_positions_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QHBoxLayout()
        title = QLabel("📋 Open Positions")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #e94560;")
        header.addWidget(title)

        self.btn_close_all = QPushButton("❌ Close All")
        self.btn_close_all.setEnabled(False)
        self.btn_close_all.setStyleSheet("""
            QPushButton { background-color: #e94560; color: #fff; padding: 8px 16px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #ff6b6b; }
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        self.btn_close_all.clicked.connect(self._close_all_positions)
        header.addWidget(self.btn_close_all)
        header.addStretch()
        layout.addLayout(header)

        self.pos_table = QTableWidget()
        self.pos_table.setColumnCount(9)
        self.pos_table.setHorizontalHeaderLabels([
            "Symbol", "Side", "Quantity", "Entry", "Mark", "Leverage", "PnL", "PnL %", "Action"
        ])
        self.pos_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.pos_table.setStyleSheet("""
            QTableWidget { background-color: #16213e; color: #fff; gridline-color: #0f3460; border: none; border-radius: 8px; }
            QHeaderView::section { background-color: #0f3460; color: #fff; padding: 8px; border: none; font-weight: bold; }
        """)
        layout.addWidget(self.pos_table)

        self.pos_status = QLabel("No open positions")
        self.pos_status.setStyleSheet("color: #a0a0a0; font-size: 13px;")
        layout.addWidget(self.pos_status)

        return page

    def _create_config_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #1a1a2e; border: none;")

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # === API Settings ===
        api_group = QGroupBox("🔑 API Settings")
        api_group.setStyleSheet(self._groupbox_style())
        api_layout = QFormLayout(api_group)
        api_layout.setSpacing(12)
        api_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cfg_api_key = QLineEdit()
        self.cfg_api_key.setPlaceholderText("Paste your BingX API Key here")
        self.cfg_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.cfg_api_key.setStyleSheet(self._input_style())
        api_layout.addRow("API Key:", self.cfg_api_key)

        self.cfg_api_secret = QLineEdit()
        self.cfg_api_secret.setPlaceholderText("Paste your BingX API Secret here")
        self.cfg_api_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.cfg_api_secret.setStyleSheet(self._input_style())
        api_layout.addRow("API Secret:", self.cfg_api_secret)

        self.cfg_demo = QCheckBox("Demo Mode (Paper Trading - no real money)")
        self.cfg_demo.setChecked(True)
        self.cfg_demo.setStyleSheet("color: #fff; spacing: 8px; font-size: 13px;")
        api_layout.addRow(self.cfg_demo)

        layout.addWidget(api_group)

        # === Trading Settings ===
        trade_group = QGroupBox("⚙️ Trading Settings")
        trade_group.setStyleSheet(self._groupbox_style())
        trade_layout = QFormLayout(trade_group)
        trade_layout.setSpacing(12)
        trade_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cfg_leverage = QSpinBox()
        self.cfg_leverage.setRange(1, 50)
        self.cfg_leverage.setValue(10)
        self.cfg_leverage.setStyleSheet(self._spinbox_style())
        trade_layout.addRow("Max Leverage:", self.cfg_leverage)

        self.cfg_positions = QSpinBox()
        self.cfg_positions.setRange(1, 20)
        self.cfg_positions.setValue(3)
        self.cfg_positions.setStyleSheet(self._spinbox_style())
        trade_layout.addRow("Max Positions:", self.cfg_positions)

        self.cfg_risk = QDoubleSpinBox()
        self.cfg_risk.setRange(0.1, 10.0)
        self.cfg_risk.setValue(1.0)
        self.cfg_risk.setSingleStep(0.5)
        self.cfg_risk.setDecimals(1)
        self.cfg_risk.setSuffix(" %")
        self.cfg_risk.setStyleSheet(self._spinbox_style())
        trade_layout.addRow("Risk per Trade:", self.cfg_risk)

        self.cfg_scan_interval = QSpinBox()
        self.cfg_scan_interval.setRange(1, 60)
        self.cfg_scan_interval.setValue(5)
        self.cfg_scan_interval.setSuffix(" min")
        self.cfg_scan_interval.setStyleSheet(self._spinbox_style())
        trade_layout.addRow("Scan Interval:", self.cfg_scan_interval)

        self.cfg_max_daily = QSpinBox()
        self.cfg_max_daily.setRange(1, 50)
        self.cfg_max_daily.setValue(15)
        self.cfg_max_daily.setStyleSheet(self._spinbox_style())
        trade_layout.addRow("Max Daily Trades:", self.cfg_max_daily)

        self.cfg_sl_pct = QDoubleSpinBox()
        self.cfg_sl_pct.setRange(0.1, 10.0)
        self.cfg_sl_pct.setValue(1.5)
        self.cfg_sl_pct.setSingleStep(0.1)
        self.cfg_sl_pct.setDecimals(1)
        self.cfg_sl_pct.setSuffix(" %")
        self.cfg_sl_pct.setStyleSheet(self._spinbox_style())
        trade_layout.addRow("Default Stop Loss:", self.cfg_sl_pct)

        self.cfg_tp_pct = QDoubleSpinBox()
        self.cfg_tp_pct.setRange(0.5, 20.0)
        self.cfg_tp_pct.setValue(3.0)
        self.cfg_tp_pct.setSingleStep(0.5)
        self.cfg_tp_pct.setDecimals(1)
        self.cfg_tp_pct.setSuffix(" %")
        self.cfg_tp_pct.setStyleSheet(self._spinbox_style())
        trade_layout.addRow("Default Take Profit:", self.cfg_tp_pct)

        self.cfg_trailing = QDoubleSpinBox()
        self.cfg_trailing.setRange(0.5, 10.0)
        self.cfg_trailing.setValue(2.0)
        self.cfg_trailing.setSingleStep(0.5)
        self.cfg_trailing.setDecimals(1)
        self.cfg_trailing.setSuffix(" %")
        self.cfg_trailing.setStyleSheet(self._spinbox_style())
        trade_layout.addRow("Trailing Stop Distance:", self.cfg_trailing)

        self.cfg_trailing_act = QDoubleSpinBox()
        self.cfg_trailing_act.setRange(0.5, 10.0)
        self.cfg_trailing_act.setValue(1.5)
        self.cfg_trailing_act.setSingleStep(0.5)
        self.cfg_trailing_act.setDecimals(1)
        self.cfg_trailing_act.setSuffix(" %")
        self.cfg_trailing_act.setStyleSheet(self._spinbox_style())
        trade_layout.addRow("Trailing Activation:", self.cfg_trailing_act)

        self.cfg_max_hold = QSpinBox()
        self.cfg_max_hold.setRange(30, 1440)
        self.cfg_max_hold.setValue(240)
        self.cfg_max_hold.setSuffix(" min")
        self.cfg_max_hold.setStyleSheet(self._spinbox_style())
        trade_layout.addRow("Max Hold Time:", self.cfg_max_hold)

        layout.addWidget(trade_group)

        # === Market Filters ===
        filter_group = QGroupBox("📊 Market Filters")
        filter_group.setStyleSheet(self._groupbox_style())
        filter_layout = QFormLayout(filter_group)
        filter_layout.setSpacing(12)
        filter_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cfg_min_adx = QDoubleSpinBox()
        self.cfg_min_adx.setRange(1.0, 50.0)
        self.cfg_min_adx.setValue(10.0)
        self.cfg_min_adx.setSingleStep(1.0)
        self.cfg_min_adx.setDecimals(1)
        self.cfg_min_adx.setStyleSheet(self._spinbox_style())
        filter_layout.addRow("Min ADX:", self.cfg_min_adx)

        self.cfg_min_atr = QDoubleSpinBox()
        self.cfg_min_atr.setRange(0.1, 5.0)
        self.cfg_min_atr.setValue(0.5)
        self.cfg_min_atr.setSingleStep(0.1)
        self.cfg_min_atr.setDecimals(1)
        self.cfg_min_atr.setSuffix(" %")
        self.cfg_min_atr.setStyleSheet(self._spinbox_style())
        filter_layout.addRow("Min ATR %:", self.cfg_min_atr)

        self.cfg_min_volume = QDoubleSpinBox()
        self.cfg_min_volume.setRange(1000, 10000000)
        self.cfg_min_volume.setValue(50000)
        self.cfg_min_volume.setSingleStep(10000)
        self.cfg_min_volume.setDecimals(0)
        self.cfg_min_volume.setSuffix(" USDT")
        self.cfg_min_volume.setStyleSheet(self._spinbox_style())
        filter_layout.addRow("Min Volume 24h:", self.cfg_min_volume)

        self.cfg_min_signal = QDoubleSpinBox()
        self.cfg_min_signal.setRange(0.05, 1.0)
        self.cfg_min_signal.setValue(0.25)
        self.cfg_min_signal.setSingleStep(0.05)
        self.cfg_min_signal.setDecimals(2)
        self.cfg_min_signal.setStyleSheet(self._spinbox_style())
        filter_layout.addRow("Min Signal Strength:", self.cfg_min_signal)

        self.cfg_max_spread = QDoubleSpinBox()
        self.cfg_max_spread.setRange(0.1, 5.0)
        self.cfg_max_spread.setValue(0.5)
        self.cfg_max_spread.setSingleStep(0.1)
        self.cfg_max_spread.setDecimals(1)
        self.cfg_max_spread.setSuffix(" %")
        self.cfg_max_spread.setStyleSheet(self._spinbox_style())
        filter_layout.addRow("Max Spread:", self.cfg_max_spread)

        self.cfg_max_funding = QDoubleSpinBox()
        self.cfg_max_funding.setRange(-1.0, 1.0)
        self.cfg_max_funding.setValue(0.0)
        self.cfg_max_funding.setSingleStep(0.01)
        self.cfg_max_funding.setDecimals(2)
        self.cfg_max_funding.setSuffix(" %")
        self.cfg_max_funding.setStyleSheet(self._spinbox_style())
        filter_layout.addRow("Max Funding Rate:", self.cfg_max_funding)

        self.cfg_use_mtf = QCheckBox("Use Multi-Timeframe Confirmation")
        self.cfg_use_mtf.setChecked(True)
        self.cfg_use_mtf.setStyleSheet("color: #fff; font-size: 13px;")
        filter_layout.addRow(self.cfg_use_mtf)

        self.cfg_use_spread = QCheckBox("Use Spread Filter")
        self.cfg_use_spread.setChecked(True)
        self.cfg_use_spread.setStyleSheet("color: #fff; font-size: 13px;")
        filter_layout.addRow(self.cfg_use_spread)

        self.cfg_use_trap = QCheckBox("Enable Trap Detection")
        self.cfg_use_trap.setChecked(True)
        self.cfg_use_trap.setStyleSheet("color: #fff; font-size: 13px;")
        filter_layout.addRow(self.cfg_use_trap)

        layout.addWidget(filter_group)

        # === Risk Management ===
        risk_group = QGroupBox("🛡️ Risk Management")
        risk_group.setStyleSheet(self._groupbox_style())
        risk_layout = QFormLayout(risk_group)
        risk_layout.setSpacing(12)
        risk_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cfg_daily_loss = QDoubleSpinBox()
        self.cfg_daily_loss.setRange(1.0, 50.0)
        self.cfg_daily_loss.setValue(8.0)
        self.cfg_daily_loss.setSingleStep(1.0)
        self.cfg_daily_loss.setDecimals(1)
        self.cfg_daily_loss.setSuffix(" %")
        self.cfg_daily_loss.setStyleSheet(self._spinbox_style())
        risk_layout.addRow("Daily Loss Limit:", self.cfg_daily_loss)

        self.cfg_max_total_risk = QDoubleSpinBox()
        self.cfg_max_total_risk.setRange(1.0, 50.0)
        self.cfg_max_total_risk.setValue(5.0)
        self.cfg_max_total_risk.setSingleStep(1.0)
        self.cfg_max_total_risk.setDecimals(1)
        self.cfg_max_total_risk.setSuffix(" %")
        self.cfg_max_total_risk.setStyleSheet(self._spinbox_style())
        risk_layout.addRow("Max Total Risk:", self.cfg_max_total_risk)

        self.cfg_anti_martingale = QCheckBox("Enable Anti-Martingale")
        self.cfg_anti_martingale.setChecked(True)
        self.cfg_anti_martingale.setStyleSheet("color: #fff; font-size: 13px;")
        risk_layout.addRow(self.cfg_anti_martingale)

        self.cfg_reduce_weekend = QCheckBox("Reduce Risk on Weekends")
        self.cfg_reduce_weekend.setChecked(True)
        self.cfg_reduce_weekend.setStyleSheet("color: #fff; font-size: 13px;")
        risk_layout.addRow(self.cfg_reduce_weekend)

        layout.addWidget(risk_group)

        # === Save Button ===
        self.btn_save = QPushButton("💾 Save All Settings")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #4ecca3; color: #1a1a2e;
                padding: 15px; border-radius: 8px; font-weight: bold; font-size: 15px;
            }
            QPushButton:hover { background-color: #6effc0; }
        """)
        self.btn_save.clicked.connect(self._save_settings)
        layout.addWidget(self.btn_save)
        layout.addStretch()

        scroll.setWidget(page)
        return scroll

    def _groupbox_style(self):
        return """
            QGroupBox { 
                color: #e94560; font-size: 14px; font-weight: bold; 
                border: 1px solid #16213e; border-radius: 10px; margin-top: 12px; padding-top: 12px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px; }
        """

    def _input_style(self):
        return """
            QLineEdit { 
                background-color: #16213e; color: #fff; padding: 10px; 
                border: 1px solid #0f3460; border-radius: 6px; font-size: 13px;
            }
            QLineEdit:focus { border: 2px solid #e94560; }
        """

    def _spinbox_style(self):
        return """
            QSpinBox, QDoubleSpinBox { 
                background-color: #16213e; color: #fff; padding: 8px; 
                border: 1px solid #0f3460; border-radius: 6px; font-size: 13px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus { border: 2px solid #e94560; }
        """

    def _create_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        control = QHBoxLayout()
        self.btn_clear_logs = QPushButton("🗑️ Clear")
        self.btn_clear_logs.setStyleSheet("""
            QPushButton { background-color: #e94560; color: #fff; padding: 8px 16px; border-radius: 6px; }
            QPushButton:hover { background-color: #ff6b6b; }
        """)
        self.btn_clear_logs.clicked.connect(self._clear_logs)
        control.addWidget(self.btn_clear_logs)

        self.combo_log_level = QComboBox()
        self.combo_log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.combo_log_level.setCurrentText("INFO")
        self.combo_log_level.setStyleSheet("background-color: #16213e; color: #fff; padding: 5px;")
        self.combo_log_level.currentTextChanged.connect(self._change_log_level)
        control.addWidget(QLabel("Log Level:"))
        control.addWidget(self.combo_log_level)

        self.btn_export_logs = QPushButton("📤 Export")
        self.btn_export_logs.setStyleSheet("""
            QPushButton { background-color: #74b9ff; color: #1a1a2e; padding: 8px 16px; border-radius: 6px; }
            QPushButton:hover { background-color: #a29bfe; }
        """)
        self.btn_export_logs.clicked.connect(self._export_logs)
        control.addWidget(self.btn_export_logs)

        control.addStretch()
        layout.addLayout(control)

        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setMaximumBlockCount(10000)
        self.log_viewer.setStyleSheet("background-color: #0d1b2a; color: #a0a0a0; border-radius: 8px; padding: 10px; font-family: Consolas, monospace;")
        layout.addWidget(self.log_viewer)

        return page

    def _create_stats_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("📈 Trading Statistics")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #e94560;")
        layout.addWidget(title)

        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setStyleSheet("""
            QTextEdit { background-color: #16213e; color: #fff; border-radius: 10px; padding: 15px; font-size: 13px; font-family: Consolas, monospace; }
        """)
        layout.addWidget(self.stats_text)

        return page

    def _switch_page(self, key: str):
        idx = {"dashboard": 0, "positions": 1, "config": 2, "logs": 3, "stats": 4}.get(key, 0)
        self.stack.setCurrentIndex(idx)
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)
        self.logger.debug(f"Switched to page: {key}")

    def _connect_signals(self):
        self.log_signal.connect(self._append_log)
        self.stats_signal.connect(self._update_ui_stats)
        gui_handler = GuiLogHandler(self.log_signal)
        gui_handler.setLevel(logging.DEBUG)
        logging.getLogger("CryptoBot").addHandler(gui_handler)
        self.logger.debug("GUI log handler connected")

    def _update_stats(self):
        if self.engine and self.engine.running:
            try:
                stats = self.engine.get_stats()
                self.stats_signal.emit(stats)
            except Exception as e:
                self.logger.debug(f"Stats update error: {e}")

    def _update_ui_stats(self, stats: dict):
        balance = stats.get("balance", 0)
        pnl = stats.get("daily_pnl", 0)
        positions = stats.get("positions_count", 0)
        win_rate = stats.get("win_rate", 0)
        total_trades = stats.get("total_trades", 0)
        latency = stats.get("api_latency_ms", 0)
        health = stats.get("health_status", "OK")

        # Update dashboard cards
        self.dash_cards["balance"].setText(f"{balance:.2f} USDT")
        self.dash_cards["pnl"].setText(f"{pnl:+.2f} USDT")
        self.dash_cards["positions"].setText(str(positions))
        self.dash_cards["winrate"].setText(f"{win_rate:.1f}%")
        self.dash_cards["trades"].setText(str(total_trades))
        self.dash_cards["latency"].setText(f"{latency:.0f} ms")

        self._update_positions_table()

        # Update health
        if "DEGRADED" in str(health):
            self.health_label.setText(f"● Health: {health}")
            self.health_label.setStyleSheet("color: #fdcb6e; font-size: 11px;")
        else:
            self.health_label.setText(f"● Health: {health}")
            self.health_label.setStyleSheet("color: #4ecca3; font-size: 11px;")

        self.status_bar.showMessage(
            f"Balance: {balance:.2f} USDT | Positions: {positions} | "
            f"Daily PnL: {pnl:.2f} | Win Rate: {win_rate:.1f}% | Health: {health}"
        )

        # Update stats page
        self._update_stats_page(stats)

    def _update_positions_table(self):
        try:
            open_pos = self.engine.get_open_positions()
            self.pos_table.setRowCount(len(open_pos))
            total_pnl = 0.0

            for row, pos in enumerate(open_pos):
                symbol = pos.get("symbol", "UNKNOWN")
                side = pos.get("side", "UNKNOWN")
                qty = float(pos.get("quantity", 0))
                entry = float(pos.get("entry_price", 0))
                mark = float(pos.get("current_price", entry))
                leverage = int(pos.get("leverage", 1))

                if side.upper() in ("LONG", "BUY"):
                    pnl = (mark - entry) * qty * leverage
                else:
                    pnl = (entry - mark) * qty * leverage

                pnl_pct = (pnl / (entry * qty) * 100) if entry > 0 and qty > 0 else 0
                total_pnl += pnl

                items = [symbol, side, f"{qty:.6f}", f"{entry:.4f}", f"{mark:.4f}",
                         str(leverage), f"{pnl:+.2f}", f"{pnl_pct:+.2f}%", "Close"]
                for col, text in enumerate(items):
                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col == 6 and pnl > 0:
                        item.setForeground(Qt.GlobalColor.green)
                    elif col == 6 and pnl < 0:
                        item.setForeground(Qt.GlobalColor.red)
                    self.pos_table.setItem(row, col, item)

                btn = QPushButton("❌")
                btn.setMaximumWidth(40)
                btn.setStyleSheet("background-color: #e94560; color: #fff; border-radius: 4px;")
                btn.clicked.connect(lambda checked, s=symbol: self._close_position(s))
                self.pos_table.setCellWidget(row, 8, btn)

            if open_pos:
                self.pos_status.setText(f"Active Positions: {len(open_pos)} | Total Unrealized PnL: {total_pnl:+.2f} USDT")
                self.pos_status.setStyleSheet("color: #fff; font-size: 13px;")
                self.btn_close_all.setEnabled(True)
            else:
                self.pos_status.setText("No open positions")
                self.pos_status.setStyleSheet("color: #a0a0a0; font-size: 13px;")
                self.btn_close_all.setEnabled(False)
        except Exception as e:
            self.logger.debug(f"Positions update error: {e}")

    def _update_stats_page(self, stats: dict):
        try:
            text = f"""
╔══════════════════════════════════════════════════════════════╗
║                    TRADING STATISTICS                        ║
╠══════════════════════════════════════════════════════════════╣
  Balance:           {stats.get('balance', 0):.2f} USDT
  Start Balance:     {stats.get('start_balance', 0):.2f} USDT
  Daily PnL:         {stats.get('daily_pnl', 0):+.2f} USDT
  Weekly PnL:        {stats.get('weekly_pnl', 0):+.2f} USDT
  Total PnL:         {stats.get('total_pnl', 0):+.2f} USDT

  Total Trades:      {stats.get('total_trades', 0)}
  Winning Trades:    {stats.get('winning_trades', 0)}
  Win Rate:          {stats.get('win_rate', 0):.1f}%

  Open Positions:    {stats.get('positions_count', 0)}
  API Latency:       {stats.get('api_latency_ms', 0):.0f} ms
  Health Status:     {stats.get('health_status', 'OK')}
  Uptime:            {stats.get('uptime_seconds', 0):.0f} seconds

  Scan Results:      {stats.get('scan_result_count', 0)} signals
  Adaptive Interval: {stats.get('adaptive_interval', 0):.0f} seconds
╚══════════════════════════════════════════════════════════════╝
"""
            self.stats_text.setText(text)
        except Exception as e:
            self.logger.debug(f"Stats page update error: {e}")

    def _close_position(self, symbol: str):
        reply = QMessageBox.question(self, "Close Position", f"Close {symbol}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.logger.info(f"User requested close position: {symbol}")
            async def do_close():
                try:
                    pos = self.engine.positions.get(symbol)
                    if pos:
                        result = await self.engine.trade_executor.close_position_async(symbol, pos.side, pos.quantity)
                        if result:
                            self.logger.info(f"Position {symbol} closed successfully")
                        else:
                            self.logger.error(f"Failed to close position {symbol}")
                except Exception as e:
                    self.logger.error(f"Close error {symbol}: {e}")
            asyncio.create_task(do_close())

    def _close_all_positions(self):
        reply = QMessageBox.question(self, "Close All", "Close ALL positions?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.logger.info("User requested close ALL positions")
            async def do_close_all():
                try:
                    for symbol, pos in list(self.engine.positions.items()):
                        await self.engine.trade_executor.close_position_async(symbol, pos.side, pos.quantity)
                    self.logger.info("All positions closed")
                except Exception as e:
                    self.logger.error(f"Close all error: {e}")
            asyncio.create_task(do_close_all())

    def _load_settings(self):
        try:
            self.cfg_api_key.setText(self.settings.get("api_key", ""))
            self.cfg_api_secret.setText(self.settings.get("api_secret", ""))
            self.cfg_demo.setChecked(self.settings.get("demo_mode", True))
            self.cfg_leverage.setValue(self.settings.get("max_leverage", 10))
            self.cfg_positions.setValue(self.settings.get("max_positions", 3))
            self.cfg_risk.setValue(self.settings.get("max_risk_per_trade", 1.0))
            self.cfg_scan_interval.setValue(self.settings.get("scan_interval_minutes", 5))
            self.cfg_max_daily.setValue(self.settings.get("max_daily_trades", 15))
            self.cfg_sl_pct.setValue(self.settings.get("default_sl_pct", 1.5))
            self.cfg_tp_pct.setValue(self.settings.get("default_tp_pct", 3.0))
            self.cfg_trailing.setValue(self.settings.get("trailing_stop_distance_percent", 2.0))
            self.cfg_trailing_act.setValue(self.settings.get("trailing_activation", 1.5))
            self.cfg_max_hold.setValue(self.settings.get("max_hold_time_minutes", 240))
            self.cfg_min_adx.setValue(self.settings.get("min_adx", 10.0))
            self.cfg_min_atr.setValue(self.settings.get("min_atr_percent", 0.5))
            self.cfg_min_volume.setValue(self.settings.get("min_volume_24h_usdt", 50000))
            self.cfg_min_signal.setValue(self.settings.get("min_signal_strength", 0.25))
            self.cfg_max_spread.setValue(self.settings.get("max_spread_percent", 0.5))
            self.cfg_max_funding.setValue(self.settings.get("max_funding_rate", 0.0))
            self.cfg_use_mtf.setChecked(self.settings.get("use_multi_timeframe", True))
            self.cfg_use_spread.setChecked(self.settings.get("use_spread_filter", True))
            self.cfg_use_trap.setChecked(self.settings.get("trap_detector_enabled", True))
            self.cfg_daily_loss.setValue(self.settings.get("daily_loss_limit_percent", 8.0))
            self.cfg_max_total_risk.setValue(self.settings.get("max_total_risk_percent", 5.0))
            self.cfg_anti_martingale.setChecked(self.settings.get("anti_martingale_enabled", True))
            self.cfg_reduce_weekend.setChecked(self.settings.get("reduce_risk_on_weekends", True))
            self.logger.debug("Settings loaded into UI")
        except Exception as e:
            self.logger.error(f"Load settings error: {e}")

    def _save_settings(self):
        try:
            api_key = self.cfg_api_key.text().strip()
            api_secret = self.cfg_api_secret.text().strip()

            updates = {
                "api_key": api_key,
                "api_secret": api_secret,
                "demo_mode": self.cfg_demo.isChecked(),
                "max_leverage": self.cfg_leverage.value(),
                "max_positions": self.cfg_positions.value(),
                "max_risk_per_trade": self.cfg_risk.value(),
                "scan_interval_minutes": self.cfg_scan_interval.value(),
                "max_daily_trades": self.cfg_max_daily.value(),
                "default_sl_pct": self.cfg_sl_pct.value(),
                "default_tp_pct": self.cfg_tp_pct.value(),
                "trailing_stop_distance_percent": self.cfg_trailing.value(),
                "trailing_activation": self.cfg_trailing_act.value(),
                "max_hold_time_minutes": self.cfg_max_hold.value(),
                "min_adx": self.cfg_min_adx.value(),
                "min_atr_percent": self.cfg_min_atr.value(),
                "min_volume_24h_usdt": self.cfg_min_volume.value(),
                "min_signal_strength": self.cfg_min_signal.value(),
                "max_spread_percent": self.cfg_max_spread.value(),
                "max_funding_rate": self.cfg_max_funding.value(),
                "use_multi_timeframe": self.cfg_use_mtf.isChecked(),
                "use_spread_filter": self.cfg_use_spread.isChecked(),
                "trap_detector_enabled": self.cfg_use_trap.isChecked(),
                "daily_loss_limit_percent": self.cfg_daily_loss.value(),
                "max_total_risk_percent": self.cfg_max_total_risk.value(),
                "anti_martingale_enabled": self.cfg_anti_martingale.isChecked(),
                "reduce_risk_on_weekends": self.cfg_reduce_weekend.isChecked(),
            }
            self.settings.update(updates)
            self.api_client.update_credentials(api_key, api_secret)

            demo = self.cfg_demo.isChecked()
            self.mode_label.setText("MODE: PAPER" if demo else "MODE: LIVE")
            self.mode_label.setStyleSheet(
                "color: #4ecca3; font-weight: bold; font-size: 12px;" if demo else "color: #ff6b6b; font-weight: bold; font-size: 12px;"
            )

            self.logger.info("Settings saved via GUI")
            QMessageBox.information(self, "Saved", "All settings saved successfully!\\nAPI credentials updated.")
        except Exception as e:
            self.logger.error(f"Save settings error: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

    def _clear_logs(self):
        self.log_viewer.clear()
        self.dash_log.clear()
        self.logger.debug("Logs cleared by user")

    def _change_log_level(self, level: str):
        level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING,
                     "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL}
        new_level = level_map.get(level, logging.INFO)
        logging.getLogger("CryptoBot").setLevel(new_level)
        self.logger.info(f"Log level changed to {level}")

    def _export_logs(self):
        try:
            from PyQt6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(self, "Export Logs", "bot_logs.txt", "Text Files (*.txt)")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.log_viewer.toPlainText())
                self.logger.info(f"Logs exported to {path}")
                QMessageBox.information(self, "Exported", f"Logs saved to {path}")
        except Exception as e:
            self.logger.error(f"Export logs error: {e}")

    def run_scan(self):
        self.status_label.setText("🔍 Scanning...")
        self.scan_btn.setEnabled(False)
        self.logger.info("Manual scan initiated by user")
        if self.engine and self.engine.running:
            async def do_scan():
                try:
                    await self.engine._scan_and_trade()
                    signals = self.engine.get_last_scan_signals()
                    self._update_signals_table(signals)
                    self.status_label.setText(f"✅ Signals: {len(signals)}")
                    self.logger.info(f"Scan complete: {len(signals)} signals found")
                except Exception as e:
                    self.logger.error(f"Scan error: {e}")
                    self.status_label.setText("❌ Scan failed")
                finally:
                    self.scan_btn.setEnabled(True)
            asyncio.create_task(do_scan())
        else:
            self.status_label.setText("⚠️ Engine not running")
            self.scan_btn.setEnabled(True)
            self.logger.warning("Scan requested but engine not running")

    def _update_signals_table(self, signals):
        self.dash_signals_table.setRowCount(0)
        if not signals:
            return
        self.dash_signals_table.setRowCount(len(signals))
        for row, sig in enumerate(signals):
            symbol = sig.get("symbol", "?")
            indicators = sig.get("indicators", {})
            direction = indicators.get("signal_direction", "?")
            score = indicators.get("signal_strength", 0)
            adx = indicators.get("adx", 0)
            atr_pct = indicators.get("atr_percent", 0)
            price = indicators.get("close_price", 0.0)
            time_str = datetime.now().strftime("%H:%M:%S")

            items = [
                QTableWidgetItem(symbol),
                QTableWidgetItem(direction),
                QTableWidgetItem(f"{score:.2f}"),
                QTableWidgetItem(f"{adx:.1f}"),
                QTableWidgetItem(f"{atr_pct:.2f}%"),
                QTableWidgetItem(f"{price:.4f}"),
                QTableWidgetItem(time_str),
            ]
            for col, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 1:
                    if direction == "LONG":
                        item.setForeground(Qt.GlobalColor.green)
                    elif direction == "SHORT":
                        item.setForeground(Qt.GlobalColor.red)
                self.dash_signals_table.setItem(row, col, item)

    def toggle_engine(self):
        if not self.engine.running:
            self.engine_btn.setText("⏹ Stop Engine")
            self.engine_btn.setStyleSheet("color: #ff6b6b; font-weight: bold; font-size: 13px; padding: 10px;")
            self.status_label.setText("🚀 Starting...")
            self.logger.info("TradingEngine START requested by user")
            async def start_engine():
                try:
                    await self.engine.start()
                    self.status_label.setText("✅ Engine running")
                    self.logger.info("TradingEngine started successfully")
                except Exception as e:
                    self.logger.error(f"Engine start error: {e}")
                    self.status_label.setText("❌ Start failed")
                    self.engine_btn.setText("▶ Start Engine")
                    self.engine_btn.setStyleSheet("color: #4ecca3; font-weight: bold; font-size: 13px; padding: 10px;")
            asyncio.create_task(start_engine())
        else:
            self.engine_btn.setText("▶ Start Engine")
            self.engine_btn.setStyleSheet("color: #4ecca3; font-weight: bold; font-size: 13px; padding: 10px;")
            self.status_label.setText("🛑 Stopping...")
            self.logger.info("TradingEngine STOP requested by user")
            async def stop_engine():
                try:
                    await self.engine.stop()
                    self.status_label.setText("⏹ Engine stopped")
                    self.logger.info("TradingEngine stopped")
                except Exception as e:
                    self.logger.error(f"Engine stop error: {e}")
            asyncio.create_task(stop_engine())

    def toggle_autopilot(self):
        checked = self.autopilot_btn.isChecked()
        self.autopilot_btn.setText("🤖 AutoPilot ON" if checked else "🤖 AutoPilot OFF")
        status = "ACTIVE" if checked else "STANDBY"
        self.logger.info(f"AutoPilot {status}")

    def _append_log(self, text: str):
        self.log_viewer.appendPlainText(text)
        self.dash_log.appendPlainText(text)
        scrollbar = self.log_viewer.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        self.logger.info("Window closing - shutting down...")
        self.update_timer.stop()
        self.scan_timer.stop()
        event.accept()
