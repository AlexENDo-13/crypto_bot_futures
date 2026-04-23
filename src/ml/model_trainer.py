"""
ML Model Trainer – обучение ансамбля RandomForest + XGBoost на исторических данных.
"""

import pickle
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
from src.core.logger import BotLogger

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    import xgboost as xgb
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


class MLModelTrainer:
    def __init__(self, logger: BotLogger):
        self.logger = logger
        self.models_dir = Path("data/ml_models")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.rf_model = None
        self.xgb_model = None
        self.scaler = None
        self.is_trained = False

    def _extract_features(self, indicators: Dict) -> np.ndarray:
        feats = [
            indicators.get("atr_percent", 3.0),
            indicators.get("rsi", 50.0),
            indicators.get("adx", 20.0),
            float(indicators.get("trend_score", 0)),
            indicators.get("volume_score", 0.5),
            indicators.get("stoch_k", 50.0) if "stoch_k" in indicators else 50.0,
        ]
        return np.array(feats)

    def prepare_data(self, trades: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
        X, y = [], []
        for t in trades:
            ind = t.get("indicators_at_entry")
            if not ind:
                continue
            X.append(self._extract_features(ind))
            y.append(1 if t.get("pnl", 0) > 0 else 0)
        return np.array(X), np.array(y)

    def train(self, trades: List[Dict]):
        if not ML_AVAILABLE:
            self.logger.warning("ML библиотеки не установлены")
            return

        if len(trades) < 50:
            self.logger.info(f"Недостаточно сделок для обучения: {len(trades)}")
            return

        X, y = self.prepare_data(trades)
        if len(X) < 50:
            return

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.rf_model = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
        self.rf_model.fit(X_scaled, y)

        self.xgb_model = xgb.XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.1, use_label_encoder=False, eval_metric='logloss')
        self.xgb_model.fit(X_scaled, y)

        self.is_trained = True
        self._save_models()
        self.logger.info(f"ML модели обучены на {len(X)} примерах")

    def predict_ensemble(self, indicators: Dict) -> float:
        if not self.is_trained:
            return 0.5
        X = self._extract_features(indicators).reshape(1, -1)
        X_scaled = self.scaler.transform(X)
        rf_prob = self.rf_model.predict_proba(X_scaled)[0][1]
        xgb_prob = self.xgb_model.predict_proba(X_scaled)[0][1]
        return (rf_prob + xgb_prob) / 2.0

    def _save_models(self):
        with open(self.models_dir / "rf_model.pkl", "wb") as f:
            pickle.dump(self.rf_model, f)
        with open(self.models_dir / "xgb_model.pkl", "wb") as f:
            pickle.dump(self.xgb_model, f)
        with open(self.models_dir / "scaler.pkl", "wb") as f:
            pickle.dump(self.scaler, f)

    def load_models(self) -> bool:
        try:
            with open(self.models_dir / "rf_model.pkl", "rb") as f:
                self.rf_model = pickle.load(f)
            with open(self.models_dir / "xgb_model.pkl", "rb") as f:
                self.xgb_model = pickle.load(f)
            with open(self.models_dir / "scaler.pkl", "rb") as f:
                self.scaler = pickle.load(f)
            self.is_trained = True
            return True
        except:
            return False