"""
Predictor – высокоуровневый интерфейс для ML предсказаний.
"""

import time
from typing import Dict, List
from src.core.logger import BotLogger
from src.ml.model_trainer import MLModelTrainer
from src.ml.feature_engineering import extract_ml_features


class MLPredictor:
    def __init__(self, logger: BotLogger):
        self.logger = logger
        self.trainer = MLModelTrainer(logger)
        self.trainer.load_models()
        self.last_train_time = 0
        self.train_interval = 7 * 86400

    def should_enter(self, indicators: Dict, df=None) -> bool:
        if not self.trainer.is_trained:
            return True
        features = extract_ml_features(indicators, df)
        proba = self.trainer.predict_ensemble(indicators)
        self.logger.debug(f"ML ансамбль: вероятность успеха {proba:.2f}")
        return proba >= 0.55

    def train_if_needed(self, trades: List[Dict]):
        if len(trades) < 50:
            return
        now = time.time()
        if now - self.last_train_time >= self.train_interval:
            self.trainer.train(trades)
            self.last_train_time = now