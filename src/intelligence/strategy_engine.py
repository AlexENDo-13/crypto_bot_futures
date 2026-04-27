#!/usr/bin/env python3
"""StrategyEngine — adaptive strategy selection with performance tracking."""
import time
from collections import deque
from typing import Dict, Any, List

class StrategyEngine:
    """
    Адаптивный движок стратегий.
    Отслеживает производительность разных типов сигналов и адаптирует веса.
    """
    def __init__(self, logger, settings):
        self.logger = logger
        self.settings = settings
        self._trade_history: deque = deque(maxlen=100)
        self._strategy_performance: Dict[str, Dict[str, Any]] = {}
        self._recent_results: deque = deque(maxlen=20)
        self._total_trades = 0
        self._winning_trades = 0
        self._current_best_strategy = "mixed"
        self._last_adaptation = 0
        self._adaptation_interval = 1800  # 30 min

    def record_trade_result(self, pnl: float, strategy: str = "", entry_type: str = ""):
        self._total_trades += 1
        if pnl > 0:
            self._winning_trades += 1
            self._recent_results.append(1)
        else:
            self._recent_results.append(0)

        strategy_name = strategy or entry_type or "mixed"
        if strategy_name not in self._strategy_performance:
            self._strategy_performance[strategy_name] = {
                "trades": 0, "wins": 0, "total_pnl": 0.0, "avg_pnl": 0.0
            }
        perf = self._strategy_performance[strategy_name]
        perf["trades"] += 1
        if pnl > 0:
            perf["wins"] += 1
        perf["total_pnl"] += pnl
        perf["avg_pnl"] = perf["total_pnl"] / perf["trades"]

        self.logger.info(f"STRATEGY TRACKING: {strategy_name} | PnL={pnl:+.4f} | "
                        f"Total={perf['trades']} | Wins={perf['wins']} | Avg={perf['avg_pnl']:+.4f}")

        now = time.time()
        if now - self._last_adaptation > self._adaptation_interval:
            self._adapt_weights()
            self._last_adaptation = now

    def _adapt_weights(self):
        if not self._strategy_performance:
            return
        best = max(self._strategy_performance.items(), key=lambda x: x[1]["avg_pnl"])
        self._current_best_strategy = best[0]
        recent_wr = sum(self._recent_results) / len(self._recent_results) * 100 if self._recent_results else 0
        self.logger.info(f"STRATEGY ADAPTATION: Best strategy = {best[0]} (avg_pnl={best[1]['avg_pnl']:+.4f}) | "
                        f"Recent win rate: {recent_wr:.1f}%")

    def get_recent_performance(self) -> Dict[str, Any]:
        recent_wr = sum(self._recent_results) / len(self._recent_results) * 100 if self._recent_results else 0
        return {
            "total_trades": self._total_trades,
            "winning_trades": self._winning_trades,
            "win_rate": (self._winning_trades / self._total_trades * 100) if self._total_trades > 0 else 0,
            "recent_win_rate": recent_wr,
            "best_strategy": self._current_best_strategy,
            "strategies": dict(self._strategy_performance),
        }

    def get_signal_weight(self, entry_type: str) -> float:
        if entry_type in self._strategy_performance:
            perf = self._strategy_performance[entry_type]
            if perf["trades"] >= 3:
                wr = perf["wins"] / perf["trades"]
                return 0.5 + wr  # 0.5 to 1.5
        return 1.0
