"""
Main Window for CryptoBot v9.3 (FIXED)
Full GUI with pages: Dashboard, Positions, Config, Logs
Fixed: Config page fields, API key input, settings save/load
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
    QPlainTextEdit, QSplitter, QStatusBar, QMessageBox,
    QStackedWidget, QFrame, QLineEdit, QGroupBox, QFormLayout,
    QSpinBox, QDoubleSpinBox, QCheckBox, QScrollArea
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
        self.setWindowTitle("CryptoBot v9.3 - Neural Adaptive GUI [FIXED]")
        self.resize(1400, 900)

        self._init_ui()
        self._connect_signals()
        self._load_settings()

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_stats)
        self.update_timer.start(2000)

        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.run_scan)
        self.scan_timer.start(60000)

        self.logger.info("MainWindow initialized with TradingEngine v9.3")

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Left sidebar ---
        sidebar = QFrame()
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet("""
            QFrame { background-color: #1e1e2e; border-right: 1px solid #313244; }
            QPushButton {
                background-color: transparent; color: #cdd6f4; border: none;
                padding: 12px; text-align: left; font-size: 13px;
            }
            QPushButton:hover { background-color: #313244; }
            QPushButton:checked { background-color: #45475a; border-left: 3px solid #89b4fa; }
            QLabel { color: #6c7086; font-size: 10px; padding: 8px; }
        """)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 10, 0, 10)
        sidebar_layout.setSpacing(2)

        demo = self.settings.get("demo_mode", True)
        self.mode_label = QLabel("MODE: PAPER" if demo else "MODE: LIVE")
        self.mode_label.setStyleSheet(
            "color: #a6e3a1; font-weight: bold;" if demo else "color: #f38ba8; font-weight: bold;"
        )
        sidebar_layout.addWidget(self.mode_label)
        sidebar_layout.addSpacing(10)

        self.nav_buttons = {}
        pages = [
            ("dashboard", "Dashboard"),
            ("positions", "Positions"),
            ("config", "Config"),
            ("logs", "Logs"),
        ]
        for key, label in pages:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._switch_page(k))
            sidebar_layout.addWidget(btn)
            self.nav_buttons[key] = btn

        sidebar_layout.addStretch()

        self.engine_btn = QPushButton("Start Engine")
        self.engine_btn.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        self.engine_btn.clicked.connect(self.toggle_engine)
        sidebar_layout.addWidget(self.engine_btn)

        self.scan_btn = QPushButton("Scan Now")
        self.scan_btn.clicked.connect(self.run_scan)
        sidebar_layout.addWidget(self.scan_btn)

        self.autopilot_btn = QPushButton("AutoPilot OFF")
        self.autopilot_btn.setCheckable(True)
        self.autopilot_btn.clicked.connect(self.toggle_autopilot)
        sidebar_layout.addWidget(self.autopilot_btn)

        sidebar_layout.addSpacing(10)
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #89b4fa;")
        sidebar_layout.addWidget(self.status_label)

        main_layout.addWidget(sidebar)

        # --- Main content ---
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: #1e1e2e;")

        self.page_dashboard = self._create_dashboard_page()
        self.stack.addWidget(self.page_dashboard)

        self.page_positions = self._create_positions_page()
        self.stack.addWidget(self.page_positions)

        self.page_config = self._create_config_page()
        self.stack.addWidget(self.page_config)

        self.page_logs = self._create_logs_page()
        self.stack.addWidget(self.page_logs)

        main_layout.addWidget(self.stack, stretch=1)
        self._switch_page("dashboard")
        self.nav_buttons["dashboard"].setChecked(True)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("CryptoBot v9.3 Ready")

    def _create_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        cards = QHBoxLayout()
        self.dash_balance = QLabel("Balance: --")
        self.dash_pnl = QLabel("Daily PnL: --")
        self.dash_positions = QLabel("Positions: 0")
        self.dash_winrate = QLabel("Win Rate: --")
        for lbl in [self.dash_balance, self.dash_pnl, self.dash_positions, self.dash_winrate]:
            lbl.setStyleSheet("""
                QLabel {
                    background-color: #313244; color: #cdd6f4;
                    padding: 15px; border-radius: 8px; font-size: 14px;
                }
            """)
            cards.addWidget(lbl)
        layout.addLayout(cards)

        self.dash_signals_table = QTableWidget()
        self.dash_signals_table.setColumnCount(5)
        self.dash_signals_table.setHorizontalHeaderLabels(["Symbol", "Direction", "Strength", "Price", "Time"])
        self.dash_signals_table.setStyleSheet("""
            QTableWidget { background-color: #181825; color: #cdd6f4; gridline-color: #313244; border: none; }
            QHeaderView::section { background-color: #313244; color: #cdd6f4; padding: 6px; border: none; }
        """)
        layout.addWidget(self.dash_signals_table)

        self.dash_log = QPlainTextEdit()
        self.dash_log.setReadOnly(True)
        self.dash_log.setMaximumBlockCount(100)
        self.dash_log.setStyleSheet("background-color: #11111b; color: #a6adc8;")
        layout.addWidget(self.dash_log)

        return page

    def _create_positions_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        header = QHBoxLayout()
        title = QLabel("Open Positions")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #cdd6f4;")
        header.addWidget(title)

        self.btn_close_all = QPushButton("Close All")
        self.btn_close_all.setEnabled(False)
        self.btn_close_all.setStyleSheet("""
            QPushButton { background-color: #f38ba8; color: #1e1e2e; padding: 6px 12px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #eba0ac; }
        """)
        self.btn_close_all.clicked.connect(self._close_all_positions)
        header.addWidget(self.btn_close_all)
        header.addStretch()
        layout.addLayout(header)

        self.pos_table = QTableWidget()
        self.pos_table.setColumnCount(8)
        self.pos_table.setHorizontalHeaderLabels([
            "Symbol", "Side", "Quantity", "Entry Price", "Mark Price", "PnL", "PnL %", "Actions"
        ])
        self.pos_table.setStyleSheet("""
            QTableWidget { background-color: #181825; color: #cdd6f4; gridline-color: #313244; border: none; }
            QHeaderView::section { background-color: #313244; color: #cdd6f4; padding: 6px; border: none; }
        """)
        layout.addWidget(self.pos_table)

        self.pos_status = QLabel("No open positions")
        self.pos_status.setStyleSheet("color: #6c7086;")
        layout.addWidget(self.pos_status)

        return page

    def _create_config_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #1e1e2e; border: none;")

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # === API Settings ===
        api_group = QGroupBox("API Settings")
        api_group.setStyleSheet("""
            QGroupBox { 
                color: #cdd6f4; font-size: 14px; font-weight: bold; 
                border: 1px solid #313244; border-radius: 8px; margin-top: 10px; padding-top: 10px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)
        api_layout = QFormLayout(api_group)
        api_layout.setSpacing(10)

        self.cfg_api_key = QLineEdit()
        self.cfg_api_key.setPlaceholderText("Paste BingX API Key here")
        self.cfg_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.cfg_api_key.setStyleSheet("""
            QLineEdit { background-color: #181825; color: #cdd6f4; padding: 8px; border: 1px solid #313244; border-radius: 4px; }
            QLineEdit:focus { border: 1px solid #89b4fa; }
        """)
        api_layout.addRow("API Key:", self.cfg_api_key)

        self.cfg_api_secret = QLineEdit()
        self.cfg_api_secret.setPlaceholderText("Paste BingX API Secret here")
        self.cfg_api_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.cfg_api_secret.setStyleSheet("""
            QLineEdit { background-color: #181825; color: #cdd6f4; padding: 8px; border: 1px solid #313244; border-radius: 4px; }
            QLineEdit:focus { border: 1px solid #89b4fa; }
        """)
        api_layout.addRow("API Secret:", self.cfg_api_secret)

        self.cfg_demo = QCheckBox("Demo Mode (Paper Trading)")
        self.cfg_demo.setChecked(True)
        self.cfg_demo.setStyleSheet("color: #cdd6f4; spacing: 8px;")
        api_layout.addRow(self.cfg_demo)

        layout.addWidget(api_group)

        # === Trading Settings ===
        trade_group = QGroupBox("Trading Settings")
        trade_group.setStyleSheet(api_group.styleSheet())
        trade_layout = QFormLayout(trade_group)
        trade_layout.setSpacing(10)

        self.cfg_leverage = QSpinBox()
        self.cfg_leverage.setRange(1, 50)
        self.cfg_leverage.setValue(10)
        self.cfg_leverage.setStyleSheet("color: #cdd6f4; background-color: #181825;")
        trade_layout.addRow("Max Leverage:", self.cfg_leverage)

        self.cfg_positions = QSpinBox()
        self.cfg_positions.setRange(1, 20)
        self.cfg_positions.setValue(3)
        self.cfg_positions.setStyleSheet("color: #cdd6f4; background-color: #181825;")
        trade_layout.addRow("Max Positions:", self.cfg_positions)

        self.cfg_risk = QDoubleSpinBox()
        self.cfg_risk.setRange(0.1, 10.0)
        self.cfg_risk.setValue(1.0)
        self.cfg_risk.setSingleStep(0.5)
        self.cfg_risk.setDecimals(1)
        self.cfg_risk.setSuffix(" %")
        self.cfg_risk.setStyleSheet("color: #cdd6f4; background-color: #181825;")
        trade_layout.addRow("Risk per Trade:", self.cfg_risk)

        self.cfg_scan_interval = QSpinBox()
        self.cfg_scan_interval.setRange(1, 60)
        self.cfg_scan_interval.setValue(5)
        self.cfg_scan_interval.setSuffix(" min")
        self.cfg_scan_interval.setStyleSheet("color: #cdd6f4; background-color: #181825;")
        trade_layout.addRow("Scan Interval:", self.cfg_scan_interval)

        self.cfg_max_daily = QSpinBox()
        self.cfg_max_daily.setRange(1, 50)
        self.cfg_max_daily.setValue(15)
        self.cfg_max_daily.setStyleSheet("color: #cdd6f4; background-color: #181825;")
        trade_layout.addRow("Max Daily Trades:", self.cfg_max_daily)

        self.cfg_sl_pct = QDoubleSpinBox()
        self.cfg_sl_pct.setRange(0.1, 10.0)
        self.cfg_sl_pct.setValue(1.5)
        self.cfg_sl_pct.setSingleStep(0.1)
        self.cfg_sl_pct.setDecimals(1)
        self.cfg_sl_pct.setSuffix(" %")
        self.cfg_sl_pct.setStyleSheet("color: #cdd6f4; background-color: #181825;")
        trade_layout.addRow("Default SL %:", self.cfg_sl_pct)

        self.cfg_tp_pct = QDoubleSpinBox()
        self.cfg_tp_pct.setRange(0.5, 20.0)
        self.cfg_tp_pct.setValue(3.0)
        self.cfg_tp_pct.setSingleStep(0.5)
        self.cfg_tp_pct.setDecimals(1)
        self.cfg_tp_pct.setSuffix(" %")
        self.cfg_tp_pct.setStyleSheet("color: #cdd6f4; background-color: #181825;")
        trade_layout.addRow("Default TP %:", self.cfg_tp_pct)

        layout.addWidget(trade_group)

        # === Filters ===
        filter_group = QGroupBox("Market Filters")
        filter_group.setStyleSheet(api_group.styleSheet())
        filter_layout = QFormLayout(filter_group)
        filter_layout.setSpacing(10)

        self.cfg_min_adx = QDoubleSpinBox()
        self.cfg_min_adx.setRange(1.0, 50.0)
        self.cfg_min_adx.setValue(10.0)
        self.cfg_min_adx.setSingleStep(1.0)
        self.cfg_min_adx.setDecimals(1)
        self.cfg_min_adx.setStyleSheet("color: #cdd6f4; background-color: #181825;")
        filter_layout.addRow("Min ADX:", self.cfg_min_adx)

        self.cfg_min_atr = QDoubleSpinBox()
        self.cfg_min_atr.setRange(0.1, 5.0)
        self.cfg_min_atr.setValue(0.5)
        self.cfg_min_atr.setSingleStep(0.1)
        self.cfg_min_atr.setDecimals(1)
        self.cfg_min_atr.setSuffix(" %")
        self.cfg_min_atr.setStyleSheet("color: #cdd6f4; background-color: #181825;")
        filter_layout.addRow("Min ATR %:", self.cfg_min_atr)

        self.cfg_min_volume = QDoubleSpinBox()
        self.cfg_min_volume.setRange(1000, 10000000)
        self.cfg_min_volume.setValue(50000)
        self.cfg_min_volume.setSingleStep(10000)
        self.cfg_min_volume.setDecimals(0)
        self.cfg_min_volume.setSuffix(" USDT")
        self.cfg_min_volume.setStyleSheet("color: #cdd6f4; background-color: #181825;")
        filter_layout.addRow("Min Volume 24h:", self.cfg_min_volume)

        self.cfg_min_signal = QDoubleSpinBox()
        self.cfg_min_signal.setRange(0.05, 1.0)
        self.cfg_min_signal.setValue(0.25)
        self.cfg_min_signal.setSingleStep(0.05)
        self.cfg_min_signal.setDecimals(2)
        self.cfg_min_signal.setStyleSheet("color: #cdd6f4; background-color: #181825;")
        filter_layout.addRow("Min Signal Strength:", self.cfg_min_signal)

        self.cfg_use_mtf = QCheckBox("Use Multi-Timeframe")
        self.cfg_use_mtf.setChecked(True)
        self.cfg_use_mtf.setStyleSheet("color: #cdd6f4;")
        filter_layout.addRow(self.cfg_use_mtf)

        self.cfg_use_spread = QCheckBox("Use Spread Filter")
        self.cfg_use_spread.setChecked(True)
        self.cfg_use_spread.setStyleSheet("color: #cdd6f4;")
        filter_layout.addRow(self.cfg_use_spread)

        layout.addWidget(filter_group)

        # === Save Button ===
        self.btn_save = QPushButton("Save Settings")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1; color: #1e1e2e;
                padding: 12px; border-radius: 6px; font-weight: bold; font-size: 14px;
            }
            QPushButton:hover { background-color: #b4f0b4; }
        """)
        self.btn_save.clicked.connect(self._save_settings)
        layout.addWidget(self.btn_save)
        layout.addStretch()

        scroll.setWidget(page)
        return scroll

    def _create_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        control = QHBoxLayout()
        self.btn_clear_logs = QPushButton("Clear")
        self.btn_clear_logs.clicked.connect(self._clear_logs)
        control.addWidget(self.btn_clear_logs)

        self.combo_log_level = QComboBox()
        self.combo_log_level.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.combo_log_level.setCurrentText("INFO")
        control.addWidget(self.combo_log_level)
        control.addStretch()
        layout.addLayout(control)

        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setMaximumBlockCount(5000)
        self.log_viewer.setStyleSheet("background-color: #11111b; color: #a6adc8;")
        layout.addWidget(self.log_viewer)

        return page

    def _switch_page(self, key: str):
        idx = {"dashboard": 0, "positions": 1, "config": 2, "logs": 3}.get(key, 0)
        self.stack.setCurrentIndex(idx)
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)

    def _connect_signals(self):
        self.log_signal.connect(self._append_log)
        self.stats_signal.connect(self._update_ui_stats)
        gui_handler = GuiLogHandler(self.log_signal)
        logging.getLogger("CryptoBot").addHandler(gui_handler)

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

        self.dash_balance.setText(f"Balance: {balance:.2f} USDT")
        self.dash_pnl.setText(f"Daily PnL: {pnl:+.2f} USDT")
        self.dash_positions.setText(f"Positions: {positions}")
        self.dash_winrate.setText(f"Win Rate: {win_rate:.1f}%")

        self._update_positions_table()

        health = stats.get("health_status", "OK")
        self.status_bar.showMessage(
            f"Balance: {balance:.2f} USDT | Positions: {positions} | "
            f"Daily PnL: {pnl:.2f} | Win Rate: {win_rate:.1f}% | Health: {health}"
        )

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
                         f"{pnl:+.2f}", f"{pnl_pct:+.2f}%", "Close"]
                for col, text in enumerate(items):
                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col == 5 and pnl > 0:
                        item.setForeground(Qt.GlobalColor.green)
                    elif col == 5 and pnl < 0:
                        item.setForeground(Qt.GlobalColor.red)
                    self.pos_table.setItem(row, col, item)

                btn = QPushButton("X")
                btn.setMaximumWidth(40)
                btn.clicked.connect(lambda checked, s=symbol: self._close_position(s))
                self.pos_table.setCellWidget(row, 7, btn)

            if open_pos:
                self.pos_status.setText(f"Positions: {len(open_pos)} | Total PnL: {total_pnl:+.2f} USDT")
                self.pos_status.setStyleSheet("color: #cdd6f4;")
                self.btn_close_all.setEnabled(True)
            else:
                self.pos_status.setText("No open positions")
                self.pos_status.setStyleSheet("color: #6c7086;")
                self.btn_close_all.setEnabled(False)
        except Exception as e:
            self.logger.debug(f"Positions update error: {e}")

    def _close_position(self, symbol: str):
        reply = QMessageBox.question(self, "Close Position", f"Close {symbol}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            async def do_close():
                try:
                    pos = self.engine.positions.get(symbol)
                    if pos:
                        await self.engine.trade_executor.close_position_async(symbol, pos.side, pos.quantity)
                except Exception as e:
                    self.logger.error(f"Close error {symbol}: {e}")
            asyncio.create_task(do_close())

    def _close_all_positions(self):
        reply = QMessageBox.question(self, "Close All", "Close ALL positions?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            async def do_close_all():
                try:
                    for symbol, pos in list(self.engine.positions.items()):
                        await self.engine.trade_executor.close_position_async(symbol, pos.side, pos.quantity)
                except Exception as e:
                    self.logger.error(f"Close all error: {e}")
            asyncio.create_task(do_close_all())

    def _load_settings(self):
        """Load settings from config into UI fields"""
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
            self.cfg_min_adx.setValue(self.settings.get("min_adx", 10.0))
            self.cfg_min_atr.setValue(self.settings.get("min_atr_percent", 0.5))
            self.cfg_min_volume.setValue(self.settings.get("min_volume_24h_usdt", 50000))
            self.cfg_min_signal.setValue(self.settings.get("min_signal_strength", 0.25))
            self.cfg_use_mtf.setChecked(self.settings.get("use_multi_timeframe", True))
            self.cfg_use_spread.setChecked(self.settings.get("use_spread_filter", True))
        except Exception as e:
            self.logger.error(f"Load settings error: {e}")

    def _save_settings(self):
        """Save UI fields to config and update API client"""
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
                "min_adx": self.cfg_min_adx.value(),
                "min_atr_percent": self.cfg_min_atr.value(),
                "min_volume_24h_usdt": self.cfg_min_volume.value(),
                "min_signal_strength": self.cfg_min_signal.value(),
                "use_multi_timeframe": self.cfg_use_mtf.isChecked(),
                "use_spread_filter": self.cfg_use_spread.isChecked(),
            }
            self.settings.update(updates)
            self.api_client.update_credentials(api_key, api_secret)

            demo = self.cfg_demo.isChecked()
            self.mode_label.setText("MODE: PAPER" if demo else "MODE: LIVE")
            self.mode_label.setStyleSheet(
                "color: #a6e3a1; font-weight: bold;" if demo else "color: #f38ba8; font-weight: bold;"
            )

            QMessageBox.information(self, "Saved", "Settings saved! API credentials updated.")
            self.logger.info("Settings saved via GUI")
        except Exception as e:
            self.logger.error(f"Save settings error: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

    def _clear_logs(self):
        self.log_viewer.clear()

    def run_scan(self):
        self.status_label.setText("Scanning...")
        self.scan_btn.setEnabled(False)
        if self.engine and self.engine.running:
            async def do_scan():
                try:
                    await self.engine._scan_and_trade()
                    signals = self.engine.get_last_scan_signals()
                    self._update_signals_table(signals)
                    self.status_label.setText(f"Signals: {len(signals)}")
                except Exception as e:
                    self.logger.error(f"Scan error: {e}")
                    self.status_label.setText("Scan failed")
                finally:
                    self.scan_btn.setEnabled(True)
            asyncio.create_task(do_scan())
        else:
            self.status_label.setText("Engine not running")
            self.scan_btn.setEnabled(True)

    def _update_signals_table(self, signals):
        self.dash_signals_table.setRowCount(0)
        if not signals:
            return
        self.dash_signals_table.setRowCount(len(signals))
        for row, sig in enumerate(signals):
            symbol = sig.get("symbol", "?")
            direction = sig.get("direction", sig.get("indicators", {}).get("signal_direction", "?"))
            score = sig.get("confidence", sig.get("indicators", {}).get("signal_strength", 0))
            price = sig.get("price", sig.get("indicators", {}).get("close_price", 0.0))
            time_str = datetime.now().strftime("%H:%M:%S")

            items = [
                QTableWidgetItem(symbol),
                QTableWidgetItem(direction),
                QTableWidgetItem(f"{score:.2f}"),
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
            self.engine_btn.setText("Stop Engine")
            self.engine_btn.setStyleSheet("color: #f38ba8; font-weight: bold;")
            self.status_label.setText("Engine starting...")
            async def start_engine():
                try:
                    await self.engine.start()
                    self.status_label.setText("Engine running")
                except Exception as e:
                    self.logger.error(f"Engine start error: {e}")
                    self.status_label.setText("Start failed")
                    self.engine_btn.setText("Start Engine")
                    self.engine_btn.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            asyncio.create_task(start_engine())
            self.logger.info("TradingEngine START requested")
        else:
            self.engine_btn.setText("Start Engine")
            self.engine_btn.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            self.status_label.setText("Engine stopping...")
            async def stop_engine():
                try:
                    await self.engine.stop()
                    self.status_label.setText("Engine stopped")
                except Exception as e:
                    self.logger.error(f"Engine stop error: {e}")
            asyncio.create_task(stop_engine())
            self.logger.info("TradingEngine STOP requested")

    def toggle_autopilot(self):
        checked = self.autopilot_btn.isChecked()
        self.autopilot_btn.setText("AutoPilot ON" if checked else "AutoPilot OFF")
        status = "ACTIVE" if checked else "STANDBY"
        self.logger.info(f"AutoPilot {status}")

    def _append_log(self, text: str):
        self.log_viewer.appendPlainText(text)
        self.dash_log.appendPlainText(text)
        scrollbar = self.log_viewer.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        self.logger.info("Window closing...")
        self.update_timer.stop()
        self.scan_timer.stop()
        event.accept()
