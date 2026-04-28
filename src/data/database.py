#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite Database Manager v1.0
Таблицы: trades, signals, errors, metrics, journal, offline_cache.
"""
import sqlite3
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "data/trades.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_tables(self):
        schema = """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT UNIQUE,
            symbol TEXT,
            side TEXT,
            entry_price REAL,
            exit_price REAL,
            size REAL,
            pnl REAL,
            pnl_percent REAL,
            status TEXT,
            strategy TEXT,
            mode TEXT,
            opened_at TEXT,
            closed_at TEXT,
            metadata TEXT
        );
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            signal_type TEXT,
            strength REAL,
            confidence REAL,
            features TEXT,
            executed INTEGER DEFAULT 0,
            reject_reason TEXT
        );
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            module TEXT,
            error_type TEXT,
            message TEXT,
            stacktrace TEXT,
            resolved INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            metric_name TEXT,
            value REAL,
            tags TEXT
        );
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            category TEXT,
            note TEXT,
            tags TEXT
        );
        CREATE TABLE IF NOT EXISTS offline_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            timeframe TEXT,
            candle_data TEXT,
            fetched_at TEXT,
            expires_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
        CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
        CREATE INDEX IF NOT EXISTS idx_signals_time ON signals(timestamp);
        CREATE INDEX IF NOT EXISTS idx_errors_time ON errors(timestamp);
        CREATE INDEX IF NOT EXISTS idx_cache_symbol ON offline_cache(symbol, timeframe);
        """
        with self._connect() as conn:
            conn.executescript(schema)
        logger.info("Database initialized")

    def insert_trade(self, trade: Dict[str, Any]) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO trades
                    (trade_id, symbol, side, entry_price, exit_price, size, pnl, pnl_percent,
                     status, strategy, mode, opened_at, closed_at, metadata)
                    VALUES (:trade_id, :symbol, :side, :entry_price, :exit_price, :size, :pnl,
                            :pnl_percent, :status, :strategy, :mode, :opened_at, :closed_at, :metadata)
                """, {k: json.dumps(v) if isinstance(v, dict) else v for k, v in trade.items()})
            return True
        except Exception as e:
            logger.error(f"DB insert_trade error: {e}")
            return False

    def get_trades(self, symbol: Optional[str] = None, limit: int = 100) -> List[Dict]:
        with self._connect() as conn:
            if symbol:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE symbol=? ORDER BY opened_at DESC LIMIT ?",
                    (symbol, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM trades ORDER BY opened_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    def get_trade_stats(self, days: int = 7) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                       SUM(pnl) as total_pnl,
                       AVG(pnl_percent) as avg_pnl_pct
                FROM trades
                WHERE opened_at >= date('now', '-{} days')
            """.format(days)).fetchone()
            return dict(row) if row else {}

    def insert_signal(self, signal: Dict[str, Any]):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO signals (timestamp, symbol, signal_type, strength, confidence, features, executed, reject_reason)
                VALUES (:timestamp, :symbol, :signal_type, :strength, :confidence, :features, :executed, :reject_reason)
            """, signal)

    def log_error(self, module: str, error_type: str, message: str, stacktrace: str = ""):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO errors (timestamp, module, error_type, message, stacktrace)
                VALUES (?, ?, ?, ?, ?)
            """, (datetime.now().isoformat(), module, error_type, message, stacktrace))

    def get_unresolved_errors(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM errors WHERE resolved=0 ORDER BY timestamp DESC").fetchall()
            return [dict(r) for r in rows]

    def record_metric(self, name: str, value: float, tags: Optional[Dict] = None):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO metrics (timestamp, metric_name, value, tags)
                VALUES (?, ?, ?, ?)
            """, (datetime.now().isoformat(), name, value, json.dumps(tags) if tags else None))

    def add_journal_note(self, category: str, note: str, tags: Optional[List[str]] = None):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO journal (timestamp, category, note, tags)
                VALUES (?, ?, ?, ?)
            """, (datetime.now().isoformat(), category, note, json.dumps(tags) if tags else None))

    # Offline cache
    def cache_candles(self, symbol: str, timeframe: str, candles: List[Dict]):
        with self._connect() as conn:
            conn.execute("DELETE FROM offline_cache WHERE symbol=? AND timeframe=?", (symbol, timeframe))
            conn.execute("""
                INSERT INTO offline_cache (symbol, timeframe, candle_data, fetched_at, expires_at)
                VALUES (?, ?, ?, ?, datetime('now', '+1 day'))
            """, (symbol, timeframe, json.dumps(candles), datetime.now().isoformat()))

    def get_cached_candles(self, symbol: str, timeframe: str) -> Optional[List[Dict]]:
        with self._connect() as conn:
            row = conn.execute("""
                SELECT candle_data FROM offline_cache
                WHERE symbol=? AND timeframe=? AND expires_at > datetime('now')
            """, (symbol, timeframe)).fetchone()
            if row:
                return json.loads(row["candle_data"])
            return None
