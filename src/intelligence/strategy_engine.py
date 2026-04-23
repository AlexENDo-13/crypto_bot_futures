#!/usr/bin/env python3
import logging, time
from typing import Dict, Any

class StrategyEngine:
    def __init__(self, logger, settings):
        self.logger = logger; self.settings = settings
        self.last_trade_time = 0; self.trade_results = []; self.consecutive_losses = 0
        self.best_strategy = "default"; self.strategy_performance = {}
    def record_trade_result(self, pnl, strategy="default"):
        self.trade_results.append({"pnl": pnl, "time": time.time(), "strategy": strategy})
        if len(self.trade_results) > 200: self.trade_results = self.trade_results[-200:]
        if pnl < 0: self.consecutive_losses += 1
        else: self.consecutive_losses = 0
        if strategy not in self.strategy_performance: self.strategy_performance[strategy] = {"trades": 0, "wins": 0, "total_pnl": 0}
        self.strategy_performance[strategy]["trades"] += 1
        if pnl > 0: self.strategy_performance[strategy]["wins"] += 1
        self.strategy_performance[strategy]["total_pnl"] += pnl
    def get_recent_performance(self, window=20):
        recent = self.trade_results[-window:]
        if not recent: return {"win_rate": 0, "avg_pnl": 0, "total": 0, "consecutive_losses": 0, "strategies": self.strategy_performance}
        wins = sum(1 for t in recent if t["pnl"] > 0)
        total_pnl = sum(t["pnl"] for t in recent)
        return {"win_rate": wins / len(recent), "avg_pnl": total_pnl / len(recent), "total": len(recent),
                "consecutive_losses": self.consecutive_losses, "strategies": self.strategy_performance}
    def get_best_strategy(self):
        best = "default"; best_wr = 0
        for strat, perf in self.strategy_performance.items():
            if perf["trades"] > 5:
                wr = perf["wins"] / perf["trades"]
                if wr > best_wr: best_wr = wr; best = strat
        return best
