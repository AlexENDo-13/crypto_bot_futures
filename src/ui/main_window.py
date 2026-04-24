"""
Main Window v5.0 - Advanced GUI with charts, real-time monitoring,
and comprehensive control panel.
"""
import sys
from typing import Optional, List
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QPlainTextEdit, QSplitter,
    QHeaderView, QGroupBox, QGridLayout, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QProgressBar, QMessageBox, QStatusBar,
    QFrame, QSizePolicy, QMenuBar, QMenu, QAction, QFileDialog
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QThread
from PyQt5.QtGui import QColor, QFont, QPalette

from src.core.config import get_config
from src.core.logger import get_logger, BotLogger, QtLogHandler
from src.core.events import get_event_bus, EventType
from src.trading.data_fetcher import DataFetcher
from src.trading.trade_executor import TradeExecutor
from src.trading.risk_manager import RiskManager
from src.trading.market_scanner import MarketScanner
from src.ai.ml_engine import MLEngine
from src.notifications.telegram import TelegramNotifier
from src.notifications.discord import DiscordNotifier

logger = get_logger()


def apply_dark_theme(app):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(15, 15, 20))
    palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.Base, QColor(25, 25, 32))
    palette.setColor(QPalette.AlternateBase, QColor(32, 32, 40))
    palette.setColor(QPalette.ToolTipBase, QColor(35, 35, 45))
    palette.setColor(QPalette.ToolTipText, QColor(220, 220, 220))
    palette.setColor(QPalette.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.Button, QColor(40, 40, 50))
    palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.BrightText, QColor(255, 80, 80))
    palette.setColor(QPalette.Highlight, QColor(0, 160, 220))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    app.setStyleSheet("""
        QMainWindow { background-color: #0f0f14; }
        QGroupBox { border: 1px solid #3a3a4a; border-radius: 6px; margin-top: 10px; padding-top: 10px; font-weight: bold; color: #a0a0b0; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        QPushButton { background-color: #2d5a8a; color: white; border: none; border-radius: 4px; padding: 8px 16px; font-weight: bold; }
        QPushButton:hover { background-color: #3d7ab0; }
        QPushButton:pressed { background-color: #1d4a7a; }
        QPushButton:disabled { background-color: #3a3a4a; color: #666; }
        QPushButton#startBtn { background-color: #0d8a5a; }
        QPushButton#startBtn:hover { background-color: #0daa6a; }
        QPushButton#stopBtn { background-color: #8a2d2d; }
        QPushButton#stopBtn:hover { background-color: #aa3d3d; }
        QTableWidget { background-color: #191920; border: 1px solid #3a3a4a; gridline-color: #2a2a3a; }
        QTableWidget::item { padding: 6px; }
        QTableWidget::item:selected { background-color: #0d5a7a; }
        QHeaderView::section { background-color: #22222c; color: #a0a0b0; padding: 8px; border: 1px solid #3a3a4a; font-weight: bold; }
        QTextEdit { background-color: #121218; color: #c0c0c0; border: 1px solid #3a3a4a; font-family: Consolas, Monaco, monospace; font-size: 12px; }
        QComboBox, QSpinBox, QDoubleSpinBox { background-color: #22222c; color: #e0e0e0; border: 1px solid #3a3a4a; padding: 4px; border-radius: 3px; }
        QProgressBar { border: 1px solid #3a3a4a; border-radius: 4px; text-align: center; color: white; }
        QProgressBar::chunk { background-color: #0d8a5a; border-radius: 3px; }
        QLabel { color: #c0c0c0; }
        QTabWidget::pane { border: 1px solid #3a3a4a; background-color: #191920; }
        QTabBar::tab { background-color: #22222c; color: #a0a0b0; padding: 8px 16px; border: 1px solid #3a3a4a; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
        QTabBar::tab:selected { background-color: #191920; color: #e0e0e0; }
        QTabBar::tab:hover { background-color: #2d2d3a; }
        QMenuBar { background-color: #1a1a22; color: #c0c0c0; }
        QMenuBar::item:selected { background-color: #2d5a8a; }
        QMenu { background-color: #1a1a22; border: 1px solid #3a3a4a; }
        QMenu::item:selected { background-color: #2d5a8a; }
    """)


