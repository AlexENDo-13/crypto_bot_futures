import sqlite3
import os

class SQLiteTradeHistory:
    def __init__(self, db_path="data/trades.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                side TEXT,
                quantity REAL,
                entry_price REAL,
                exit_price REAL,
                leverage INTEGER,
                pnl REAL,
                pnl_percent REAL,
                exit_reason TEXT,
                strategy TEXT,
                entry_time TEXT,
                exit_time TEXT
            )
        """)
        conn.commit()
        conn.close()

    def record_trade(self, trade_data: dict):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO trades (symbol, side, quantity, entry_price, exit_price,
                              leverage, pnl, pnl_percent, exit_reason, strategy,
                              entry_time, exit_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_data.get("symbol"),
            trade_data.get("side"),
            trade_data.get("quantity"),
            trade_data.get("entry_price"),
            trade_data.get("exit_price", 0),
            trade_data.get("leverage"),
            trade_data.get("realized_pnl", 0),
            trade_data.get("realized_pnl_percent", 0),
            trade_data.get("exit_reason"),
            trade_data.get("strategy"),
            trade_data.get("entry_time"),
            trade_data.get("exit_time"),
        ))
        conn.commit()
        conn.close()

    def close(self):
        pass
