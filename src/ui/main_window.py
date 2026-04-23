""" Главное окно приложения торгового бота """
import sys
import asyncio
import threading
from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QStatusBar, QLabel, QPushButton, QMessageBox, QApplication
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPalette
from src.ui.pages.dashboard import DashboardPage
from src.ui.pages.positions import PositionsPage
from src.ui.pages.trades_history import TradesHistoryPage
from src.ui.pages.config import ConfigPanel
from src.ui.pages.logs import LogsPage
from src.ui.pages.system_monitor import SystemMonitorPage
from src.ui.system_tray import SystemTray
from src.config.settings import Settings
from src.core.logger import BotLogger


class EngineInitWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

    def run(self):
        try:
            from src.core.engine.trading_engine import TradingEngine
            from src.core.market.data_fetcher import MarketDataFetcher
            from src.core.scanner.market_scanner import MarketScanner
            from src.core.executor.trade_executor import TradeExecutor
            from src.core.risk.risk_manager import RiskManager
            from src.utils.api_client import AsyncBingXClient
            logger = BotLogger("TradingBot")
            logger.info("Инициализация компонентов торгового движка...")
            api_client = AsyncBingXClient(
                api_key=self.settings.get("api_key", ""),
                api_secret=self.settings.get("api_secret", ""),
                demo_mode=self.settings.get("demo_mode", True)
            )
            data_fetcher = MarketDataFetcher(api_client, self.settings, logger)
            scanner = MarketScanner(api_client, self.settings, logger)
            executor = TradeExecutor(api_client, self.settings, logger)
            risk_manager = RiskManager(api_client, self.settings)
            engine = TradingEngine(
                client=api_client,
                data_fetcher=data_fetcher,
                scanner=scanner,
                executor=executor,
                risk_manager=risk_manager,
                settings=self.settings,
                logger=logger
            )
            logger.info("Торговый движок успешно создан")
            self.finished.emit(engine)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.logger = BotLogger("MainWindow")
        self.engine = None
        self.api_client = None
        self.data_fetcher = None
        self.scanner = None
        self.executor = None
        self.risk_manager = None
        self.setWindowTitle("Crypto Trading Bot - BingX Futures")
        self.setMinimumSize(1200, 800)
        self._init_ui()
        self._init_statusbar()
        self.tray = SystemTray(QApplication.instance(), self, self.logger)
        self.tray.show()
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(1000)
        self._start_engine_init()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        top_panel = QHBoxLayout()
        self.btn_start = QPushButton("▶ Запустить")
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._toggle_engine)
        top_panel.addWidget(self.btn_start)

        self.btn_pause = QPushButton("⏸ Пауза")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._toggle_pause)
        top_panel.addWidget(self.btn_pause)

        self.btn_stop = QPushButton("⏹ Стоп")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_engine)
        top_panel.addWidget(self.btn_stop)

        top_panel.addStretch()
        self.lbl_status = QLabel("⚪ Движок не инициализирован")
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #E0E0E0;")
        top_panel.addWidget(self.lbl_status)
        main_layout.addLayout(top_panel)

        self.tabs = QTabWidget()
        self.dashboard_page = DashboardPage()
        self.tabs.addTab(self.dashboard_page, "📊 Дашборд")
        self.positions_page = PositionsPage()
        self.tabs.addTab(self.positions_page, "📈 Позиции")
        self.trades_page = TradesHistoryPage()
        self.tabs.addTab(self.trades_page, "📋 История")
        self.config_page = ConfigPanel(settings=self.settings)
        self.tabs.addTab(self.config_page, "⚙ Настройки")
        self.logs_page = LogsPage()
        self.tabs.addTab(self.logs_page, "📜 Логи")
        self.monitor_page = SystemMonitorPage()
        self.tabs.addTab(self.monitor_page, "🖥 Система")
        main_layout.addWidget(self.tabs)

    def _init_statusbar(self):
        self.statusbar = self.statusBar()
        self.lbl_balance = QLabel("💰 Баланс: --")
        self.lbl_pnl = QLabel("📊 PnL: --")
        self.lbl_positions = QLabel("📈 Позиций: 0")
        for lbl in [self.lbl_balance, self.lbl_pnl, self.lbl_positions]:
            lbl.setStyleSheet("color: #E0E0E0;")
            self.statusbar.addPermanentWidget(lbl)

    def _start_engine_init(self):
        self.lbl_status.setText("🔄 Инициализация движка...")
        self.worker = EngineInitWorker(self.settings)
        self.worker.finished.connect(self._on_engine_ready)
        self.worker.error.connect(self._on_engine_error)
        self.worker.start()

    def _on_engine_ready(self, engine):
        self.engine = engine
        self.api_client = engine.client
        self.data_fetcher = engine.data_fetcher
        self.scanner = engine.scanner
        self.executor = engine.executor
        self.risk_manager = engine.risk_manager
        self.logger.add_callback(self.logs_page.add_log)
        self.engine.set_update_callback(self._on_engine_update)
        self.btn_start.setEnabled(True)
        self.lbl_status.setText("🟢 Движок готов")
        self.logger.info("Движок инициализирован и готов к работе")

    def _on_engine_error(self, error_msg):
        self.lbl_status.setText(f"🔴 Ошибка: {error_msg[:50]}")
        QMessageBox.critical(self, "Ошибка инициализации", f"Не удалось запустить торговый движок:\n\n{error_msg}")

    def _on_engine_update(self, data: dict):
        if data.get("type") == "status":
            status = data.get("data", {})
            self.lbl_balance.setText(f"💰 Баланс: {status.get('balance', 0):.2f} USDT")
            self.lbl_pnl.setText(f"📊 PnL: {status.get('pnl', 0):.2f}")
            self.lbl_positions.setText(f"📈 Позиций: {status.get('positions', 0)}")
            self.dashboard_page.update_status(status)
        elif data.get("type") == "signals":
            self.dashboard_page.update_signals(data.get("data", []))

    def _toggle_engine(self):
        if self.engine is None:
            return
        if self.engine.is_running():
            self._stop_engine()
        else:
            self._start_engine()

    def _start_engine(self):
        if self.engine:
            self.engine.start()
            self.btn_start.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_stop.setEnabled(True)
            self.lbl_status.setText("🟢 Торговля активна")

    def _stop_engine(self):
        if self.engine:
            self.engine.stop()
            self.btn_start.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.lbl_status.setText("🔴 Движок остановлен")

    def _toggle_pause(self):
        if self.engine is None:
            return
        if self.engine.state.value == "PAUSED":
            self.engine.resume()
            self.btn_pause.setText("⏸ Пауза")
            self.lbl_status.setText("🟢 Торговля активна")
        else:
            self.engine.pause()
            self.btn_pause.setText("▶ Продолжить")
            self.lbl_status.setText("🟡 Торговля на паузе")

    def _update_status(self):
        if self.engine:
            status = self.engine.get_status()
            self.lbl_balance.setText(f"💰 Баланс: {status.get('balance', 0):.2f} USDT")
            self.lbl_pnl.setText(f"📊 PnL: {status.get('pnl', 0):.2f}")
            self.lbl_positions.setText(f"📈 Позиций: {status.get('positions', 0)}")

    def closeEvent(self, event):
        if self.engine:
            self.engine.stop()
        if self.api_client:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.api_client.close())
                loop.close()
            except Exception:
                pass
        event.accept()


