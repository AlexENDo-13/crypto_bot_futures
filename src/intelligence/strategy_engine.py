"""
Strategy Engine – эволюция весов и расчёт рейтинга.
"""

import json
import random
import time
from pathlib import Path
from typing import Dict
from src.core.logger import BotLogger


class StrategyEngine:
    def __init__(self, logger: BotLogger, config):
        self.logger = logger
        self.config = config
        self.weights = {"volume": 0.25, "atr": 0.25, "trend": 0.30, "rsi": 0.10, "funding": 0.10}
        self.models_dir = Path("data/models")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._load_weights()
        self.last_trade_time = time.time()

    def _load_weights(self):
        wf = self.models_dir / "strategy_weights.json"
        if wf.exists():
            try:
                with open(wf) as f:
                    self.weights.update(json.load(f))
            except:
                pass

    def save_weights(self):
        with open(self.models_dir / "strategy_weights.json", 'w') as f:
            json.dump(self.weights, f, indent=2)

    def calculate_rating(self, symbol: str, volume: float, atr_percent: float,
                         trend_score: int, rsi: float, funding_rate: float) -> float:
        import math
        v_score = min(math.log10(max(volume, 1e6)) / 10, 1.0)
        a_score = min(atr_percent / 3, 1.0) if atr_percent <= 8 else max(0, 1 - (atr_percent - 8) / 10)
        t_score = abs(trend_score)
        r_score = 1.0 if 40 <= rsi <= 60 else (0.7 if 30 <= rsi < 40 or 60 < rsi <= 70 else 0.3)
        f_score = min(1.0, funding_rate * 1000) if funding_rate >= 0 else 0.0
        return (self.weights["volume"] * v_score + self.weights["atr"] * a_score +
                self.weights["trend"] * t_score + self.weights["rsi"] * r_score +
                self.weights["funding"] * f_score)

    def evolve(self, success: bool, symbol: str = None):
        mutation = 0.05 if success else 0.1
        for k in self.weights:
            self.weights[k] *= (1 + random.uniform(0, mutation)) if success else (1 - random.uniform(0, mutation))
        total = sum(self.weights.values())
        for k in self.weights:
            self.weights[k] /= total
        self.save_weights()

    def record_trade_result(self, pnl: float, symbol: str = None):
        self.last_trade_time = time.time()