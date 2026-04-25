"""
CryptoBot v9.0 - ML Engine
"""
import logging
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

class MLEngine:
    """Machine Learning signal filter."""

    def __init__(self):
        self.logger = logging.getLogger("CryptoBot.ML")
        self.model = None
        self.scaler = StandardScaler() if SKLEARN_OK else None
        self.trained = False
        self.features_history: List[List[float]] = []
        self.labels: List[int] = []
        self.logger.info("MLEngine v9.0 | sklearn=%s", SKLEARN_OK)

    def extract_features(self, df: pd.DataFrame) -> List[float]:
        """Extract features from price data."""
        try:
            returns = df["close"].pct_change().dropna()
            features = [
                float(returns.mean()),
                float(returns.std()),
                float(df["volume"].iloc[-1] / df["volume"].rolling(20).mean().iloc[-1]) if df["volume"].rolling(20).mean().iloc[-1] > 0 else 1.0,
                float((df["close"].iloc[-1] - df["close"].rolling(20).mean().iloc[-1]) / df["close"].rolling(20).mean().iloc[-1]) if df["close"].rolling(20).mean().iloc[-1] > 0 else 0.0,
                float(df["close"].iloc[-1] / df["close"].iloc[-20] - 1) if len(df) >= 20 else 0.0,
                float((df["high"].iloc[-1] - df["low"].iloc[-1]) / df["close"].iloc[-1]),
            ]
            return features
        except Exception as e:
            self.logger.debug("Feature extraction error: %s", e)
            return [0.0] * 6

    def train(self, features: List[float], label: int):
        """Add training sample."""
        self.features_history.append(features)
        self.labels.append(label)
        if len(self.features_history) > 1000:
            self.features_history = self.features_history[-500:]
            self.labels = self.labels[-500:]
        if len(self.features_history) >= 50 and SKLEARN_OK:
            try:
                X = np.array(self.features_history)
                y = np.array(self.labels)
                self.scaler = StandardScaler()
                X_scaled = self.scaler.fit_transform(X)
                self.model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
                self.model.fit(X_scaled, y)
                self.trained = True
                self.logger.info("ML model trained | samples=%d", len(y))
            except Exception as e:
                self.logger.warning("ML train error: %s", e)

    def filter_signal(self, confidence: float, features: List[float]) -> tuple:
        """Filter signal through ML model."""
        if not self.trained or not SKLEARN_OK or self.model is None:
            return True, confidence
        try:
            X = np.array([features])
            X_scaled = self.scaler.transform(X)
            prob = self.model.predict_proba(X_scaled)[0]
            ml_conf = prob[1] if len(prob) > 1 else prob[0]
            combined = confidence * 0.7 + ml_conf * 0.3
            return combined > 0.5, combined
        except Exception as e:
            self.logger.debug("ML filter error: %s", e)
            return True, confidence

    def save_model(self, path: str = "data/models/ml_model.pkl"):
        """Save model to disk."""
        if not self.trained or not SKLEARN_OK:
            return
        try:
            import pickle
            import os
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                pickle.dump({"model": self.model, "scaler": self.scaler}, f)
            self.logger.info("ML model saved to %s", path)
        except Exception as e:
            self.logger.warning("ML save error: %s", e)

    def load_model(self, path: str = "data/models/ml_model.pkl"):
        """Load model from disk."""
        if not SKLEARN_OK:
            return
        try:
            import pickle
            import os
            if os.path.exists(path):
                with open(path, "rb") as f:
                    data = pickle.load(f)
                    self.model = data.get("model")
                    self.scaler = data.get("scaler")
                    self.trained = True
                    self.logger.info("ML model loaded from %s", path)
        except Exception as e:
            self.logger.warning("ML load error: %s", e)
