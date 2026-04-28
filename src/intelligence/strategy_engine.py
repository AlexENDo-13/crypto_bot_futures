#!/usr/bin/env python3
"""StrategyEngine v11.3 — Enhanced with Session #2 learning + Session #3 ML."""
import time
from collections import deque
from typing import Dict, Any, List

from src.intelligence.trade_journal import TradeJournal
from src.intelligence.parameter_optimizer import ParameterOptimizer
from src.intelligence.time_based_learning import TimeBasedLearning
from src.intelligence.market_regime_v2 import MarketRegimeV2
from src.intelligence.self_confidence import SelfConfidence
from src.intelligence.error_patterns import ErrorPatternDetector
from src.intelligence.ml.ml_predictor import MLPredictor
from src.intelligence.ml.volatility_forecast import VolatilityForecaster
from src.intelligence.ml.correlation_matrix import CorrelationMatrix

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

        # Session #2 modules
        self.journal = TradeJournal()
        self.optimizer = ParameterOptimizer()
        self.time_learning = TimeBasedLearning()
        self.regime_detector = MarketRegimeV2()
        self.confidence = SelfConfidence()
        self.error_patterns = ErrorPatternDetector()

        # Session #3: ML modules
        self.ml_predictor = MLPredictor()
        self.vol_forecaster = VolatilityForecaster()
        self.correlation = CorrelationMatrix()

    def record_trade_result(self, pnl: float, strategy: str = "", entry_type: str = "",
                           market_regime: str = "", symbol: str = "",
                           entry_time_iso: str = "", sl_pct: float = 1.5,
                           tp_pct: float = 3.0, exit_reason: str = "",
                           max_profit_pct: float = 0.0, max_loss_pct: float = 0.0,
                           candidate: Dict = None):
        """Record trade outcome across all learning and ML modules."""
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

        # Feed Session #2 modules
        trade_record = {
            "symbol": symbol, "strategy": strategy_name, "realized_pnl": pnl,
            "exit_reason": exit_reason, "entry_time": entry_time_iso,
            "max_profit_pct": max_profit_pct, "max_loss_pct": max_loss_pct
        }
        self.journal.record_trade(trade_record)
        self.optimizer.record_trade_outcome(sl_pct, tp_pct, pnl, exit_reason, max_profit_pct, max_loss_pct)
        self.time_learning.record_trade(pnl, entry_time_iso)
        self.regime_detector.record_trade(market_regime or self._market_regime, pnl)
        self.error_patterns.record_trade(pnl)

        # Feed Session #3: ML
        if candidate:
            self.ml_predictor.record_outcome(candidate, pnl)
            # Feed return for volatility forecasting
            if symbol:
                ret = (pnl / max(abs(max_profit_pct), 0.1)) if max_profit_pct != 0 else 0
                self.vol_forecaster.feed_return(symbol, ret)

        # Periodic adaptation
        now = time.time()
        if now - self._last_adaptation > self._adaptation_interval:
            self._adapt_weights()
            self.optimizer.adapt()
            self._last_adaptation = now

    def _adapt_weights(self):
        if not self._strategy_performance:
            return
        best = max(self._strategy_performance.items(), key=lambda x: x[1]["avg_pnl"])
        self._current_best_strategy = best[0]
        recent_wr = sum(self._recent_results) / len(self._recent_results) * 100 if self._recent_results else 0
        self.logger.info(f"STRATEGY ADAPT: Best={best[0]} (avg_pnl={best[1]['avg_pnl']:+.4f}) | "
            f"Recent WR: {recent_wr:.1f}% | Strategies tracked: {len(self._strategy_performance)}")

    def score_candidate(self, candidate: Dict, balance: float = 100.0) -> float:
        """Score a candidate 0-100 using all learning + ML modules."""
        recent_wr = (self._winning_trades / self._total_trades * 100) if self._total_trades > 0 else 50.0

        # Base confidence from Session #2
        base_score = self.confidence.score_signal(
            candidate=candidate,
            strategy_engine=self,
            market_regime=self.regime_detector,
            time_learning=self.time_learning,
            trade_journal=self.journal,
            recent_win_rate=recent_wr,
            consecutive_losses=self.error_patterns._loss_streak
        )

        # Session #3: ML prediction boost
        if self.settings.get("ml_enabled", True):
            ml_should, ml_prob, ml_reason = self.ml_predictor.predict(candidate)
            ml_boost = (ml_prob - 0.5) * 20  # -10 to +10 boost
            base_score += ml_boost

            if not ml_should:
                base_score *= 0.7  # Heavy penalty if ML says no
                self.logger.info(f"ML REJECT: {candidate.get('symbol')} — {ml_reason}")
            else:
                self.logger.info(f"ML BOOST: {candidate.get('symbol')} +{ml_boost:.1f}% — {ml_reason}")

        return min(100, max(0, base_score))

    def can_trade(self, balance: float = 100.0) -> tuple:
        """Check if bot should trade now. Returns (ok, reason)."""
        ok, reason = self.error_patterns.can_trade()
        if not ok:
            return False, reason

        ok, reason = self.time_learning.is_good_time_to_trade()
        if not ok:
            return False, f"TIME: {reason}"

        return True, "OK"

    def check_correlation(self, candidate_symbol: str, open_positions: List[str]) -> Tuple[bool, str]:
        """Check if new symbol is too correlated with existing positions."""
        if not self.settings.get("correlation_filter_enabled", True):
            return True, "Correlation filter disabled"

        if not open_positions:
            return True, "No open positions"

        threshold = self.settings.get("max_correlation", 0.8)
        for pos_sym in open_positions:
            corr = self.correlation.get_correlation(candidate_symbol, pos_sym)
            if abs(corr) > threshold:
                return False, f"Correlation: {candidate_symbol} vs {pos_sym} = {corr:.2f} (max {threshold})"

        return True, "Correlation OK"

    def get_signal_weight(self, entry_type: str) -> float:
        if entry_type in self._strategy_performance:
            perf = self._strategy_performance[entry_type]
            if perf["trades"] >= 3:
                wr = perf["wins"] / perf["trades"]
                if perf["loss_streak"] >= 3:
                    return max(0.3, 0.5 + wr * 0.5)
                return 0.5 + wr
        return 1.0

    def update_market_regime(self, regime: str):
        self._regime_history.append(regime)
        if len(self._regime_history) >= 5:
            from collections import Counter
            self._market_regime = Counter(self._regime_history).most_common(1)[0][0]

    def feed_regime_data(self, prices: list, volumes: list = None, atrs: list = None):
        self.regime_detector.feed_data(prices, volumes, atrs)
        detected = self.regime_detector.detect_regime()
        self.update_market_regime(detected)

    def feed_price_for_ml(self, symbol: str, price: float, atr_percent: float = None):
        """Feed price data for ML modules."""
        self.vol_forecaster.feed_price(symbol, price, atr_percent)
        self.correlation.feed_price(symbol, price)

    def get_vol_adjustment(self, symbol: str) -> float:
        """Get position size adjustment based on volatility forecast."""
        return self.vol_forecaster.get_position_size_adjustment(symbol)

    def get_recent_performance(self) -> Dict[str, Any]:
        recent_wr = sum(self._recent_results) / len(self._recent_results) * 100 if self._recent_results else 0
        return {
            "total_trades": self._total_trades,
            "winning_trades": self._winning_trades,
            "win_rate": (self._winning_trades / self._total_trades * 100) if self._total_trades > 0 else 0,
            "recent_win_rate": recent_wr,
            "best_strategy": self._current_best_strategy,
            "strategies": dict(self._strategy_performance),
            # Session #2 stats
            "journal_summary": self.journal.get_summary(),
            "optimizer": self.optimizer.get_stats(),
            "time_learning": self.time_learning.get_stats(),
            "regime": self.regime_detector.get_stats(),
            "confidence": self.confidence.get_stats(),
            "error_patterns": self.error_patterns.get_stats(),
            # Session #3 stats
            "ml_predictor": self.ml_predictor.get_stats(),
            "volatility_forecast": self.vol_forecaster.get_stats(),
            "correlation_matrix": self.correlation.get_stats(),
        }
