"""
System Tray Module – иконка в трее с управлением и мониторингом.
"""

import sys
import psutil
from pathlib import Path
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication, QStyle
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer, pyqtSignal, QObject


class TraySignals(QObject):
    start_bot = pyqtSignal()
    stop_bot = pyqtSignal()
    scan_now = pyqtSignal()
    show_window = pyqtSignal()


class SystemTray(QSystemTrayIcon):
    def __init__(self, app: QApplication, main_window, logger):
        super().__init__()
        self.app = app
        self.main_window = main_window
        self.logger = logger
        self.engine = None
        self.signals = TraySignals()

        icon_path = Path("src/ui/icon.png")
        if icon_path.exists():
            self.setIcon(QIcon(str(icon_path)))
        else:
            self.setIcon(app.style().standardIcon(QStyle.SP_ComputerIcon))

        self.setVisible(True)
        self.setToolTip("BingX Bot")

        self._create_menu()

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_tray_tooltip)
        self.update_timer.start(5000)

        self.activated.connect(self._on_activated)

    def set_engine(self, engine):
        self.engine = engine

    def _create_menu(self):
        menu = QMenu()

        self.status_action = QAction("⏹ Бот остановлен", self)
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)
        menu.addSeparator()

        show_action = QAction("📊 Показать окно", self)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)

        start_action = QAction("▶ Запустить бота", self)
        start_action.triggered.connect(self._start_bot)
        menu.addAction(start_action)

        stop_action = QAction("⏹ Остановить бота", self)
        stop_action.triggered.connect(self._stop_bot)
        menu.addAction(stop_action)

        scan_action = QAction("🔍 Сканировать сейчас", self)
        scan_action.triggered.connect(self._scan_now)
        menu.addAction(scan_action)

        menu.addSeparator()
        quit_action = QAction("❌ Выход", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def _show_window(self):
        self.signals.show_window.emit()

    def _start_bot(self):
        self.signals.start_bot.emit()

    def _stop_bot(self):
        self.signals.stop_bot.emit()

    def _scan_now(self):
        self.signals.scan_now.emit()

    def _quit_app(self):
        self.signals.stop_bot.emit()
        self.app.quit()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_window()

    def _update_tray_tooltip(self):
        if not self.engine or not self.engine.running:
            self.setToolTip("BingX Bot – Остановлен")
            self.status_action.setText("⏹ Бот остановлен")
            return

        balance = self.engine.balance
        positions = len(self.engine.open_positions)
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent

        self.setToolTip(f"BingX Bot\nБаланс: {balance:.2f} USDT\nПозиций: {positions}\nCPU: {cpu:.1f}% | RAM: {mem:.1f}%")
        self.status_action.setText(f"🟢 Бот работает | {balance:.0f} USDT | {positions} поз.")

    def show_toast(self, title: str, message: str, duration: int = 3):
        self.showMessage(title, message, QSystemTrayIcon.Information, duration * 1000)