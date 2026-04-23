"""
Trades History Page – история сделок с экспортом в CSV и автообновлением.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QPushButton, QHeaderView, QAbstractItemView,
                             QLineEdit, QComboBox, QFileDialog, QLabel)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
import csv
from src.utils.sqlite_history import SQLiteTradeHistory


class TradesHistoryPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.trades = []

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh)
        self.refresh_timer.start(5000)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.stats_label = QLabel("Сделок: 0 | Win Rate: 0% | PnL: 0.00 USDT")
        self.stats_label.setStyleSheet("color: #8B949E; font-size: 10pt; padding: 5px;")
        layout.addWidget(self.stats_label)

        filter_layout = QHBoxLayout()
        self.symbol_filter = QLineEdit()
        self.symbol_filter.setPlaceholderText("Фильтр по символу")
        self.symbol_filter.textChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.symbol_filter)

        self.side_filter = QComboBox()
        self.side_filter.addItems(["Все", "BUY", "SELL"])
        self.side_filter.currentTextChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.side_filter)

        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.force_refresh)
        filter_layout.addWidget(self.refresh_btn)

        self.export_btn = QPushButton("📁 Экспорт CSV")
        self.export_btn.clicked.connect(self.export_csv)
        filter_layout.addWidget(self.export_btn)

        layout.addLayout(filter_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Время", "Символ", "Сторона", "Вход", "Выход",
            "Кол-во", "PnL", "PnL %", "Причина"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

    def set_trades(self, trades: list):
        sorted_trades = sorted(
            trades,
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )
        self.trades = sorted_trades
        self.apply_filter()
        self.update_stats()

    def update_stats(self):
        if not self.trades:
            self.stats_label.setText("Сделок: 0 | Win Rate: 0% | PnL: 0.00 USDT")
            return

        total = len(self.trades)
        wins = sum(1 for t in self.trades if float(t.get("pnl", 0)) > 0)
        total_pnl = sum(float(t.get("pnl", 0)) for t in self.trades)
        win_rate = (wins / total * 100) if total else 0

        color = "#3FB950" if total_pnl >= 0 else "#F85149"
        self.stats_label.setText(
            f'Сделок: {total} | Win Rate: {win_rate:.1f}% | '
            f'<span style="color:{color};">PnL: {total_pnl:+.2f} USDT</span>'
        )

    def apply_filter(self):
        symbol = self.symbol_filter.text().upper()
        side = self.side_filter.currentText()
        filtered = []
        for t in self.trades:
            if symbol and symbol not in t.get("symbol", "").upper():
                continue
            if side != "Все" and t.get("side", "") != side:
                continue
            filtered.append(t)
        self._populate_table(filtered)

    def _populate_table(self, trades):
        self.table.setRowCount(len(trades))
        for row, t in enumerate(trades):
            ts = t.get("timestamp", "")
            if len(ts) > 19:
                ts = ts[:19].replace("T", " ")

            self.table.setItem(row, 0, QTableWidgetItem(ts))
            self.table.setItem(row, 1, QTableWidgetItem(t.get("symbol", "")))

            side = t.get("side", "")
            side_item = QTableWidgetItem(side)
            if side == "BUY":
                side_item.setForeground(QColor("#3FB950"))
            else:
                side_item.setForeground(QColor("#F85149"))
            self.table.setItem(row, 2, side_item)

            self.table.setItem(row, 3, QTableWidgetItem(f"{float(t.get('entry_price', 0)):.4f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{float(t.get('exit_price', 0)):.4f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{float(t.get('quantity', 0)):.4f}"))

            pnl = float(t.get("pnl", 0))
            pnl_item = QTableWidgetItem(f"{pnl:+.2f}")
            pnl_item.setForeground(QColor("#3FB950") if pnl >= 0 else QColor("#F85149"))
            self.table.setItem(row, 6, pnl_item)

            pnl_pct = float(t.get("pnl_percent", 0))
            pnl_pct_item = QTableWidgetItem(f"{pnl_pct:+.2f}%")
            pnl_pct_item.setForeground(QColor("#3FB950") if pnl_pct >= 0 else QColor("#F85149"))
            self.table.setItem(row, 7, pnl_pct_item)

            self.table.setItem(row, 8, QTableWidgetItem(t.get("exit_reason", "")))

        self.table.resizeColumnsToContents()

    def auto_refresh(self):
        try:
            db = SQLiteTradeHistory()
            trades = db.get_trades(500)
            db.close()
            if len(trades) != len(self.trades):
                self.set_trades(trades)
        except Exception:
            pass

    def force_refresh(self):
        try:
            db = SQLiteTradeHistory()
            trades = db.get_trades(500)
            db.close()
            self.set_trades(trades)
        except Exception as e:
            self.stats_label.setText(f"Ошибка обновления: {e}")

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить историю", "trades_history.csv", "CSV (*.csv)"
        )
        if path and self.trades:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                if self.trades:
                    writer = csv.DictWriter(f, fieldnames=self.trades[0].keys())
                    writer.writeheader()
                    writer.writerows(self.trades)
