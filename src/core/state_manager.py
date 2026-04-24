"""
CryptoBot v7.0 - State Manager
"""
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class StateManager:
    def __init__(self, db_path: str = "data/state/bot_state.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("CryptoBot.State")
        self._init_db()
        self.logger.info(f"StateManager v7.0 | db={db_path}")

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    symbol TEXT PRIMARY KEY, side TEXT, size REAL,
                    entry_price REAL, leverage INTEGER, stop_loss REAL,
                    take_profit REAL, margin REAL, open_time TEXT,
                    pnl REAL, pnl_percent REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT, side TEXT, order_type TEXT,
                    quantity REAL, fill_price REAL, pnl REAL,
                    status TEXT, fill_time TEXT, metadata TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stats (
                    key TEXT PRIMARY KEY, value TEXT
                )
            """)
            conn.commit()

    def save_position(self, position: Dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO positions
                (symbol, side, size, entry_price, leverage, stop_loss, take_profit, margin, open_time, pnl, pnl_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (position.get("symbol"), position.get("side"), position.get("size"),
                  position.get("entry_price"), position.get("leverage", 1),
                  position.get("stop_loss", 0), position.get("take_profit", 0),
                  position.get("margin", 0), position.get("open_time", datetime.now().isoformat()),
                  position.get("pnl", 0), position.get("pnl_percent", 0)))
            conn.commit()

    def load_positions(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM positions")
            return [dict(row) for row in cursor.fetchall()]

    def remove_position(self, symbol: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
            conn.commit()

    def save_trade(self, trade: Dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO trades (symbol, side, order_type, quantity, fill_price, pnl, status, fill_time, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (trade.get("symbol"), trade.get("side"), trade.get("order_type"),
                  trade.get("quantity"), trade.get("fill_price"), trade.get("pnl", 0),
                  trade.get("status"), trade.get("fill_time", datetime.now().isoformat()),
                  json.dumps(trade.get("metadata", {}))))
            conn.commit()

    def load_trades(self, limit: int = 100) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM trades ORDER BY fill_time DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def save_stat(self, key: str, value: Any):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO stats (key, value) VALUES (?, ?)",
                        (key, json.dumps(value)))
            conn.commit()

    def load_stat(self, key: str, default=None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT value FROM stats WHERE key = ?", (key,))
            row = cursor.fetchone()
            return json.loads(row[0]) if row else default

    def clear_all(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM positions")
            conn.execute("DELETE FROM trades")
            conn.execute("DELETE FROM stats")
            conn.commit()
        self.logger.info("All state cleared")
