#!/usr/bin/env python3
"""MainWindow v2.0 — Full GUI for CryptoBot v10.0"""
import asyncio
import logging
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTabWidget, QTextEdit, QCheckBox,
    QSpinBox, QDoubleSpinBox, QGroupBox, QGridLayout, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
    QProgressBar, QFrame, QScrollArea, QFormLayout, QComboBox
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor

logger = logging.getLogger("CryptoBot")

class LogSignal(QObject):
    new_log = pyqtSignal(str)

class MainWindow(QMainWindow):
    def __init__(self, api_client, engine, settings):
        super().__init__()
        self.api_client = api_client
        self.engine = engine
        self.settings = settings
        self.setWindowTitle("CryptoBot v10.0 — Neural Adaptive Trading System")
        self.setMinimumSize(1400, 900)
        self._init_ui()
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_ui)
        self._timer.start(1500)
        logger.info("MainWindow initialized - CryptoBot v10.0")
        logger.info("=" * 60)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # ===== HEADER =====
        header_frame = QFrame()
        header_frame.setStyleSheet("background: #1a1a2e; border-radius: 8px; padding: 8px;")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)

        self.title_label = QLabel("🤖 CryptoBot v10.0")
        self.title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #00d4ff;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        self.status_badge = QLabel("● STOPPED")
        self.status_badge.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.status_badge.setStyleSheet("color: #e74c3c; padding: 4px 12px; background: #2d1f1f; border-radius: 12px;")
        header_layout.addWidget(self.status_badge)

        self.mode_badge = QLabel("PAPER")
        self.mode_badge.setFont(QFont("Segoe UI", 11))
        self.mode_badge.setStyleSheet("color: #f39c12; padding: 4px 12px; background: #2d2a1f; border-radius: 12px;")
        header_layout.addWidget(self.mode_badge)

        layout.addWidget(header_frame)

        # ===== STATS BAR =====
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background: #16213e; border-radius: 6px; padding: 6px;")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setSpacing(20)
        stats_layout.setContentsMargins(12, 6, 12, 6)

        self.stat_balance = self._create_stat_label("Balance", "--")
        self.stat_positions = self._create_stat_label("Positions", "0")
        self.stat_daily_pnl = self._create_stat_label("Daily PnL", "--")
        self.stat_winrate = self._create_stat_label("Win Rate", "--")
        self.stat_trades = self._create_stat_label("Trades", "0")
        self.stat_tier = self._create_stat_label("Tier", "--")
        self.stat_health = self._create_stat_label("Health", "OK")

        for lbl in [self.stat_balance, self.stat_positions, self.stat_daily_pnl,
                    self.stat_winrate, self.stat_trades, self.stat_tier, self.stat_health]:
            stats_layout.addWidget(lbl)
        stats_layout.addStretch()
        layout.addWidget(stats_frame)

        # ===== CONTROL BUTTONS =====
        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 4, 0, 4)

        self.start_btn = QPushButton("▶️  START ENGINE")
        self.start_btn.setStyleSheet("""
            QPushButton { background: #27ae60; color: white; font-size: 14px; font-weight: bold;
                          padding: 12px 24px; border-radius: 6px; }
            QPushButton:hover { background: #2ecc71; }
            QPushButton:disabled { background: #1e8449; }
        """)
        self.start_btn.clicked.connect(self._start_engine)
        btn_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹️  STOP ENGINE")
        self.stop_btn.setStyleSheet("""
            QPushButton { background: #e74c3c; color: white; font-size: 14px; font-weight: bold;
                          padding: 12px 24px; border-radius: 6px; }
            QPushButton:hover { background: #c0392b; }
            QPushButton:disabled { background: #922b21; }
        """)
        self.stop_btn.clicked.connect(self._stop_engine)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)

        self.scan_btn = QPushButton("🔍  MANUAL SCAN")
        self.scan_btn.setStyleSheet("""
            QPushButton { background: #3498db; color: white; font-size: 14px; font-weight: bold;
                          padding: 12px 24px; border-radius: 6px; }
            QPushButton:hover { background: #2980b9; }
        """)
        self.scan_btn.clicked.connect(self._manual_scan)
        btn_layout.addWidget(self.scan_btn)

        self.emergency_btn = QPushButton("🚨 CLOSE ALL")
        self.emergency_btn.setStyleSheet("""
            QPushButton { background: #8e44ad; color: white; font-size: 14px; font-weight: bold;
                          padding: 12px 24px; border-radius: 6px; }
            QPushButton:hover { background: #7d3c98; }
        """)
        self.emergency_btn.clicked.connect(self._emergency_close)
        btn_layout.addWidget(self.emergency_btn)

        btn_layout.addStretch()
        layout.addWidget(btn_frame)

        # ===== TABS =====
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #2c3e50; border-radius: 4px; background: #0f0f23; }
            QTabBar::tab { background: #1a1a2e; color: #8892b0; padding: 10px 20px; margin-right: 2px;
                           border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #0f0f23; color: #00d4ff; border-bottom: 2px solid #00d4ff; }
            QTabBar::tab:hover { background: #16213e; color: #ccd6f6; }
        """)
        layout.addWidget(self.tabs)

        # --- Tab 1: Dashboard (Logs) ---
        self._init_dashboard_tab()
        # --- Tab 2: Positions ---
        self._init_positions_tab()
        # --- Tab 3: Signals ---
        self._init_signals_tab()
        # --- Tab 4: Stats ---
        self._init_stats_tab()
        # --- Tab 5: Risk ---
        self._init_risk_tab()
        # --- Tab 6: Config ---
        self._init_config_tab()

        # Log handler
        self._setup_log_handler()

    def _create_stat_label(self, title, value):
        frame = QFrame()
        frame.setStyleSheet("background: transparent;")
        vlay = QVBoxLayout(frame)
        vlay.setSpacing(2)
        vlay.setContentsMargins(0, 0, 0, 0)
        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 9))
        title_lbl.setStyleSheet("color: #8892b0;")
        val_lbl = QLabel(value)
        val_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        val_lbl.setStyleSheet("color: #ccd6f6;")
        vlay.addWidget(title_lbl)
        vlay.addWidget(val_lbl)
        frame.title_lbl = title_lbl
        frame.val_lbl = val_lbl
        return frame

    def _init_dashboard_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit { background: #0a0a14; color: #a8b2d1; border: 1px solid #2c3e50;
                        border-radius: 4px; padding: 8px; }
        """)
        layout.addWidget(self.log_text)
        self.tabs.addTab(tab, "📊 Dashboard")

    def _init_positions_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        self.pos_table = QTableWidget()
        self.pos_table.setColumnCount(9)
        self.pos_table.setHorizontalHeaderLabels([
            "Symbol", "Side", "Entry", "Current", "Qty", "Lev", "PnL $", "PnL %", "SL / TP"
        ])
        self.pos_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.pos_table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.pos_table.setStyleSheet("""
            QTableWidget { background: #0a0a14; color: #ccd6f6; gridline-color: #2c3e50;
                           border: 1px solid #2c3e50; border-radius: 4px; }
            QHeaderView::section { background: #1a1a2e; color: #00d4ff; padding: 8px;
                                   border: 1px solid #2c3e50; font-weight: bold; }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:selected { background: #16213e; }
        """)
        self.pos_table.setAlternatingRowColors(True)
        layout.addWidget(self.pos_table)

        btn_layout = QHBoxLayout()
        self.refresh_pos_btn = QPushButton("🔄 Refresh Positions")
        self.refresh_pos_btn.clicked.connect(self._refresh_positions)
        btn_layout.addWidget(self.refresh_pos_btn)

        self.close_sel_btn = QPushButton("❌ Close Selected")
        self.close_sel_btn.clicked.connect(self._close_selected_position)
        btn_layout.addWidget(self.close_sel_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self.tabs.addTab(tab, "📈 Positions")

    def _init_signals_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        self.sig_table = QTableWidget()
        self.sig_table.setColumnCount(8)
        self.sig_table.setHorizontalHeaderLabels([
            "Symbol", "Direction", "Regime", "ADX", "ATR%", "RSI", "Signal", "MTF"
        ])
        self.sig_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sig_table.setStyleSheet(self.pos_table.styleSheet())
        self.sig_table.setAlternatingRowColors(True)
        layout.addWidget(self.sig_table)

        btn_layout = QHBoxLayout()
        self.refresh_sig_btn = QPushButton("🔄 Refresh Signals")
        self.refresh_sig_btn.clicked.connect(self._refresh_signals)
        btn_layout.addWidget(self.refresh_sig_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self.tabs.addTab(tab, "📡 Signals")

    def _init_stats_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Performance group
        perf_group = QGroupBox("📊 Performance")
        perf_group.setStyleSheet("QGroupBox { color: #00d4ff; font-weight: bold; font-size: 13px; }")
        perf_grid = QGridLayout(perf_group)
        self.stat_total_pnl = QLabel("Total PnL: --")
        self.stat_total_trades = QLabel("Total Trades: 0")
        self.stat_winning = QLabel("Winning: 0")
        self.stat_losing = QLabel("Losing: 0")
        self.stat_avg_pnl = QLabel("Avg PnL: --")
        self.stat_best_trade = QLabel("Best: --")
        self.stat_worst_trade = QLabel("Worst: --")
        for i, lbl in enumerate([self.stat_total_pnl, self.stat_total_trades, self.stat_winning,
                                  self.stat_losing, self.stat_avg_pnl, self.stat_best_trade, self.stat_worst_trade]):
            lbl.setFont(QFont("Segoe UI", 11))
            lbl.setStyleSheet("color: #ccd6f6; padding: 4px;")
            perf_grid.addWidget(lbl, i // 2, i % 2)
        scroll_layout.addWidget(perf_group)

        # Engine group
        engine_group = QGroupBox("⚙️ Engine")
        engine_group.setStyleSheet(perf_group.styleSheet())
        engine_grid = QGridLayout(engine_group)
        self.stat_uptime = QLabel("Uptime: --")
        self.stat_loops = QLabel("Loops: 0")
        self.stat_latency = QLabel("API Latency: --")
        self.stat_scan_interval = QLabel("Scan Interval: --")
        self.stat_last_error = QLabel("Last Error: --")
        self.stat_api_errors = QLabel("API Errors: 0")
        for i, lbl in enumerate([self.stat_uptime, self.stat_loops, self.stat_latency,
                                  self.stat_scan_interval, self.stat_last_error, self.stat_api_errors]):
            lbl.setFont(QFont("Segoe UI", 11))
            lbl.setStyleSheet("color: #ccd6f6; padding: 4px;")
            engine_grid.addWidget(lbl, i // 2, i % 2)
        scroll_layout.addWidget(engine_group)

        # Strategy group
        strat_group = QGroupBox("🧠 Strategy Engine")
        strat_group.setStyleSheet(perf_group.styleSheet())
        strat_grid = QGridLayout(strat_group)
        self.stat_best_strategy = QLabel("Best Strategy: --")
        self.stat_recent_wr = QLabel("Recent Win Rate: --")
        self.stat_strategies = QLabel("Strategies: --")
        for i, lbl in enumerate([self.stat_best_strategy, self.stat_recent_wr, self.stat_strategies]):
            lbl.setFont(QFont("Segoe UI", 11))
            lbl.setStyleSheet("color: #ccd6f6; padding: 4px;")
            strat_grid.addWidget(lbl, i, 0)
        scroll_layout.addWidget(strat_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        self.tabs.addTab(tab, "📉 Stats")

    def _init_risk_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        risk_group = QGroupBox("🛡️ Risk Metrics")
        risk_group.setStyleSheet("QGroupBox { color: #e74c3c; font-weight: bold; font-size: 13px; }")
        risk_grid = QGridLayout(risk_group)
        self.risk_daily_pnl = QLabel("Daily PnL: --")
        self.risk_daily_loss = QLabel("Daily Loss: --")
        self.risk_consecutive = QLabel("Consecutive Losses: 0")
        self.risk_exposure = QLabel("Risk Exposure: --")
        self.risk_max_pos = QLabel("Max Positions: --")
        self.risk_risk_per = QLabel("Risk/Trade: --")
        self.risk_circuit = QLabel("Circuit Breaker: OFF")
        for i, lbl in enumerate([self.risk_daily_pnl, self.risk_daily_loss, self.risk_consecutive,
                                  self.risk_exposure, self.risk_max_pos, self.risk_risk_per, self.risk_circuit]):
            lbl.setFont(QFont("Segoe UI", 11))
            lbl.setStyleSheet("color: #ccd6f6; padding: 4px;")
            risk_grid.addWidget(lbl, i // 2, i % 2)
        scroll_layout.addWidget(risk_group)

        scan_group = QGroupBox("🔍 Scan Stats")
        scan_group.setStyleSheet("QGroupBox { color: #f39c12; font-weight: bold; font-size: 13px; }")
        scan_grid = QGridLayout(scan_group)
        self.scan_total = QLabel("Total Scanned: 0")
        self.scan_passed = QLabel("Passed: 0")
        self.scan_empty = QLabel("Empty Streak: 0")
        self.scan_market = QLabel("Market Trend: --")
        for i, lbl in enumerate([self.scan_total, self.scan_passed, self.scan_empty, self.scan_market]):
            lbl.setFont(QFont("Segoe UI", 11))
            lbl.setStyleSheet("color: #ccd6f6; padding: 4px;")
            scan_grid.addWidget(lbl, i // 2, i % 2)
        scroll_layout.addWidget(scan_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        self.tabs.addTab(tab, "🛡️ Risk")

    def _init_config_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        form = QFormLayout(scroll_content)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # API
        api_group = QGroupBox("🔑 API Configuration")
        api_group.setStyleSheet("QGroupBox { color: #00d4ff; font-weight: bold; font-size: 13px; }")
        api_form = QFormLayout(api_group)
        self.api_key_input = QLineEdit(self.settings.get("api_key", ""))
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_secret_input = QLineEdit(self.settings.get("api_secret", ""))
        self.api_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_form.addRow("API Key:", self.api_key_input)
        api_form.addRow("API Secret:", self.api_secret_input)
        form.addRow(api_group)

        # Risk
        risk_group = QGroupBox("⚖️ Risk Settings")
        risk_group.setStyleSheet(api_group.styleSheet())
        risk_form = QFormLayout(risk_group)
        self.max_pos_spin = QSpinBox()
        self.max_pos_spin.setRange(1, 20)
        self.max_pos_spin.setValue(self.settings.get("max_positions", 3))
        self.risk_spin = QDoubleSpinBox()
        self.risk_spin.setRange(0.1, 10.0)
        self.risk_spin.setSingleStep(0.1)
        self.risk_spin.setValue(self.settings.get("max_risk_per_trade", 1.0))
        self.lev_spin = QSpinBox()
        self.lev_spin.setRange(1, 50)
        self.lev_spin.setValue(self.settings.get("max_leverage", 10))
        self.sl_spin = QDoubleSpinBox()
        self.sl_spin.setRange(0.1, 10.0)
        self.sl_spin.setSingleStep(0.1)
        self.sl_spin.setValue(self.settings.get("default_sl_pct", 1.5))
        self.tp_spin = QDoubleSpinBox()
        self.tp_spin.setRange(0.1, 20.0)
        self.tp_spin.setSingleStep(0.1)
        self.tp_spin.setValue(self.settings.get("default_tp_pct", 3.0))
        risk_form.addRow("Max Positions:", self.max_pos_spin)
        risk_form.addRow("Risk/Trade %:", self.risk_spin)
        risk_form.addRow("Max Leverage:", self.lev_spin)
        risk_form.addRow("Default SL %:", self.sl_spin)
        risk_form.addRow("Default TP %:", self.tp_spin)
        form.addRow(risk_group)

        # Trading
        trade_group = QGroupBox("📈 Trading Settings")
        trade_group.setStyleSheet(api_group.styleSheet())
        trade_form = QFormLayout(trade_group)
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(["1m", "5m", "15m", "30m", "1h", "4h"])
        self.timeframe_combo.setCurrentText(self.settings.get("timeframe", "15m"))
        self.scan_spin = QSpinBox()
        self.scan_spin.setRange(1, 60)
        self.scan_spin.setValue(self.settings.get("scan_interval_minutes", 5))
        self.hold_spin = QSpinBox()
        self.hold_spin.setRange(10, 1440)
        self.hold_spin.setValue(self.settings.get("max_hold_time_minutes", 240))
        trade_form.addRow("Timeframe:", self.timeframe_combo)
        trade_form.addRow("Scan Interval (min):", self.scan_spin)
        trade_form.addRow("Max Hold (min):", self.hold_spin)
        form.addRow(trade_group)

        # Features
        feat_group = QGroupBox("🔧 Features")
        feat_group.setStyleSheet(api_group.styleSheet())
        feat_form = QFormLayout(feat_group)
        self.demo_check = QCheckBox("Demo Mode (Paper Trading)")
        self.demo_check.setChecked(self.settings.get("demo_mode", True))
        self.demo_check.setStyleSheet("color: #ccd6f6;")
        self.trailing_check = QCheckBox("Trailing Stop")
        self.trailing_check.setChecked(self.settings.get("trailing_stop_enabled", True))
        self.trailing_check.setStyleSheet("color: #ccd6f6;")
        self.partial_check = QCheckBox("Partial Close")
        self.partial_check.setChecked(self.settings.get("partial_close_enabled", True))
        self.partial_check.setStyleSheet("color: #ccd6f6;")
        self.mtf_check = QCheckBox("Multi-Timeframe Analysis")
        self.mtf_check.setChecked(self.settings.get("use_multi_timeframe", True))
        self.mtf_check.setStyleSheet("color: #ccd6f6;")
        feat_form.addRow(self.demo_check)
        feat_form.addRow(self.trailing_check)
        feat_form.addRow(self.partial_check)
        feat_form.addRow(self.mtf_check)
        form.addRow(feat_group)

        save_btn = QPushButton("💾 Save All Settings")
        save_btn.setStyleSheet("""
            QPushButton { background: #2980b9; color: white; font-size: 14px; font-weight: bold;
                          padding: 12px; border-radius: 6px; }
            QPushButton:hover { background: #3498db; }
        """)
        save_btn.clicked.connect(self._save_settings)
        form.addRow(save_btn)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        self.tabs.addTab(tab, "⚙️ Config")

    def _setup_log_handler(self):
        class QTextEditHandler(logging.Handler):
            def __init__(self, widget):
                super().__init__()
                self.widget = widget
            def emit(self, record):
                msg = self.format(record)
                self.widget.append(msg)
                sb = self.widget.verticalScrollBar()
                sb.setValue(sb.maximum())
        handler = QTextEditHandler(self.log_text)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s | %(message)s", datefmt="%H:%M:%S"))
        logging.getLogger("CryptoBot").addHandler(handler)

    def _save_settings(self):
        self.settings.set("api_key", self.api_key_input.text().strip())
        self.settings.set("api_secret", self.api_secret_input.text().strip())
        self.settings.set("max_positions", self.max_pos_spin.value())
        self.settings.set("max_risk_per_trade", self.risk_spin.value())
        self.settings.set("max_leverage", self.lev_spin.value())
        self.settings.set("default_sl_pct", self.sl_spin.value())
        self.settings.set("default_tp_pct", self.tp_spin.value())
        self.settings.set("timeframe", self.timeframe_combo.currentText())
        self.settings.set("scan_interval_minutes", self.scan_spin.value())
        self.settings.set("max_hold_time_minutes", self.hold_spin.value())
        self.settings.set("demo_mode", self.demo_check.isChecked())
        self.settings.set("trailing_stop_enabled", self.trailing_check.isChecked())
        self.settings.set("partial_close_enabled", self.partial_check.isChecked())
        self.settings.set("use_multi_timeframe", self.mtf_check.isChecked())
        self.settings.save()
        self.api_client.update_credentials(
            self.api_key_input.text().strip(),
            self.api_secret_input.text().strip()
        )
        self.mode_badge.setText("PAPER" if self.demo_check.isChecked() else "LIVE")
        self.mode_badge.setStyleSheet(
            "color: #f39c12; padding: 4px 12px; background: #2d2a1f; border-radius: 12px;"
            if self.demo_check.isChecked() else
            "color: #e74c3c; padding: 4px 12px; background: #2d1f1f; border-radius: 12px;"
        )
        logger.info("Settings saved via GUI")
        QMessageBox.information(self, "Saved", "All settings saved successfully!")

    def _start_engine(self):
        if not self.engine.running:
            asyncio.create_task(self.engine.start())
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_badge.setText("● RUNNING")
            self.status_badge.setStyleSheet("color: #27ae60; padding: 4px 12px; background: #1f2d1f; border-radius: 12px;")
            logger.info("TradingEngine START requested by user")

    def _stop_engine(self):
        if self.engine.running:
            asyncio.create_task(self.engine.stop())
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_badge.setText("● STOPPED")
            self.status_badge.setStyleSheet("color: #e74c3c; padding: 4px 12px; background: #2d1f1f; border-radius: 12px;")
            logger.info("TradingEngine STOP requested by user")

    def _manual_scan(self):
        if not self.engine.running:
            logger.warning("Scan requested but engine not running")
            QMessageBox.warning(self, "Engine Not Running", "Start the engine first!")
            return
        logger.info("Manual scan initiated by user")

    def _emergency_close(self):
        reply = QMessageBox.question(self, "Emergency Close",
            "Close ALL open positions immediately?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            logger.warning("EMERGENCY CLOSE ALL requested by user")
            asyncio.create_task(self._do_emergency_close())

    async def _do_emergency_close(self):
        for sym, pos in list(self.engine.positions.items()):
            try:
                await self.engine.trade_executor.close_position_async(
                    sym, pos.side, pos.quantity,
                    "LONG" if pos.side.value == "BUY" else "SHORT"
                )
                logger.info(f"Emergency closed {sym}")
            except Exception as e:
                logger.error(f"Emergency close error {sym}: {e}")

    def _refresh_positions(self):
        self._update_positions_table()

    def _refresh_signals(self):
        self._update_signals_table()

    def _close_selected_position(self):
        row = self.pos_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a position to close")
            return
        symbol = self.pos_table.item(row, 0).text()
        pos = self.engine.positions.get(symbol)
        if pos:
            reply = QMessageBox.question(self, "Close Position",
                f"Close position {symbol}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                asyncio.create_task(self.engine.trade_executor.close_position_async(
                    symbol, pos.side, pos.quantity,
                    "LONG" if pos.side.value == "BUY" else "SHORT"
                ))
                logger.info(f"Manual close requested for {symbol}")

    def _update_ui(self):
        try:
            stats = self.engine.get_stats()
            balance = stats.get("balance", 0)
            pos_count = stats.get("positions_count", 0)
            daily_pnl = stats.get("daily_pnl", 0)
            win_rate = stats.get("win_rate", 0)
            total_trades = stats.get("total_trades", 0)
            health = stats.get("health_status", "OK")
            tier = stats.get("risk_stats", {}).get("balance_tier", "--")

            self.stat_balance.val_lbl.setText(f"${balance:.2f}")
            self.stat_balance.val_lbl.setStyleSheet("color: #27ae60;" if balance > 0 else "color: #e74c3c;")
            self.stat_positions.val_lbl.setText(str(pos_count))
            self.stat_daily_pnl.val_lbl.setText(f"{daily_pnl:+.2f}")
            self.stat_daily_pnl.val_lbl.setStyleSheet("color: #27ae60;" if daily_pnl >= 0 else "color: #e74c3c;")
            self.stat_winrate.val_lbl.setText(f"{win_rate:.1f}%")
            self.stat_trades.val_lbl.setText(str(total_trades))
            self.stat_tier.val_lbl.setText(tier.upper())
            self.stat_health.val_lbl.setText(health)
            self.stat_health.val_lbl.setStyleSheet("color: #27ae60;" if health == "OK" else "color: #e74c3c;")

            self._update_positions_table()
            self._update_signals_table()
            self._update_stats_tab(stats)
            self._update_risk_tab(stats)

            if not self.engine.running:
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
                self.status_badge.setText("● STOPPED")
                self.status_badge.setStyleSheet("color: #e74c3c; padding: 4px 12px; background: #2d1f1f; border-radius: 12px;")
        except Exception as e:
            pass

    def _update_positions_table(self):
        positions = self.engine.get_open_positions()
        self.pos_table.setRowCount(len(positions))
        for i, p in enumerate(positions):
            items = [
                p.get("symbol", ""),
                p.get("side", ""),
                f"{p.get('entry_price', 0):.6f}",
                f"{p.get('current_price', 0):.6f}",
                f"{p.get('quantity', 0):.6f}",
                f"{p.get('leverage', 1)}x",
                f"{p.get('unrealized_pnl', 0):+.4f}",
                f"{p.get('realized_pnl_percent', 0):+.2f}%",
                f"{p.get('stop_loss', 0):.4f} / {p.get('take_profit', 0):.4f}",
            ]
            for j, val in enumerate(items):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j == 6:  # PnL $
                    item.setForeground(QColor("#27ae60" if p.get('unrealized_pnl', 0) >= 0 else "#e74c3c"))
                if j == 1:  # Side
                    item.setForeground(QColor("#27ae60" if val == "BUY" else "#e74c3c"))
                self.pos_table.setItem(i, j, item)

    def _update_signals_table(self):
        signals = self.engine.get_last_scan_signals()
        self.sig_table.setRowCount(len(signals))
        for i, sig in enumerate(signals[:20]):
            ind = sig.get("indicators", {})
            items = [
                sig.get("symbol", ""),
                ind.get("signal_direction", "--"),
                ind.get("market_regime", "--"),
                f"{ind.get('adx', 0):.1f}",
                f"{ind.get('atr_percent', 0):.2f}%",
                f"{ind.get('rsi', 0):.1f}",
                f"{ind.get('signal_strength', 0):.2f}",
                f"{ind.get('mtf_agreement', 0):.1f}/{ind.get('mtf_total', 0)}",
            ]
            for j, val in enumerate(items):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j == 1:
                    item.setForeground(QColor("#27ae60" if val == "LONG" else "#e74c3c" if val == "SHORT" else "#8892b0"))
                self.sig_table.setItem(i, j, item)

    def _update_stats_tab(self, stats):
        total_pnl = stats.get("total_pnl", 0)
        self.stat_total_pnl.setText(f"Total PnL: {total_pnl:+.4f} USDT")
        self.stat_total_pnl.setStyleSheet(f"color: {'#27ae60' if total_pnl >= 0 else '#e74c3c'}; padding: 4px;")
        self.stat_total_trades.setText(f"Total Trades: {stats.get('total_trades', 0)}")
        self.stat_winning.setText(f"Winning: {stats.get('winning_trades', 0)}")
        self.stat_losing.setText(f"Losing: {stats.get('total_trades', 0) - stats.get('winning_trades', 0)}")
        self.stat_avg_pnl.setText(f"Avg PnL: {stats.get('total_pnl', 0) / max(stats.get('total_trades', 1), 1):+.4f}")

        closed = self.engine.get_closed_positions()
        if closed:
            pnls = [p.get("realized_pnl", 0) for p in closed]
            self.stat_best_trade.setText(f"Best: {max(pnls):+.4f}")
            self.stat_worst_trade.setText(f"Worst: {min(pnls):+.4f}")

        self.stat_uptime.setText(f"Uptime: {stats.get('uptime_seconds', 0) / 60:.1f} min")
        self.stat_loops.setText(f"Loops: {stats.get('loop_count', 0)}")
        self.stat_latency.setText(f"API Latency: {stats.get('api_latency_ms', 0):.0f} ms")
        self.stat_scan_interval.setText(f"Scan Interval: {stats.get('adaptive_interval', 0):.0f}s")
        self.stat_last_error.setText(f"Last Error: {stats.get('last_error', '--')}")
        self.stat_api_errors.setText(f"API Errors: {stats.get('api_health', {}).get('consecutive_errors', 0)}")

        strat = stats.get("strategy_stats", {})
        self.stat_best_strategy.setText(f"Best Strategy: {strat.get('best_strategy', '--')}")
        self.stat_recent_wr.setText(f"Recent Win Rate: {strat.get('recent_win_rate', 0):.1f}%")
        strategies = strat.get("strategies", {})
        self.stat_strategies.setText(f"Strategies tracked: {len(strategies)}")

    def _update_risk_tab(self, stats):
        risk = stats.get("risk_stats", {})
        self.risk_daily_pnl.setText(f"Daily PnL: {risk.get('daily_pnl', 0):+.4f}")
        self.risk_daily_pnl.setStyleSheet(f"color: {'#27ae60' if risk.get('daily_pnl', 0) >= 0 else '#e74c3c'}; padding: 4px;")
        self.risk_daily_loss.setText(f"Daily Loss: {risk.get('daily_loss', 0):.4f}")
        self.risk_consecutive.setText(f"Consecutive Losses: {risk.get('consecutive_losses', 0)}")
        self.risk_exposure.setText(f"Risk Exposure: {risk.get('total_risk_exposure', 0):.4f}")
        self.risk_max_pos.setText(f"Max Positions: {risk.get('max_positions', 0)}")
        self.risk_risk_per.setText(f"Risk/Trade: {risk.get('risk_per_trade', 0):.2f}%")

        rc = stats.get("risk_controller_stats", {})
        self.risk_circuit.setText(f"Circuit Breaker: {'ON' if rc.get('circuit_breaker') else 'OFF'}")
        self.risk_circuit.setStyleSheet(f"color: {'#e74c3c' if rc.get('circuit_breaker') else '#27ae60'}; padding: 4px;")

        scan = stats.get("scan_stats", {})
        self.scan_total.setText(f"Total Scanned: {scan.get('total', 0)}")
        self.scan_passed.setText(f"Passed: {scan.get('passed', 0)}")
        self.scan_empty.setText(f"Empty Streak: {scan.get('empty_streak', 0)}")
        self.scan_market.setText(f"Market Trend: {scan.get('market_trend', '--')}")
