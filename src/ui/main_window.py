#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MainWindow — полностью переработанный thread-safe интерфейс.
Никакого прямого доступа к UI из фонового потока. Всё через pyqtSignal.
"""
import sys
import os
import asyncio
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QTabWidget, QSplitter, QStatusBar, QMessageBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QFrame,
    QGridLayout, QFileDialog, QApplication
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QColor, QFont, QPalette

from src.config.settings import Settings
from src.core.logger import BotLogger
from src.core.engine.trading_engine import TradingEngine
from src.utils.api_client import AsyncBingXClient

DARK_STYLESHEET = """
QMainWindow { background-color: #0d1117; color: #c9d1d9; }
QWidget { background-color: #0d1117; color: #c9d1d9; }
QTextEdit, QLineEdit {
    background-color: #161b22; color: #c9d1d9; border: 1px solid #30363d;
    border-radius: 6px; padding: 6px; font-family: Consolas, monospace;
}
QPushButton {
    background-color: #238636; color: #ffffff; border: none;
    border-radius: 6px; padding: 8px 16px; font-weight: bold;
}
QPushButton:hover { background-color: #2ea043; }
QPushButton:disabled { background-color: #30363d; color: #8b949e; }
QPushButton#danger { background-color: #da3633; }
QPushButton#danger:hover { background-color: #f85149; }
QPushButton#secondary { background-color: #1f6feb; }
QPushButton#secondary:hover { background-color: #388bfd; }
QGroupBox {
    border: 1px solid #30363d; border-radius: 8px; margin-top: 10px;
    padding-top: 10px; font-weight: bold; color: #58a6ff;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; }
QTabWidget::pane { border: 1px solid #30363d; background-color: #0d1117; }
QTabBar::tab {
    background-color: #161b22; color: #8b949e; padding: 8px 16px;
    border: 1px solid #30363d; border-bottom: none;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
}
QTabBar::tab:selected { background-color: #0d1117; color: #c9d1d9; border-bottom: 2px solid #58a6ff; }
QTableWidget {
    background-color: #161b22; color: #c9d1d9; border: 1px solid #30363d;
    gridline-color: #30363d; alternate-background-color: #1c2128;
}
QHeaderView::section {
    background-color: #161b22; color: #c9d1d9; padding: 6px;
    border: 1px solid #30363d; font-weight: bold;
}
QStatusBar { background-color: #161b22; color: #8b949e; }
QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #161b22; color: #c9d1d9; border: 1px solid #30363d;
    border-radius: 4px; padding: 4px;
}
QCheckBox { color: #c9d1d9; }
QProgressBar {
    border: 1px solid #30363d; border-radius: 4px; text-align: center;
    background-color: #161b22; color: #c9d1d9;
}
QProgressBar::chunk { background-color: #238636; border-radius: 4px; }
QScrollArea { border: none; }
QFrame#card {
    background-color: #161b22; border: 1px solid #30363d;
    border-radius: 8px; padding: 12px;
}
QLabel#metric { font-size: 18px; font-weight: bold; color: #58a6ff; }
QLabel#metric_label { font-size: 11px; color: #8b949e; }
QLabel#positive { color: #3fb950; }
QLabel#negative { color: #f85149; }
"""

def apply_dark_theme(app):
    app.setStyleSheet(DARK_STYLESHEET)


class QtLogHandler(logging.Handler):
    """Logging handler, который эмитит pyqtSignal. Безопасен для межпоточного использования."""
    def __init__(self, signal):
        super().__init__()
        self.signal = signal
        self.setFormatter(logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%H:%M:%S"
        ))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.signal.emit(msg, record.levelno)
        except Exception:
            pass


class AsyncThread(QThread):
    """Фоновый поток с asyncio event loop. Все логи идут через pyqtSignal."""
    log_signal = pyqtSignal(str, int)
    stats_signal = pyqtSignal(dict)

    def __init__(self, engine: TradingEngine):
        super().__init__()
        self.engine = engine
        self.loop = None
        self._qt_handler = None

    def run(self):
        # Подключаем логгер к UI через сигнал (thread-safe)
        self._qt_handler = QtLogHandler(self.log_signal)
        self._qt_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(self._qt_handler)
        # Также подключаем конкретные логгеры
        for name in ["TradingEngine", "AsyncBingXClient", "RiskManager", "MainWindow", "TradeExecutor", "MarketScanner"]:
            logging.getLogger(name).addHandler(self._qt_handler)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.engine.start())
            while self.engine.running:
                self.loop.run_until_complete(asyncio.sleep(2))
                try:
                    stats = self.engine.get_stats()
                    self.stats_signal.emit(stats)
                except Exception as e:
                    self.log_signal.emit(f"⚠️ Ошибка получения stats: {e}", 40)
        except Exception as e:
            self.log_signal.emit(f"❌ Ошибка потока: {e}", 50)
        finally:
            if self._qt_handler:
                logging.getLogger().removeHandler(self._qt_handler)
            self.loop.close()

    def stop(self):
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.engine.stop(), self.loop)


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.logger = BotLogger("MainWindow", level=settings.get("log_level", "INFO"))
        self.engine = None
        self.thread = None
        self.api_client = None
        self._start_time = time.time()

        # Хеши для отслеживания изменений (чтобы не перерисовывать таблицы без нужды)
        self._last_positions_hash = None
        self._last_history_hash = None
        self._last_signals_hash = None
        self._last_stats = {}

        self.setWindowTitle("Crypto Trading Bot v2.1")
        self.setMinimumSize(1400, 900)

        self._setup_ui()
        self._setup_timers()
        self.logger.info("📝 Логгер инициализирован. Логи: logs/")

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # ===== TOP BAR =====
        top = QHBoxLayout()

        self.btn_start = QPushButton("▶  СТАРТ")
        self.btn_start.setObjectName("secondary")
        self.btn_start.setMinimumWidth(100)
        self.btn_start.clicked.connect(self._start_engine)
        top.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹  СТОП")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.setMinimumWidth(100)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_engine)
        top.addWidget(self.btn_stop)

        top.addSpacing(20)

        self._add_metric_card(top, "💰 Баланс", "lbl_balance", "0.00 USDT")
        self._add_metric_card(top, "📊 PnL день", "lbl_daily_pnl", "0.00")
        self._add_metric_card(top, "📈 Win Rate", "lbl_winrate", "0%")
        self._add_metric_card(top, "🔄 Позиций", "lbl_positions", "0")
        self._add_metric_card(top, "⏱️ Latency", "lbl_latency", "0 ms")

        top.addStretch()

        self.lbl_status = QLabel("⏸ Остановлен")
        self.lbl_status.setStyleSheet("color: #f85149; font-weight: bold; font-size: 14px;")
        top.addWidget(self.lbl_status)

        layout.addLayout(top)

        # ===== TABS =====
        self.tabs = QTabWidget()
        self._setup_logs_tab()
        self._setup_positions_tab()
        self._setup_history_tab()
        self._setup_signals_tab()
        self._setup_settings_tab()
        self._setup_system_tab()
        layout.addWidget(self.tabs)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готов к работе | Настройте API ключи и нажмите СТАРТ")

    def _add_metric_card(self, layout, label, obj_name, value):
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(2)
        lbl_label = QLabel(label)
        lbl_label.setObjectName("metric_label")
        lbl_value = QLabel(value)
        lbl_value.setObjectName("metric")
        setattr(self, obj_name, lbl_value)
        card_layout.addWidget(lbl_label)
        card_layout.addWidget(lbl_value)
        layout.addWidget(card)

    def _setup_logs_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFont(QFont("Consolas", 9))
        l.addWidget(self.txt_log)
        self.tabs.addTab(w, "📝 Логи")

    def _setup_positions_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        self.tbl_positions = QTableWidget()
        self.tbl_positions.setColumnCount(9)
        self.tbl_positions.setHorizontalHeaderLabels([
            "Пара", "Напр.", "Вход", "Текущая", "Qty", "Leverage", "PnL", "PnL %", "Время"
        ])
        self.tbl_positions.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_positions.setAlternatingRowColors(True)
        l.addWidget(self.tbl_positions)
        self.tabs.addTab(w, "📊 Позиции")

    def _setup_history_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        self.tbl_history = QTableWidget()
        self.tbl_history.setColumnCount(8)
        self.tbl_history.setHorizontalHeaderLabels([
            "Время", "Пара", "Напр.", "Вход", "Выход", "PnL", "PnL %", "Причина"
        ])
        self.tbl_history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_history.setAlternatingRowColors(True)
        l.addWidget(self.tbl_history)
        btn_export = QPushButton("📤 Экспорт CSV")
        btn_export.clicked.connect(self._export_history)
        l.addWidget(btn_export)
        self.tabs.addTab(w, "📈 История")

    def _setup_signals_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        self.tbl_signals = QTableWidget()
        self.tbl_signals.setColumnCount(8)
        self.tbl_signals.setHorizontalHeaderLabels([
            "Пара", "Напр.", "Режим", "ADX", "ATR%", "Signal", "RSI", "Тип"
        ])
        self.tbl_signals.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_signals.setAlternatingRowColors(True)
        l.addWidget(self.tbl_signals)
        self.tabs.addTab(w, "🔍 Сигналы")

    def _setup_settings_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(10)

        # API
        g = QGroupBox("🔑 API Настройки")
        gl = QGridLayout()
        gl.addWidget(QLabel("API Key:"), 0, 0)
        self.txt_api_key = QLineEdit(self.settings.get("api_key", ""))
        self.txt_api_key.setEchoMode(QLineEdit.Password)
        gl.addWidget(self.txt_api_key, 0, 1)
        gl.addWidget(QLabel("API Secret:"), 1, 0)
        self.txt_api_secret = QLineEdit(self.settings.get("api_secret", ""))
        self.txt_api_secret.setEchoMode(QLineEdit.Password)
        gl.addWidget(self.txt_api_secret, 1, 1)
        self.chk_demo = QCheckBox("Демо режим")
        self.chk_demo.setChecked(self.settings.get("demo_mode", True))
        gl.addWidget(self.chk_demo, 2, 0, 1, 2)
        g.setLayout(gl)
        l.addWidget(g)

        # Trading
        g = QGroupBox("⚙️ Торговые параметры")
        gl = QGridLayout()
        self._add_setting_combo(gl, "Таймфрейм:", "cmb_timeframe", self.settings.get("timeframe", "15m"),
                               ["1m","5m","15m","30m","1h","4h"], 0)
        self._add_setting_dspin(gl, "Риск на сделку %:", "spn_risk", self.settings.get("max_risk_per_trade", 1.0), 0.1, 10.0, 0.1, 1)
        self._add_setting_spin(gl, "Макс. плечо:", "spn_leverage", self.settings.get("max_leverage", 10), 1, 125, 2)
        self._add_setting_spin(gl, "Макс. позиций:", "spn_max_pos", self.settings.get("max_positions", 2), 1, 20, 3)
        self._add_setting_dspin(gl, "SL %:", "spn_sl", self.settings.get("default_sl_pct", 1.5), 0.1, 20.0, 0.1, 4)
        self._add_setting_dspin(gl, "TP %:", "spn_tp", self.settings.get("default_tp_pct", 3.0), 0.1, 50.0, 0.1, 5)
        self._add_setting_spin(gl, "Интервал сканирования (мин):", "spn_scan", self.settings.get("scan_interval_minutes", 5), 1, 60, 6)
        g.setLayout(gl)
        l.addWidget(g)

        # Risk
        g = QGroupBox("🛡️ Риск-менеджмент")
        gl = QGridLayout()
        self._add_setting_dspin(gl, "Дневной лимит убытков %:", "spn_daily_loss", self.settings.get("daily_loss_limit_percent", 8.0), 1.0, 50.0, 0.5, 0)
        self._add_setting_dspin(gl, "Макс. общий риск %:", "spn_total_risk", self.settings.get("max_total_risk_percent", 5.0), 1.0, 50.0, 0.5, 1)
        self._add_setting_spin(gl, "Макс. ордеров/час:", "spn_max_orders", self.settings.get("max_orders_per_hour", 6), 1, 50, 2)
        self._add_setting_dspin(gl, "Трейлинг активация %:", "spn_trail_act", self.settings.get("trailing_activation", 1.5), 0.1, 10.0, 0.1, 3)
        self._add_setting_dspin(gl, "Трейлинг дистанция %:", "spn_trail_dist", self.settings.get("trailing_stop_distance_percent", 2.0), 0.1, 10.0, 0.1, 4)
        self._add_setting_spin(gl, "Макс. удержание (мин):", "spn_hold", self.settings.get("max_hold_time_minutes", 240), 10, 1440, 5)
        g.setLayout(gl)
        l.addWidget(g)

        # Scanner
        g = QGroupBox("🔍 Параметры сканера")
        gl = QGridLayout()
        self._add_setting_dspin(gl, "Мин. ADX:", "spn_adx", self.settings.get("min_adx", 10), 1.0, 50.0, 1.0, 0)
        self._add_setting_dspin(gl, "Мин. ATR %:", "spn_atr", self.settings.get("min_atr_percent", 0.5), 0.1, 5.0, 0.1, 1)
        self._add_setting_dspin(gl, "Мин. объём 24h:", "spn_vol", self.settings.get("min_volume_24h_usdt", 50000), 1000, 10000000, 1000, 2)
        self._add_setting_dspin(gl, "Мин. сила сигнала:", "spn_signal", self.settings.get("min_signal_strength", 0.25), 0.05, 1.0, 0.05, 3)
        self.chk_mtf = QCheckBox("Мультитаймфрейм (MTF)")
        self.chk_mtf.setChecked(self.settings.get("use_multi_timeframe", True))
        gl.addWidget(self.chk_mtf, 4, 0, 1, 2)
        self.chk_spread = QCheckBox("Фильтр спреда")
        self.chk_spread.setChecked(self.settings.get("use_spread_filter", True))
        gl.addWidget(self.chk_spread, 5, 0, 1, 2)
        g.setLayout(gl)
        l.addWidget(g)

        # Notifications
        g = QGroupBox("📢 Уведомления")
        gl = QGridLayout()
        self.chk_telegram = QCheckBox("Telegram")
        self.chk_telegram.setChecked(self.settings.get("telegram_enabled", False))
        gl.addWidget(self.chk_telegram, 0, 0)
        gl.addWidget(QLabel("Bot Token:"), 1, 0)
        self.txt_tg_token = QLineEdit(self.settings.get("telegram_bot_token", ""))
        gl.addWidget(self.txt_tg_token, 1, 1)
        gl.addWidget(QLabel("Chat ID:"), 2, 0)
        self.txt_tg_chat = QLineEdit(self.settings.get("telegram_chat_id", ""))
        gl.addWidget(self.txt_tg_chat, 2, 1)
        g.setLayout(gl)
        l.addWidget(g)

        btn_save = QPushButton("💾 Сохранить все настройки")
        btn_save.clicked.connect(self._save_settings)
        l.addWidget(btn_save)
        l.addStretch()

        scroll.setWidget(w)
        self.tabs.addTab(scroll, "⚙️ Настройки")

    def _add_setting_combo(self, grid, label, attr_name, value, items, row):
        grid.addWidget(QLabel(label), row, 0)
        widget = QComboBox()
        widget.addItems(items)
        widget.setCurrentText(str(value))
        setattr(self, attr_name, widget)
        grid.addWidget(widget, row, 1)

    def _add_setting_spin(self, grid, label, attr_name, value, min_v, max_v, row):
        grid.addWidget(QLabel(label), row, 0)
        widget = QSpinBox()
        widget.setRange(min_v, max_v)
        widget.setValue(int(value))
        setattr(self, attr_name, widget)
        grid.addWidget(widget, row, 1)

    def _add_setting_dspin(self, grid, label, attr_name, value, min_v, max_v, step, row):
        grid.addWidget(QLabel(label), row, 0)
        widget = QDoubleSpinBox()
        widget.setRange(min_v, max_v)
        widget.setValue(float(value))
        widget.setSingleStep(step)
        widget.setDecimals(2 if step >= 0.1 else 3)
        setattr(self, attr_name, widget)
        grid.addWidget(widget, row, 1)

    def _setup_system_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(12)

        grid = QGridLayout()
        grid.setSpacing(10)
        self.sys_labels = {}
        metrics = [
            ("CPU", "sys_cpu"), ("RAM", "sys_ram"), ("Диск", "sys_disk"),
            ("API Latency", "sys_latency"), ("Uptime", "sys_uptime"),
            ("Потоков", "sys_threads"), ("Процессов", "sys_procs"),
            ("Сетевые ошибки", "sys_net_err"),
        ]
        for i, (label, key) in enumerate(metrics):
            card = QFrame()
            card.setObjectName("card")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 8, 12, 8)
            lbl_name = QLabel(label)
            lbl_name.setObjectName("metric_label")
            lbl_val = QLabel("--")
            lbl_val.setObjectName("metric")
            self.sys_labels[key] = lbl_val
            cl.addWidget(lbl_name)
            cl.addWidget(lbl_val)
            grid.addWidget(card, i // 4, i % 4)
        l.addLayout(grid)

        self.lbl_api_status = QLabel("🔴 API: Не подключено")
        self.lbl_api_status.setStyleSheet("font-size: 14px; font-weight: bold;")
        l.addWidget(self.lbl_api_status)

        self.lbl_last_error = QLabel("Последняя ошибка: --")
        self.lbl_last_error.setStyleSheet("color: #f85149;")
        l.addWidget(self.lbl_last_error)

        self.txt_config_summary = QTextEdit()
        self.txt_config_summary.setReadOnly(True)
        self.txt_config_summary.setMaximumHeight(200)
        l.addWidget(QLabel("Текущая конфигурация:"))
        l.addWidget(self.txt_config_summary)
        l.addStretch()
        self.tabs.addTab(w, "🖥️ Система")

    def _setup_timers(self):
        # Таймер для таблиц (тяжёлая отрисовка) — реже
        self._table_timer = QTimer()
        self._table_timer.timeout.connect(self._update_tables)
        self._table_timer.start(3000)  # каждые 3 сек

    def _log_to_ui(self, msg: str, level: int = 20):
        """Слот для log_signal — вызывается в UI-потоке."""
        color = "#c9d1d9"
        if level >= 50: color = "#f85149"
        elif level >= 40: color = "#f85149"
        elif level >= 30: color = "#d29922"
        elif level <= 10: color = "#8b949e"
        self.txt_log.append(f'<span style="color:{color}">{msg}</span>')
        # Ограничиваем размер лога (иначе QTextEdit тормозит)
        if self.txt_log.document().blockCount() > 500:
            cursor = self.txt_log.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.BlockUnderCursor)
            cursor.removeSelectedText()

    def _update_stats(self, stats: dict):
        """Быстрое обновление метрик (по сигналу каждые 2 сек)."""
        try:
            self._last_stats = stats
            self.lbl_balance.setText(f"{stats.get('balance', 0):.4f} USDT")

            daily_pnl = stats.get('risk_stats', {}).get('daily_pnl', 0)
            self.lbl_daily_pnl.setText(f"{daily_pnl:+.4f}")
            self.lbl_daily_pnl.setStyleSheet(
                f"color: {'#3fb950' if daily_pnl >= 0 else '#f85149'}; font-size: 18px; font-weight: bold;"
            )

            win_rate = stats.get('win_rate', 0)
            self.lbl_winrate.setText(f"{win_rate:.1f}%")

            self.lbl_positions.setText(f"{stats.get('positions_count', 0)}")

            latency = stats.get('api_latency_ms', 0)
            self.lbl_latency.setText(f"{latency:.0f} ms")
            self.lbl_latency.setStyleSheet(
                f"color: {'#3fb950' if latency < 500 else '#f85149' if latency > 2000 else '#d29922'}; "
                f"font-size: 18px; font-weight: bold;"
            )

            # System tab — только текстовые метрики (лёгкие)
            self._update_system_text(stats)
        except Exception as e:
            pass  # Не падаем при ошибке UI

    def _update_tables(self):
        """Обновление таблиц (тяжёлая операция) — по таймеру каждые 3 сек."""
        if not self.engine:
            return
        try:
            stats = self._last_stats

            # Positions — обновляем только если изменились
            pos_hash = stats.get("positions_hash")
            if pos_hash != self._last_positions_hash:
                self._last_positions_hash = pos_hash
                positions = self.engine.get_open_positions()
                self.tbl_positions.setRowCount(len(positions))
                for i, pos in enumerate(positions):
                    self._set_table_item(self.tbl_positions, i, 0, pos.get("symbol", ""))
                    side = pos.get("side", "")
                    self._set_table_item(self.tbl_positions, i, 1, side,
                                         color="#3fb950" if side == "BUY" else "#f85149")
                    self._set_table_item(self.tbl_positions, i, 2, f"{pos.get('entry_price', 0):.4f}")
                    self._set_table_item(self.tbl_positions, i, 3, f"{pos.get('current_price', 0):.4f}")
                    self._set_table_item(self.tbl_positions, i, 4, f"{pos.get('quantity', 0):.6f}")
                    self._set_table_item(self.tbl_positions, i, 5, f"{pos.get('leverage', 1)}x")
                    pnl = pos.get("unrealized_pnl", 0)
                    self._set_table_item(self.tbl_positions, i, 6, f"{pnl:+.4f}",
                                         color="#3fb950" if pnl >= 0 else "#f85149")
                    pnl_pct = pos.get("unrealized_pnl_percent", 0)
                    self._set_table_item(self.tbl_positions, i, 7, f"{pnl_pct:+.2f}%",
                                         color="#3fb950" if pnl_pct >= 0 else "#f85149")
                    entry_time = pos.get("entry_time", "--")
                    if entry_time and entry_time != "--":
                        try:
                            entry_time = entry_time.split("T")[1].split(".")[0]
                        except:
                            pass
                    self._set_table_item(self.tbl_positions, i, 8, str(entry_time))

            # History — обновляем только если изменилась
            hist_hash = stats.get("history_hash")
            if hist_hash != self._last_history_hash:
                self._last_history_hash = hist_hash
                history = self.engine.get_closed_positions()
                self.tbl_history.setRowCount(min(len(history), 50))
                for i, h in enumerate(history[:50]):
                    exit_time = h.get("exit_time", "--")
                    if exit_time and exit_time != "--":
                        try:
                            exit_time = exit_time.split("T")[1].split(".")[0]
                        except:
                            pass
                    self._set_table_item(self.tbl_history, i, 0, str(exit_time))
                    self._set_table_item(self.tbl_history, i, 1, h.get("symbol", ""))
                    self._set_table_item(self.tbl_history, i, 2, h.get("side", ""))
                    self._set_table_item(self.tbl_history, i, 3, f"{h.get('entry_price', 0):.4f}")
                    self._set_table_item(self.tbl_history, i, 4, f"{h.get('exit_price', 0):.4f}")
                    pnl = h.get("realized_pnl", 0)
                    self._set_table_item(self.tbl_history, i, 5, f"{pnl:+.4f}",
                                         color="#3fb950" if pnl >= 0 else "#f85149")
                    pnl_pct = h.get("realized_pnl_percent", 0)
                    self._set_table_item(self.tbl_history, i, 6, f"{pnl_pct:+.2f}%",
                                         color="#3fb950" if pnl_pct >= 0 else "#f85149")
                    self._set_table_item(self.tbl_history, i, 7, h.get("exit_reason", ""))

            # Signals — обновляем только если изменились
            sig_hash = stats.get("signals_hash")
            if sig_hash != self._last_signals_hash:
                self._last_signals_hash = sig_hash
                signals = self.engine.get_last_scan_signals()
                self.tbl_signals.setRowCount(len(signals))
                for i, s in enumerate(signals):
                    ind = s.get("indicators", {})
                    self._set_table_item(self.tbl_signals, i, 0, s.get("symbol", ""))
                    direction = ind.get("signal_direction", "")
                    self._set_table_item(self.tbl_signals, i, 1, direction,
                                         color="#3fb950" if direction == "LONG" else "#f85149" if direction == "SHORT" else "#8b949e")
                    self._set_table_item(self.tbl_signals, i, 2, ind.get("market_regime", ""))
                    self._set_table_item(self.tbl_signals, i, 3, f"{ind.get('adx', 0):.1f}")
                    self._set_table_item(self.tbl_signals, i, 4, f"{ind.get('atr_percent', 0):.2f}%")
                    self._set_table_item(self.tbl_signals, i, 5, f"{ind.get('signal_strength', 0):.2f}")
                    self._set_table_item(self.tbl_signals, i, 6, f"{ind.get('rsi', 0):.1f}")
                    self._set_table_item(self.tbl_signals, i, 7, ind.get("entry_type", ""))

            # Config summary
            if self.txt_config_summary and self.tabs.currentIndex() == 5:  # Только на вкладке Система
                cfg = json.dumps(self.settings.to_dict(), indent=2, ensure_ascii=False)
                self.txt_config_summary.setText(cfg)

        except Exception as e:
            pass

    def _set_table_item(self, table, row, col, text, color=None):
        item = QTableWidgetItem(str(text))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        if color:
            item.setForeground(QColor(color))
        table.setItem(row, col, item)

    def _update_system_text(self, stats):
        """Обновление текстовых метрик системы (лёгкие)."""
        try:
            if not HAS_PSUTIL:
                self.sys_labels["sys_cpu"].setText("N/A")
                self.sys_labels["sys_ram"].setText("N/A")
                self.sys_labels["sys_disk"].setText("N/A")
            else:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                self.sys_labels["sys_cpu"].setText(f"{cpu:.1f}%")
                self.sys_labels["sys_cpu"].setStyleSheet(
                    f"color: {'#f85149' if cpu > 80 else '#3fb950' if cpu < 30 else '#d29922'}; font-size: 18px; font-weight: bold;"
                )
                self.sys_labels["sys_ram"].setText(f"{ram.percent:.1f}%")
                self.sys_labels["sys_ram"].setStyleSheet(
                    f"color: {'#f85149' if ram.percent > 85 else '#3fb950' if ram.percent < 50 else '#d29922'}; font-size: 18px; font-weight: bold;"
                )
                self.sys_labels["sys_disk"].setText(f"{disk.percent:.1f}%")

            self.sys_labels["sys_latency"].setText(f"{stats.get('api_latency_ms', 0):.0f} ms")
            uptime = time.time() - self._start_time
            hours = int(uptime // 3600)
            mins = int((uptime % 3600) // 60)
            secs = int(uptime % 60)
            self.sys_labels["sys_uptime"].setText(f"{hours:02d}:{mins:02d}:{secs:02d}")

            if HAS_PSUTIL:
                self.sys_labels["sys_threads"].setText(str(psutil.Process().num_threads()))
                self.sys_labels["sys_procs"].setText(str(len(psutil.pids())))

            self.sys_labels["sys_net_err"].setText(str(stats.get('risk_stats', {}).get('consecutive_losses', 0)))

            if self.engine and self.engine.running:
                self.lbl_api_status.setText("🟢 API: Подключено")
                self.lbl_api_status.setStyleSheet("font-size: 14px; font-weight: bold; color: #3fb950;")
            else:
                self.lbl_api_status.setText("🔴 API: Не подключено")
                self.lbl_api_status.setStyleSheet("font-size: 14px; font-weight: bold; color: #f85149;")

            last_err = stats.get("last_error", "")
            if last_err:
                self.lbl_last_error.setText(f"Последняя ошибка: {last_err}")
            else:
                self.lbl_last_error.setText("Последняя ошибка: --")
        except Exception:
            pass

    def _start_engine(self):
        try:
            self._save_settings()
            api_key = self.txt_api_key.text().strip()
            api_secret = self.txt_api_secret.text().strip()
            demo_mode = self.chk_demo.isChecked()

            if not demo_mode and (not api_key or not api_secret):
                QMessageBox.warning(self, "Ошибка", "Введите API ключи для реального режима!")
                return

            self.api_client = AsyncBingXClient(
                api_key=api_key, api_secret=api_secret,
                demo_mode=demo_mode, settings=self.settings.to_dict(),
            )
            self.engine = TradingEngine(
                settings=self.settings, logger=self.logger, api_client=self.api_client,
            )

            # НЕ используем set_ui_callback — всё через сигналы!
            self.thread = AsyncThread(self.engine)
            self.thread.log_signal.connect(self._log_to_ui)
            self.thread.stats_signal.connect(self._update_stats)
            self.thread.start()

            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.lbl_status.setText("🟢 Работает")
            self.lbl_status.setStyleSheet("color: #3fb950; font-weight: bold; font-size: 14px;")
            self.status_bar.showMessage(f"Движок запущен | Режим: {'Демо' if demo_mode else 'Реальный'}")
            self.logger.info("▶ Асинхронный торговый движок запущен")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка запуска", str(e))
            self.logger.error(f"Ошибка запуска: {e}")

    def _stop_engine(self):
        if self.thread:
            self.thread.stop()
            self.thread.wait(5000)
            self.thread = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("⏸ Остановлен")
        self.lbl_status.setStyleSheet("color: #f85149; font-weight: bold; font-size: 14px;")
        self.status_bar.showMessage("Движок остановлен")
        self.logger.info("⏹ Торговый движок остановлен")

    def _save_settings(self):
        self.settings.set("api_key", self.txt_api_key.text().strip())
        self.settings.set("api_secret", self.txt_api_secret.text().strip())
        self.settings.set("demo_mode", self.chk_demo.isChecked())
        self.settings.set("timeframe", self.cmb_timeframe.currentText())
        self.settings.set("max_risk_per_trade", self.spn_risk.value())
        self.settings.set("max_leverage", self.spn_leverage.value())
        self.settings.set("max_positions", self.spn_max_pos.value())
        self.settings.set("default_sl_pct", self.spn_sl.value())
        self.settings.set("default_tp_pct", self.spn_tp.value())
        self.settings.set("scan_interval_minutes", int(self.spn_scan.value()))
        self.settings.set("daily_loss_limit_percent", self.spn_daily_loss.value())
        self.settings.set("max_total_risk_percent", self.spn_total_risk.value())
        self.settings.set("max_orders_per_hour", int(self.spn_max_orders.value()))
        self.settings.set("trailing_activation", self.spn_trail_act.value())
        self.settings.set("trailing_stop_distance_percent", self.spn_trail_dist.value())
        self.settings.set("max_hold_time_minutes", int(self.spn_hold.value()))
        self.settings.set("min_adx", self.spn_adx.value())
        self.settings.set("min_atr_percent", self.spn_atr.value())
        self.settings.set("min_volume_24h_usdt", self.spn_vol.value())
        self.settings.set("min_signal_strength", self.spn_signal.value())
        self.settings.set("use_multi_timeframe", self.chk_mtf.isChecked())
        self.settings.set("use_spread_filter", self.chk_spread.isChecked())
        self.settings.set("telegram_enabled", self.chk_telegram.isChecked())
        self.settings.set("telegram_bot_token", self.txt_tg_token.text().strip())
        self.settings.set("telegram_chat_id", self.txt_tg_chat.text().strip())
        self.logger.info("💾 Настройки сохранены")

    def _export_history(self):
        if not self.engine:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт истории", "trades_history.csv", "CSV (*.csv)")
        if path:
            try:
                import csv
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Exit Time", "Symbol", "Side", "Entry", "Exit", "PnL", "PnL %", "Reason"])
                    for h in self.engine.get_closed_positions():
                        writer.writerow([
                            h.get("exit_time", ""), h.get("symbol", ""), h.get("side", ""),
                            h.get("entry_price", 0), h.get("exit_price", 0),
                            h.get("realized_pnl", 0), h.get("realized_pnl_percent", 0),
                            h.get("exit_reason", ""),
                        ])
                QMessageBox.information(self, "Готово", f"История сохранена: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", str(e))

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            reply = QMessageBox.question(self, "Подтверждение",
                "Торговый движок работает. Остановить перед выходом?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self._stop_engine()
            else:
                event.ignore()
                return
        event.accept()
