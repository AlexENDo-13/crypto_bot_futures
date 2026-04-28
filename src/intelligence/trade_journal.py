#!/usr/bin/env python3
"""
Trade Journal Analyzer (B1) — understands its own mistakes.
Analyzes closed trades to find patterns: which symbols, times, strategies fail most.
"""
import json
import os
import time
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger("CryptoBot.Journal")

class TradeJournal:
    def __init__(self, journal_path: str = "logs/trade_journal.json"):
        self.journal_path = journal_path
        self.trades: List[Dict] = []
        self._symbol_stats: Dict[str, Dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "total_pnl": 0.0, "avg_pnl": 0.0})
        self._strategy_stats: Dict[str, Dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "total_pnl": 0.0})
        self._hour_stats: Dict[int, Dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "total_pnl": 0.0})
        self._day_stats: Dict[int, Dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "total_pnl": 0.0})
        self._exit_reason_stats: Dict[str, Dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "total_pnl": 0.0})
        self._load()

    def _load(self):
        if os.path.exists(self.journal_path):
            try:
                with open(self.journal_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.trades = data.get("trades", [])
                self._rebuild_stats()
                logger.info(f"Journal loaded: {len(self.trades)} trades")
            except Exception as e:
                logger.error(f"Journal load error: {e}")
                self.trades = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.journal_path), exist_ok=True)
            with open(self.journal_path, "w", encoding="utf-8") as f:
                json.dump({"trades": self.trades[-500:], "last_update": time.time()}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Journal save error: {e}")

    def _rebuild_stats(self):
        self._symbol_stats.clear()
        self._strategy_stats.clear()
        self._hour_stats.clear()
        self._day_stats.clear()
        self._exit_reason_stats.clear()
        for t in self.trades:
            self._update_stats(t)

    def _update_stats(self, trade: Dict):
        symbol = trade.get("symbol", "UNKNOWN")
        strategy = trade.get("strategy", "mixed")
        pnl = float(trade.get("realized_pnl", 0))
        is_win = pnl > 0
        exit_reason = trade.get("exit_reason", "UNKNOWN")

        # Symbol stats
        s = self._symbol_stats[symbol]
        s["trades"] += 1
        s["wins"] += 1 if is_win else 0
        s["total_pnl"] += pnl
        s["avg_pnl"] = s["total_pnl"] / s["trades"]

        # Strategy stats
        st = self._strategy_stats[strategy]
        st["trades"] += 1
        st["wins"] += 1 if is_win else 0
        st["total_pnl"] += pnl

        # Hour stats
        entry_time = trade.get("entry_time", "")
        try:
            dt = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
            hour = dt.hour
            day = dt.weekday()
        except Exception:
            hour = 0
            day = 0
        h = self._hour_stats[hour]
        h["trades"] += 1
        h["wins"] += 1 if is_win else 0
        h["total_pnl"] += pnl

        d = self._day_stats[day]
        d["trades"] += 1
        d["wins"] += 1 if is_win else 0
        d["total_pnl"] += pnl

        # Exit reason stats
        er = self._exit_reason_stats[exit_reason]
        er["trades"] += 1
        er["wins"] += 1 if is_win else 0
        er["total_pnl"] += pnl

    def record_trade(self, trade: Dict):
        """Record a closed trade for analysis."""
        self.trades.append(trade)
        self._update_stats(trade)
        if len(self.trades) % 10 == 0:
            self._save()
        logger.info(f"JOURNAL: Recorded {trade.get('symbol')} {trade.get('side')} PnL={trade.get('realized_pnl', 0):+.4f}")

    def get_symbol_report(self, symbol: str) -> Dict:
        s = self._symbol_stats.get(symbol, {"trades": 0, "wins": 0, "total_pnl": 0.0, "avg_pnl": 0.0})
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] > 0 else 0
        return {
            "symbol": symbol,
            "trades": s["trades"],
            "win_rate": wr,
            "total_pnl": s["total_pnl"],
            "avg_pnl": s["avg_pnl"],
            "verdict": "AVOID" if wr < 30 and s["trades"] >= 5 else "CAUTION" if wr < 45 and s["trades"] >= 3 else "OK"
        }

    def get_worst_symbols(self, min_trades: int = 3, top_n: int = 5) -> List[Dict]:
        results = []
        for sym, stats in self._symbol_stats.items():
            if stats["trades"] >= min_trades:
                wr = stats["wins"] / stats["trades"] * 100
                results.append({"symbol": sym, "win_rate": wr, "trades": stats["trades"], "total_pnl": stats["total_pnl"]})
        results.sort(key=lambda x: x["win_rate"])
        return results[:top_n]

    def get_best_hours(self) -> List[Dict]:
        results = []
        for hour, stats in self._hour_stats.items():
            if stats["trades"] >= 2:
                wr = stats["wins"] / stats["trades"] * 100
                results.append({"hour": hour, "win_rate": wr, "trades": stats["trades"], "total_pnl": stats["total_pnl"]})
        results.sort(key=lambda x: x["win_rate"], reverse=True)
        return results

    def get_best_days(self) -> List[Dict]:
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        results = []
        for day, stats in self._day_stats.items():
            if stats["trades"] >= 2:
                wr = stats["wins"] / stats["trades"] * 100
                results.append({"day": days[day], "win_rate": wr, "trades": stats["trades"], "total_pnl": stats["total_pnl"]})
        results.sort(key=lambda x: x["win_rate"], reverse=True)
        return results

    def get_exit_analysis(self) -> Dict[str, Any]:
        """Analyze which exit reasons are most profitable."""
        results = {}
        for reason, stats in self._exit_reason_stats.items():
            wr = (stats["wins"] / stats["trades"] * 100) if stats["trades"] > 0 else 0
            results[reason] = {
                "trades": stats["trades"],
                "win_rate": wr,
                "total_pnl": stats["total_pnl"],
                "avg_pnl": stats["total_pnl"] / stats["trades"] if stats["trades"] > 0 else 0
            }
        return results

    def get_mistake_patterns(self) -> List[str]:
        """Return human-readable mistake patterns."""
        patterns = []
        # Pattern 1: Symbols with bad performance
        worst = self.get_worst_symbols(min_trades=3, top_n=3)
        for w in worst:
            if w["win_rate"] < 35:
                patterns.append(f"AVOID {w['symbol']}: {w['win_rate']:.0f}% WR over {w['trades']} trades")
        # Pattern 2: Exit reason analysis
        exits = self.get_exit_analysis()
        if "STOP_LOSS" in exits and exits["STOP_LOSS"]["trades"] >= 5:
            sl_wr = exits["STOP_LOSS"]["win_rate"]
            if sl_wr < 20:
                patterns.append(f"SL too tight: only {sl_wr:.0f}% of SL exits are profitable")
        if "TIME_EXIT" in exits and exits["TIME_EXIT"]["trades"] >= 3:
            te_wr = exits["TIME_EXIT"]["win_rate"]
            if te_wr > 50:
                patterns.append(f"Consider longer hold: time exits have {te_wr:.0f}% WR")
        # Pattern 3: Best/worst hours
        best_hours = self.get_best_hours()
        if len(best_hours) >= 2:
            patterns.append(f"Best trading hours: {best_hours[0]['hour']:02d}:00-{best_hours[1]['hour']:02d}:00 (WR {best_hours[0]['win_rate']:.0f}%)")
        return patterns

    def get_summary(self) -> Dict[str, Any]:
        total = len(self.trades)
        wins = sum(1 for t in self.trades if t.get("realized_pnl", 0) > 0)
        total_pnl = sum(t.get("realized_pnl", 0) for t in self.trades)
        return {
            "total_trades": total,
            "win_rate": (wins / total * 100) if total > 0 else 0,
            "total_pnl": total_pnl,
            "symbols_tracked": len(self._symbol_stats),
            "strategies_tracked": len(self._strategy_stats),
            "mistake_patterns": self.get_mistake_patterns(),
            "worst_symbols": self.get_worst_symbols(),
            "best_hours": self.get_best_hours()[:5],
            "best_days": self.get_best_days(),
        }
