"""
CryptoBot v6.0 - ML Engine
Machine learning signal filtering and prediction.
"""
import logging
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

SKLEARN_AVAILABLE = False
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    pass


class MLEngine:
    """Machine Learning Engine for signal filtering."""

    def __init__(self):
        self.logger = logging.getLogger("CryptoBot.ML")
        self.model = None
        self.scaler = None
        self.trained = False

        if SKLEARN_AVAILABLE:
            self.model = RandomForestClassifier(n_estimators=100, max_depth=10, 
                                                random_state=42, n_jobs=-1)
            self.scaler = StandardScaler()
            self.logger.info("MLEngine v6.0 initialized | sklearn=True")
        else:
            self.logger.warning("MLEngine v6.0 initialized | sklearn=False (install scikit-learn)")

    def extract_features(self, df: pd.DataFrame) -> np.ndarray:
        """Extract features from OHLCV data."""
        features = []

        # Price features
        features.append(df["close"].iloc[-1])
        features.append((df["close"].iloc[-1] - df["open"].iloc[-1]) / df["open"].iloc[-1])

        # Volatility
        features.append(df["high"].iloc[-1] / df["low"].iloc[-1] - 1)

        # Volume features
        vol_sma = df["volume"].rolling(20).mean().iloc[-1]
        features.append(df["volume"].iloc[-1] / vol_sma if vol_sma > 0 else 1.0)

        # Trend features
        if len(df) >= 20:
            features.append((df["close"].iloc[-1] - df["close"].iloc[-20]) / df["close"].iloc[-20])
        else:
            features.append(0.0)

        # RSI-like feature
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean().iloc[-1]
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
        rs = gain / loss if loss > 0 else 1.0
        rsi = 100 - (100 / (1 + rs))
        features.append(rsi / 100)

        return np.array(features).reshape(1, -1)

    def train(self, X: np.ndarray, y: np.ndarray):
        """Train the ML model."""
        if not SKLEARN_AVAILABLE or self.model is None:
            return

        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)

            self.model.fit(X_train_scaled, y_train)
            score = self.model.score(X_test_scaled, y_test)

            self.trained = True
            self.logger.info(f"ML model trained | accuracy={score:.3f}")
        except Exception as e:
            self.logger.error(f"ML training failed: {e}")

    def predict(self, features: np.ndarray) -> float:
        """Predict probability of successful trade."""
        if not SKLEARN_AVAILABLE or not self.trained or self.model is None:
            return 0.5

        try:
            features_scaled = self.scaler.transform(features)
            proba = self.model.predict_proba(features_scaled)[0]
            return float(proba[1])  # Probability of class 1 (success)
        except Exception as e:
            self.logger.error(f"ML prediction failed: {e}")
            return 0.5

    def filter_signal(self, signal_confidence: float, features: np.ndarray,
                     threshold: float = 0.6) -> tuple[bool, float]:
        """Filter signal using ML prediction."""
        if not self.trained:
            return signal_confidence >= threshold, signal_confidence

        ml_score = self.predict(features)
        combined = (signal_confidence + ml_score) / 2

        return combined >= threshold, combined
