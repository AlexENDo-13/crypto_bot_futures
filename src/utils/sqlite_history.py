#!/usr/bin/env python3
import sqlite3, os
from datetime import datetime

class SQLiteHistory:
    def __init__(self, db_path="data/history/trades.db"):
        self.db_path = db_path; os.makedirs(os.path.dirname(db_path), exist_ok=True); self._init_db()
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, side TEXT,
                    entry_price REAL, exit_price REAL, quantity REAL, leverage INTEGER,
                    pnl REAL, pnl_percent REAL, exit_reason TEXT, entry_time TEXT,
                    exit_time TEXT, strategy TEXT
                )
            """)
            conn.commit()
    def add_trade(self, trade):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO trades (symbol, side, entry_price, exit_price, quantity, leverage, pnl, pnl_percent, exit_reason, entry_time, exit_time, strategy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (trade.get("symbol"), trade.get("side"), trade.get("entry_price"), trade.get("exit_price"),
                  trade.get("quantity"), trade.get("leverage"), trade.get("realized_pnl"),
                  trade.get("realized_pnl_percent"), trade.get("exit_reason"), trade.get("entry_time"),
                  trade.get("exit_time"), trade.get("strategy")))
            conn.commit()
    def get_trades(self, limit=100):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM trades ORDER BY exit_time DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]
