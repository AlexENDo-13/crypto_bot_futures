"""
Daily Report – генерация ежедневного отчёта с метриками.
"""

from datetime import datetime, timedelta
from typing import Dict, List
from src.utils.sqlite_history import SQLiteTradeHistory


class DailyReport:
    def __init__(self):
        self.db = SQLiteTradeHistory()

    def generate(self) -> Dict:
        today = datetime.now().date()
        trades = self.db.get_trades(1000)
        today_trades = [t for t in trades if datetime.fromisoformat(t["timestamp"]).date() == today]

        total_pnl = sum(t["pnl"] for t in today_trades)
        wins = sum(1 for t in today_trades if t["pnl"] > 0)
        losses = len(today_trades) - wins
        win_rate = (wins / len(today_trades) * 100) if today_trades else 0

        symbol_pnl: Dict[str, float] = {}
        for t in today_trades:
            sym = t["symbol"]
            symbol_pnl[sym] = symbol_pnl.get(sym, 0) + t["pnl"]
        best_symbol = max(symbol_pnl.items(), key=lambda x: x[1]) if symbol_pnl else (None, 0)
        worst_symbol = min(symbol_pnl.items(), key=lambda x: x[1]) if symbol_pnl else (None, 0)

        hour_pnl = {h: 0.0 for h in range(24)}
        hour_trades = {h: 0 for h in range(24)}
        for t in today_trades:
            hour = datetime.fromisoformat(t["timestamp"]).hour
            hour_pnl[hour] += t["pnl"]
            hour_trades[hour] += 1

        return {
            "date": today.isoformat(),
            "total_trades": len(today_trades),
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "best_symbol": best_symbol[0],
            "best_symbol_pnl": best_symbol[1],
            "worst_symbol": worst_symbol[0],
            "worst_symbol_pnl": worst_symbol[1],
            "hour_pnl": hour_pnl,
            "hour_trades": hour_trades
        }

    def format_telegram(self, report: Dict) -> str:
        return (f"📊 <b>Ежедневный отчёт {report['date']}</b>\n"
                f"Сделок: {report['total_trades']} | Win Rate: {report['win_rate']:.1f}%\n"
                f"PnL: {report['total_pnl']:+.2f} USDT\n"
                f"🏆 Лучшая: {report['best_symbol']} ({report['best_symbol_pnl']:+.2f})\n"
                f"📉 Худшая: {report['worst_symbol']} ({report['worst_symbol_pnl']:+.2f})")