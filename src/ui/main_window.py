"""Main GUI window for bot control and monitoring."""
import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QCheckBox,
    QTabWidget, QTextEdit, QTableWidget, QTableWidgetItem,
    QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox,
    QMessageBox, QFileDialog, QSplitter
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
import asyncio


class LogWorker(QThread):
    """Worker thread for async log updates."""
    log_signal = pyqtSignal(str)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.running = True

    def run(self):
        while self.running:
            # Placeholder for log polling
            self.msleep(1000)

    def stop(self):
        self.running = False


class MainWindow(QMainWindow):
    """Главное окно GUI для управления и мониторинга бота."""

    def __init__(self, api_client, settings, engine):
        super().__init__()
        self.api_client = api_client
        self.settings = settings
        self.engine = engine
        self.log_worker = None

        self.setWindowTitle("CryptoBot v10.0 — Neural Adaptive Trading")
        self.setMinimumSize(1200, 800)

        self._build_ui()
        self._setup_timers()
        self._load_settings()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # === TOP BAR ===
        top_bar = QHBoxLayout()

        self.status_label = QLabel("● Остановлен")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        top_bar.addWidget(self.status_label)

        top_bar.addStretch()

        self.btn_start = QPushButton("▶ Запустить")
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 16px;")
        self.btn_start.clicked.connect(self._on_start)
        top_bar.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹ Остановить")
        self.btn_stop.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 8px 16px;")
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_stop.setEnabled(False)
        top_bar.addWidget(self.btn_stop)

        main_layout.addLayout(top_bar)

        # === TABS ===
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Dashboard
        self.tabs.addTab(self._build_dashboard_tab(), "📊 Дашборд")
        # Tab 2: Positions
        self.tabs.addTab(self._build_positions_tab(), "📈 Позиции")
        # Tab 3: Config
        self.tabs.addTab(self._build_config_tab(), "⚙️ Настройки")
        # Tab 4: Logs
        self.tabs.addTab(self._build_logs_tab(), "📝 Логи")
        # Tab 5: Market
        self.tabs.addTab(self._build_market_tab(), "🌐 Рынок")

    def _build_dashboard_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Balance card
        balance_group = QGroupBox("💰 Баланс")
        balance_layout = QVBoxLayout(balance_group)
        self.lbl_balance = QLabel("Загрузка...")
        self.lbl_balance.setStyleSheet("font-size: 24px; font-weight: bold;")
        balance_layout.addWidget(self.lbl_balance)

        self.lbl_daily_pnl = QLabel("Дневной P&L: $0.00")
        self.lbl_daily_pnl.setStyleSheet("font-size: 14px;")
        balance_layout.addWidget(self.lbl_daily_pnl)
        layout.addWidget(balance_group)

        # Stats
        stats_group = QGroupBox("📊 Статистика")
        stats_layout = QHBoxLayout(stats_group)

        self.lbl_open_pos = QLabel("Открытых позиций: 0")
        self.lbl_total_trades = QLabel("Всего сделок: 0")
        self.lbl_win_rate = QLabel("Win Rate: 0%")

        stats_layout.addWidget(self.lbl_open_pos)
        stats_layout.addWidget(self.lbl_total_trades)
        stats_layout.addWidget(self.lbl_win_rate)
        layout.addWidget(stats_group)

        # Active signals
        signals_group = QGroupBox("🔔 Активные сигналы")
        signals_layout = QVBoxLayout(signals_group)
        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(5)
        self.signals_table.setHorizontalHeaderLabels(["Символ", "Сторона", "Тип", "Уверенность", "Время"])
        signals_layout.addWidget(self.signals_table)
        layout.addWidget(signals_group)

        layout.addStretch()
        return widget

    def _build_positions_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(8)
        self.positions_table.setHorizontalHeaderLabels([
            "Символ", "Сторона", "Размер", "Вход", "Тек. цена", "P&L %", "SL", "TP"
        ])
        layout.addWidget(self.positions_table)

        btn_close_selected = QPushButton("❌ Закрыть выбранную")
        btn_close_selected.clicked.connect(self._close_selected_position)
        layout.addWidget(btn_close_selected)

        return widget

    def _build_config_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # API Settings
        api_group = QGroupBox("🔑 API Настройки")
        api_layout = QVBoxLayout(api_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("API Key:"))
        self.txt_api_key = QLineEdit()
        self.txt_api_key.setEchoMode(QLineEdit.Password)
        row1.addWidget(self.txt_api_key)
        api_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("API Secret:"))
        self.txt_api_secret = QLineEdit()
        self.txt_api_secret.setEchoMode(QLineEdit.Password)
        row2.addWidget(self.txt_api_secret)
        api_layout.addLayout(row2)

        self.chk_testnet = QCheckBox("Testnet")
        api_layout.addWidget(self.chk_testnet)

        self.chk_demo = QCheckBox("Demo Mode (без реальных сделок)")
        api_layout.addWidget(self.chk_demo)

        layout.addWidget(api_group)

        # Risk Settings
        risk_group = QGroupBox("⚠️ Риск-менеджмент")
        risk_layout = QVBoxLayout(risk_group)

        row_r1 = QHBoxLayout()
        row_r1.addWidget(QLabel("Плечо:"))
        self.spin_leverage = QSpinBox()
        self.spin_leverage.setRange(1, 125)
        self.spin_leverage.setValue(5)
        row_r1.addWidget(self.spin_leverage)
        risk_layout.addLayout(row_r1)

        row_r2 = QHBoxLayout()
        row_r2.addWidget(QLabel("Риск на сделку %:"))
        self.spin_risk = QDoubleSpinBox()
        self.spin_risk.setRange(0.1, 10.0)
        self.spin_risk.setValue(2.0)
        self.spin_risk.setSingleStep(0.1)
        row_r2.addWidget(self.spin_risk)
        risk_layout.addLayout(row_r2)

        row_r3 = QHBoxLayout()
        row_r3.addWidget(QLabel("Макс позиций:"))
        self.spin_max_pos = QSpinBox()
        self.spin_max_pos.setRange(1, 20)
        self.spin_max_pos.setValue(3)
        row_r3.addWidget(self.spin_max_pos)
        risk_layout.addLayout(row_r3)

        layout.addWidget(risk_group)

        # Trading Settings
        trade_group = QGroupBox("📈 Торговля")
        trade_layout = QVBoxLayout(trade_group)

        row_t1 = QHBoxLayout()
        row_t1.addWidget(QLabel("Символы (через запятую):"))
        self.txt_symbols = QLineEdit("BTC-USDT,ETH-USDT,SOL-USDT,XRP-USDT")
        row_t1.addWidget(self.txt_symbols)
        trade_layout.addLayout(row_t1)

        row_t2 = QHBoxLayout()
        row_t2.addWidget(QLabel("Таймфреймы:"))
        self.txt_timeframes = QLineEdit("15m,1h,4h,1d")
        row_t2.addWidget(self.txt_timeframes)
        trade_layout.addLayout(row_t2)

        layout.addWidget(trade_group)

        # Save button
        self.btn_save_config = QPushButton("💾 Сохранить настройки")
        self.btn_save_config.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 10px;")
        self.btn_save_config.clicked.connect(self._save_config)
        layout.addWidget(self.btn_save_config)

        layout.addStretch()
        return widget

    def _build_logs_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas, monospace; font-size: 12px;")
        layout.addWidget(self.log_text)

        btn_clear = QPushButton("🗑 Очистить")
        btn_clear.clicked.connect(self.log_text.clear)
        layout.addWidget(btn_clear)

        return widget

    def _build_market_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.market_table = QTableWidget()
        self.market_table.setColumnCount(5)
        self.market_table.setHorizontalHeaderLabels(["Символ", "Цена", "Изм. 24h", "Объём", "Действие"])
        layout.addWidget(self.market_table)

        btn_refresh = QPushButton("🔄 Обновить")
        btn_refresh.clicked.connect(self._refresh_market)
        layout.addWidget(btn_refresh)

        return widget

    def _setup_timers(self):
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_ui)
        self.update_timer.start(2000)  # Update every 2 seconds

    def _load_settings(self):
        self.txt_api_key.setText(self.settings.get("api_key", ""))
        self.txt_api_secret.setText(self.settings.get("api_secret", ""))
        self.chk_testnet.setChecked(self.settings.get("testnet", True))
        self.chk_demo.setChecked(self.settings.get("demo_mode", True))
        self.spin_leverage.setValue(self.settings.get("leverage", 5))
        self.spin_risk.setValue(self.settings.get("risk_per_trade", 2.0))
        self.spin_max_pos.setValue(self.settings.get("max_positions", 3))
        self.txt_symbols.setText(",".join(self.settings.get("symbols", ["BTC-USDT", "ETH-USDT"])))
        self.txt_timeframes.setText(",".join(self.settings.get("timeframes", ["15m", "1h", "4h", "1d"])))

    def _save_config(self):
        self.settings.set("api_key", self.txt_api_key.text().strip())
        self.settings.set("api_secret", self.txt_api_secret.text().strip())
        self.settings.set("testnet", self.chk_testnet.isChecked())
        self.settings.set("demo_mode", self.chk_demo.isChecked())
        self.settings.set("leverage", self.spin_leverage.value())
        self.settings.set("risk_per_trade", self.spin_risk.value())
        self.settings.set("max_positions", self.spin_max_pos.value())
        self.settings.set("symbols", [s.strip() for s in self.txt_symbols.text().split(",") if s.strip()])
        self.settings.set("timeframes", [t.strip() for t in self.txt_timeframes.text().split(",") if t.strip()])

        QMessageBox.information(self, "Сохранено", "Настройки успешно сохранены!")

    def _on_start(self):
        self.engine.running = True
        self.status_label.setText("● Работает")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_text.append("[INFO] Бот запущен")

    def _on_stop(self):
        self.engine.running = False
        self.status_label.setText("● Остановлен")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.log_text.append("[INFO] Бот остановлен")

    def _update_ui(self):
        # Update positions table
        positions = getattr(self.engine, "positions", [])
        self.positions_table.setRowCount(len(positions))
        for i, pos in enumerate(positions):
            self.positions_table.setItem(i, 0, QTableWidgetItem(pos.symbol))
            self.positions_table.setItem(i, 1, QTableWidgetItem(pos.side))
            self.positions_table.setItem(i, 2, QTableWidgetItem(str(pos.quantity)))
            self.positions_table.setItem(i, 3, QTableWidgetItem(str(pos.entry_price)))
            self.positions_table.setItem(i, 4, QTableWidgetItem("—"))
            self.positions_table.setItem(i, 5, QTableWidgetItem("—"))
            self.positions_table.setItem(i, 6, QTableWidgetItem(str(pos.stop_loss)))
            self.positions_table.setItem(i, 7, QTableWidgetItem(str(pos.take_profit)))

        self.lbl_open_pos.setText(f"Открытых позиций: {len(positions)}")

    def _close_selected_position(self):
        selected = self.positions_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Внимание", "Выберите позицию для закрытия")
            return
        row = selected[0].row()
        positions = getattr(self.engine, "positions", [])
        if row < len(positions):
            pos = positions[row]
            QMessageBox.information(self, "Закрытие", f"Закрытие позиции {pos.symbol}...")
            # In real implementation, call order_manager.close_position

    def _refresh_market(self):
        self.log_text.append("[INFO] Обновление данных рынка...")
        # Placeholder for market data refresh

    def closeEvent(self, event):
        if self.log_worker:
            self.log_worker.stop()
            self.log_worker.wait()
        event.accept()
