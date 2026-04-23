#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MainWindow — полноценное управление ботом через PyQt5 интерфейс.
Все настройки, логи, позиции, аналитика — без необходимости лезть в конфиг.
"""
import sys
import asyncio
import threading
import json
import os
from datetime import datetime
from typing import Dict, List

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QStatusBar, QLabel, QPushButton, QMessageBox, QApplication,
    QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QGroupBox, QFormLayout, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QFrame, QProgressBar, QScrollArea,
    QFileDialog, QDialog, QDialogButtonBox, QPlainTextEdit,
    QListWidget, QListWidgetItem, QInputDialog
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QTextCursor

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
            logger = BotLogger("TradingBot", level=self.settings.get("log_level", "INFO"))
            logger.info("Инициализация торгового движка...")
            engine = TradingEngine(self.settings, logger)
            logger.info("✅ Торговый движок успешно создан")
            self.finished.emit(engine)
        except Exception as e:
            import traceback
            self.error.emit(f"{str(e)}\n{traceback.format_exc()}")


class LogTextEdit(QPlainTextEdit):
    """QPlainTextEdit с автоскроллом и цветным выводом."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(5000)
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                padding: 5px;
            }
        """)

    def append_log(self, text: str, level: int = 20):
        colors = {
            10: "#888888",   # DEBUG
            20: "#d4d4d4",   # INFO
            30: "#ff8c00",   # WARNING
            40: "#ff4444",   # ERROR
            50: "#ff0000",   # CRITICAL
        }
        color = colors.get(level, "#d4d4d4")
        timestamp = datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:#666;">[{timestamp}]</span> <span style="color:{color};">{text}</span>'
        self.appendHtml(html)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class MainWindow(QMainWindow):
    """Главное окно с полным управлением ботом."""

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.logger = BotLogger("MainWindow", level=settings.get("log_level", "INFO"))
        self.engine = None
        self.setWindowTitle("🤖 Crypto Trading Bot — BingX Futures")
        self.setMinimumSize(1400, 900)
        self.resize(1600, 1000)
        self._init_ui()
        self._init_statusbar()
        self._init_timers()
        self._start_engine_init()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # === TOP CONTROL BAR ===
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        self.btn_start = QPushButton("▶ СТАРТ")
        self.btn_start.setStyleSheet("QPushButton { background-color: #2d5a27; color: white; font-weight: bold; padding: 8px 16px; font-size: 12px; } QPushButton:hover { background-color: #3a7a32; }")
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._toggle_engine)
        top_bar.addWidget(self.btn_start)

        self.btn_pause = QPushButton("⏸ ПАУЗА")
        self.btn_pause.setStyleSheet("QPushButton { background-color: #5a4a1a; color: white; font-weight: bold; padding: 8px 16px; font-size: 12px; } QPushButton:hover { background-color: #7a6a2a; }")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._toggle_pause)
        top_bar.addWidget(self.btn_pause)

        self.btn_stop = QPushButton("⏹ СТОП")
        self.btn_stop.setStyleSheet("QPushButton { background-color: #5a1a1a; color: white; font-weight: bold; padding: 8px 16px; font-size: 12px; } QPushButton:hover { background-color: #7a2a2a; }")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_engine)
        top_bar.addWidget(self.btn_stop)

        self.btn_scan = QPushButton("🔍 СКАНИРОВАТЬ")
        self.btn_scan.setStyleSheet("QPushButton { background-color: #1a3a5a; color: white; font-weight: bold; padding: 8px 16px; font-size: 12px; } QPushButton:hover { background-color: #2a5a7a; }")
        self.btn_scan.setEnabled(False)
        self.btn_scan.clicked.connect(self._force_scan)
        top_bar.addWidget(self.btn_scan)

        self.btn_emergency = QPushButton("🚨 ЭКСТРЕННОЕ ЗАКРЫТИЕ")
        self.btn_emergency.setStyleSheet("QPushButton { background-color: #8b0000; color: white; font-weight: bold; padding: 8px 16px; font-size: 12px; } QPushButton:hover { background-color: #aa0000; }")
        self.btn_emergency.setEnabled(False)
        self.btn_emergency.clicked.connect(self._emergency_close)
        top_bar.addWidget(self.btn_emergency)

        self.btn_save = QPushButton("💾 СОХРАНИТЬ НАСТРОЙКИ")
        self.btn_save.setStyleSheet("QPushButton { background-color: #3a3a3a; color: #e0e0e0; padding: 8px 16px; } QPushButton:hover { background-color: #4a4a4a; }")
        self.btn_save.clicked.connect(self._save_settings)
        top_bar.addWidget(self.btn_save)

        top_bar.addStretch()

        self.lbl_status = QLabel("⚪ Инициализация...")
        self.lbl_status.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFA500; padding: 5px;")
        top_bar.addWidget(self.lbl_status)

        main_layout.addLayout(top_bar)

        # === TABS ===
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3c3c3c; background: #252525; }
            QTabBar::tab { background: #2d2d2d; color: #a0a0a0; padding: 10px 20px; font-size: 11px; }
            QTabBar::tab:selected { background: #3c3c3c; color: #ffffff; border-bottom: 2px solid #0078d4; }
            QTabBar::tab:hover { background: #353535; color: #e0e0e0; }
        """)

        self._init_dashboard_tab()
        self._init_positions_tab()
        self._init_settings_tab()
        self._init_analytics_tab()
        self._init_logs_tab()

        main_layout.addWidget(self.tabs)

    def _init_dashboard_tab(self):
        """Вкладка Dashboard — ключевые метрики."""
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)

        # Left panel — metrics
        left = QVBoxLayout()

        # Balance card
        bal_group = QGroupBox("💰 Баланс")
        bal_group.setStyleSheet("QGroupBox { color: #e0e0e0; font-weight: bold; border: 1px solid #3c3c3c; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        bal_layout = QFormLayout()
        self.lbl_balance_total = QLabel("--")
        self.lbl_balance_total.setStyleSheet("font-size: 18px; color: #4CAF50; font-weight: bold;")
        self.lbl_balance_available = QLabel("--")
        self.lbl_balance_real = QLabel("--")
        bal_layout.addRow("Виртуальный:", self.lbl_balance_total)
        bal_layout.addRow("Доступный:", self.lbl_balance_available)
        bal_layout.addRow("Реальный:", self.lbl_balance_real)
        bal_group.setLayout(bal_layout)
        left.addWidget(bal_group)

        # PnL card
        pnl_group = QGroupBox("📊 PnL")
        pnl_group.setStyleSheet("QGroupBox { color: #e0e0e0; font-weight: bold; border: 1px solid #3c3c3c; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        pnl_layout = QFormLayout()
        self.lbl_pnl_daily = QLabel("--")
        self.lbl_pnl_daily.setStyleSheet("font-size: 16px;")
        self.lbl_pnl_weekly = QLabel("--")
        self.lbl_pnl_total = QLabel("--")
        self.lbl_winrate = QLabel("--")
        pnl_layout.addRow("Дневной:", self.lbl_pnl_daily)
        pnl_layout.addRow("Недельный:", self.lbl_pnl_weekly)
        pnl_layout.addRow("Общий:", self.lbl_pnl_total)
        pnl_layout.addRow("Win Rate:", self.lbl_winrate)
        pnl_group.setLayout(pnl_layout)
        left.addWidget(pnl_group)

        # Status card
        status_group = QGroupBox("⚡ Статус")
        status_group.setStyleSheet("QGroupBox { color: #e0e0e0; font-weight: bold; border: 1px solid #3c3c3c; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        status_layout = QFormLayout()
        self.lbl_state = QLabel("ОСТАНОВЛЕН")
        self.lbl_state.setStyleSheet("font-size: 16px; color: #888; font-weight: bold;")
        self.lbl_positions_count = QLabel("0")
        self.lbl_scan_time = QLabel("--")
        self.lbl_next_scan = QLabel("--")
        self.lbl_uptime = QLabel("--")
        status_layout.addRow("Состояние:", self.lbl_state)
        status_layout.addRow("Позиций:", self.lbl_positions_count)
        status_layout.addRow("Последний скан:", self.lbl_scan_time)
        status_layout.addRow("Следующий скан:", self.lbl_next_scan)
        status_layout.addRow("Время работы:", self.lbl_uptime)
        status_group.setLayout(status_layout)
        left.addWidget(status_group)

        left.addStretch()
        layout.addLayout(left, 1)

        # Right panel — positions table
        right = QVBoxLayout()
        pos_label = QLabel("📈 Активные позиции")
        pos_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e0e0e0;")
        right.addWidget(pos_label)

        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(9)
        self.positions_table.setHorizontalHeaderLabels([
            "Символ", "Сторона", "Кол-во", "Вход", "Текущая",
            "SL", "TP", "PnL", "PnL%"
        ])
        self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.positions_table.setStyleSheet("""
            QTableWidget { background: #1e1e1e; color: #e0e0e0; gridline-color: #3c3c3c; }
            QHeaderView::section { background: #2d2d2d; color: #e0e0e0; padding: 5px; border: 1px solid #3c3c3c; }
            QTableWidget::item { padding: 5px; }
            QTableWidget::item:selected { background: #264f78; }
        """)
        self.positions_table.setAlternatingRowColors(True)
        right.addWidget(self.positions_table)
        layout.addLayout(right, 2)

        self.tabs.addTab(page, "📊 Дашборд")

    def _init_positions_tab(self):
        """Вкладка позиций с детальной информацией."""
        page = QWidget()
        layout = QVBoxLayout(page)

        self.positions_detail_table = QTableWidget()
        self.positions_detail_table.setColumnCount(12)
        self.positions_detail_table.setHorizontalHeaderLabels([
            "Символ", "Сторона", "Кол-во", "Вход", "Текущая", "SL", "TP",
            "PnL (USDT)", "PnL (%)", "Плечо", "Стратегия", "Время входа"
        ])
        self.positions_detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.positions_detail_table.setStyleSheet("""
            QTableWidget { background: #1e1e1e; color: #e0e0e0; gridline-color: #3c3c3c; }
            QHeaderView::section { background: #2d2d2d; color: #e0e0e0; padding: 5px; border: 1px solid #3c3c3c; }
        """)
        layout.addWidget(self.positions_detail_table)

        btn_close_selected = QPushButton("❌ Закрыть выбранную позицию")
        btn_close_selected.setStyleSheet("QPushButton { background-color: #5a1a1a; color: white; padding: 8px; } QPushButton:hover { background-color: #7a2a2a; }")
        btn_close_selected.clicked.connect(self._close_selected_position)
        layout.addWidget(btn_close_selected)

        self.tabs.addTab(page, "📈 Позиции")

    def _init_settings_tab(self):
        """Вкладка настроек — полное управление без конфига."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        # === API Settings ===
        api_group = QGroupBox("🔑 API BingX")
        api_group.setStyleSheet("QGroupBox { color: #e0e0e0; font-weight: bold; border: 1px solid #3c3c3c; margin-top: 10px; font-size: 12px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        api_layout = QFormLayout()

        self.inp_api_key = QLineEdit(self.settings.get("api_key", ""))
        self.inp_api_key.setEchoMode(QLineEdit.Password)
        self.inp_api_key.setStyleSheet("QLineEdit { background: #2d2d2d; color: #e0e0e0; border: 1px solid #555; padding: 5px; }")
        api_layout.addRow("API Key:", self.inp_api_key)

        self.inp_api_secret = QLineEdit(self.settings.get("api_secret", ""))
        self.inp_api_secret.setEchoMode(QLineEdit.Password)
        self.inp_api_secret.setStyleSheet("QLineEdit { background: #2d2d2d; color: #e0e0e0; border: 1px solid #555; padding: 5px; }")
        api_layout.addRow("API Secret:", self.inp_api_secret)

        self.chk_demo = QCheckBox("Демо-режим (песочница)")
        self.chk_demo.setChecked(self.settings.get("demo_mode", True))
        self.chk_demo.setStyleSheet("color: #e0e0e0;")
        api_layout.addRow("", self.chk_demo)

        self.inp_virtual_balance = QDoubleSpinBox()
        self.inp_virtual_balance.setRange(1, 1000000)
        self.inp_virtual_balance.setValue(self.settings.get("virtual_balance", 100.0))
        self.inp_virtual_balance.setDecimals(2)
        self.inp_virtual_balance.setSuffix(" USDT")
        self.inp_virtual_balance.setStyleSheet("QDoubleSpinBox { background: #2d2d2d; color: #e0e0e0; border: 1px solid #555; padding: 5px; }")
        api_layout.addRow("Виртуальный баланс:", self.inp_virtual_balance)

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        # === Risk Settings ===
        risk_group = QGroupBox("⚠️ Риск-менеджмент")
        risk_group.setStyleSheet("QGroupBox { color: #e0e0e0; font-weight: bold; border: 1px solid #3c3c3c; margin-top: 10px; font-size: 12px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        risk_layout = QFormLayout()

        self.inp_max_positions = QSpinBox()
        self.inp_max_positions.setRange(1, 20)
        self.inp_max_positions.setValue(self.settings.get("max_positions", 2))
        risk_layout.addRow("Макс. позиций:", self.inp_max_positions)

        self.inp_risk_per_trade = QDoubleSpinBox()
        self.inp_risk_per_trade.setRange(0.1, 20.0)
        self.inp_risk_per_trade.setValue(self.settings.get("max_risk_per_trade", 1.0))
        self.inp_risk_per_trade.setDecimals(2)
        self.inp_risk_per_trade.setSuffix(" %")
        risk_layout.addRow("Риск на сделку:", self.inp_risk_per_trade)

        self.inp_max_leverage = QSpinBox()
        self.inp_max_leverage.setRange(1, 125)
        self.inp_max_leverage.setValue(self.settings.get("max_leverage", 10))
        risk_layout.addRow("Макс. плечо:", self.inp_max_leverage)

        self.inp_sl_pct = QDoubleSpinBox()
        self.inp_sl_pct.setRange(0.1, 20.0)
        self.inp_sl_pct.setValue(self.settings.get("default_sl_pct", 1.5))
        self.inp_sl_pct.setDecimals(2)
        self.inp_sl_pct.setSuffix(" %")
        risk_layout.addRow("Стоп-лосс (ATR x):", self.inp_sl_pct)

        self.inp_tp_pct = QDoubleSpinBox()
        self.inp_tp_pct.setRange(0.1, 50.0)
        self.inp_tp_pct.setValue(self.settings.get("default_tp_pct", 3.0))
        self.inp_tp_pct.setDecimals(2)
        self.inp_tp_pct.setSuffix(" %")
        risk_layout.addRow("Тейк-профит (ATR x):", self.inp_tp_pct)

        self.inp_daily_loss = QDoubleSpinBox()
        self.inp_daily_loss.setRange(1.0, 50.0)
        self.inp_daily_loss.setValue(self.settings.get("daily_loss_limit_percent", 8.0))
        self.inp_daily_loss.setDecimals(2)
        self.inp_daily_loss.setSuffix(" %")
        risk_layout.addRow("Дневной лимит убытков:", self.inp_daily_loss)

        self.inp_max_hold = QSpinBox()
        self.inp_max_hold.setRange(10, 1440)
        self.inp_max_hold.setValue(self.settings.get("max_hold_time_minutes", 240))
        self.inp_max_hold.setSuffix(" мин")
        risk_layout.addRow("Макс. время удержания:", self.inp_max_hold)

        self.chk_anti_martingale = QCheckBox("Anti-Martingale (снижать риск после убытков)")
        self.chk_anti_martingale.setChecked(self.settings.get("anti_martingale_enabled", True))
        self.chk_anti_martingale.setStyleSheet("color: #e0e0e0;")
        risk_layout.addRow("", self.chk_anti_martingale)

        self.chk_weekend_reduce = QCheckBox("Снижать риск по выходным")
        self.chk_weekend_reduce.setChecked(self.settings.get("reduce_risk_on_weekends", True))
        self.chk_weekend_reduce.setStyleSheet("color: #e0e0e0;")
        risk_layout.addRow("", self.chk_weekend_reduce)

        risk_group.setLayout(risk_layout)
        layout.addWidget(risk_group)

        # === Strategy Settings ===
        strat_group = QGroupBox("📈 Стратегия")
        strat_group.setStyleSheet("QGroupBox { color: #e0e0e0; font-weight: bold; border: 1px solid #3c3c3c; margin-top: 10px; font-size: 12px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        strat_layout = QFormLayout()

        self.cmb_timeframe = QComboBox()
        self.cmb_timeframe.addItems(["1m", "5m", "15m", "30m", "1h", "4h"])
        self.cmb_timeframe.setCurrentText(self.settings.get("timeframe", "15m"))
        self.cmb_timeframe.setStyleSheet("QComboBox { background: #2d2d2d; color: #e0e0e0; border: 1px solid #555; padding: 5px; }")
        strat_layout.addRow("Таймфрейм:", self.cmb_timeframe)

        self.inp_scan_interval = QSpinBox()
        self.inp_scan_interval.setRange(1, 60)
        self.inp_scan_interval.setValue(self.settings.get("scan_interval_minutes", 5))
        self.inp_scan_interval.setSuffix(" мин")
        strat_layout.addRow("Интервал сканирования:", self.inp_scan_interval)

        self.inp_min_adx = QDoubleSpinBox()
        self.inp_min_adx.setRange(5, 50)
        self.inp_min_adx.setValue(self.settings.get("min_adx", 15))
        self.inp_min_adx.setDecimals(1)
        strat_layout.addRow("Мин. ADX:", self.inp_min_adx)

        self.inp_min_atr = QDoubleSpinBox()
        self.inp_min_atr.setRange(0.1, 10.0)
        self.inp_min_atr.setValue(self.settings.get("min_atr_percent", 1.0))
        self.inp_min_atr.setDecimals(2)
        self.inp_min_atr.setSuffix(" %")
        strat_layout.addRow("Мин. ATR:", self.inp_min_atr)

        self.inp_min_volume = QDoubleSpinBox()
        self.inp_min_volume.setRange(1000, 10000000)
        self.inp_min_volume.setValue(self.settings.get("min_volume_24h_usdt", 100000))
        self.inp_min_volume.setDecimals(0)
        self.inp_min_volume.setSuffix(" USDT")
        strat_layout.addRow("Мин. объём 24ч:", self.inp_min_volume)

        self.inp_min_signal = QDoubleSpinBox()
        self.inp_min_signal.setRange(0.1, 1.0)
        self.inp_min_signal.setValue(self.settings.get("min_signal_strength", 0.35))
        self.inp_min_signal.setDecimals(2)
        self.inp_min_signal.setSingleStep(0.05)
        strat_layout.addRow("Мин. сила сигнала:", self.inp_min_signal)

        self.chk_mtf = QCheckBox("Multi-Timeframe подтверждение")
        self.chk_mtf.setChecked(self.settings.get("use_multi_timeframe", True))
        self.chk_mtf.setStyleSheet("color: #e0e0e0;")
        strat_layout.addRow("", self.chk_mtf)

        self.chk_trailing = QCheckBox("Трейлинг-стоп")
        self.chk_trailing.setChecked(self.settings.get("trailing_stop_enabled", True))
        self.chk_trailing.setStyleSheet("color: #e0e0e0;")
        strat_layout.addRow("", self.chk_trailing)

        self.inp_trailing_dist = QDoubleSpinBox()
        self.inp_trailing_dist.setRange(0.1, 10.0)
        self.inp_trailing_dist.setValue(self.settings.get("trailing_stop_distance_percent", 2.0))
        self.inp_trailing_dist.setDecimals(2)
        self.inp_trailing_dist.setSuffix(" %")
        strat_layout.addRow("Трейлинг дистанция:", self.inp_trailing_dist)

        self.inp_trailing_act = QDoubleSpinBox()
        self.inp_trailing_act.setRange(0.1, 10.0)
        self.inp_trailing_act.setValue(self.settings.get("trailing_activation", 1.5))
        self.inp_trailing_act.setDecimals(2)
        self.inp_trailing_act.setSuffix(" %")
        strat_layout.addRow("Трейлинг активация:", self.inp_trailing_act)

        strat_group.setLayout(strat_layout)
        layout.addWidget(strat_group)

        # === Filters ===
        filt_group = QGroupBox("🔍 Фильтры")
        filt_group.setStyleSheet("QGroupBox { color: #e0e0e0; font-weight: bold; border: 1px solid #3c3c3c; margin-top: 10px; font-size: 12px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        filt_layout = QFormLayout()

        self.chk_spread = QCheckBox("Фильтр по спреду")
        self.chk_spread.setChecked(self.settings.get("use_spread_filter", True))
        self.chk_spread.setStyleSheet("color: #e0e0e0;")
        filt_layout.addRow("", self.chk_spread)

        self.inp_max_spread = QDoubleSpinBox()
        self.inp_max_spread.setRange(0.01, 2.0)
        self.inp_max_spread.setValue(self.settings.get("max_spread_percent", 0.3))
        self.inp_max_spread.setDecimals(2)
        self.inp_max_spread.setSuffix(" %")
        filt_layout.addRow("Макс. спред:", self.inp_max_spread)

        self.inp_max_funding = QDoubleSpinBox()
        self.inp_max_funding.setRange(-1.0, 1.0)
        self.inp_max_funding.setValue(self.settings.get("max_funding_rate", 0.0))
        self.inp_max_funding.setDecimals(4)
        self.inp_max_funding.setSingleStep(0.0001)
        filt_layout.addRow("Макс. funding rate:", self.inp_max_funding)

        self.chk_bollinger = QCheckBox("Bollinger Bands фильтр")
        self.chk_bollinger.setChecked(self.settings.get("use_bollinger_filter", True))
        self.chk_bollinger.setStyleSheet("color: #e0e0e0;")
        filt_layout.addRow("", self.chk_bollinger)

        self.chk_ichimoku = QCheckBox("Ichimoku фильтр")
        self.chk_ichimoku.setChecked(self.settings.get("use_ichimoku_indicator", True))
        self.chk_ichimoku.setStyleSheet("color: #e0e0e0;")
        filt_layout.addRow("", self.chk_ichimoku)

        filt_group.setLayout(filt_layout)
        layout.addWidget(filt_group)

        # === Symbols Lists ===
        sym_group = QGroupBox("📋 Символы")
        sym_group.setStyleSheet("QGroupBox { color: #e0e0e0; font-weight: bold; border: 1px solid #3c3c3c; margin-top: 10px; font-size: 12px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        sym_layout = QHBoxLayout()

        # Whitelist
        wl_layout = QVBoxLayout()
        wl_label = QLabel("✅ Whitelist (пусто = все)")
        wl_label.setStyleSheet("color: #4CAF50;")
        wl_layout.addWidget(wl_label)
        self.list_whitelist = QListWidget()
        self.list_whitelist.setStyleSheet("QListWidget { background: #1e1e1e; color: #e0e0e0; border: 1px solid #555; }")
        for s in self.settings.get("symbols_whitelist", []):
            self.list_whitelist.addItem(s)
        wl_layout.addWidget(self.list_whitelist)
        btn_add_wl = QPushButton("+ Добавить")
        btn_add_wl.clicked.connect(lambda: self._add_symbol(self.list_whitelist))
        btn_rem_wl = QPushButton("- Удалить")
        btn_rem_wl.clicked.connect(lambda: self._remove_symbol(self.list_whitelist))
        wl_btns = QHBoxLayout()
        wl_btns.addWidget(btn_add_wl)
        wl_btns.addWidget(btn_rem_wl)
        wl_layout.addLayout(wl_btns)
        sym_layout.addLayout(wl_layout)

        # Blacklist
        bl_layout = QVBoxLayout()
        bl_label = QLabel("❌ Blacklist")
        bl_label.setStyleSheet("color: #f44336;")
        bl_layout.addWidget(bl_label)
        self.list_blacklist = QListWidget()
        self.list_blacklist.setStyleSheet("QListWidget { background: #1e1e1e; color: #e0e0e0; border: 1px solid #555; }")
        for s in self.settings.get("blacklist", []):
            self.list_blacklist.addItem(s)
        bl_layout.addWidget(self.list_blacklist)
        btn_add_bl = QPushButton("+ Добавить")
        btn_add_bl.clicked.connect(lambda: self._add_symbol(self.list_blacklist))
        btn_rem_bl = QPushButton("- Удалить")
        btn_rem_bl.clicked.connect(lambda: self._remove_symbol(self.list_blacklist))
        bl_btns = QHBoxLayout()
        bl_btns.addWidget(btn_add_bl)
        bl_btns.addWidget(btn_rem_bl)
        bl_layout.addLayout(bl_btns)
        sym_layout.addLayout(bl_layout)

        sym_group.setLayout(sym_layout)
        layout.addWidget(sym_group)

        # === Notifications ===
        notif_group = QGroupBox("🔔 Уведомления")
        notif_group.setStyleSheet("QGroupBox { color: #e0e0e0; font-weight: bold; border: 1px solid #3c3c3c; margin-top: 10px; font-size: 12px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        notif_layout = QFormLayout()

        self.chk_telegram = QCheckBox("Telegram")
        self.chk_telegram.setChecked(self.settings.get("telegram_enabled", False))
        self.chk_telegram.setStyleSheet("color: #e0e0e0;")
        notif_layout.addRow("", self.chk_telegram)

        self.inp_tg_token = QLineEdit(self.settings.get("telegram_bot_token", ""))
        self.inp_tg_token.setEchoMode(QLineEdit.Password)
        self.inp_tg_token.setStyleSheet("QLineEdit { background: #2d2d2d; color: #e0e0e0; border: 1px solid #555; padding: 5px; }")
        notif_layout.addRow("TG Bot Token:", self.inp_tg_token)

        self.inp_tg_chat = QLineEdit(self.settings.get("telegram_chat_id", ""))
        self.inp_tg_chat.setStyleSheet("QLineEdit { background: #2d2d2d; color: #e0e0e0; border: 1px solid #555; padding: 5px; }")
        notif_layout.addRow("TG Chat ID:", self.inp_tg_chat)

        self.chk_discord = QCheckBox("Discord")
        self.chk_discord.setChecked(self.settings.get("discord_enabled", False))
        self.chk_discord.setStyleSheet("color: #e0e0e0;")
        notif_layout.addRow("", self.chk_discord)

        self.inp_discord_url = QLineEdit(self.settings.get("discord_webhook_url", ""))
        self.inp_discord_url.setEchoMode(QLineEdit.Password)
        self.inp_discord_url.setStyleSheet("QLineEdit { background: #2d2d2d; color: #e0e0e0; border: 1px solid #555; padding: 5px; }")
        notif_layout.addRow("Discord Webhook:", self.inp_discord_url)

        notif_group.setLayout(notif_layout)
        layout.addWidget(notif_group)

        layout.addStretch()
        scroll.setWidget(page)
        self.tabs.addTab(scroll, "⚙ Настройки")

    def _init_analytics_tab(self):
        """Вкладка аналитики."""
        page = QWidget()
        layout = QVBoxLayout(page)

        self.analytics_text = QTextEdit()
        self.analytics_text.setReadOnly(True)
        self.analytics_text.setStyleSheet("""
            QTextEdit { background: #1e1e1e; color: #e0e0e0; border: 1px solid #3c3c3c; padding: 10px; font-family: Consolas; font-size: 12px; }
        """)
        self.analytics_text.setText(
            "📊 Аналитика будет доступна после начала торговли.\n\n"
            "Здесь отображается:\n"
            "• Статистика по стратегиям\n"
            "• Win/Loss ratio\n"
            "• Средний PnL\n"
            "• Просадки\n"
            "• Эффективность индикаторов"
        )
        layout.addWidget(self.analytics_text)

        btn_refresh = QPushButton("🔄 Обновить аналитику")
        btn_refresh.clicked.connect(self._refresh_analytics)
        layout.addWidget(btn_refresh)

        self.tabs.addTab(page, "📊 Аналитика")

    def _init_logs_tab(self):
        """Вкладка логов."""
        page = QWidget()
        layout = QVBoxLayout(page)

        # Log filters
        filter_layout = QHBoxLayout()
        self.chk_log_debug = QCheckBox("DEBUG")
        self.chk_log_debug.setChecked(False)
        self.chk_log_debug.setStyleSheet("color: #888;")
        self.chk_log_info = QCheckBox("INFO")
        self.chk_log_info.setChecked(True)
        self.chk_log_info.setStyleSheet("color: #e0e0e0;")
        self.chk_log_warn = QCheckBox("WARNING")
        self.chk_log_warn.setChecked(True)
        self.chk_log_warn.setStyleSheet("color: #ff8c00;")
        self.chk_log_error = QCheckBox("ERROR")
        self.chk_log_error.setChecked(True)
        self.chk_log_error.setStyleSheet("color: #ff4444;")

        for chk in [self.chk_log_debug, self.chk_log_info, self.chk_log_warn, self.chk_log_error]:
            filter_layout.addWidget(chk)
            chk.stateChanged.connect(self._filter_logs)

        filter_layout.addStretch()
        btn_clear = QPushButton("🗑 Очистить")
        btn_clear.clicked.connect(self._clear_logs)
        filter_layout.addWidget(btn_clear)
        btn_export = QPushButton("📤 Экспорт")
        btn_export.clicked.connect(self._export_logs)
        filter_layout.addWidget(btn_export)
        layout.addLayout(filter_layout)

        self.log_text = LogTextEdit()
        layout.addWidget(self.log_text)

        self.tabs.addTab(page, "📜 Логи")

    def _init_statusbar(self):
        self.statusbar = self.statusBar()
        self.statusbar.setStyleSheet("background: #2e2e2e; color: #e0e0e0;")
        self.lbl_status_balance = QLabel("💰 --")
        self.lbl_status_pnl = QLabel("📊 --")
        self.lbl_status_pos = QLabel("📈 0")
        self.lbl_status_api = QLabel("🔌 --")
        for lbl in [self.lbl_status_balance, self.lbl_status_pnl, self.lbl_status_pos, self.lbl_status_api]:
            lbl.setStyleSheet("color: #e0e0e0; padding: 5px 10px;")
            self.statusbar.addPermanentWidget(lbl)

    def _init_timers(self):
        self._timer_ui = QTimer()
        self._timer_ui.timeout.connect(self._update_ui)
        self._timer_ui.start(1000)

        self._timer_positions = QTimer()
        self._timer_positions.timeout.connect(self._update_positions_display)
        self._timer_positions.start(2000)

        self._start_time = None

    def _start_engine_init(self):
        self.lbl_status.setText("🔄 Инициализация движка...")
        self.log_text.append_log("Инициализация торгового движка...")
        self.worker = EngineInitWorker(self.settings)
        self.worker.finished.connect(self._on_engine_ready)
        self.worker.error.connect(self._on_engine_error)
        self.worker.start()

    def _on_engine_ready(self, engine):
        self.engine = engine
        self.engine.set_ui_callback(self._on_engine_update)
        self.logger.set_ui_callback(self._on_log_message)
        self.btn_start.setEnabled(True)
        self.btn_scan.setEnabled(True)
        self.lbl_status.setText("🟢 Движок готов")
        self.lbl_status_api.setText("🔌 API: OK")
        self.log_text.append_log("✅ Движок инициализирован. Нажмите СТАРТ для торговли.", 20)
        self._update_dashboard()

    def _on_engine_error(self, error_msg):
        self.lbl_status.setText(f"🔴 Ошибка инициализации")
        self.lbl_status_api.setText("🔌 API: ОШИБКА")
        self.log_text.append_log(f"❌ Ошибка инициализации: {error_msg[:200]}", 40)
        QMessageBox.critical(self, "Ошибка", f"Не удалось запустить движок:\n\n{error_msg[:500]}")

    def _on_log_message(self, msg: str, level: int):
        self.log_text.append_log(msg, level)

    def _on_engine_update(self, data: dict):
        if data.get("type") == "status":
            self._update_dashboard()
        elif data.get("type") == "new_position":
            self._update_positions_display()
            pos = data.get("data", {})
            self.log_text.append_log(f"🟢 Новая позиция: {pos.get('symbol', '')} {pos.get('side', '')}", 20)
        elif data.get("type") == "position_closed":
            self._update_positions_display()
            pos = data.get("data", {})
            pnl = pos.get("realized_pnl", 0)
            level = 40 if pnl < 0 else 20
            emoji = "🔴" if pnl < 0 else "🟢"
            self.log_text.append_log(
                f"{emoji} Позиция закрыта: {pos.get('symbol', '')} | PnL: {pnl:+.2f} USDT", level
            )

    def _update_ui(self):
        if self.engine:
            status = self.engine.get_status()
            self.lbl_status_balance.setText(f"💰 {status.get('balance', 0):.2f} USDT")
            self.lbl_status_pnl.setText(f"📊 {status.get('pnl', 0):+.2f}")
            self.lbl_status_pos.setText(f"📈 {status.get('positions', 0)}")

            if self._start_time and status.get("running"):
                uptime = datetime.now() - self._start_time
                self.lbl_uptime.setText(str(uptime).split(".")[0])

            state = status.get("state", "STOPPED")
            colors = {"RUNNING": "#4CAF50", "PAUSED": "#FFA500", "STOPPED": "#888"}
            self.lbl_state.setText(state)
            self.lbl_state.setStyleSheet(f"font-size: 16px; color: {colors.get(state, '#888')}; font-weight: bold;")

    def _update_dashboard(self):
        if not self.engine:
            return
        status = self.engine.get_status()
        self.lbl_balance_total.setText(f"{status.get('balance', 0):.2f} USDT")
        self.lbl_balance_available.setText(f"{status.get('balance', 0):.2f} USDT")
        self.lbl_balance_real.setText(f"{status.get('real_balance', 0):.2f} USDT")
        self.lbl_positions_count.setText(str(status.get("positions", 0)))
        self.lbl_pnl_daily.setText(f"{status.get('daily_pnl', 0):+.2f} USDT")
        self.lbl_pnl_total.setText(f"{status.get('pnl', 0):+.2f} USDT")

    def _update_positions_display(self):
        if not self.engine:
            return
        positions = self.engine.open_positions

        # Dashboard table
        self.positions_table.setRowCount(len(positions))
        for i, (sym, pos) in enumerate(positions.items()):
            items = [
                QTableWidgetItem(sym),
                QTableWidgetItem(pos.side.value),
                QTableWidgetItem(f"{pos.quantity:.6f}"),
                QTableWidgetItem(f"{pos.entry_price:.4f}"),
                QTableWidgetItem(f"{pos.current_price:.4f}"),
                QTableWidgetItem(f"{pos.stop_loss_price:.4f}"),
                QTableWidgetItem(f"{pos.take_profit_price:.4f}"),
                QTableWidgetItem(f"{pos.unrealized_pnl:+.2f}"),
                QTableWidgetItem(f"{pos.unrealized_pnl_percent:+.2f}%"),
            ]
            for j, item in enumerate(items):
                if j == 1:
                    item.setForeground(QColor("#4CAF50" if pos.side.value == "BUY" else "#f44336"))
                if j in [7, 8]:
                    color = "#4CAF50" if pos.unrealized_pnl >= 0 else "#f44336"
                    item.setForeground(QColor(color))
                self.positions_table.setItem(i, j, item)

        # Detail table
        self.positions_detail_table.setRowCount(len(positions))
        for i, (sym, pos) in enumerate(positions.items()):
            items = [
                QTableWidgetItem(sym),
                QTableWidgetItem(pos.side.value),
                QTableWidgetItem(f"{pos.quantity:.6f}"),
                QTableWidgetItem(f"{pos.entry_price:.4f}"),
                QTableWidgetItem(f"{pos.current_price:.4f}"),
                QTableWidgetItem(f"{pos.stop_loss_price:.4f}"),
                QTableWidgetItem(f"{pos.take_profit_price:.4f}"),
                QTableWidgetItem(f"{pos.unrealized_pnl:+.2f}"),
                QTableWidgetItem(f"{pos.unrealized_pnl_percent:+.2f}%"),
                QTableWidgetItem(str(pos.leverage)),
                QTableWidgetItem(pos.strategy),
                QTableWidgetItem(pos.entry_time.strftime("%H:%M:%S") if pos.entry_time else "--"),
            ]
            for j, item in enumerate(items):
                self.positions_detail_table.setItem(i, j, item)

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
            self._start_time = datetime.now()
            self.btn_start.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_stop.setEnabled(True)
            self.btn_scan.setEnabled(True)
            self.btn_emergency.setEnabled(True)
            self.lbl_status.setText("🟢 Торговля активна")
            self.log_text.append_log("▶ Торговля запущена", 20)

    def _stop_engine(self):
        if self.engine:
            self.engine.stop()
            self.btn_start.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.btn_scan.setEnabled(False)
            self.btn_emergency.setEnabled(False)
            self.lbl_status.setText("🔴 Движок остановлен")
            self.log_text.append_log("⏹ Торговля остановлена", 20)
            self._start_time = None

    def _toggle_pause(self):
        if self.engine is None:
            return
        if self.engine._state == "PAUSED":
            self.engine.resume()
            self.btn_pause.setText("⏸ ПАУЗА")
            self.lbl_status.setText("🟢 Торговля активна")
            self.log_text.append_log("▶ Торговля возобновлена", 20)
        else:
            self.engine.pause()
            self.btn_pause.setText("▶ ПРОДОЛЖИТЬ")
            self.lbl_status.setText("🟡 Торговля на паузе")
            self.log_text.append_log("⏸ Торговля на паузе", 30)

    def _force_scan(self):
        if self.engine:
            self.engine.scan_now()
            self.lbl_status.setText("🔍 Сканирование...")
            self.log_text.append_log("🔍 Принудительное сканирование запущено", 20)

    def _emergency_close(self):
        reply = QMessageBox.question(
            self, "🚨 Экстренное закрытие",
            "Закрыть ВСЕ позиции немедленно?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes and self.engine:
            self.log_text.append_log("🚨 ЭКСТРЕННОЕ ЗАКРЫТИЕ ВСЕХ ПОЗИЦИЙ!", 50)
            asyncio.create_task(self.engine.emergency_close_all_async())

    def _close_selected_position(self):
        # TODO: implement selected position close
        pass

    def _save_settings(self):
        """Сохраняет все настройки из UI в config."""
        self.settings.set("api_key", self.inp_api_key.text())
        self.settings.set("api_secret", self.inp_api_secret.text())
        self.settings.set("demo_mode", self.chk_demo.isChecked())
        self.settings.set("virtual_balance", self.inp_virtual_balance.value())
        self.settings.set("max_positions", self.inp_max_positions.value())
        self.settings.set("max_risk_per_trade", self.inp_risk_per_trade.value())
        self.settings.set("max_leverage", self.inp_max_leverage.value())
        self.settings.set("default_sl_pct", self.inp_sl_pct.value())
        self.settings.set("default_tp_pct", self.inp_tp_pct.value())
        self.settings.set("daily_loss_limit_percent", self.inp_daily_loss.value())
        self.settings.set("max_hold_time_minutes", self.inp_max_hold.value())
        self.settings.set("anti_martingale_enabled", self.chk_anti_martingale.isChecked())
        self.settings.set("reduce_risk_on_weekends", self.chk_weekend_reduce.isChecked())
        self.settings.set("timeframe", self.cmb_timeframe.currentText())
        self.settings.set("scan_interval_minutes", self.inp_scan_interval.value())
        self.settings.set("min_adx", self.inp_min_adx.value())
        self.settings.set("min_atr_percent", self.inp_min_atr.value())
        self.settings.set("min_volume_24h_usdt", self.inp_min_volume.value())
        self.settings.set("min_signal_strength", self.inp_min_signal.value())
        self.settings.set("use_multi_timeframe", self.chk_mtf.isChecked())
        self.settings.set("trailing_stop_enabled", self.chk_trailing.isChecked())
        self.settings.set("trailing_stop_distance_percent", self.inp_trailing_dist.value())
        self.settings.set("trailing_activation", self.inp_trailing_act.value())
        self.settings.set("use_spread_filter", self.chk_spread.isChecked())
        self.settings.set("max_spread_percent", self.inp_max_spread.value())
        self.settings.set("max_funding_rate", self.inp_max_funding.value())
        self.settings.set("use_bollinger_filter", self.chk_bollinger.isChecked())
        self.settings.set("use_ichimoku_indicator", self.chk_ichimoku.isChecked())
        self.settings.set("telegram_enabled", self.chk_telegram.isChecked())
        self.settings.set("telegram_bot_token", self.inp_tg_token.text())
        self.settings.set("telegram_chat_id", self.inp_tg_chat.text())
        self.settings.set("discord_enabled", self.chk_discord.isChecked())
        self.settings.set("discord_webhook_url", self.inp_discord_url.text())

        # Whitelist/Blacklist
        whitelist = [self.list_whitelist.item(i).text() for i in range(self.list_whitelist.count())]
        blacklist = [self.list_blacklist.item(i).text() for i in range(self.list_blacklist.count())]
        self.settings.set("symbols_whitelist", whitelist)
        self.settings.set("blacklist", blacklist)

        self.settings.save()
        self.log_text.append_log("💾 Настройки сохранены", 20)
        QMessageBox.information(self, "Сохранено", "Настройки сохранены в config/bot_config.json")

    def _add_symbol(self, list_widget: QListWidget):
        text, ok = QInputDialog.getText(self, "Добавить символ", "Введите символ (например: BTC-USDT):")
        if ok and text:
            list_widget.addItem(text.upper().strip())

    def _remove_symbol(self, list_widget: QListWidget):
        for item in list_widget.selectedItems():
            list_widget.takeItem(list_widget.row(item))

    def _refresh_analytics(self):
        if not self.engine:
            return
        stats = self.engine.get_status()
        text = f"""
📊 АНАЛИТИКА
{'='*50}
Баланс: {stats.get('balance', 0):.2f} USDT
Дневной PnL: {stats.get('daily_pnl', 0):+.2f} USDT
Позиций открыто: {stats.get('positions', 0)}
Состояние: {stats.get('state', 'UNKNOWN')}
Последовательных убытков: {stats.get('consecutive_losses', 0)}

⚙️ Активные настройки:
Риск на сделку: {self.settings.get('max_risk_per_trade', 1.0)}%
Макс. позиций: {self.settings.get('max_positions', 2)}
Плечо: {self.settings.get('max_leverage', 10)}x
Таймфрейм: {self.settings.get('timeframe', '15m')}
Трейлинг: {'Да' if self.settings.get('trailing_stop_enabled') else 'Нет'}
"""
        self.analytics_text.setText(text)

    def _filter_logs(self):
        pass  # TODO: implement log filtering

    def _clear_logs(self):
        self.log_text.clear()

    def _export_logs(self):
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт логов", "logs_export.txt", "Text Files (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_text.toPlainText())
            QMessageBox.information(self, "Экспорт", f"Логи сохранены в {path}")

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
        QMainWindow { background: #2d2d2d; }
        QWidget { background: #2d2d2d; color: #E0E0E0; }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background: #2d2d2d; color: #E0E0E0; border: 1px solid #555; padding: 4px;
        }
        QCheckBox { color: #E0E0E0; }
        QLabel { color: #E0E0E0; }
        QPushButton {
            background-color: #3c3c3c; color: #E0E0E0; border: 1px solid #555;
            padding: 6px 12px; border-radius: 3px;
        }
        QPushButton:hover { background-color: #4a4a4a; }
        QPushButton:disabled { background-color: #2e2e2e; color: #666; }
        QStatusBar { background: #2e2e2e; color: #E0E0E0; }
        QScrollArea { border: none; }
        QGroupBox { margin-top: 10px; }
    """)
