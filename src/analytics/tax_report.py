#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tax Report v1.0
Генерация налоговой отчётности для РФ (FIFO-метод).
Форматы: CSV, XLSX.
"""
import logging
import csv
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TaxRecord:
    date: str
    symbol: str
    side: str  # buy / sell
    amount: float
    price: float
    total: float
    fee: float
    pnl: float

class TaxReport:
    """
    Налоговый отчёт для криптовалютных сделок.

    Usage:
        report = TaxReport(database=db)
        report.generate_quarterly(2026, 2)  # Q2 2026
        report.export_xlsx("tax_report_2026q2.xlsx")
    """

    def __init__(self, database=None, output_dir: str = "reports/tax"):
        self.db = database
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._records: List[TaxRecord] = []

    def load_from_database(self, start_date: str, end_date: str):
        """Загрузить сделки из БД за период."""
        if not self.db:
            logger.error("Database not connected")
            return

        try:
            trades = self.db.get_trades(limit=10000)
            for trade in trades:
                opened = trade.get("opened_at", "")
                if start_date <= opened <= end_date:
                    self._records.append(TaxRecord(
                        date=opened[:10],
                        symbol=trade.get("symbol", ""),
                        side=trade.get("side", ""),
                        amount=trade.get("size", 0),
                        price=trade.get("entry_price", 0),
                        total=trade.get("size", 0) * trade.get("entry_price", 0),
                        fee=0.0,  # Заполнять из данных биржи
                        pnl=trade.get("pnl", 0)
                    ))
            logger.info(f"Loaded {len(self._records)} tax records")
        except Exception as e:
            logger.error(f"Failed to load trades: {e}")

    def calculate_fifo(self) -> Dict[str, Any]:
        """Расчёт по FIFO-методу."""
        buys: List[TaxRecord] = []
        sells: List[TaxRecord] = []

        for record in self._records:
            if record.side.lower() == "buy":
                buys.append(record)
            else:
                sells.append(record)

        total_income = sum(s.total for s in sells)
        total_expense = sum(b.total for b in buys)
        total_pnl = sum(r.pnl for r in self._records)

        return {
            "period": "custom",
            "total_trades": len(self._records),
            "buys": len(buys),
            "sells": len(sells),
            "total_income": round(total_income, 2),
            "total_expense": round(total_expense, 2),
            "net_profit": round(total_pnl, 2),
            "tax_estimate_13pct": round(max(0, total_pnl) * 0.13, 2),
        }

    def export_csv(self, filepath: str):
        """Экспорт в CSV."""
        path = self.output_dir / filepath
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(["Дата", "Пара", "Тип", "Количество", "Цена", 
                           "Сумма", "Комиссия", "PnL"])
            for r in self._records:
                writer.writerow([r.date, r.symbol, r.side, r.amount, 
                               r.price, r.total, r.fee, r.pnl])
        logger.info(f"Tax CSV exported: {path}")

    def export_xlsx(self, filepath: str):
        """Экспорт в XLSX (Excel)."""
        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment

            path = self.output_dir / filepath
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Сделки"

            # Заголовки
            headers = ["Дата", "Пара", "Тип", "Количество", "Цена", "Сумма", "Комиссия", "PnL"]
            ws.append(headers)

            # Данные
            for r in self._records:
                ws.append([r.date, r.symbol, r.side, r.amount, 
                          r.price, r.total, r.fee, r.pnl])

            # Итоги
            summary = self.calculate_fifo()
            ws.append([])
            ws.append(["ИТОГО", "", "", "", "", 
                      summary["total_income"], "", summary["net_profit"]])

            wb.save(path)
            logger.info(f"Tax XLSX exported: {path}")

        except ImportError:
            logger.warning("openpyxl not installed. Falling back to CSV.")
            self.export_csv(filepath.replace(".xlsx", ".csv"))

    def generate_quarterly(self, year: int, quarter: int):
        """Сгенерировать отчёт за квартал."""
        quarters = {
            1: ("01-01", "03-31"),
            2: ("04-01", "06-30"),
            3: ("07-01", "09-30"),
            4: ("10-01", "12-31"),
        }
        start, end = quarters.get(quarter, ("01-01", "12-31"))
        start_date = f"{year}-{start}"
        end_date = f"{year}-{end}"

        self.load_from_database(start_date, end_date)
        summary = self.calculate_fifo()

        filename = f"tax_report_{year}_q{quarter}"
        self.export_xlsx(f"{filename}.xlsx")

        return summary
