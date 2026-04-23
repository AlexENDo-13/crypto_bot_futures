"""
Страница открытых позиций
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor


class PositionsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        # Таймер автообновления
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._auto_update)
        self.update_timer.start(5000)  # каждые 5 секунд

    def init_ui(self):
        layout = QVBoxLayout()

        # Заголовок
        header = QHBoxLayout()
        self.title = QLabel("📊 Открытые позиции")
        self.title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(self.title)

        self.btn_close_all = QPushButton("❌ Закрыть все")
        self.btn_close_all.clicked.connect(self._close_all_positions)
        self.btn_close_all.setEnabled(False)
        header.addWidget(self.btn_close_all)
        header.addStretch()
        layout.addLayout(header)

        # Таблица позиций
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Символ", "Направление", "Кол-во", "Цена входа",
            "Текущая цена", "PnL", "PnL %", "Действия"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Статус
        self.status_label = QLabel("Нет открытых позиций")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def update_positions(self, positions):
        """
        Обновляет таблицу позиций.
        Принимает list (от engine) или dict (старый формат).
        """
        if isinstance(positions, dict):
            positions = list(positions.values())
        elif not isinstance(positions, list):
            positions = []

        self.table.setRowCount(len(positions))
        total_pnl = 0.0

        for row, pos in enumerate(positions):
            symbol = pos.get("symbol", pos.get("Symbol", "UNKNOWN"))
            side = pos.get("side", pos.get("positionSide", "UNKNOWN"))
            qty = float(pos.get("quantity", pos.get("positionAmt", 0)))
            entry_price = float(pos.get("entryPrice", pos.get("avgPrice", 0)))
            current_price = float(pos.get("markPrice", pos.get("lastPrice", entry_price)))

            # Расчёт PnL
            if side.upper() == "LONG":
                pnl = (current_price - entry_price) * qty
            else:
                pnl = (entry_price - current_price) * qty

            pnl_percent = (pnl / (entry_price * qty) * 100) if entry_price > 0 and qty > 0 else 0
            total_pnl += pnl

            items = [
                symbol, side, f"{qty:.6f}", f"{entry_price:.4f}",
                f"{current_price:.4f}", f"{pnl:+.2f}", f"{pnl_percent:+.2f}%", "Закрыть"
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if col == 5:  # PnL
                    if pnl > 0:
                        item.setForeground(QColor("#4CAF50"))
                    elif pnl < 0:
                        item.setForeground(QColor("#F44336"))
                if col == 6:  # PnL %
                    if pnl_percent > 0:
                        item.setForeground(QColor("#4CAF50"))
                    elif pnl_percent < 0:
                        item.setForeground(QColor("#F44336"))
                self.table.setItem(row, col, item)

        self.status_label.setText(
            f"Всего позиций: {len(positions)} | Общий PnL: {total_pnl:+.2f} USDT"
        )

    def _auto_update(self):
        # Будет вызываться из MainWindow
        pass

    def _close_all_positions(self):
        QMessageBox.information(self, "Закрыть все", "Функция в разработке")
