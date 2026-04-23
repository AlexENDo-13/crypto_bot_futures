"""
Главное окно приложения торгового бота
"""
import sys
import asyncio
import threading
from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QStatusBar, QLabel, QPushButton,
    QMessageBox, QApplication, QSplitter
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QMetaObject, Q_ARG
from PyQt5.QtGui import QFont, QIcon

from src.ui.pages.dashboard import DashboardPage
from src.ui.pages.positions import PositionsPage
from src.ui.pages.trades_history import TradesHistoryPage
from src.ui.pages.config import ConfigPage
from src.ui.pages.logs import LogsPage
from src.ui.pages.system_monitor import SystemMonitorPage
from src.ui.system_tray import SystemTray
from src.config.settings import Settings
from src.core.logger import Logger


class EngineInitWorker(QThread):
    """Поток для асинхронной инициализации движка"""
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

            logger = Logger("TradingBot")
            logger.info("Инициализация компонентов торгового движка...")

            # Создаём клиента API
            api_client = AsyncBingXClient(
                api_key=self.settings.api_key,
                secret_key=self.settings.api_secret,
                demo_mode=self.settings.demo_mode
            )

            # Зависимые компоненты
            data_fetcher = MarketDataFetcher(api_client, self.settings, logger)
            scanner = MarketScanner(api_client, self.settings, logger)
            executor = TradeExecutor(api_client, self.settings, logger)
            risk_manager = RiskManager(api_client, self.settings)

            # Создаём движок с ВСЕМИ обязательными аргументами
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
        self.logger = Logger("MainWindow")
        self.engine = None
        self.api_client = None
        self.data_fetcher = None
        self.scanner = None
        self.executor = None
        self.risk_manager = None

        self.setWindowTitle("Crypto Trading Bot - BingX Futures")
        self.setMinimumSize(1200, 800)

        # Инициализация UI
        self._init_ui()
        self._init_menu()
        self._init_statusbar()

        # Системный трей
        self.tray = SystemTray(self)
        self.tray.show()

        # Таймер обновления статуса
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(1000)

        # Запуск инициализации движка в фоне
        self._start_engine_init()

    def _init_ui(self):
        """Инициализация пользовательского интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Верхняя панель с кнопками управления
        top_panel = QHBoxLayout()
        self.btn_start = QPushButton("▶ Запустить")
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self.start_engine)

        self.btn_stop = QPushButton("⏹ Остановить")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_engine)

        self.btn_pause = QPushButton("⏸ Пауза")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self.pause_engine)

        top_panel.addWidget(self.btn_start)
        top_panel.addWidget(self.btn_stop)
        top_panel.addWidget(self.btn_pause)
        top_panel.addStretch()

        self.label_status = QLabel("Статус: Инициализация...")
        top_panel.addWidget(self.label_status)

        main_layout.addLayout(top_panel)

        # Вкладки
        self.tab_widget = QTabWidget()
        self.dashboard = DashboardPage()
        self.positions_page = PositionsPage()
        self.trades_page = TradesHistoryPage()
        self.config_page = ConfigPage(self.settings)
        self.logs_page = LogsPage()
        self.monitor_page = SystemMonitorPage()

        self.tab_widget.addTab(self.dashboard, "Дашборд")
        self.tab_widget.addTab(self.positions_page, "Позиции")
        self.tab_widget.addTab(self.trades_page, "История сделок")
        self.tab_widget.addTab(self.monitor_page, "Мониторинг")
        self.tab_widget.addTab(self.config_page, "Настройки")
        self.tab_widget.addTab(self.logs_page, "Логи")

        main_layout.addWidget(self.tab_widget)

    def _init_menu(self):
        """Инициализация меню"""
        menubar = self.menuBar()

        # Файл
        file_menu = menubar.addMenu("Файл")
        exit_action = file_menu.addAction("Выход")
        exit_action.triggered.connect(self.close)

        # Вид
        view_menu = menubar.addMenu("Вид")
        view_menu.addAction("Всегда поверх других").setCheckable(True)

        # Помощь
        help_menu = menubar.addMenu("Помощь")
        help_menu.addAction("О программе", self._show_about)

    def _init_statusbar(self):
        """Инициализация строки состояния"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Готов")

    def _start_engine_init(self):
        """Запуск асинхронной инициализации движка"""
        self.worker = EngineInitWorker(self.settings)
        self.worker.finished.connect(self._on_engine_ready)
        self.worker.error.connect(self._on_engine_error)
        self.worker.start()

    def _on_engine_ready(self, engine):
        """Обработчик успешной инициализации движка"""
        self.engine = engine
        self.engine.set_update_callback(self._on_engine_update)

        # Сохраняем ссылки на компоненты для доступа
        self.api_client = engine.client
        self.data_fetcher = engine.data_fetcher
        self.scanner = engine.scanner
        self.executor = engine.executor
        self.risk_manager = engine.risk_manager

        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_pause.setEnabled(False)
        self.label_status.setText("Статус: Готов")
        self.statusbar.showMessage("Движок инициализирован")
        self.logger.info("Главное окно: движок готов к работе")

    def _on_engine_error(self, error_msg):
        """Обработчик ошибки инициализации"""
        self.label_status.setText("Статус: Ошибка инициализации")
        self.statusbar.showMessage(f"Ошибка: {error_msg}")
        self.logger.error(f"Ошибка инициализации движка: {error_msg}")
        QMessageBox.critical(self, "Ошибка", f"Не удалось инициализировать торговый движок:\n{error_msg}")

    def start_engine(self):
        """Запуск торгового движка"""
        if self.engine:
            try:
                self.engine.start()
                self.btn_start.setEnabled(False)
                self.btn_stop.setEnabled(True)
                self.btn_pause.setEnabled(True)
                self.label_status.setText("Статус: Работает")
                self.statusbar.showMessage("Торговый движок запущен")
                self.logger.info("Движок запущен пользователем")
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось запустить движок: {e}")

    def stop_engine(self):
        """Остановка торгового движка"""
        if self.engine:
            try:
                self.engine.stop()
                self.btn_start.setEnabled(True)
                self.btn_stop.setEnabled(False)
                self.btn_pause.setEnabled(False)
                self.label_status.setText("Статус: Остановлен")
                self.statusbar.showMessage("Торговый движок остановлен")
                self.logger.info("Движок остановлен пользователем")
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Ошибка при остановке движка: {e}")

    def pause_engine(self):
        """Пауза торгового движка"""
        if self.engine and hasattr(self.engine, 'pause'):
            try:
                self.engine.pause()
                self.btn_pause.setText("▶ Продолжить")
                self.btn_pause.clicked.disconnect()
                self.btn_pause.clicked.connect(self.resume_engine)
                self.label_status.setText("Статус: Пауза")
                self.statusbar.showMessage("Торговля приостановлена")
                self.logger.info("Движок поставлен на паузу")
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось поставить на паузу: {e}")

    def resume_engine(self):
        """Возобновление работы после паузы"""
        if self.engine and hasattr(self.engine, 'resume'):
            try:
                self.engine.resume()
                self.btn_pause.setText("⏸ Пауза")
                self.btn_pause.clicked.disconnect()
                self.btn_pause.clicked.connect(self.pause_engine)
                self.label_status.setText("Статус: Работает")
                self.statusbar.showMessage("Торговля возобновлена")
                self.logger.info("Движок возобновлён")
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось возобновить: {e}")

    def _on_engine_update(self, data):
        """Обновление данных от движка"""
        # Обновление дашборда
        QMetaObject.invokeMethod(
            self.dashboard, "update_data",
            Qt.QueuedConnection, Q_ARG(object, data)
        )

    def _update_status(self):
        """Периодическое обновление статусной строки"""
        if self.engine:
            try:
                status = self.engine.get_status()
                self.statusbar.showMessage(
                    f"Баланс: {status.get('balance', 0):.2f} USDT | "
                    f"Позиций: {status.get('positions', 0)} | "
                    f"PnL: {status.get('pnl', 0):.2f} USDT"
                )
            except:
                pass

    def _show_about(self):
        """Показать окно 'О программе'"""
        QMessageBox.about(
            self,
            "О программе",
            "<h3>Crypto Trading Bot</h3>"
            "<p>Версия 1.0.0</p>"
            "<p>Торговый бот для BingX Futures с элементами ИИ.</p>"
        )

    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        if self.engine and self.engine.is_running():
            reply = QMessageBox.question(
                self, 'Подтверждение',
                'Торговый движок активен. Остановить и выйти?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.engine.stop()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
