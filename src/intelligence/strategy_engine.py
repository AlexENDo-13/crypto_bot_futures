#!/usr/bin/env python3
import time
from typing import Dict, List
from collections import deque

class StrategyEngine:
    def __init__(self, logger, settings):
        self.logger = logger; self.settings = settings
        self._trade_results = deque(maxlen=100)
        self._strategy_performance = {}
        self._last_best = "default"

    def record_trade_result(self, pnl: float, strategy: str = "default"):
        self._trade_results.append({"pnl": pnl, "strategy": strategy, "time": time.time()})
        if strategy not in self._strategy_performance:
            self._strategy_performance[strategy] = {"trades": 0, "wins": 0, "total_pnl": 0.0}
        self._strategy_performance[strategy]["trades"] += 1
        self._strategy_performance[strategy]["total_pnl"] += pnl
        if pnl > 0: self._strategy_performance[strategy]["wins"] += 1

    def get_recent_performance(self) -> Dict:
        if not self._strategy_performance: return {"best_strategy": "default", "total_trades": 0, "win_rate": 0}
        best = max(self._strategy_performance.items(), key=lambda x: x[1]["total_pnl"] / max(x[1]["trades"], 1))
        self._last_best = best[0]
        total = sum(s["trades"] for s in self._strategy_performance.values())
        wins = sum(s["wins"] for s in self._strategy_performance.values())
        return {
            "best_strategy": best[0],
            "best_win_rate": (best[1]["wins"] / best[1]["trades"] * 100) if best[1]["trades"] > 0 else 0,
            "total_trades": total,
            "overall_win_rate": (wins / total * 100) if total > 0 else 0,
        }
