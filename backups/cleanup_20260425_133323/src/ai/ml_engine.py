"""
ML Engine v5.0 - Lightweight ensemble model for signal prediction.
Uses sklearn with automatic retraining and feature importance.
"""
import os
import json
import pickle
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

from src.trading.data_fetcher import DataFetcher
from src.core.config import get_config
from src.core.logger import get_logger

logger = get_logger()

# Try to import sklearn
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, classification_report
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    logger.warning("scikit-learn not installed. ML features disabled.")


@dataclass
class MLPrediction:
    symbol: str
    direction: str  # UP, DOWN, NEUTRAL
    confidence: float
    probability: float
    features_used: List[str]


class MLEngine:
    """Machine learning prediction engine"""

    def __init__(self):
        self.config = get_config().ai
        self.model_dir = Path(self.config.model_path)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.data_fetcher = DataFetcher()

        self._models: Dict[str, any] = {}
        self._scaler: Optional[StandardScaler] = None
        self._feature_importance: Dict[str, float] = {}
        self._last_train_time: Optional[datetime] = None
        self._training = False

        self._load_models()
        logger.info("MLEngine v5.0 | sklearn=%s", HAS_SKLEARN)

    def _load_models(self):
        """Load saved models from disk"""
        if not HAS_SKLEARN:
            return

        model_file = self.model_dir / "ensemble_model.pkl"
        scaler_file = self.model_dir / "scaler.pkl"

        if model_file.exists():
            try:
                with open(model_file, "rb") as f:
                    self._models = pickle.load(f)
                logger.info("Loaded ML models from disk")
            except Exception as e:
                logger.error("Model load error: %s", e)

        if scaler_file.exists():
            try:
                with open(scaler_file, "rb") as f:
                    self._scaler = pickle.load(f)
            except Exception as e:
                logger.error("Scaler load error: %s", e)

    def _save_models(self):
        """Save models to disk"""
        if not HAS_SKLEARN:
            return

        try:
            with open(self.model_dir / "ensemble_model.pkl", "wb") as f:
                pickle.dump(self._models, f)
            if self._scaler:
                with open(self.model_dir / "scaler.pkl", "wb") as f:
                    pickle.dump(self._scaler, f)
            logger.info("ML models saved")
        except Exception as e:
            logger.error("Model save error: %s", e)

    def extract_features(self, symbol: str, timeframe: str = "15m") -> Optional[np.ndarray]:
        """Extract feature vector for prediction"""
        try:
            tf_data = self.data_fetcher.get_multi_timeframe(symbol)
            if timeframe not in tf_data:
                return None

            df = self.data_fetcher.calculate_indicators(tf_data[timeframe])
            if len(df) < 50:
                return None

            latest = df.iloc[-1]

            features = []
            feature_names = []

            # Price returns
            for tf, label in [("1m", "1m"), ("5m", "5m"), ("15m", "15m"), ("1h", "1h")]:
                if tf in tf_data and len(tf_data[tf]) > 1:
                    ret = tf_data[tf]["close"].pct_change().iloc[-1]
                    features.append(ret)
                    feature_names.append(f"returns_{label}")
                else:
                    features.append(0)
                    feature_names.append(f"returns_{label}")

            # RSI
            features.append(float(latest.get("rsi", 50)))
            feature_names.append("rsi")
            features.append(float(latest.get("rsi_slope", 0)))
            feature_names.append("rsi_slope")

            # MACD
            features.append(float(latest.get("macd", 0)))
            feature_names.append("macd")
            features.append(float(latest.get("macd_hist", 0)))
            feature_names.append("macd_hist")

            # EMA
            features.append(float(latest.get("ema_ratio", 1)))
            feature_names.append("ema_ratio")

            # ATR
            features.append(float(latest.get("atr_pct", 0)))
            feature_names.append("atr_pct")

            # BB
            features.append(float(latest.get("bb_position", 0.5)))
            feature_names.append("bb_position")
            features.append(float(latest.get("bb_width", 0)))
            feature_names.append("bb_width")

            # Volume
            features.append(float(latest.get("volume_ratio", 1)))
            feature_names.append("volume_ratio")

            # S/R
            features.append(float(latest.get("support_dist", 0)))
            feature_names.append("support_dist")
            features.append(float(latest.get("resistance_dist", 0)))
            feature_names.append("resistance_dist")

            return np.array(features).reshape(1, -1)

        except Exception as e:
            logger.error("Feature extraction error: %s", e)
            return None

    def predict(self, symbol: str, timeframe: str = "15m") -> Optional[MLPrediction]:
        """Predict direction for symbol"""
        if not HAS_SKLEARN or not self._models:
            return None

        features = self.extract_features(symbol, timeframe)
        if features is None:
            return None

        try:
            if self._scaler:
                features = self._scaler.transform(features)

            # Ensemble voting
            votes = {"UP": 0, "DOWN": 0, "NEUTRAL": 0}
            probs = []

            for name, model in self._models.items():
                pred = model.predict(features)[0]
                proba = model.predict_proba(features)[0]
                votes[pred] += 1
                probs.append(max(proba))

            direction = max(votes, key=votes.get)
            confidence = votes[direction] / len(self._models)
            avg_prob = np.mean(probs)

            return MLPrediction(
                symbol=symbol,
                direction=direction,
                confidence=confidence,
                probability=avg_prob,
                features_used=list(self.config.features)
            )

        except Exception as e:
            logger.error("Prediction error: %s", e)
            return None

    def train(self, dataset: pd.DataFrame = None, symbols: List[str] = None):
        """Train models on historical data"""
        if not HAS_SKLEARN:
            logger.warning("sklearn not available, skipping training")
            return

        if self._training:
            return
        self._training = True

        try:
            if dataset is None:
                from src.ai.ai_exporter import AIExporter
                exporter = AIExporter()
                dataset = exporter.build_dataset(symbols or ["BTC-USDT", "ETH-USDT"], samples_per_symbol=300)

            if dataset.empty or len(dataset) < self.config.min_samples_for_training:
                logger.warning("Insufficient data for training: %d samples", len(dataset))
                self._training = False
                return

            # Prepare features
            feature_cols = [c for c in dataset.columns if c not in ["symbol", "timestamp", "label", "future_return_15m"]]
            X = dataset[feature_cols].fillna(0)
            y = dataset["label"]

            # Scale
            self._scaler = StandardScaler()
            X_scaled = self._scaler.fit_transform(X)

            # Split
            X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)

            # Train ensemble
            self._models = {}

            if "rf" in self.config.ensemble_models:
                rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
                rf.fit(X_train, y_train)
                self._models["rf"] = rf
                logger.info("RF trained | acc=%.3f", accuracy_score(y_test, rf.predict(X_test)))

            if "gb" in self.config.ensemble_models:
                gb = GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42)
                gb.fit(X_train, y_train)
                self._models["gb"] = gb
                logger.info("GB trained | acc=%.3f", accuracy_score(y_test, gb.predict(X_test)))

            # Feature importance
            if "rf" in self._models:
                importances = dict(zip(feature_cols, self._models["rf"].feature_importances_))
                self._feature_importance = dict(sorted(importances.items(), key=lambda x: x[1], reverse=True))

            self._last_train_time = datetime.now()
            self._save_models()

            logger.info("ML training complete | samples=%d models=%d", len(dataset), len(self._models))

        except Exception as e:
            logger.error("Training error: %s", e)
        finally:
            self._training = False

    def should_retrain(self) -> bool:
        if self._last_train_time is None:
            return True
        hours = (datetime.now() - self._last_train_time).total_seconds() / 3600
        return hours >= self.config.retrain_interval_hours

    def get_feature_importance(self) -> Dict[str, float]:
        return dict(self._feature_importance)
