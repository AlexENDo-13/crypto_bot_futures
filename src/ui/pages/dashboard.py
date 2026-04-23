"""
Dashboard Page – общая информация: баланс, PnL, график, кнопки управления.
Добавлен переключатель демо-режима.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
                             QPushButton, QFrame, QSplitter, QGridLayout, QCheckBox)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont
from src.ui.widgets.realtime_chart import RealtimeChart
from src.ui.widgets.pie_chart import PieChart


class DashboardPage(QWidget):
    start_signal = pyqtSignal()
    stop_signal = pyqtSignal()
    scan_signal = pyqtSignal()
    toggle_demo_signal = pyqtSignal(bool)  # True = demo mode ON

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.pnl_history = []

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Карточки с использованием QGridLayout для равномерного распределения
        cards_widget = QWidget()
        cards_layout = QGridLayout(cards_widget)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(10)

        self.balance_label = self._create_card("💰 Виртуальный баланс", "0.00 USDT")
        self.real_balance_label = self._create_card("💳 Реальный баланс", "— USDT")
        self.pnl_label = self._create_card("📈 P&L (нереализ.)", "0.00 USDT (0.00%)")
        self.positions_label = self._create_card("📌 Открыто позиций", "0")

        # Карточка режима с переключателем
        mode_card = QFrame()
        mode_card.setObjectName("card")
        mode_layout = QVBoxLayout(mode_card)
        mode_layout.setContentsMargins(12, 12, 12, 12)
        mode_title = QLabel("⚙️ Режим")
        mode_title.setStyleSheet("color: #8B949E; font-size: 10pt;")
        mode_layout.addWidget(mode_title)

        mode_switch_layout = QHBoxLayout()
        self.mode_label = QLabel("Демо")
        self.mode_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.mode_label.setStyleSheet("color: #C9D1D9;")
        mode_switch_layout.addWidget(self.mode_label)
        mode_switch_layout.addStretch()
        self.demo_checkbox = QCheckBox("Демо-режим")
        self.demo_checkbox.setChecked(True)
        self.demo_checkbox.stateChanged.connect(self._on_demo_toggled)
        mode_switch_layout.addWidget(self.demo_checkbox)
        mode_layout.addLayout(mode_switch_layout)
        mode_layout.addStretch()

        cards_layout.addWidget(self.balance_label, 0, 0)
        cards_layout.addWidget(self.real_balance_label, 0, 1)
        cards_layout.addWidget(self.pnl_label, 0, 2)
        cards_layout.addWidget(self.positions_label, 1, 0)
        cards_layout.addWidget(mode_card, 1, 1)

        # Растягиваем столбцы равномерно
        for i in range(3):
            cards_layout.setColumnStretch(i, 1)

        layout.addWidget(cards_widget)

        # Кнопки управления
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ ЗАПУСТИТЬ БОТА")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.clicked.connect(self.start_signal.emit)

        self.stop_btn = QPushButton("⏹ ОСТАНОВИТЬ")
        self.stop_btn.setObjectName("dangerButton")
        self.stop_btn.clicked.connect(self.stop_signal.emit)
        self.stop_btn.setEnabled(False)

        self.scan_btn = QPushButton("🔍 Сканировать сейчас")
        self.scan_btn.clicked.connect(self.scan_signal.emit)
        self.scan_btn.setEnabled(False)

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.scan_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Графики
        charts_splitter = QSplitter(Qt.Horizontal)

        chart_group = QGroupBox("📉 График PnL")
        chart_layout = QVBoxLayout()
        self.chart = RealtimeChart()
        chart_layout.addWidget(self.chart)
        chart_group.setLayout(chart_layout)
        charts_splitter.addWidget(chart_group)

        weights_group = QGroupBox("🧠 Веса стратегии")
        weights_layout = QVBoxLayout()
        self.pie_chart = PieChart()
        weights_layout.addWidget(self.pie_chart)
        weights_group.setLayout(weights_layout)
        charts_splitter.addWidget(weights_group)

        charts_splitter.setSizes([600, 300])
        layout.addWidget(charts_splitter)
        layout.addStretch()

    def _create_card(self, title, default_text):
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #8B949E; font-size: 10pt;")
        value_label = QLabel(default_text)
        value_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        value_label.setStyleSheet("color: #C9D1D9;")
        value_label.setWordWrap(True)
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        card_layout.addStretch()
        return card

    def _on_demo_toggled(self, state):
        is_demo = state == Qt.Checked
        self.toggle_demo_signal.emit(is_demo)

    def update_status(self, balance, real_balance, pnl, pnl_percent, mode, positions_count, weights=None):
        self.balance_label.findChild(QLabel).setText(f"{balance:.2f} USDT")
        real_text = f"{real_balance:.2f} USDT" if real_balance > 0 else "— USDT"
        self.real_balance_label.findChild(QLabel).setText(real_text)

        color = "#3FB950" if pnl >= 0 else "#F85149"
        pnl_text = f'<span style="color:{color};">{pnl:+.2f} USDT ({pnl_percent:+.2f}%)</span>'
        self.pnl_label.findChild(QLabel).setText(pnl_text)
        self.pnl_label.findChild(QLabel).setTextFormat(Qt.RichText)

        self.positions_label.findChild(QLabel).setText(str(positions_count))
        self.mode_label.setText(mode)
        # Обновляем чекбокс в соответствии с текущим режимом
        self.demo_checkbox.blockSignals(True)
        self.demo_checkbox.setChecked(mode == "Демо")
        self.demo_checkbox.blockSignals(False)

        self.pnl_history.append(pnl)
        if len(self.pnl_history) > 200:
            self.pnl_history = self.pnl_history[-200:]
        self.chart.update_data(pnl)

        if weights:
            self.pie_chart.set_weights(weights)

    def set_buttons_state(self, running: bool):
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.scan_btn.setEnabled(running)