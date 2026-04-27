#!/usr/bin/env python3
"""MainWindow — GUI for CryptoBot v10.0"""
import asyncio
import logging
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTabWidget, QTextEdit, QCheckBox,
    QSpinBox, QDoubleSpinBox, QGroupBox, QGridLayout, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont

logger = logging.getLogger("CryptoBot")

class MainWindow(QMainWindow):
    def __init__(self, api_client, engine, settings):
        super().__init__()
        self.api_client = api_client
        self.engine = engine
        self.settings = settings
        self.setWindowTitle("CryptoBot v10.0 — Neural Adaptive Trading")
        self.setMinimumSize(1200, 800)
        self._init_ui()
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_ui)
        self._timer.start(2000)
        logger.info("MainWindow initialized - CryptoBot v10.0")
        logger.info("=" * 60)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Header
        header = QLabel("🤖 CryptoBot v10.0 — Neural Adaptive Trading System")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Status bar
        self.status_label = QLabel("Status: STOPPED | Balance: -- | Positions: 0")
        self.status_label.setFont(QFont("Segoe UI", 11))
        self.status_label.setStyleSheet("padding: 8px; background: #2c3e50; color: white; border-radius: 4px;")
        layout.addWidget(self.status_label)

        # Tabs
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Tab 1: Dashboard
        dash = QWidget()
        dash_layout = QVBoxLayout(dash)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        dash_layout.addWidget(self.log_text)
        tabs.addTab(dash, "📊 Dashboard")

        # Tab 2: Positions
        pos_tab = QWidget()
        pos_layout = QVBoxLayout(pos_tab)
        self.pos_table = QTableWidget()
        self.pos_table.setColumnCount(8)
        self.pos_table.setHorizontalHeaderLabels(["Symbol", "Side", "Entry", "Current", "Qty", "Leverage", "PnL", "SL / TP"])
        self.pos_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        pos_layout.addWidget(self.pos_table)
        tabs.addTab(pos_tab, "📈 Positions")

        # Tab 3: Config
        config_tab = QWidget()
        config_layout = QVBoxLayout(config_tab)

        api_group = QGroupBox("API Configuration")
        api_grid = QGridLayout(api_group)
        api_grid.addWidget(QLabel("API Key:"), 0, 0)
        self.api_key_input = QLineEdit(self.settings.get("api_key", ""))
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_grid.addWidget(self.api_key_input, 0, 1)
        api_grid.addWidget(QLabel("API Secret:"), 1, 0)
        self.api_secret_input = QLineEdit(self.settings.get("api_secret", ""))
        self.api_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_grid.addWidget(self.api_secret_input, 1, 1)
        config_layout.addWidget(api_group)

        risk_group = QGroupBox("Risk Settings")
        risk_grid = QGridLayout(risk_group)
        risk_grid.addWidget(QLabel("Max Positions:"), 0, 0)
        self.max_pos_spin = QSpinBox()
        self.max_pos_spin.setRange(1, 10)
        self.max_pos_spin.setValue(self.settings.get("max_positions", 3))
        risk_grid.addWidget(self.max_pos_spin, 0, 1)
        risk_grid.addWidget(QLabel("Risk/Trade %:"), 1, 0)
        self.risk_spin = QDoubleSpinBox()
        self.risk_spin.setRange(0.1, 5.0)
        self.risk_spin.setSingleStep(0.1)
        self.risk_spin.setValue(self.settings.get("max_risk_per_trade", 1.0))
        risk_grid.addWidget(self.risk_spin, 1, 1)
        risk_grid.addWidget(QLabel("Max Leverage:"), 2, 0)
        self.lev_spin = QSpinBox()
        self.lev_spin.setRange(1, 50)
        self.lev_spin.setValue(self.settings.get("max_leverage", 10))
        risk_grid.addWidget(self.lev_spin, 2, 1)
        config_layout.addWidget(risk_group)

        self.demo_check = QCheckBox("Demo Mode (Paper Trading)")
        self.demo_check.setChecked(self.settings.get("demo_mode", True))
        config_layout.addWidget(self.demo_check)

        save_btn = QPushButton("💾 Save Settings")
        save_btn.clicked.connect(self._save_settings)
        config_layout.addWidget(save_btn)
        config_layout.addStretch()
        tabs.addTab(config_tab, "⚙️ Config")

        # Control buttons
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶️ START ENGINE")
        self.start_btn.setStyleSheet("background: #27ae60; color: white; font-size: 14px; padding: 10px;")
        self.start_btn.clicked.connect(self._start_engine)
        btn_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹️ STOP ENGINE")
        self.stop_btn.setStyleSheet("background: #e74c3c; color: white; font-size: 14px; padding: 10px;")
        self.stop_btn.clicked.connect(self._stop_engine)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)

        self.scan_btn = QPushButton("🔍 MANUAL SCAN")
        self.scan_btn.setStyleSheet("background: #3498db; color: white; font-size: 14px; padding: 10px;")
        self.scan_btn.clicked.connect(self._manual_scan)
        btn_layout.addWidget(self.scan_btn)

        layout.addLayout(btn_layout)

        # Log handler
        self._setup_log_handler()

    def _setup_log_handler(self):
        class QTextEditHandler(logging.Handler):
            def __init__(self, widget):
                super().__init__()
                self.widget = widget
            def emit(self, record):
                msg = self.format(record)
                self.widget.append(msg)
                self.widget.verticalScrollBar().setValue(self.widget.verticalScrollBar().maximum())
        handler = QTextEditHandler(self.log_text)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s | %(message)s", datefmt="%H:%M:%S"))
        logging.getLogger("CryptoBot").addHandler(handler)

    def _save_settings(self):
        self.settings.set("api_key", self.api_key_input.text().strip())
        self.settings.set("api_secret", self.api_secret_input.text().strip())
        self.settings.set("max_positions", self.max_pos_spin.value())
        self.settings.set("max_risk_per_trade", self.risk_spin.value())
        self.settings.set("max_leverage", self.lev_spin.value())
        self.settings.set("demo_mode", self.demo_check.isChecked())
        self.settings.save()
        self.api_client.update_credentials(
            self.api_key_input.text().strip(),
            self.api_secret_input.text().strip()
        )
        logger.info("Settings saved via GUI")
        QMessageBox.information(self, "Saved", "Settings saved successfully!")

    def _start_engine(self):
        if not self.engine.running:
            asyncio.create_task(self.engine.start())
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            logger.info("TradingEngine START requested by user")

    def _stop_engine(self):
        if self.engine.running:
            asyncio.create_task(self.engine.stop())
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            logger.info("TradingEngine STOP requested by user")

    def _manual_scan(self):
        if not self.engine.running:
            logger.warning("Scan requested but engine not running")
            QMessageBox.warning(self, "Engine Not Running", "Start the engine first!")
            return
        logger.info("Manual scan initiated by user")
        # Scan will happen on next loop iteration automatically

    def _update_ui(self):
        try:
            stats = self.engine.get_stats()
            status = "RUNNING" if self.engine.running else "STOPPED"
            balance = stats.get("balance", 0)
            pos_count = stats.get("positions_count", 0)
            daily_pnl = stats.get("daily_pnl", 0)
            win_rate = stats.get("win_rate", 0)
            health = stats.get("health_status", "OK")
            self.status_label.setText(
                f"Status: {status} | Balance: ${balance:.2f} | Positions: {pos_count} | "
                f"Daily PnL: {daily_pnl:+.2f} | Win Rate: {win_rate:.1f}% | Health: {health}"
            )

            # Update positions table
            positions = self.engine.get_open_positions()
            self.pos_table.setRowCount(len(positions))
            for i, p in enumerate(positions):
                self.pos_table.setItem(i, 0, QTableWidgetItem(p.get("symbol", "")))
                self.pos_table.setItem(i, 1, QTableWidgetItem(p.get("side", "")))
                self.pos_table.setItem(i, 2, QTableWidgetItem(f"{p.get('entry_price', 0):.4f}"))
                self.pos_table.setItem(i, 3, QTableWidgetItem(f"{p.get('current_price', 0):.4f}"))
                self.pos_table.setItem(i, 4, QTableWidgetItem(f"{p.get('quantity', 0):.4f}"))
                self.pos_table.setItem(i, 5, QTableWidgetItem(f"{p.get('leverage', 1)}x"))
                pnl = p.get("unrealized_pnl", 0)
                item = QTableWidgetItem(f"{pnl:+.4f}")
                item.setForeground(Qt.GlobalColor.green if pnl >= 0 else Qt.GlobalColor.red)
                self.pos_table.setItem(i, 6, item)
                self.pos_table.setItem(i, 7, QTableWidgetItem(f"{p.get('stop_loss', 0):.4f} / {p.get('take_profit', 0):.4f}"))

            if not self.engine.running:
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
        except Exception as e:
            pass
