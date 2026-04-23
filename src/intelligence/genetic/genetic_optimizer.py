"""
Genetic Optimizer – оптимизация порогов индикаторов (RSI, ADX, ATR) раз в сутки.
"""

import random
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple
from src.core.logger import BotLogger


class GeneticOptimizer:
    def __init__(self, logger: BotLogger, config: Dict):
        self.logger = logger
        self.config = config
        self.population_size = 20
        self.generations = 10
        self.mutation_rate = 0.1
        self.crossover_rate = 0.7
        self.best_thresholds = None
        self.thresholds_file = Path("data/models/thresholds.json")
        self._load_best()

    def _load_best(self):
        if self.thresholds_file.exists():
            try:
                with open(self.thresholds_file, 'r') as f:
                    self.best_thresholds = json.load(f)
            except:
                pass

    def _save_best(self):
        with open(self.thresholds_file, 'w') as f:
            json.dump(self.best_thresholds, f, indent=2)

    def optimize(self, trade_history: List[Dict]) -> Dict:
        if len(trade_history) < 30:
            return self._default_thresholds()

        def fitness(thresholds: Dict) -> float:
            wins = 0
            total = 0
            for trade in trade_history:
                ind = trade.get("indicators_at_entry", {})
                rsi = ind.get("rsi", 50)
                adx = ind.get("adx", 20)
                atr = ind.get("atr_percent", 3)
                if rsi > thresholds.get("rsi_overbought", 70):
                    continue
                if rsi < thresholds.get("rsi_oversold", 30):
                    continue
                if adx < thresholds.get("min_adx", 20):
                    continue
                if atr < thresholds.get("min_atr", 1.5):
                    continue
                total += 1
                if trade.get("pnl", 0) > 0:
                    wins += 1
            return wins / total if total > 0 else 0.0

        population = [self._random_thresholds() for _ in range(self.population_size)]
        for gen in range(self.generations):
            scored = [(ind, fitness(ind)) for ind in population]
            scored.sort(key=lambda x: x[1], reverse=True)
            best = scored[0][0]
            new_pop = [best]
            while len(new_pop) < self.population_size:
                p1, _ = self._tournament(scored)
                p2, _ = self._tournament(scored)
                child = self._crossover(p1, p2)
                child = self._mutate(child)
                new_pop.append(child)
            population = new_pop

        self.best_thresholds = scored[0][0]
        self._save_best()
        self.logger.info(f"Оптимизированы пороги: {self.best_thresholds}")
        return self.best_thresholds

    def _random_thresholds(self) -> Dict:
        return {
            "rsi_oversold": random.randint(20, 35),
            "rsi_overbought": random.randint(65, 80),
            "min_adx": random.randint(15, 30),
            "min_atr": round(random.uniform(1.0, 3.0), 1)
        }

    def _default_thresholds(self) -> Dict:
        return {"rsi_oversold": 30, "rsi_overbought": 70, "min_adx": 20, "min_atr": 1.5}

    def _tournament(self, scored, k=3):
        selected = random.sample(scored, k)
        return max(selected, key=lambda x: x[1])

    def _crossover(self, p1: Dict, p2: Dict) -> Dict:
        child = {}
        for key in p1:
            child[key] = p1[key] if random.random() < 0.5 else p2[key]
        return child

    def _mutate(self, ind: Dict) -> Dict:
        mutated = ind.copy()
        if random.random() < self.mutation_rate:
            mutated["rsi_oversold"] = max(15, min(40, mutated["rsi_oversold"] + random.randint(-3, 3)))
        if random.random() < self.mutation_rate:
            mutated["rsi_overbought"] = max(60, min(85, mutated["rsi_overbought"] + random.randint(-3, 3)))
        if random.random() < self.mutation_rate:
            mutated["min_adx"] = max(10, min(40, mutated["min_adx"] + random.randint(-2, 2)))
        if random.random() < self.mutation_rate:
            mutated["min_atr"] = round(max(0.5, min(5.0, mutated["min_atr"] + random.uniform(-0.3, 0.3))), 1)
        return mutated