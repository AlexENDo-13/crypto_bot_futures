"""
Асинхронная история сделок + синхронная обёртка
"""
import asyncio
import aiosqlite
import json
from pathlib import Path
from typing import Dict, List, Optional

class AsyncSQLiteTradeHistory:
    def __init__(self, db_path="data/history/trades.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[aiosqlite.Connection] = None

    async def _get_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            self._conn = await aiosqlite.connect(str(self.db_path))
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._create_table()
        return self._conn

    async def _create_table(self):
        conn = await self._get_conn()
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT, 
                symbol TEXT, 
                side TEXT, 
                entry_price REAL, 
                exit_price REAL,
                quantity REAL, 
                pnl REAL, 
                pnl_percent REAL, 
                exit_reason TEXT,
                hold_time_hours REAL, 
                indicators_json TEXT
            )
        """)
        await conn.commit()

    async def add_trade(self, trade: Dict):
        conn = await self._get_conn()
        ind_json = json.dumps(trade.get('indicators_at_entry', {}))
        await conn.execute("""
            INSERT INTO trades (
                timestamp, symbol, side, entry_price, exit_price, 
                quantity, pnl, pnl_percent, exit_reason, hold_time_hours, indicators_json
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            trade.get('timestamp'), 
            trade.get('symbol'), 
            trade.get('side'), 
            trade.get('entry_price'),
            trade.get('exit_price'), 
            trade.get('quantity'), 
            trade.get('pnl'), 
            trade.get('pnl_percent'),
            trade.get('exit_reason'), 
            trade.get('hold_time_hours'), 
            ind_json
        ))
        await conn.commit()

    # Алиас для совместимости с вызовами _async
    async def add_trade_async(self, trade: Dict):
        return await self.add_trade(trade)

    async def get_trades(self, limit=100) -> List[Dict]:
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", 
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
        trades = []
        for r in rows:
            trades.append({
                'id': r[0],
                'timestamp': r[1], 
                'symbol': r[2], 
                'side': r[3], 
                'entry_price': r[4], 
                'exit_price': r[5],
                'quantity': r[6], 
                'pnl': r[7], 
                'pnl_percent': r[8], 
                'exit_reason': r[9], 
                'hold_time_hours': r[10],
                'indicators_at_entry': json.loads(r[11]) if r[11] else {}
            })
        return trades

    async def get_statistics(self) -> Dict:
        conn = await self._get_conn()
        async with conn.execute("SELECT COUNT(*), SUM(pnl), AVG(pnl) FROM trades") as cursor:
            total, total_pnl, avg_pnl = await cursor.fetchone()
        async with conn.execute("SELECT COUNT(*) FROM trades WHERE pnl > 0") as cursor:
            wins_row = await cursor.fetchone()
            wins = wins_row[0] if wins_row else 0
        total = total or 0
        return {
            "total_trades": total,
            "win_count": wins,
            "loss_count": total - wins,
            "total_pnl": round(total_pnl or 0.0, 2),
            "avg_pnl": round(avg_pnl or 0.0, 2),
            "win_rate": round((wins / total * 100) if total else 0.0, 1)
        }

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None


# ----------------------------------------------------------------------
# Синхронная обёртка для обратной совместимости
# ----------------------------------------------------------------------
class SQLiteTradeHistory:
    """Синхронная обёртка над AsyncSQLiteTradeHistory для совместимости."""
    def __init__(self, db_path="data/history/trades.db"):
        self._async = AsyncSQLiteTradeHistory(db_path)

    def _run(self, coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)

    def add_trade(self, trade):
        return self._run(self._async.add_trade(trade))

    def get_trades(self, limit=100):
        return self._run(self._async.get_trades(limit))

    def get_statistics(self):
        return self._run(self._async.get_statistics())

    def close(self):
        return self._run(self._async.close())
