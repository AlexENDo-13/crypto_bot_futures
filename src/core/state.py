"""
State Persistence - SQLite-based state management.
Survives restarts, tracks positions, orders, stats.
"""
import sqlite3
import json
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger()


class StateManager:
    """
    Persistent state manager using SQLite.
    Stores positions, orders, trades, and bot state.
    """

    def __init__(self, db_path: str = "data/state/bot_state.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()
        logger.info("StateManager initialized | db=%s", self.db_path)

    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL,
                    quantity REAL,
                    leverage INTEGER,
                    margin REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    trailing_stop REAL,
                    unrealized_pnl REAL DEFAULT 0,
                    realized_pnl REAL DEFAULT 0,
                    status TEXT DEFAULT 'OPEN',
                    opened_at TEXT,
                    closed_at TEXT,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT UNIQUE,
                    symbol TEXT,
                    side TEXT,
                    position_side TEXT,
                    order_type TEXT,
                    quantity REAL,
                    price REAL,
                    filled_qty REAL DEFAULT 0,
                    avg_price REAL,
                    status TEXT,
                    reduce_only INTEGER DEFAULT 0,
                    created_at TEXT,
                    filled_at TEXT,
                    commission REAL DEFAULT 0,
                    pnl REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    side TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    quantity REAL,
                    pnl REAL,
                    pnl_pct REAL,
                    commission REAL,
                    reason TEXT,
                    duration_sec INTEGER,
                    closed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    trades INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    total_volume REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS bot_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
                CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
                CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(closed_at);
            """)

    def save_position(self, position: Dict[str, Any]) -> int:
        """Save or update position"""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO positions 
                   (symbol, side, entry_price, quantity, leverage, margin, 
                    stop_loss, take_profit, trailing_stop, opened_at, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT DO UPDATE SET
                   quantity=excluded.quantity,
                   unrealized_pnl=excluded.unrealized_pnl,
                   realized_pnl=excluded.realized_pnl,
                   status=excluded.status,
                   closed_at=excluded.closed_at""",
                (
                    position.get("symbol"), position.get("side"),
                    position.get("entry_price"), position.get("quantity"),
                    position.get("leverage"), position.get("margin"),
                    position.get("stop_loss"), position.get("take_profit"),
                    position.get("trailing_stop"), datetime.now().isoformat(),
                    json.dumps(position.get("metadata", {}))
                )
            )
            conn.commit()
            return cursor.lastrowid

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open positions"""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if symbol:
                rows = conn.execute(
                    "SELECT * FROM positions WHERE symbol=? AND status='OPEN'",
                    (symbol,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM positions WHERE status='OPEN'"
                ).fetchall()
            return [dict(row) for row in rows]

    def close_position(self, position_id: int, exit_price: float, pnl: float, reason: str):
        """Mark position as closed"""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE positions 
                   SET status='CLOSED', closed_at=?, realized_pnl=?
                   WHERE id=?""",
                (datetime.now().isoformat(), pnl, position_id)
            )
            conn.commit()

    def save_trade(self, trade: Dict[str, Any]):
        """Record completed trade"""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO trades 
                   (symbol, side, entry_price, exit_price, quantity, pnl, pnl_pct,
                    commission, reason, duration_sec, closed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trade.get("symbol"), trade.get("side"),
                    trade.get("entry_price"), trade.get("exit_price"),
                    trade.get("quantity"), trade.get("pnl"), trade.get("pnl_pct"),
                    trade.get("commission", 0), trade.get("reason"),
                    trade.get("duration_sec", 0), datetime.now().isoformat()
                )
            )
            conn.commit()

    def get_trade_history(self, limit: int = 100, symbol: Optional[str] = None) -> List[Dict]:
        """Get recent trades"""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if symbol:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE symbol=? ORDER BY closed_at DESC LIMIT ?",
                    (symbol, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM trades ORDER BY closed_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> Dict[str, Any]:
        """Get overall trading statistics"""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            wins = conn.execute("SELECT COUNT(*) FROM trades WHERE pnl > 0").fetchone()[0]
            losses = conn.execute("SELECT COUNT(*) FROM trades WHERE pnl < 0").fetchone()[0]
            total_pnl = conn.execute("SELECT COALESCE(SUM(pnl), 0) FROM trades").fetchone()[0]
            gross_profit = conn.execute(
                "SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE pnl > 0"
            ).fetchone()[0]
            gross_loss = abs(conn.execute(
                "SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE pnl < 0"
            ).fetchone()[0])

            profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

            return {
                "total_trades": total,
                "wins": wins,
                "losses": losses,
                "win_rate": (wins / total * 100) if total > 0 else 0,
                "total_pnl": total_pnl,
                "gross_profit": gross_profit,
                "gross_loss": gross_loss,
                "profit_factor": profit_factor,
                "avg_pnl": total_pnl / total if total > 0 else 0,
            }

    def set_state(self, key: str, value: Any):
        """Save arbitrary state"""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO bot_state (key, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                   value=excluded.value, updated_at=excluded.updated_at""",
                (key, json.dumps(value), datetime.now().isoformat())
            )
            conn.commit()

    def get_state(self, key: str, default=None) -> Any:
        """Load arbitrary state"""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM bot_state WHERE key=?", (key,)
            ).fetchone()
            if row:
                return json.loads(row[0])
            return default
