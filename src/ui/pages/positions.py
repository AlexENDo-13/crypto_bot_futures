"""
Positions Page – таблица открытых позиций.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
                             QPushButton, QHeaderView, QAbstractItemView)
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QColor


class PositionsPage(QWidget):
    close_position_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Символ", "Сторона", "Кол-во", "Вход", "Тек. цена", "P&L", ""])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

    def update_positions(self, positions: dict):
        self.table.setRowCount(len(positions))
        row = 0
        for symbol, pos in positions.items():
            side = pos["side"]
            qty = pos["qty"]
            entry = pos["entry_price"]
            current = pos["current_price"]
            if side == "BUY":
                pnl = (current - entry) * qty
            else:
                pnl = (entry - current) * qty

            self.table.setItem(row, 0, QTableWidgetItem(symbol))
            side_item = QTableWidgetItem(side)
            side_item.setForeground(QColor("#3FB950") if side == "BUY" else QColor("#F85149"))
            self.table.setItem(row, 1, side_item)
            self.table.setItem(row, 2, QTableWidgetItem(f"{qty:.4f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{entry:.4f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{current:.4f}"))
            pnl_item = QTableWidgetItem(f"{pnl:+.2f}")
            pnl_item.setForeground(QColor("#3FB950") if pnl >= 0 else QColor("#F85149"))
            self.table.setItem(row, 5, pnl_item)

            close_btn = QPushButton("❌ Закрыть")
            close_btn.clicked.connect(lambda checked, s=symbol: self.close_position_signal.emit(s))
            self.table.setCellWidget(row, 6, close_btn)
            row += 1