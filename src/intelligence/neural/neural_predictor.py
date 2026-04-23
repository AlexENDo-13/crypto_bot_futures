import pickle
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional

from src.core.logger import BotLogger

try:
    from sklearn.linear_model import SGDClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

class NeuralPredictor:
    def __init__(self, logger: BotLogger, confidence_threshold: float = 0.55):
        self.logger = logger
        self.confidence_threshold = confidence_threshold
        self.model: Optional[SGDClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.is_trained = False
        self.min_samples_for_training = 15

        self.models_dir = Path("data/models")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.model_file = self.models_dir / "sgd_model.pkl"
        self.scaler_file = self.models_dir / "scaler_sgd.pkl"

        if SKLEARN_AVAILABLE:
            self._load_or_create_model()
        else:
            self.logger.warning("scikit-learn не установлен. Нейропредиктор отключён.")

    def _load_or_create_model(self):
        if self.model_file.exists() and self.scaler_file.exists():
            try:
                with open(self.model_file, 'rb') as f:
                    self.model = pickle.load(f)
                with open(self.scaler_file, 'rb') as f:
                    self.scaler = pickle.load(f)
                self.is_trained = True
                self.logger.info("Загружена сохранённая модель SGD")
            except Exception:
                self._create_new_model()
        else:
            self._create_new_model()

    def _create_new_model(self):
        self.model = SGDClassifier(loss='log_loss', penalty='l2', random_state=42, warm_start=True)
        self.scaler = StandardScaler()
        self.is_trained = False

    def _extract_features(self, indicators: Dict) -> np.ndarray:
        feats = [
            indicators.get("atr_percent", 3.0),
            indicators.get("rsi", 50.0),
            indicators.get("adx", 20.0),
            float(indicators.get("trend_score", 0)),
            indicators.get("volume_score", 0.5),
            indicators.get("mfi", 50.0) if "mfi" in indicators else 50.0,
        ]
        bb_upper = indicators.get("bb_upper", 0)
        bb_lower = indicators.get("bb_lower", 0)
        close = indicators.get("close_price", 0)
        bb_width = (bb_upper - bb_lower) / close * 100 if close else 5.0
        feats.append(bb_width)
        return np.array(feats).reshape(1, -1)

    def predict_proba(self, indicators: Dict) -> float:
        if not self.is_trained:
            return 0.5
        X = self._extract_features(indicators)
        X_scaled = self.scaler.transform(X)
        proba = self.model.predict_proba(X_scaled)[0]
        return float(proba[1]) if len(proba) > 1 else 0.5

    def train_from_history(self, trades: List[Dict], data_fetcher=None):
        if not SKLEARN_AVAILABLE or len(trades) < self.min_samples_for_training:
            return

        X_list, y_list = [], []
        for trade in trades:
            ind = trade.get("indicators_at_entry")
            if not ind:
                continue
            feats = self._extract_features(ind).flatten()
            X_list.append(feats)
            y_list.append(1 if trade.get("pnl", 0) > 0 else 0)

        if len(X_list) < self.min_samples_for_training:
            return

        X = np.array(X_list)
        y = np.array(y_list)
        self.scaler.fit(X)
        X_scaled = self.scaler.transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True

        with open(self.model_file, 'wb') as f:
            pickle.dump(self.model, f)
        with open(self.scaler_file, 'wb') as f:
            pickle.dump(self.scaler, f)
        self.logger.info(f"Модель обучена на {len(X_list)} сделках")