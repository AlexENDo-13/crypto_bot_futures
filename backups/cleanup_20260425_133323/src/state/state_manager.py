"""
StateManager v7.1
Persists and retrieves bot state using SQLite.
"""
import logging
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class StateManager:
    def __init__(self, db_path: str = "data/state/bot_state.db"):
        self.logger = logging.getLogger("CryptoBot.State")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_tables()
        self.logger.info(f"StateManager v7.1 | db={self.db_path}")

    def _init_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                strategy TEXT,
                direction TEXT,
                confidence REAL,
                price REAL,
                reason TEXT
            )
        """)
        self.conn.commit()

    def set(self, key: str, value: Any):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO state (key, value, updated_at) VALUES (?, ?, ?)",
            (key, str(value), datetime.now().isoformat())
        )
        self.conn.commit()

    def get(self, key: str, default=None) -> Optional[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM state WHERE key=?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

    def save_signal(self, signal: dict):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO signals (timestamp, symbol, strategy, direction, confidence, price, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            signal.get("symbol"),
            signal.get("strategy"),
            signal.get("direction"),
            signal.get("confidence"),
            signal.get("price"),
            signal.get("reason")
        ))
        self.conn.commit()

    def get_recent_signals(self, limit: int = 100) -> list:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,))
        return cursor.fetchall()

    def close(self):
        self.conn.close()
        self.logger.info("StateManager closed")
