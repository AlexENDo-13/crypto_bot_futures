#!/usr/bin/env python3
"""
Correlation Matrix (C4) — tracks pair correlations to avoid overexposure.
"""
import json
import os
import time
import logging
from collections import deque
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

logger = logging.getLogger("CryptoBot.Correlation")

class CorrelationMatrix:
    def __init__(self, data_path: str = "logs/correlation_matrix.json",
                 lookback: int = 100, update_interval: int = 300):
        self.data_path = data_path
        self.lookback = lookback
        self.update_interval = update_interval
        self._price_history: Dict[str, deque] = {}
        self._returns_history: Dict[str, deque] = {}
        self._correlation_matrix: Dict[str, Dict[str, float]] = {}
        self._last_update = 0
        self._load()

    def _load(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._correlation_matrix = data.get("matrix", {})
                logger.info(f"Correlation matrix loaded: {len(self._correlation_matrix)} symbols")
            except Exception as e:
                logger.error(f"Correlation load error: {e}")

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump({
                    "matrix": self._correlation_matrix,
                    "last_update": time.time()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Correlation save error: {e}")

    def feed_price(self, symbol: str, price: float):
        """Feed price update for a symbol."""
        if symbol not in self._price_history:
            self._price_history[symbol] = deque(maxlen=self.lookback)
            self._returns_history[symbol] = deque(maxlen=self.lookback)

        self._price_history[symbol].append(float(price))

        # Calculate return
        prices = list(self._price_history[symbol])
        if len(prices) >= 2:
            ret = (prices[-1] - prices[-2]) / prices[-2] * 100 if prices[-2] > 0 else 0
            self._returns_history[symbol].append(ret)

        # Update matrix periodically
        now = time.time()
        if now - self._last_update > self.update_interval:
            self._update_matrix()
            self._last_update = now

    def _update_matrix(self):
        """Recalculate correlation matrix."""
        symbols = list(self._returns_history.keys())
        if len(symbols) < 2:
            return

        # Build returns matrix
        min_len = min(len(self._returns_history[s]) for s in symbols)
        if min_len < 10:
            return

        self._correlation_matrix = {}

        for i, sym1 in enumerate(symbols):
            self._correlation_matrix[sym1] = {}
            returns1 = list(self._returns_history[sym1])[-min_len:]

            for j, sym2 in enumerate(symbols):
                if i == j:
                    self._correlation_matrix[sym1][sym2] = 1.0
                    continue

                returns2 = list(self._returns_history[sym2])[-min_len:]

                try:
                    corr = np.corrcoef(returns1, returns2)[0, 1]
                    if math.isnan(corr):
                        corr = 0.0
                    self._correlation_matrix[sym1][sym2] = round(float(corr), 3)
                except Exception:
                    self._correlation_matrix[sym1][sym2] = 0.0

        logger.info(f"Correlation matrix updated: {len(symbols)} symbols")
        self._save()

    def get_correlation(self, sym1: str, sym2: str) -> float:
        """Get correlation between two symbols."""
        if sym1 in self._correlation_matrix and sym2 in self._correlation_matrix[sym1]:
            return self._correlation_matrix[sym1][sym2]
        return 0.0

    def get_highly_correlated(self, symbol: str, threshold: float = 0.7) -> List[str]:
        """Get symbols highly correlated with given symbol."""
        if symbol not in self._correlation_matrix:
            return []

        result = []
        for sym, corr in self._correlation_matrix[symbol].items():
            if sym != symbol and abs(corr) >= threshold:
                result.append(sym)
        return result

    def check_portfolio_risk(self, positions: List[str], max_correlation: float = 0.8) -> Tuple[bool, str]:
        """Check if portfolio has too much correlated exposure."""
        if len(positions) < 2:
            return True, "OK"

        max_corr = 0.0
        max_pair = ("", "")

        for i, p1 in enumerate(positions):
            for p2 in positions[i+1:]:
                corr = self.get_correlation(p1, p2)
                if abs(corr) > max_corr:
                    max_corr = abs(corr)
                    max_pair = (p1, p2)

        if max_corr > max_correlation:
            return False, f"High correlation: {max_pair[0]} vs {max_pair[1]} = {max_corr:.2f}"

        return True, f"Max correlation: {max_corr:.2f}"

    def get_diversification_score(self, positions: List[str]) -> float:
        """Score portfolio diversification 0-100."""
        if len(positions) < 2:
            return 100.0

        correlations = []
        for i, p1 in enumerate(positions):
            for p2 in positions[i+1:]:
                correlations.append(abs(self.get_correlation(p1, p2)))

        if not correlations:
            return 100.0

        avg_corr = sum(correlations) / len(correlations)
        # Lower correlation = higher score
        score = max(0, 100 - avg_corr * 100)
        return round(score, 1)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "symbols_tracked": len(self._returns_history),
            "matrix_size": len(self._correlation_matrix),
            "last_update": self._last_update,
            "sample_sizes": {k: len(v) for k, v in self._returns_history.items()}
        }
