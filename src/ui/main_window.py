#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MainWindow v4.0 — полноценный интерфейс с интегрированным логгером, мониторингом и аварийной остановкой."""
import sys, os, asyncio, threading, time, json, csv
from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QGroupBox,
    QGridLayout, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QLineEdit, QMessageBox, QFileDialog, QProgressBar, QSplitter,
    QHeaderView, QSystemTrayIcon, QMenu, QAction, QApplication,
    QFrame, QScrollArea, QDialog, QDialogButtonBox,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QIcon, QColor

from src.config.settings import Settings
from src.core.engine.trading_engine import TradingEngine
from src.core.logger import BotLogger, QtLogHandler
from src.utils.api_client import AsyncBingXClient
from src.notifications.telegram_notifier import TelegramNotifier

class AsyncWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, coro):
        super().__init__()
        self.coro = coro
    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.coro)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QMainWindow):
    log_signal = pyqtSignal(str)

    def __init__(self, settings: Settings, logger: BotLogger = None, healing_monitor=None):
        super().__init__()
        self.settings = settings
        self.healing_monitor = healing_monitor
        self.logger = logger
        self.setWindowTitle("Crypto Trading Bot v4.0")
        self.setGeometry(100, 100, 1500, 950)

        self.api_client = None
        self.trading_engine = None
        self.telegram = None
        self._running = False
        self._ui_logger_handler = None

        self._init_ui()
        self._init_timers()
        self._init_tray()
        self._apply_settings()
        self._connect_logger()

    def _connect_logger(self):
        if self.logger:
            self.log_signal.connect(self._append_log)
            self._ui_logger_handler = QtLogHandler(lambda msg: self.log_signal.emit(msg))
            self.logger.add_ui_handler(self._ui_logger_handler)

    def _append_log(self, msg):
        self.log_text.append(msg)
        if self.log_text.document().blockCount() > 2000:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.BlockUnderCursor)
            cursor.removeSelectedText()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header = QHBoxLayout()
        self.status_label = QLabel("⏹ Остановлен")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff4444;")
        header.addWidget(self.status_label)

        self.balance_label = QLabel("Баланс: --")
        self.balance_label.setStyleSheet("font-size: 14px; color: #00ff88;")
        header.addWidget(self.balance_label)

        self.pnl_label = QLabel("PnL: --")
        self.pnl_label.setStyleSheet("font-size: 14px;")
        header.addWidget(self.pnl_label)

        self.win_rate_label = QLabel("Win Rate: --")
        header.addWidget(self.win_rate_label)

        header.addStretch()

        self.btn_start = QPushButton("▶ СТАРТ")
        self.btn_start.setStyleSheet("background-color: #00aa44; color: white; font-weight: bold; padding: 8px 20px;")
        self.btn_start.clicked.connect(self.start_bot)
        header.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹ СТОП")
        self.btn_stop.setStyleSheet("background-color: #aa2222; color: white; font-weight: bold; padding: 8px 20px;")
        self.btn_stop.clicked.connect(self.stop_bot)
        self.btn_stop.setEnabled(False)
        header.addWidget(self.btn_stop)

        self.btn_emergency = QPushButton("🚨 АВАРИЯ")
        self.btn_emergency.setStyleSheet("background-color: #ff0000; color: white; font-weight: bold; padding: 8px 20px;")
        self.btn_emergency.clicked.connect(self.emergency_stop)
        self.btn_emergency.setEnabled(False)
        header.addWidget(self.btn_emergency)

        layout.addLayout(header)

        # Tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self._init_dashboard_tab()
        self._init_positions_tab()
        self._init_history_tab()
        self._init_signals_tab()
        self._init_settings_tab()
        self._init_logs_tab()
        self._init_stats_tab()

    def _init_dashboard_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        cards = QHBoxLayout()
        self.card_positions = self._create_card("Открытые позиции", "0")
        self.card_daily_pnl = self._create_card("Дневной PnL", "0.00")
        self.card_total_trades = self._create_card("Всего сделок", "0")
        self.card_win_rate = self._create_card("Win Rate", "0%")
        self.card_api_health = self._create_card("API Health", "OK")
        cards.addWidget(self.card_positions)
        cards.addWidget(self.card_daily_pnl)
        cards.addWidget(self.card_total_trades)
        cards.addWidget(self.card_win_rate)
        cards.addWidget(self.card_api_health)
        layout.addLayout(cards)
        self.scan_stats_label = QLabel("Последнее сканирование: --")
        layout.addWidget(self.scan_stats_label)
        self.health_label = QLabel("Статус: OK")
        layout.addWidget(self.health_label)
        layout.addStretch()
        self.tabs.addTab(tab, "📊 Дашборд")

    def _create_card(self, title: str, value: str) -> QGroupBox:
        card = QGroupBox(title)
        card.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #444; padding: 10px; }")
        layout = QVBoxLayout(card)
        label = QLabel(value)
        label.setStyleSheet("font-size: 20px; color: #00ff88;")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        card._value_label = label
        return card

    def _init_positions_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(9)
        self.positions_table.setHorizontalHeaderLabels([
            "Пара", "Напр.", "Вход", "Текущая", "Кол-во", "Плечо",
            "SL", "TP", "PnL %"
        ])
        self.positions_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.positions_table)
        self.tabs.addTab(tab, "📈 Позиции")

    def _init_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(8)
        self.history_table.setHorizontalHeaderLabels([
            "Пара", "Напр.", "Вход", "Выход", "PnL", "PnL %", "Причина", "Время"
        ])
        layout.addWidget(self.history_table)
        self.tabs.addTab(tab, "📜 История")

    def _init_signals_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(7)
        self.signals_table.setHorizontalHeaderLabels([
            "Пара", "Напр.", "Цена", "ADX", "ATR %", "Сила", "Режим"
        ])
        layout.addWidget(self.signals_table)
        self.tabs.addTab(tab, "📡 Сигналы")

    def _init_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        grid = QGridLayout(content)
        row = 0
        grid.addWidget(QLabel("API Key:"), row, 0)
        self.api_key_input = QLineEdit(self.settings.get("api_key", ""))
        self.api_key_input.setEchoMode(QLineEdit.Password)
        grid.addWidget(self.api_key_input, row, 1); row += 1
        grid.addWidget(QLabel("API Secret:"), row, 0)
        self.api_secret_input = QLineEdit(self.settings.get("api_secret", ""))
        self.api_secret_input.setEchoMode(QLineEdit.Password)
        grid.addWidget(self.api_secret_input, row, 1); row += 1
        self.demo_check = QCheckBox("Демо-режим")
        self.demo_check.setChecked(self.settings.get("demo_mode", True))
        grid.addWidget(self.demo_check, row, 0, 1, 2); row += 1
        grid.addWidget(QLabel("Интервал сканирования (мин):"), row, 0)
        self.scan_interval_spin = QSpinBox()
        self.scan_interval_spin.setRange(1, 60)
        self.scan_interval_spin.setValue(self.settings.get("scan_interval_minutes", 5))
        grid.addWidget(self.scan_interval_spin, row, 1); row += 1
        grid.addWidget(QLabel("Макс. позиций:"), row, 0)
        self.max_pos_spin = QSpinBox()
        self.max_pos_spin.setRange(1, 20)
        self.max_pos_spin.setValue(self.settings.get("max_positions", 3))
        grid.addWidget(self.max_pos_spin, row, 1); row += 1
        grid.addWidget(QLabel("Макс. плечо:"), row, 0)
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setRange(1, 125)
        self.leverage_spin.setValue(self.settings.get("max_leverage", 10))
        grid.addWidget(self.leverage_spin, row, 1); row += 1
        grid.addWidget(QLabel("Риск на сделку %:"), row, 0)
        self.risk_spin = QDoubleSpinBox()
        self.risk_spin.setRange(0.1, 10.0)
        self.risk_spin.setSingleStep(0.1)
        self.risk_spin.setValue(self.settings.get("max_risk_per_trade", 1.0))
        grid.addWidget(self.risk_spin, row, 1); row += 1
        grid.addWidget(QLabel("Мин. ADX:"), row, 0)
        self.adx_spin = QDoubleSpinBox()
        self.adx_spin.setRange(0, 50)
        self.adx_spin.setSingleStep(0.5)
        self.adx_spin.setValue(self.settings.get("min_adx", 10))
        grid.addWidget(self.adx_spin, row, 1); row += 1
        grid.addWidget(QLabel("Мин. ATR %:"), row, 0)
        self.atr_spin = QDoubleSpinBox()
        self.atr_spin.setRange(0.05, 5.0)
        self.atr_spin.setSingleStep(0.05)
        self.atr_spin.setValue(self.settings.get("min_atr_percent", 0.5))
        grid.addWidget(self.atr_spin, row, 1); row += 1
        grid.addWidget(QLabel("Мин. объём 24h:"), row, 0)
        self.vol_spin = QSpinBox()
        self.vol_spin.setRange(1000, 10000000)
        self.vol_spin.setSingleStep(10000)
        self.vol_spin.setValue(int(self.settings.get("min_volume_24h_usdt", 50000)))
        grid.addWidget(self.vol_spin, row, 1); row += 1
        grid.addWidget(QLabel("Мин. сила сигнала:"), row, 0)
        self.signal_spin = QDoubleSpinBox()
        self.signal_spin.setRange(0.05, 1.0)
        self.signal_spin.setSingleStep(0.05)
        self.signal_spin.setValue(self.settings.get("min_signal_strength", 0.25))
        grid.addWidget(self.signal_spin, row, 1); row += 1
        self.mtf_check = QCheckBox("Мультитаймфрейм (MTF)")
        self.mtf_check.setChecked(self.settings.get("use_multi_timeframe", True))
        grid.addWidget(self.mtf_check, row, 0, 1, 2); row += 1
        self.trailing_check = QCheckBox("Trailing Stop")
        self.trailing_check.setChecked(self.settings.get("trailing_stop_enabled", True))
        grid.addWidget(self.trailing_check, row, 0, 1, 2); row += 1
        self.partial_check = QCheckBox("Частичное закрытие")
        self.partial_check.setChecked(self.settings.get("partial_close_enabled", True))
        grid.addWidget(self.partial_check, row, 0, 1, 2); row += 1
        self.aggressive_check = QCheckBox("Агрессивная адаптация")
        self.aggressive_check.setChecked(self.settings.get("aggressive_adaptation", True))
        grid.addWidget(self.aggressive_check, row, 0, 1, 2); row += 1
        btn_save = QPushButton("💾 Сохранить настройки")
        btn_save.clicked.connect(self.save_settings)
        grid.addWidget(btn_save, row, 0, 1, 2); row += 1
        btn_export = QPushButton("📤 Экспорт настроек")
        btn_export.clicked.connect(self.export_settings)
        grid.addWidget(btn_export, row, 0, 1, 2); row += 1
        btn_import = QPushButton("📥 Импорт настроек")
        btn_import.clicked.connect(self.import_settings)
        grid.addWidget(btn_import, row, 0, 1, 2); row += 1
        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.tabs.addTab(tab, "⚙️ Настройки")

    def _init_logs_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #1a1a2e; color: #e0e0e0; font-family: monospace;")
        layout.addWidget(self.log_text)
        btn_clear = QPushButton("🗑 Очистить")
        btn_clear.clicked.connect(self.log_text.clear)
        layout.addWidget(btn_clear)
        self.tabs.addTab(tab, "📝 Логи")

    def _init_stats_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setStyleSheet("background-color: #1a1a2e; color: #e0e0e0; font-family: monospace;")
        layout.addWidget(self.stats_text)
        btn_export_csv = QPushButton("📊 Экспорт CSV")
        btn_export_csv.clicked.connect(self.export_csv)
        layout.addWidget(btn_export_csv)
        self.tabs.addTab(tab, "📊 Статистика")

    def _init_timers(self):
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_ui)
        self.update_timer.start(2000)
        self.table_timer = QTimer()
        self.table_timer.timeout.connect(self.update_tables)
        self.table_timer.start(3000)

    def _init_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self)
            self.tray.setToolTip("Crypto Trading Bot v4.0")
            menu = QMenu()
            action_show = QAction("Показать", self)
            action_show.triggered.connect(self.show)
            menu.addAction(action_show)
            action_exit = QAction("Выход", self)
            action_exit.triggered.connect(QApplication.quit)
            menu.addAction(action_exit)
            self.tray.setContextMenu(menu)
            self.tray.show()

    def _apply_settings(self):
        pass

    def start_bot(self):
        if self._running: return
        self.save_settings()
        self.api_client = AsyncBingXClient(
            api_key=self.settings.get("api_key", ""),
            api_secret=self.settings.get("api_secret", ""),
            demo_mode=self.settings.get("demo_mode", True),
            settings=self.settings.to_dict(),
        )
        if self.settings.get("telegram_enabled", False):
            self.telegram = TelegramNotifier(
                token=self.settings.get("telegram_bot_token", ""),
                chat_id=self.settings.get("telegram_chat_id", ""),
                proxy=self.settings.get("telegram_proxy_url", ""),
            )
        self.trading_engine = TradingEngine(self.settings, self.logger, self.api_client, self.telegram)
        self._running = True
        self.status_label.setText("🟢 Работает")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #00ff88;")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_emergency.setEnabled(True)
        worker = AsyncWorker(self.trading_engine.start())
        worker.start()

    def stop_bot(self):
        if not self._running or not self.trading_engine: return
        self._running = False
        self.status_label.setText("⏹ Остановка...")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffaa00;")
        self.btn_emergency.setEnabled(False)
        worker = AsyncWorker(self.trading_engine.stop())
        worker.finished.connect(self._on_stopped)
        worker.start()

    def emergency_stop(self):
        if not self._running: return
        reply = QMessageBox.question(self, "🚨 Аварийная остановка", "Закрыть ВСЕ позиции и остановить бота?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes: return
        self.logger.critical("🚨 АВАРИЙНАЯ ОСТАНОВКА АКТИВИРОВАНА")
        self._running = False
        self.status_label.setText("🚨 АВАРИЯ")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff0000;")
        if self.trading_engine:
            worker = AsyncWorker(self.trading_engine.emergency_stop())
            worker.finished.connect(self._on_stopped)
            worker.start()

    def _on_stopped(self, result):
        self.status_label.setText("⏹ Остановлен")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff4444;")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_emergency.setEnabled(False)
        if self.api_client:
            asyncio.create_task(self.api_client.close())

    def save_settings(self):
        self.settings.set("api_key", self.api_key_input.text())
        self.settings.set("api_secret", self.api_secret_input.text())
        self.settings.set("demo_mode", self.demo_check.isChecked())
        self.settings.set("scan_interval_minutes", self.scan_interval_spin.value())
        self.settings.set("max_positions", self.max_pos_spin.value())
        self.settings.set("max_leverage", self.leverage_spin.value())
        self.settings.set("max_risk_per_trade", self.risk_spin.value())
        self.settings.set("min_adx", self.adx_spin.value())
        self.settings.set("min_atr_percent", self.atr_spin.value())
        self.settings.set("min_volume_24h_usdt", float(self.vol_spin.value()))
        self.settings.set("min_signal_strength", self.signal_spin.value())
        self.settings.set("use_multi_timeframe", self.mtf_check.isChecked())
        self.settings.set("trailing_stop_enabled", self.trailing_check.isChecked())
        self.settings.set("partial_close_enabled", self.partial_check.isChecked())
        self.settings.set("aggressive_adaptation", self.aggressive_check.isChecked())
        QMessageBox.information(self, "Сохранено", "Настройки сохранены")

    def export_settings(self):
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт", "bot_config.json", "JSON (*.json)")
        if path:
            if self.settings.export(path):
                QMessageBox.information(self, "Экспорт", f"Сохранено: {path}")

    def import_settings(self):
        path, _ = QFileDialog.getOpenFileName(self, "Импорт", "", "JSON (*.json)")
        if path:
            if self.settings.import_from(path):
                self._apply_settings()
                QMessageBox.information(self, "Импорт", "Настройки загружены")

    def export_csv(self):
        if not self.trading_engine: return
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт CSV", f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "CSV (*.csv)")
        if not path: return
        try:
            history = self.trading_engine.get_closed_positions()
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Пара", "Напр.", "Вход", "Выход", "PnL", "PnL %", "Причина", "Время"])
                for h in history:
                    writer.writerow([
                        h.get("symbol", ""), h.get("side", ""), h.get("entry_price", 0),
                        h.get("exit_price", 0), h.get("realized_pnl", 0), h.get("realized_pnl_percent", 0),
                        h.get("exit_reason", ""), h.get("exit_time", "")
                    ])
            QMessageBox.information(self, "Экспорт", f"CSV сохранён: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def update_ui(self):
        if not self.trading_engine: return
        stats = self.trading_engine.get_stats()
        self.balance_label.setText(f"Баланс: ${stats.get('balance', 0):.2f}")
        self.pnl_label.setText(f"PnL: ${stats.get('total_pnl', 0):.2f}")
        self.win_rate_label.setText(f"Win Rate: {stats.get('win_rate', 0):.1f}%")
        self.card_positions._value_label.setText(str(stats.get("positions_count", 0)))
        self.card_daily_pnl._value_label.setText(f"{stats.get('daily_pnl', 0):.2f}")
        self.card_total_trades._value_label.setText(str(stats.get("total_trades", 0)))
        self.card_win_rate._value_label.setText(f"{stats.get('win_rate', 0):.1f}%")
        self.card_api_health._value_label.setText(stats.get("health_status", "OK"))
        scan_stats = stats.get("scan_stats", {})
        self.scan_stats_label.setText(f"Последнее сканирование: всего={scan_stats.get('total', 0)}, прошло={scan_stats.get('passed', 0)}")
        self.health_label.setText(f"Статус: {stats.get('health_status', 'OK')} | Latency: {stats.get('api_latency_ms', 0):.0f}ms")
        risk_stats = stats.get("risk_stats", {})
        strat_stats = stats.get("strategy_stats", {})
        self.stats_text.setHtml(f"""
        <h3>Статистика</h3>
        <b>Баланс:</b> ${stats.get('balance', 0):.2f}<br>
        <b>Начальный баланс:</b> ${stats.get('start_balance', 0):.2f}<br>
        <b>Дневной PnL:</b> ${stats.get('daily_pnl', 0):.2f}<br>
        <b>Всего сделок:</b> {stats.get('total_trades', 0)}<br>
        <b>Побед:</b> {stats.get('winning_trades', 0)}<br>
        <b>Win Rate:</b> {stats.get('win_rate', 0):.1f}%<br>
        <b>Последов. убытков:</b> {risk_stats.get('consecutive_losses', 0)}<br>
        <b>Общий риск:</b> {risk_stats.get('total_risk_exposure', 0):.2f}<br>
        <b>Стратегия:</b> {strat_stats.get('best_strategy', 'default')}<br>
        <b>API Latency:</b> {stats.get('api_latency_ms', 0):.0f}ms<br>
        <b>Uptime:</b> {stats.get('uptime_seconds', 0):.0f}s<br>
        """)

    def update_tables(self):
        if not self.trading_engine: return
        positions = self.trading_engine.get_open_positions()
        self.positions_table.setRowCount(len(positions))
        for i, p in enumerate(positions):
            self.positions_table.setItem(i, 0, QTableWidgetItem(p.get("symbol", "")))
            self.positions_table.setItem(i, 1, QTableWidgetItem(p.get("side", "")))
            self.positions_table.setItem(i, 2, QTableWidgetItem(f"{p.get('entry_price', 0):.4f}"))
            self.positions_table.setItem(i, 3, QTableWidgetItem(f"{p.get('current_price', 0):.4f}"))
            self.positions_table.setItem(i, 4, QTableWidgetItem(f"{p.get('quantity', 0):.6f}"))
            self.positions_table.setItem(i, 5, QTableWidgetItem(str(p.get("leverage", 1))))
            self.positions_table.setItem(i, 6, QTableWidgetItem(f"{p.get('stop_loss_price', 0):.4f}"))
            self.positions_table.setItem(i, 7, QTableWidgetItem(f"{p.get('take_profit_price', 0):.4f}"))
            pnl = p.get("unrealized_pnl_percent", 0)
            item = QTableWidgetItem(f"{pnl:.2f}%")
            item.setForeground(QColor("#00ff88" if pnl >= 0 else "#ff4444"))
            self.positions_table.setItem(i, 8, item)
        history = self.trading_engine.get_closed_positions()
        self.history_table.setRowCount(len(history))
        for i, h in enumerate(history):
            self.history_table.setItem(i, 0, QTableWidgetItem(h.get("symbol", "")))
            self.history_table.setItem(i, 1, QTableWidgetItem(h.get("side", "")))
            self.history_table.setItem(i, 2, QTableWidgetItem(f"{h.get('entry_price', 0):.4f}"))
            self.history_table.setItem(i, 3, QTableWidgetItem(f"{h.get('exit_price', 0):.4f}"))
            pnl = h.get("realized_pnl", 0)
            item = QTableWidgetItem(f"{pnl:.4f}")
            item.setForeground(QColor("#00ff88" if pnl >= 0 else "#ff4444"))
            self.history_table.setItem(i, 4, item)
            self.history_table.setItem(i, 5, QTableWidgetItem(f"{h.get('realized_pnl_percent', 0):.2f}%"))
            self.history_table.setItem(i, 6, QTableWidgetItem(h.get("exit_reason", "")))
            self.history_table.setItem(i, 7, QTableWidgetItem(str(h.get("exit_time", ""))))
        signals = self.trading_engine.get_last_scan_signals()
        self.signals_table.setRowCount(len(signals))
        for i, s in enumerate(signals):
            ind = s.get("indicators", {})
            self.signals_table.setItem(i, 0, QTableWidgetItem(s.get("symbol", "")))
            self.signals_table.setItem(i, 1, QTableWidgetItem(ind.get("signal_direction", "")))
            self.signals_table.setItem(i, 2, QTableWidgetItem(f"{ind.get('close_price', 0):.4f}"))
            self.signals_table.setItem(i, 3, QTableWidgetItem(f"{ind.get('adx', 0):.1f}"))
            self.signals_table.setItem(i, 4, QTableWidgetItem(f"{ind.get('atr_percent', 0):.2f}%"))
            self.signals_table.setItem(i, 5, QTableWidgetItem(f"{ind.get('signal_strength', 0):.2f}"))
            self.signals_table.setItem(i, 6, QTableWidgetItem(ind.get("market_regime", "")))

    def closeEvent(self, event):
        if self._running and self.trading_engine:
            self.stop_bot()
        if self.logger and self._ui_logger_handler:
            self.logger.remove_ui_handler(self._ui_logger_handler)
        event.accept()

def apply_dark_theme(app):
    app.setStyleSheet("""
    QMainWindow, QWidget { background-color: #0f0f1a; color: #e0e0e0; }
    QTabWidget::pane { border: 1px solid #333; background-color: #0f0f1a; }
    QTabBar::tab { background-color: #1a1a2e; color: #aaa; padding: 8px 16px; border: 1px solid #333; }
    QTabBar::tab:selected { background-color: #2a2a4e; color: #fff; }
    QPushButton { background-color: #2a2a4e; color: #fff; border: 1px solid #444; padding: 6px 12px; border-radius: 4px; }
    QPushButton:hover { background-color: #3a3a5e; }
    QTableWidget { background-color: #1a1a2e; color: #e0e0e0; gridline-color: #333; }
    QHeaderView::section { background-color: #2a2a4e; color: #fff; padding: 6px; border: 1px solid #333; }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background-color: #1a1a2e; color: #e0e0e0; border: 1px solid #444; padding: 4px; }
    QCheckBox { color: #e0e0e0; }
    QGroupBox { color: #e0e0e0; border: 1px solid #444; margin-top: 8px; padding-top: 8px; }
    QTextEdit { background-color: #1a1a2e; color: #e0e0e0; border: 1px solid #333; }
    QScrollArea { border: none; }
    """)
