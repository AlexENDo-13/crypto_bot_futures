"""
Main Window for CryptoBot v9.1 (FIXED)
Full GUI with pages: Dashboard, Positions, Config, Logs
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
    QStackedWidget, QFrame
)

from src.exchange.api_client import BingXAPIClient
from src.config.settings import Settings
from src.core.engine.trading_engine import TradingEngine


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
        self.resize(1400, 900)

        self._init_ui()
        self._connect_signals()

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_stats)
        self.update_timer.start(2000)

        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.run_scan)
        self.scan_timer.start(60000)

        self.logger.info("MainWindow initialized with TradingEngine")

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
            ("dashboard", "📊 Dashboard"),
            ("positions", "📈 Positions"),
            ("config", "⚙️ Config"),
            ("logs", "📜 Logs"),
        ]
        for key, label in pages:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._switch_page(k))
            sidebar_layout.addWidget(btn)
            self.nav_buttons[key] = btn

        sidebar_layout.addStretch()

        self.engine_btn = QPushButton("▶ Start Engine")
        self.engine_btn.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        self.engine_btn.clicked.connect(self.toggle_engine)
        sidebar_layout.addWidget(self.engine_btn)

        self.scan_btn = QPushButton("🔍 Scan Now")
        self.scan_btn.clicked.connect(self.run_scan)
        sidebar_layout.addWidget(self.scan_btn)

        self.autopilot_btn = QPushButton("🤖 AutoPilot OFF")
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
        self.status_bar.showMessage("CryptoBot v9.1 Ready")

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
        title = QLabel("📊 Open Positions")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #cdd6f4;")
        header.addWidget(title)

        self.btn_close_all = QPushButton("❌ Close All")
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
        page = QWidget()
        layout = QVBoxLayout(page)

        # API Settings
        api_group = QFrame()
        api_group.setStyleSheet("QFrame { background-color: #313244; border-radius: 8px; padding: 10px; }")
        api_layout = QVBoxLayout(api_group)
        api_title = QLabel("🔑 API Settings")
        api_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #cdd6f4;")
        api_layout.addWidget(api_title)

        self.cfg_api_key = QPlainTextEdit()
        self.cfg_api_key.setPlaceholderText("BingX API Key")
        self.cfg_api_key.setMaximumBlockCount(1)
        self.cfg_api_key.setStyleSheet("background-color: #181825; color: #cdd6f4;")
        api_layout.addWidget(self.cfg_api_key)

        self.cfg_api_secret = QPlainTextEdit()
        self.cfg_api_secret.setPlaceholderText("BingX API Secret")
        self.cfg_api_secret.setMaximumBlockCount(1)
        self.cfg_api_secret.setStyleSheet("background-color: #181825; color: #cdd6f4;")
        api_layout.addWidget(self.cfg_api_secret)

        self.cfg_demo = QPushButton("Demo Mode: ON")
        self.cfg_demo.setCheckable(True)
        self.cfg_demo.setChecked(True)
        self.cfg_demo.clicked.connect(self._toggle_demo_mode)
        api_layout.addWidget(self.cfg_demo)

        layout.addWidget(api_group)

        # Trading Settings
        trade_group = QFrame()
        trade_group.setStyleSheet("QFrame { background-color: #313244; border-radius: 8px; padding: 10px; }")
        trade_layout = QVBoxLayout(trade_group)
        trade_title = QLabel("📊 Trading Settings")
        trade_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #cdd6f4;")
        trade_layout.addWidget(trade_title)

        self.cfg_leverage = QComboBox()
        self.cfg_leverage.addItems([str(i) for i in range(1, 51)])
        self.cfg_leverage.setCurrentText("10")
        trade_layout.addWidget(QLabel("Max Leverage:"))
        trade_layout.addWidget(self.cfg_leverage)

        self.cfg_positions = QComboBox()
        self.cfg_positions.addItems([str(i) for i in range(1, 21)])
        self.cfg_positions.setCurrentText("3")
        trade_layout.addWidget(QLabel("Max Positions:"))
        trade_layout.addWidget(self.cfg_positions)

        self.cfg_risk = QComboBox()
        self.cfg_risk.addItems(["0.5", "1.0", "2.0", "3.0", "5.0"])
        self.cfg_risk.setCurrentText("1.0")
        trade_layout.addWidget(QLabel("Risk per Trade %:"))
        trade_layout.addWidget(self.cfg_risk)

        self.cfg_scan_interval = QComboBox()
        self.cfg_scan_interval.addItems(["1", "3", "5", "10", "15", "30", "60"])
        self.cfg_scan_interval.setCurrentText("5")
        trade_layout.addWidget(QLabel("Scan Interval (min):"))
        trade_layout.addWidget(self.cfg_scan_interval)

        layout.addWidget(trade_group)

        # Save button
        self.btn_save = QPushButton("💾 Save Settings")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1; color: #1e1e2e;
                padding: 10px; border-radius: 6px; font-weight: bold; font-size: 14px;
            }
            QPushButton:hover { background-color: #b4f0b4; }
        """)
        self.btn_save.clicked.connect(self._save_settings)
        layout.addWidget(self.btn_save)
        layout.addStretch()

        self._load_settings()
        return page

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
                mark = float(pos.get("mark_price", entry))
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

                btn = QPushButton("❌")
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
        self.cfg_api_key.setPlainText(self.settings.get("api_key", ""))
        self.cfg_api_secret.setPlainText(self.settings.get("api_secret", ""))
        self.cfg_demo.setChecked(self.settings.get("demo_mode", True))
        self.cfg_demo.setText("Demo Mode: ON" if self.cfg_demo.isChecked() else "Demo Mode: OFF")
        self.cfg_leverage.setCurrentText(str(self.settings.get("max_leverage", 10)))
        self.cfg_positions.setCurrentText(str(self.settings.get("max_positions", 3)))
        self.cfg_risk.setCurrentText(str(self.settings.get("max_risk_per_trade", 1.0)))
        self.cfg_scan_interval.setCurrentText(str(self.settings.get("scan_interval_minutes", 5)))

    def _toggle_demo_mode(self):
        checked = self.cfg_demo.isChecked()
        self.cfg_demo.setText("Demo Mode: ON" if checked else "Demo Mode: OFF")

    def _save_settings(self):
        api_key = self.cfg_api_key.toPlainText().strip()
        api_secret = self.cfg_api_secret.toPlainText().strip()

        updates = {
            "api_key": api_key,
            "api_secret": api_secret,
            "demo_mode": self.cfg_demo.isChecked(),
            "max_leverage": int(self.cfg_leverage.currentText()),
            "max_positions": int(self.cfg_positions.currentText()),
            "max_risk_per_trade": float(self.cfg_risk.currentText()),
            "scan_interval_minutes": int(self.cfg_scan_interval.currentText()),
        }
        self.settings.update(updates)

        # Update API client credentials immediately
        self.api_client.update_credentials(api_key, api_secret)

        # Update mode label
        demo = self.cfg_demo.isChecked()
        self.mode_label.setText("MODE: PAPER" if demo else "MODE: LIVE")
        self.mode_label.setStyleSheet(
            "color: #a6e3a1; font-weight: bold;" if demo else "color: #f38ba8; font-weight: bold;"
        )

        QMessageBox.information(self, "Saved", "Settings saved! API credentials updated.")
        self.logger.info("Settings saved via GUI")

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
            self.engine_btn.setText("⏹ Stop Engine")
            self.engine_btn.setStyleSheet("color: #f38ba8; font-weight: bold;")
            self.status_label.setText("Engine starting...")
            async def start_engine():
                try:
                    await self.engine.start()
                    self.status_label.setText("Engine running")
                except Exception as e:
                    self.logger.error(f"Engine start error: {e}")
                    self.status_label.setText("Start failed")
                    self.engine_btn.setText("▶ Start Engine")
                    self.engine_btn.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            asyncio.create_task(start_engine())
            self.logger.info("TradingEngine START requested")
        else:
            self.engine_btn.setText("▶ Start Engine")
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
        self.autopilot_btn.setText("🤖 AutoPilot ON" if checked else "🤖 AutoPilot OFF")
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


class GuiLogHandler(logging.Handler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s | %(message)s", "%H:%M:%S"))

    def emit(self, record):
        msg = self.format(record)
        self.signal.emit(msg)
