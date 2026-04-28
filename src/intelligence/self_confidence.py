#!/usr/bin/env python3
"""
Self-Confidence Scorer (B5) — evaluates signals 0-100%.
Combines multiple factors: strategy performance, market regime, time window, recent streak.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("CryptoBot.Confidence")

class SelfConfidence:
    def __init__(self):
        self._recent_scores: list = []
        self._min_confidence_threshold = 45.0  # Don't trade below this

    def score_signal(self, candidate: Dict, 
                     strategy_engine=None,
                     market_regime=None,
                     time_learning=None,
                     trade_journal=None,
                     recent_win_rate: float = 50.0,
                     consecutive_losses: int = 0) -> float:
        """Score a trade signal 0-100. Higher = more confident."""
        scores = []
        weights = []

        # 1. Signal strength from indicators (0-100)
        ind = candidate.get("indicators", {})
        signal_strength = ind.get("signal_strength", 0.5) * 100
        scores.append(min(100, max(0, signal_strength)))
        weights.append(0.25)

        # 2. Strategy performance (0-100)
        entry_type = ind.get("entry_type", "mixed")
        if strategy_engine:
            strategy_weight = strategy_engine.get_signal_weight(entry_type)
            # Convert weight (0.3-1.5) to score (0-100)
            strategy_score = min(100, max(0, (strategy_weight - 0.3) / 1.2 * 100))
            scores.append(strategy_score)
            weights.append(0.20)
        else:
            scores.append(50)
            weights.append(0.20)

        # 3. Market regime fit (0-100)
        if market_regime:
            rec = market_regime.get_recommended_settings()
            direction = candidate.get("direction", "BOTH")
            regime_ok, _ = market_regime.should_trade(direction)
            regime_score = 80 if regime_ok else 20
            # Bonus for high confidence regime
            if market_regime._regime_confidence > 70:
                regime_score += 10
            scores.append(min(100, regime_score))
            weights.append(0.15)
        else:
            scores.append(50)
            weights.append(0.15)

        # 4. Time window quality (0-100)
        if time_learning:
            time_score = time_learning.get_current_score()
            scores.append(time_score)
            weights.append(0.15)
        else:
            scores.append(50)
            weights.append(0.15)

        # 5. Symbol historical performance (0-100)
        symbol = candidate.get("symbol", "")
        if trade_journal and symbol:
            report = trade_journal.get_symbol_report(symbol)
            verdict = report.get("verdict", "OK")
            if verdict == "AVOID":
                symbol_score = 10
            elif verdict == "CAUTION":
                symbol_score = 40
            else:
                symbol_score = min(100, 50 + report.get("win_rate", 50) / 2)
            scores.append(symbol_score)
            weights.append(0.15)
        else:
            scores.append(50)
            weights.append(0.15)

        # 6. Recent bot performance (0-100)
        recent_score = recent_win_rate
        # Penalize for consecutive losses
        if consecutive_losses > 0:
            recent_score -= consecutive_losses * 8  # -8% per consecutive loss
        scores.append(max(0, recent_score))
        weights.append(0.10)

        # Calculate weighted average
        total_weight = sum(weights)
        final_score = sum(s * w for s, w in zip(scores, weights)) / total_weight if total_weight > 0 else 50

        # Hard thresholds
        if consecutive_losses >= 3:
            final_score *= 0.7  # Heavy penalty
        if consecutive_losses >= 5:
            final_score *= 0.5

        final_score = min(100, max(0, final_score))
        self._recent_scores.append(final_score)
        if len(self._recent_scores) > 50:
            self._recent_scores.pop(0)

        logger.info(f"CONFIDENCE: {final_score:.0f}% for {symbol} | "
                    f"Signal={scores[0]:.0f} Strategy={scores[1]:.0f} Regime={scores[2]:.0f} "
                    f"Time={scores[3]:.0f} Symbol={scores[4]:.0f} Recent={scores[5]:.0f}")

        return final_score

    def should_take_trade(self, score: float) -> bool:
        """Determine if score is high enough to take the trade."""
        return score >= self._min_confidence_threshold

    def get_min_threshold(self) -> float:
        return self._min_confidence_threshold

    def set_min_threshold(self, threshold: float):
        self._min_confidence_threshold = max(0, min(100, threshold))

    def get_stats(self) -> Dict[str, Any]:
        avg_score = sum(self._recent_scores) / len(self._recent_scores) if self._recent_scores else 0
        return {
            "min_threshold": self._min_confidence_threshold,
            "avg_recent_score": avg_score,
            "scores_count": len(self._recent_scores),
        }
