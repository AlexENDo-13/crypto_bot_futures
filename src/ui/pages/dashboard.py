"""
Страница дашборда — основная панель с балансом, PnL, сигналами
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont


class DashboardPage(QWidget):
    """Главная страница: баланс, PnL, сигналы"""

    signal_update = pyqtSignal(dict)  # сигнал для безопасного обновления из другого потока

    def __init__(self):
        super().__init__()
        self.signal_update.connect(self._apply_update)
        self.init_ui()

    def init_ui(self):
        # Главный layout
        main_layout = QHBoxLayout()

        # Левая панель — статус
        left_layout = QVBoxLayout()

        # Баланс и PnL
        group_status = QGroupBox("💰 Состояние счёта")
        status_layout = QVBoxLayout()
        self.lbl_balance = QLabel("Баланс: -- USDT")
        self.lbl_pnl = QLabel("PnL: -- USDT")
        self.lbl_pnl_pct = QLabel("PnL %: --")
        self.lbl_positions = QLabel("Открытых позиций: 0")
        self.lbl_mode = QLabel("Режим: --")

        for lbl in [self.lbl_balance, self.lbl_pnl, self.lbl_pnl_pct, self.lbl_positions, self.lbl_mode]:
            lbl.setStyleSheet("color: #E0E0E0; font-size: 14px;")
            status_layout.addWidget(lbl)

        group_status.setLayout(status_layout)
        left_layout.addWidget(group_status)

        # Таблица последних сигналов
        group_signals = QGroupBox("📡 Сигналы (последние)")
        signals_layout = QVBoxLayout()

        self.table_signals = QTableWidget()
        self.table_signals.setColumnCount(4)
        self.table_signals.setHorizontalHeaderLabels(["Символ", "Направление", "Сила", "Цена"])
        self.table_signals.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_signals.setStyleSheet("""
            QTableWidget {
                background-color: #2b2b2b;
                color: #E0E0E0;
                gridline-color: #555;
            }
            QHeaderView::section {
                background-color: #3c3c3c;
                color: #E0E0E0;
                padding: 4px;
            }
        """)
        signals_layout.addWidget(self.table_signals)
        group_signals.setLayout(signals_layout)
        left_layout.addWidget(group_signals)

        main_layout.addLayout(left_layout)

        # Правая панель — лог движка (можно выводить важные события)
        right_layout = QVBoxLayout()
        group_log = QGroupBox("📜 События движка")
        log_layout = QVBoxLayout()
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setStyleSheet("background-color: #1e1e1e; color: #cccccc;")
        log_layout.addWidget(self.text_log)
        group_log.setLayout(log_layout)
        right_layout.addWidget(group_log)

        main_layout.addLayout(right_layout)
        self.setLayout(main_layout)

        # Общий тёмный стиль виджета
        self.setStyleSheet("""
            QWidget {
                background-color: #2e2e2e;
                color: #E0E0E0;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

    def update_status(self, status_data: dict):
        """
        Обновление блока состояния счёта.
        Ожидает словарь с ключами:
        - balance (float)
        - pnl (float)
        - pnl_percent (float, опционально)
        - positions (int)
        - mode (str, опционально)
        """
        # Для потокобезопасности используем сигнал
        self.signal_update.emit(status_data)

    def _apply_update(self, status_data: dict):
        """Реальное обновление GUI (вызывается в главном потоке)"""
        balance = status_data.get("balance", 0.0)
        pnl = status_data.get("pnl", 0.0)
        pnl_percent = status_data.get("pnl_percent", 0.0)
        positions = status_data.get("positions", 0)
        mode = status_data.get("mode", "demo" if getattr(self, "settings", None) and getattr(self.settings, "demo_mode", True) else "real")

        self.lbl_balance.setText(f"Баланс: {balance:.2f} USDT")
        self.lbl_pnl.setText(f"PnL: {pnl:+.2f} USDT")
        self.lbl_pnl_pct.setText(f"PnL %: {pnl_percent:+.2f}%")
        self.lbl_positions.setText(f"Открытых позиций: {positions}")
        self.lbl_mode.setText(f"Режим: {mode}")

        # Добавляем запись в лог дашборда
        self.text_log.append(f"Обновление: баланс={balance:.2f}, PnL={pnl:+.2f}, позиций={positions}")

    def update_signals(self, signals: list):
        """
        Обновление списка сигналов.
        signals: список словарей с ключами symbol, direction, score, price и т.д.
        """
        self.table_signals.setRowCount(0)
        if not signals:
            return
        self.table_signals.setRowCount(len(signals))
        for row, sig in enumerate(signals):
            symbol = sig.get("symbol", "?")
            direction = sig.get("direction", "?")
            score = sig.get("score", 0)
            price = sig.get("price", 0.0)

            items = [
                QTableWidgetItem(symbol),
                QTableWidgetItem(direction),
                QTableWidgetItem(f"{score:.1f}"),
                QTableWidgetItem(f"{price:.4f}"),
            ]
            for col, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setForeground(QColor("#E0E0E0"))
                self.table_signals.setItem(row, col, item)

    def add_log_message(self, message: str):
        """Добавить сообщение в лог дашборда (опционально)"""
        self.text_log.append(message)
