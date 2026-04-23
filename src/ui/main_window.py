#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MainWindow — полностью исправленное главное окно.
Совместимость с реальными сигнатурами TradingEngine.
"""
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
            logger = BotLogger("TradingBot")
            logger.info("Инициализация торгового движка...")
            engine = TradingEngine(self.settings)
            logger.info("✅ Торговый движок успешно создан")
            self.finished.emit(engine)
        except Exception as e:
            import traceback
            self.error.emit(f"{str(e)}\n{traceback.format_exc()}")


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.logger = BotLogger("MainWindow")
        self.engine = None
        self.setWindowTitle("Crypto Trading Bot - BingX Futures")
        self.setMinimumSize(1200, 800)
        self._init_ui()
        self._init_statusbar()
        self._start_engine_init()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Top panel
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

        self.btn_scan = QPushButton("🔍 Сканировать")
        self.btn_scan.setEnabled(False)
        self.btn_scan.clicked.connect(self._force_scan)
        top_panel.addWidget(self.btn_scan)

        top_panel.addStretch()
        self.lbl_status = QLabel("⚪ Инициализация...")
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #E0E0E0;")
        top_panel.addWidget(self.lbl_status)
        main_layout.addLayout(top_panel)

        # Tabs
        self.tabs = QTabWidget()

        # Dashboard
        self.dashboard_page = QWidget()
        dash_layout = QVBoxLayout(self.dashboard_page)
        self.dash_status = QLabel("Ожидание инициализации...")
        self.dash_status.setStyleSheet("font-size: 14px; padding: 20px;")
        dash_layout.addWidget(self.dash_status)
        dash_layout.addStretch()
        self.tabs.addTab(self.dashboard_page, "📊 Дашборд")

        # Positions
        self.positions_page = QWidget()
        pos_layout = QVBoxLayout(self.positions_page)
        self.positions_table = QLabel("Нет открытых позиций")
        self.positions_table.setStyleSheet("font-size: 12px; padding: 10px; font-family: monospace;")
        pos_layout.addWidget(self.positions_table)
        pos_layout.addStretch()
        self.tabs.addTab(self.positions_page, "📈 Позиции")

        # History
        self.history_page = QWidget()
        hist_layout = QVBoxLayout(self.history_page)
        self.history_label = QLabel("История сделок пуста")
        hist_layout.addWidget(self.history_label)
        hist_layout.addStretch()
        self.tabs.addTab(self.history_page, "📋 История")

        # Settings
        self.config_page = QWidget()
        cfg_layout = QVBoxLayout(self.config_page)
        cfg_info = QLabel("Настройки загружены из config/bot_config.json")
        cfg_info.setStyleSheet("padding: 20px;")
        cfg_layout.addWidget(cfg_info)

        # Quick settings display
        settings_text = ""
        for key in ["demo_mode", "virtual_balance", "max_positions", "max_risk_per_trade", 
                    "max_leverage", "timeframe", "scan_interval_minutes"]:
            val = self.settings.get(key)
            settings_text += f"{key}: {val}\n"
        self.settings_label = QLabel(settings_text)
        self.settings_label.setStyleSheet("font-family: monospace; padding: 10px;")
        cfg_layout.addWidget(self.settings_label)
        cfg_layout.addStretch()
        self.tabs.addTab(self.config_page, "⚙ Настройки")

        # Logs
        self.logs_page = QWidget()
        logs_layout = QVBoxLayout(self.logs_page)
        self.logs_text = QLabel("Логи будут отображаться здесь...")
        self.logs_text.setStyleSheet("font-family: monospace; font-size: 11px; padding: 10px;")
        self.logs_text.setWordWrap(True)
        logs_layout.addWidget(self.logs_text)
        logs_layout.addStretch()
        self.tabs.addTab(self.logs_page, "📜 Логи")

        main_layout.addWidget(self.tabs)

    def _init_statusbar(self):
        self.statusbar = self.statusBar()
        self.lbl_balance = QLabel("💰 Баланс: --")
        self.lbl_pnl = QLabel("📊 PnL: --")
        self.lbl_positions = QLabel("📈 Позиций: 0")
        for lbl in [self.lbl_balance, self.lbl_pnl, self.lbl_positions]:
            lbl.setStyleSheet("color: #E0E0E0; padding: 5px;")
            self.statusbar.addPermanentWidget(lbl)

    def _start_engine_init(self):
        self.lbl_status.setText("🔄 Инициализация движка...")
        self.worker = EngineInitWorker(self.settings)
        self.worker.finished.connect(self._on_engine_ready)
        self.worker.error.connect(self._on_engine_error)
        self.worker.start()

    def _on_engine_ready(self, engine):
        self.engine = engine
        self.engine.set_update_callback(self._on_engine_update)
        self.btn_start.setEnabled(True)
        self.btn_scan.setEnabled(True)
        self.lbl_status.setText("🟢 Движок готов")
        self.dash_status.setText(
            f"✅ Движок инициализирован\n"
            f"Режим: {'Демо' if self.settings.get('demo_mode') else 'Реальный'}\n"
            f"Баланс: {self.settings.get('virtual_balance', 100)} USDT\n"
            f"Макс. позиций: {self.settings.get('max_positions', 2)}\n"
            f"Таймфрейм: {self.settings.get('timeframe', '15m')}\n"
            f"Нажмите 'Запустить' для начала торговли"
        )
        self.logger.info("Движок инициализирован")

    def _on_engine_error(self, error_msg):
        self.lbl_status.setText(f"🔴 Ошибка: {error_msg[:50]}")
        self.dash_status.setText(f"❌ Ошибка инициализации:\n{error_msg[:500]}")
        QMessageBox.critical(self, "Ошибка", f"Не удалось запустить движок:\n\n{error_msg[:500]}")

    def _on_engine_update(self, data: dict):
        if data.get("type") == "status":
            status = data.get("data", {})
            self.lbl_balance.setText(f"💰 Баланс: {status.get('balance', 0):.2f} USDT")
            self.lbl_pnl.setText(f"📊 PnL: {status.get('pnl', 0):+.2f}")
            self.lbl_positions.setText(f"📈 Позиций: {status.get('positions', 0)}")
            self.dash_status.setText(
                f"Статус: {status.get('state', 'UNKNOWN')}\n"
                f"Баланс: {status.get('balance', 0):.2f} USDT\n"
                f"Реальный баланс: {status.get('real_balance', 0):.2f} USDT\n"
                f"Позиций: {status.get('positions', 0)}\n"
                f"PnL: {status.get('pnl', 0):+.2f}\n"
                f"Дневной PnL: {status.get('daily_pnl', 0):+.2f}"
            )
        elif data.get("type") == "new_position":
            pos = data.get("data", {})
            self._update_positions_display()
        elif data.get("type") == "log":
            log_msg = data.get("data", "")
            current = self.logs_text.text()
            lines = current.split("\n")
            lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {log_msg}")
            if len(lines) > 100:
                lines = lines[-100:]
            self.logs_text.setText("\n".join(lines))

    def _update_positions_display(self):
        if not self.engine:
            return
        positions = self.engine.open_positions
        if not positions:
            self.positions_table.setText("Нет открытых позиций")
            return

        text = "СИМВОЛ    | СТОРОНА | КОЛ-ВО    | ВХОД    | ТЕКУЩАЯ | PnL      | PnL%\n"
        text += "-" * 80 + "\n"
        for sym, pos in positions.items():
            text += (
                f"{sym:<10}| {pos.side.value:<7}| {pos.quantity:<9.4f}|"
                f" {pos.entry_price:<8.4f}| {pos.current_price:<8.4f}|"
                f" {pos.unrealized_pnl:<9.2f}| {pos.unrealized_pnl_percent:<6.2f}%\n"
            )
        self.positions_table.setText(text)

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
            self.btn_scan.setEnabled(True)
            self.lbl_status.setText("🟢 Торговля активна")
            self.logger.info("Торговля запущена")

    def _stop_engine(self):
        if self.engine:
            self.engine.stop()
            self.btn_start.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.btn_scan.setEnabled(False)
            self.lbl_status.setText("🔴 Движок остановлен")

    def _toggle_pause(self):
        if self.engine is None:
            return
        if self.engine._state == "PAUSED":
            self.engine.resume()
            self.btn_pause.setText("⏸ Пауза")
            self.lbl_status.setText("🟢 Торговля активна")
        else:
            self.engine.pause()
            self.btn_pause.setText("▶ Продолжить")
            self.lbl_status.setText("🟡 Торговля на паузе")

    def _force_scan(self):
        if self.engine:
            self.engine.scan_now()
            self.lbl_status.setText("🔍 Сканирование запущено...")

    def _update_status(self):
        if self.engine:
            status = self.engine.get_status()
            self.lbl_balance.setText(f"💰 Баланс: {status.get('balance', 0):.2f} USDT")
            self.lbl_pnl.setText(f"📊 PnL: {status.get('pnl', 0):+.2f}")
            self.lbl_positions.setText(f"📈 Позиций: {status.get('positions', 0)}")
            self._update_positions_display()

    def closeEvent(self, event):
        if self.engine:
            self.engine.stop()
        event.accept()


def apply_dark_theme(app: QApplication):
    """Применяет тёмную тему."""
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
        QLabel { color: #E0E0E0; }
    """)
