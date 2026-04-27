#!/usr/bin/env python3
"""StrategyEngine v11 — Adaptive strategy selection with detailed performance tracking."""
import time
from collections import deque
from typing import Dict, Any, List

class StrategyEngine:
    def __init__(self, logger, settings):
        self.logger = logger
        self.settings = settings
        self._trade_history: deque = deque(maxlen=200)
        self._strategy_performance: Dict[str, Dict[str, Any]] = {}
        self._recent_results: deque = deque(maxlen=50)
        self._total_trades = 0
        self._winning_trades = 0
        self._current_best_strategy = "mixed"
        self._last_adaptation = 0
        self._adaptation_interval = 1800
        self._market_regime = "unknown"
        self._regime_history: deque = deque(maxlen=20)

    def record_trade_result(self, pnl: float, strategy: str = "", entry_type: str = "", market_regime: str = ""):
        self._total_trades += 1
        if pnl > 0:
            self._winning_trades += 1
            self._recent_results.append(1)
        else:
            self._recent_results.append(0)

        strategy_name = strategy or entry_type or "mixed"
        if strategy_name not in self._strategy_performance:
            self._strategy_performance[strategy_name] = {
                "trades": 0, "wins": 0, "total_pnl": 0.0, "avg_pnl": 0.0,
                "best_pnl": 0.0, "worst_pnl": 0.0, "win_streak": 0, "loss_streak": 0,
                "last_trade_time": 0
            }
        perf = self._strategy_performance[strategy_name]
        perf["trades"] += 1
        if pnl > 0:
            perf["wins"] += 1
            perf["win_streak"] += 1
            perf["loss_streak"] = 0
        else:
            perf["loss_streak"] += 1
            perf["win_streak"] = 0
        perf["total_pnl"] += pnl
        perf["avg_pnl"] = perf["total_pnl"] / perf["trades"]
        perf["best_pnl"] = max(perf["best_pnl"], pnl)
        perf["worst_pnl"] = min(perf["worst_pnl"], pnl)
        perf["last_trade_time"] = time.time()

        self.logger.info(f"STRATEGY TRACK: {strategy_name} | PnL={pnl:+.4f} | "
                         f"Total={perf['trades']} | Wins={perf['wins']} | Avg={perf['avg_pnl']:+.4f} | "
                         f"WinStreak={perf['win_streak']} | LossStreak={perf['loss_streak']}")

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
        self.logger.info(f"STRATEGY ADAPT: Best={best[0]} (avg_pnl={best[1]['avg_pnl']:+.4f}) | "
                         f"Recent WR: {recent_wr:.1f}% | Strategies tracked: {len(self._strategy_performance)}")

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
                # Reduce weight for strategies on losing streak
                if perf["loss_streak"] >= 3:
                    return max(0.3, 0.5 + wr * 0.5)
                return 0.5 + wr
        return 1.0

    def update_market_regime(self, regime: str):
        self._regime_history.append(regime)
        if len(self._regime_history) >= 5:
            # Most common regime in last 5
            from collections import Counter
            self._market_regime = Counter(self._regime_history).most_common(1)[0][0]