# Глобальная тёмная тема (вызывается один раз при запуске)
def apply_dark_theme(app: QApplication):
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.WindowText, QColor(224, 224, 224))
    dark_palette.setColor(QPalette.Base, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.ToolTipBase, QColor(224, 224, 224))
    dark_palette.setColor(QPalette.ToolTipText, QColor(224, 224, 224))
    dark_palette.setColor(QPalette.Text, QColor(224, 224, 224))
    dark_palette.setColor(QPalette.Button, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.ButtonText, QColor(224, 224, 224))
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(dark_palette)
    app.setStyleSheet("""
        QToolTip { color: #E0E0E0; background-color: #2d2d2d; border: 1px solid #555; }
        QTabWidget::pane { border: 1px solid #555; background: #2e2e2e; }
        QTabBar::tab { background: #3c3c3c; color: #E0E0E0; padding: 8px; }
        QTabBar::tab:selected { background: #505050; }
        QPushButton { background-color: #3c3c3c; color: #E0E0E0; border: 1px solid #555; padding: 5px; border-radius: 3px; }
        QPushButton:hover { background-color: #505050; }
        QPushButton:disabled { background-color: #2e2e2e; color: #888; }
        QStatusBar { background: #2e2e2e; color: #E0E0E0; }
        QTableWidget { background-color: #2b2b2b; color: #E0E0E0; gridline-color: #555; }
        QHeaderView::section { background-color: #3c3c3c; color: #E0E0E0; padding: 4px; }
    """)