class BotWorker(QThread):
    def __init__(self, bot_core):
        super().__init__()
        self.bot_core = bot_core
        self.running = False
    def run(self):
        self.running = True
        while self.running:
            try:
                self.bot_core.tick()
            except Exception as e:
                logger.error("Tick error: %s", e)
            self.msleep(1000)
    def stop(self):
        self.running = False
        self.wait(3000)


class BotCore:
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.executor = TradeExecutor()
        self.risk_manager = RiskManager()
        self.scanner = MarketScanner()
        self.ml_engine = MLEngine()
        self.telegram = TelegramNotifier()
        self.discord = DiscordNotifier()
        self.event_bus = get_event_bus()
        self.running = False
        self.symbol = get_config().trading.primary_symbol
        self.scan_interval = 60
        self._tick_count = 0
        self.scanner.add_signal_callback(self._on_signals)
        self._setup_event_handlers()

    def _setup_event_handlers(self):
        self.event_bus.subscribe(EventType.POSITION_CLOSED, self._on_position_closed)
        self.event_bus.subscribe(EventType.RISK_ALERT, self._on_risk_alert)

    def _on_signals(self, signals):
        for sig in signals:
            if sig.confidence >= 0.7:
                self.telegram.send_signal(sig.symbol, sig.direction, sig.confidence, sig.strategy)
                self.discord.send_signal(sig.symbol, sig.direction, sig.confidence, sig.strategy)

    def _on_position_closed(self, event):
        data = event.data
        pnl = data.get("pnl", 0)
        self.telegram.send_trade(data.get("symbol"), data.get("side"), pnl, data.get("reason", ""))
        self.discord.send_trade(data.get("symbol"), data.get("side"), pnl, data.get("reason", ""))

    def _on_risk_alert(self, event):
        self.telegram.send_alert("Risk Alert", event.data.get("message", ""))

    def start(self):
        self.running = True
        self.scanner.start_continuous_scan(self.scan_interval)
        logger.info("Bot core started")

    def stop(self):
        self.running = False
        self.scanner.stop_continuous_scan()
        logger.info("Bot core stopped")

    def tick(self):
        self._tick_count += 1
        try:
            closed = self.executor.update_positions()
            for symbol, reason, pnl in closed:
                self.risk_manager.update_pnl(pnl)
                logger.pnl(f"{symbol} closed by {reason} | PnL: {pnl:+.2f}")
        except Exception as e:
            logger.error("Position update: %s", e)

        try:
            balance = self.executor.get_balance()
            self.risk_manager.update_balance(balance)
        except Exception as e:
            logger.error("Balance update: %s", e)

        # ML retrain check
        if self._tick_count % 3600 == 0 and self.ml_engine.should_retrain():
            try:
                self.ml_engine.train()
            except Exception as e:
                logger.error("ML retrain: %s", e)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(get_config().ui.window_title)
        self.setMinimumSize(get_config().ui.window_width, get_config().ui.window_height)
        self.bot_core = BotCore()
        self.worker = None
        self._setup_menu()
        self._setup_ui()
        self._setup_log_handler()
        self._setup_timers()
        logger.info("MainWindow v5.0 initialized")

    def _setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        action_export = QAction("Export Config", self)
        action_export.triggered.connect(self._export_config)
        file_menu.addAction(action_export)

        action_import = QAction("Import Config", self)
        action_import.triggered.connect(self._import_config)
        file_menu.addAction(action_import)

        file_menu.addSeparator()

        action_exit = QAction("Exit", self)
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Control bar
        control = QHBoxLayout()
        self.btn_start = QPushButton("▶ START")
        self.btn_start.setObjectName("startBtn")
        self.btn_start.setStyleSheet("font-size: 14px;")
        self.btn_start.clicked.connect(self._start_bot)
        control.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹ STOP")
        self.btn_stop.setObjectName("stopBtn")
        self.btn_stop.setStyleSheet("font-size: 14px;")
        self.btn_stop.clicked.connect(self._stop_bot)
        self.btn_stop.setEnabled(False)
        control.addWidget(self.btn_stop)

        control.addSpacing(20)

        self.lbl_status = QLabel("● STOPPED")
        self.lbl_status.setStyleSheet("color: #ff5555; font-weight: bold; font-size: 14px;")
        control.addWidget(self.lbl_status)

        control.addStretch()

        self.lbl_mode = QLabel("📋 PAPER TRADING")
        self.lbl_mode.setStyleSheet("color: #ffaa00; font-weight: bold; padding: 4px 10px; background-color: #3a2a00; border-radius: 4px;")
        if get_config().mode.value == "live":
            self.lbl_mode.setText("🔴 LIVE TRADING")
            self.lbl_mode.setStyleSheet("color: #ff3333; font-weight: bold; padding: 4px 10px; background-color: #3a0000; border-radius: 4px;")
        control.addWidget(self.lbl_mode)

        layout.addLayout(control)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left panel
        left = QWidget()
        left_layout = QVBoxLayout(left)

        account = QGroupBox("💰 Account")
        acct_grid = QGridLayout()
        acct_grid.addWidget(QLabel("Balance:"), 0, 0)
        self.lbl_balance = QLabel("0.00 USDT")
        self.lbl_balance.setStyleSheet("font-size: 16px; font-weight: bold; color: #4ade80;")
        acct_grid.addWidget(self.lbl_balance, 0, 1)
        acct_grid.addWidget(QLabel("Daily PnL:"), 1, 0)
        self.lbl_daily_pnl = QLabel("+0.00 USDT")
        self.lbl_daily_pnl.setStyleSheet("font-size: 14px; color: #888;")
        acct_grid.addWidget(self.lbl_daily_pnl, 1, 1)
        acct_grid.addWidget(QLabel("Positions:"), 2, 0)
        self.lbl_pos_count = QLabel("0")
        acct_grid.addWidget(self.lbl_pos_count, 2, 1)
        account.setLayout(acct_grid)
        left_layout.addWidget(account)

        risk = QGroupBox("🛡 Risk")
        risk_grid = QGridLayout()
        risk_grid.addWidget(QLabel("Win Rate:"), 0, 0)
        self.lbl_win_rate = QLabel("0%")
        risk_grid.addWidget(self.lbl_win_rate, 0, 1)
        risk_grid.addWidget(QLabel("Trades:"), 1, 0)
        self.lbl_total_trades = QLabel("0")
        risk_grid.addWidget(self.lbl_total_trades, 1, 1)
        risk_grid.addWidget(QLabel("Max DD:"), 2, 0)
        self.lbl_max_dd = QLabel("0.0%")
        self.lbl_max_dd.setStyleSheet("color: #ff6666;")
        risk_grid.addWidget(self.lbl_max_dd, 2, 1)
        risk_grid.addWidget(QLabel("Profit Factor:"), 3, 0)
        self.lbl_pf = QLabel("0.00")
        risk_grid.addWidget(self.lbl_pf, 3, 1)
        risk.setLayout(risk_grid)
        left_layout.addWidget(risk)

        settings = QGroupBox("⚙ Settings")
        set_grid = QGridLayout()
        set_grid.addWidget(QLabel("Symbol:"), 0, 0)
        self.cmb_symbol = QComboBox()
        self.cmb_symbol.addItems(["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT"])
        set_grid.addWidget(self.cmb_symbol, 0, 1)
        set_grid.addWidget(QLabel("Leverage:"), 1, 0)
        self.spin_lev = QSpinBox()
        self.spin_lev.setRange(1, 125)
        self.spin_lev.setValue(get_config().trading.leverage)
        set_grid.addWidget(self.spin_lev, 1, 1)
        set_grid.addWidget(QLabel("Risk %:"), 2, 0)
        self.spin_risk = QDoubleSpinBox()
        self.spin_risk.setRange(0.1, 100)
        self.spin_risk.setValue(get_config().trading.risk_per_trade_pct)
        self.spin_risk.setDecimals(1)
        set_grid.addWidget(self.spin_risk, 2, 1)
        settings.setLayout(set_grid)
        left_layout.addWidget(settings)

        left_layout.addStretch()
        splitter.addWidget(left)

        # Center tabs
        tabs = QTabWidget()

        self.pos_table = QTableWidget()
        self.pos_table.setColumnCount(8)
        self.pos_table.setHorizontalHeaderLabels(["Symbol", "Side", "Entry", "Current", "Qty", "PnL", "PnL%", "SL/TP"])
        self.pos_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tabs.addTab(self.pos_table, "📊 Positions")

        self.sig_table = QTableWidget()
        self.sig_table.setColumnCount(7)
        self.sig_table.setHorizontalHeaderLabels(["Time", "Symbol", "Dir", "Conf", "Strategy", "Entry", "Reason"])
        self.sig_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tabs.addTab(self.sig_table, "📡 Signals")

        self.hist_table = QTableWidget()
        self.hist_table.setColumnCount(6)
        self.hist_table.setHorizontalHeaderLabels(["Time", "Symbol", "Side", "PnL", "Reason", "Duration"])
        self.hist_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tabs.addTab(self.hist_table, "📜 History")

        # ML Tab
        self.ml_table = QTableWidget()
        self.ml_table.setColumnCount(5)
        self.ml_table.setHorizontalHeaderLabels(["Symbol", "Direction", "Confidence", "Probability", "Features"])
        self.ml_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tabs.addTab(self.ml_table, "🤖 ML Predictions")

        splitter.addWidget(tabs)

        # Right log panel
        log_panel = QWidget()
        log_layout = QVBoxLayout(log_panel)
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("📝 Logs"))
        log_header.addStretch()
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self._clear_logs)
        log_header.addWidget(self.btn_clear)
        log_layout.addLayout(log_header)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(5000)
        log_layout.addWidget(self.log_text)

        splitter.addWidget(log_panel)
        splitter.setSizes([250, 750, 400])
        layout.addWidget(splitter)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready | v5.0")

    def _setup_log_handler(self):
        log = get_logger()
        self.qt_handler = log.add_qt_handler(self)
        if self.qt_handler and self.qt_handler.log_signal:
            self.qt_handler.log_signal.connect(self._on_log)

    def _setup_timers(self):
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._update_ui)
        self.ui_timer.start(1000)

        self.slow_timer = QTimer(self)
        self.slow_timer.timeout.connect(self._update_slow)
        self.slow_timer.start(5000)

        self.ml_timer = QTimer(self)
        self.ml_timer.timeout.connect(self._update_ml)
        self.ml_timer.start(30000)

    @pyqtSlot(str, str, str)
    def _on_log(self, level, message, category):
        color = "#c0c0c0"
        if "ERROR" in level or "CRITICAL" in level:
            color = "#ff6666"
        elif "WARNING" in level:
            color = "#ffaa44"
        elif "TRADE" in message or "PnL" in message:
            color = "#4ade80" if "+" in message and "PnL" in message else "#ff6666" if "-" in message and "PnL" in message else "#66ccff"
        elif "SIGNAL" in message:
            color = "#cc88ff"
        elif "RISK" in message:
            color = "#ffaa00"

        self.log_text.appendHtml(f'<span style="color: {color}">{message}</span>')
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _start_bot(self):
        self.bot_core.start()
        self.worker = BotWorker(self.bot_core)
        self.worker.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_status.setText("● RUNNING")
        self.lbl_status.setStyleSheet("color: #4ade80; font-weight: bold; font-size: 14px;")
        self.status_bar.showMessage("Bot running...")
        logger.info("Bot started")

    def _stop_bot(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.bot_core.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("● STOPPED")
        self.lbl_status.setStyleSheet("color: #ff5555; font-weight: bold; font-size: 14px;")
        self.status_bar.showMessage("Bot stopped")
        logger.info("Bot stopped")

    def _update_ui(self):
        try:
            balance = self.bot_core.executor.get_balance()
            self.lbl_balance.setText(f"{balance:,.2f} USDT")

            positions = self.bot_core.executor.get_positions()
            self.lbl_pos_count.setText(str(len(positions)))

            self.pos_table.setRowCount(len(positions))
            for i, pos in enumerate(positions):
                price = self.bot_core.data_fetcher.get_current_price(pos.symbol)
                pnl = pos.calculate_pnl(price)
                pnl_pct = pos.calculate_pnl_percent(price)

                self.pos_table.setItem(i, 0, QTableWidgetItem(pos.symbol))
                self.pos_table.setItem(i, 1, QTableWidgetItem(pos.side.value))
                self.pos_table.setItem(i, 2, QTableWidgetItem(f"{pos.avg_entry_price:.2f}"))
                self.pos_table.setItem(i, 3, QTableWidgetItem(f"{price:.2f}"))
                self.pos_table.setItem(i, 4, QTableWidgetItem(f"{pos.quantity:.6f}"))

                pi = QTableWidgetItem(f"{pnl:+.2f}")
                pi.setForeground(QColor("#4ade80" if pnl >= 0 else "#ff6666"))
                self.pos_table.setItem(i, 5, pi)

                pi2 = QTableWidgetItem(f"{pnl_pct:+.2f}%")
                pi2.setForeground(QColor("#4ade80" if pnl_pct >= 0 else "#ff6666"))
                self.pos_table.setItem(i, 6, pi2)

                self.pos_table.setItem(i, 7, QTableWidgetItem(f"SL:{pos.stop_loss_price:.1f}/TP:{pos.take_profit_price:.1f}"))

            signals = self.bot_core.scanner.get_latest_signals()
            self.sig_table.setRowCount(min(len(signals), 20))
            for i, sig in enumerate(signals[:20]):
                self.sig_table.setItem(i, 0, QTableWidgetItem(datetime.now().strftime("%H:%M:%S")))
                self.sig_table.setItem(i, 1, QTableWidgetItem(sig.symbol))
                di = QTableWidgetItem(sig.direction)
                di.setForeground(QColor("#4ade80" if sig.direction == "LONG" else "#ff6666"))
                self.sig_table.setItem(i, 2, di)
                ci = QTableWidgetItem(f"{sig.confidence:.2f}")
                ci.setForeground(QColor("#4ade80" if sig.confidence > 0.8 else "#ffaa44" if sig.confidence > 0.6 else "#ff6666"))
                self.sig_table.setItem(i, 3, ci)
                self.sig_table.setItem(i, 4, QTableWidgetItem(sig.strategy))
                self.sig_table.setItem(i, 5, QTableWidgetItem(f"{sig.entry_price:.2f}"))
                self.sig_table.setItem(i, 6, QTableWidgetItem(sig.reason))

        except Exception as e:
            logger.error("UI update: %s", e)

    def _update_slow(self):
        try:
            stats = self.bot_core.risk_manager.get_stats()
            self.lbl_win_rate.setText(f"{stats.get('win_rate', 0):.1f}%")
            self.lbl_total_trades.setText(str(stats.get('total_trades', 0)))
            self.lbl_max_dd.setText(f"{stats.get('max_drawdown', 0):.1f}%")
            self.lbl_pf.setText(f"{stats.get('profit_factor', 0):.2f}")

            self.lbl_daily_pnl.setText(f"{stats.get('daily_pnl', 0):+.2f} USDT")
            self.lbl_daily_pnl.setStyleSheet(
                f"font-size: 14px; color: {'#4ade80' if stats.get('daily_pnl', 0) >= 0 else '#ff6666'}; font-weight: bold;"
            )
        except Exception as e:
            logger.error("Slow update: %s", e)

    def _update_ml(self):
        try:
            if not self.bot_core.ml_engine._models:
                return
            predictions = []
            for symbol in ["BTC-USDT", "ETH-USDT", "SOL-USDT"]:
                pred = self.bot_core.ml_engine.predict(symbol)
                if pred:
                    predictions.append(pred)

            self.ml_table.setRowCount(len(predictions))
            for i, p in enumerate(predictions):
                self.ml_table.setItem(i, 0, QTableWidgetItem(p.symbol))
                di = QTableWidgetItem(p.direction)
                di.setForeground(QColor("#4ade80" if p.direction == "UP" else "#ff6666" if p.direction == "DOWN" else "#888"))
                self.ml_table.setItem(i, 1, di)
                self.ml_table.setItem(i, 2, QTableWidgetItem(f"{p.confidence:.2f}"))
                self.ml_table.setItem(i, 3, QTableWidgetItem(f"{p.probability:.3f}"))
                self.ml_table.setItem(i, 4, QTableWidgetItem(",".join(p.features_used[:5])))
        except Exception as e:
            logger.error("ML update: %s", e)

    def _clear_logs(self):
        self.log_text.clear()

    def _export_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Config", "config.json", "JSON (*.json)")
        if path:
            get_config().save(path)
            logger.info("Config exported to %s", path)

    def _import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Config", "", "JSON (*.json)")
        if path:
            from src.core.config import set_config, Config
            set_config(Config.load(path))
            logger.info("Config imported from %s", path)

    def closeEvent(self, event):
        reply = QMessageBox.question(self, "Exit", "Stop bot and exit?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._stop_bot()
            event.accept()
        else:
            event.ignore()
