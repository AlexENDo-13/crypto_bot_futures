"""
CryptoBot v7.1 - ML Engine
"""
import logging
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

SKLEARN_OK = False
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_OK = True
except ImportError:
    pass

class MLEngine:
    def __init__(self):
        self.logger = logging.getLogger("CryptoBot.ML")
        self.model = None
        self.scaler = None
        self.trained = False

        if SKLEARN_OK:
            self.model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
            self.scaler = StandardScaler()
            self.logger.info("MLEngine v7.1 | sklearn=True")
        else:
            self.logger.warning("MLEngine v7.1 | sklearn=False")

    def extract_features(self, df: pd.DataFrame) -> np.ndarray:
        features = []
        features.append(float(df["close"].iloc[-1]))
        features.append(float((df["close"].iloc[-1] - df["open"].iloc[-1]) / max(df["open"].iloc[-1], 1e-9)))
        features.append(float(df["high"].iloc[-1] / max(df["low"].iloc[-1], 1e-9) - 1))
        vol_sma = df["volume"].rolling(20).mean().iloc[-1]
        features.append(float(df["volume"].iloc[-1] / max(vol_sma, 1e-9)))
        if len(df) >= 20:
            features.append(float((df["close"].iloc[-1] - df["close"].iloc[-20]) / max(df["close"].iloc[-20], 1e-9)))
        else:
            features.append(0.0)
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean().iloc[-1]
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
        rs = gain / max(loss, 1e-9)
        rsi = 100 - (100 / (1 + rs))
        features.append(float(rsi / 100))
        return np.array(features).reshape(1, -1)

    def predict(self, features: np.ndarray) -> float:
        if not SKLEARN_OK or not self.trained or self.model is None:
            return 0.5
        try:
            features_scaled = self.scaler.transform(features)
            proba = self.model.predict_proba(features_scaled)[0]
            return float(proba[1])
        except Exception as e:
            self.logger.debug(f"ML predict error: {e}")
            return 0.5

    def filter_signal(self, signal_confidence: float, features: np.ndarray,
                      threshold: float = 0.5) -> tuple[bool, float]:
        if not self.trained:
            return signal_confidence >= threshold, signal_confidence
        ml_score = self.predict(features)
        combined = (signal_confidence + ml_score) / 2
        return combined >= threshold, combined
