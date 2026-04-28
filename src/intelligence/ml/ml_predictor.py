#!/usr/bin/env python3
"""
ML Predictor v1 (C1+C2) — Random Forest for entry/no-entry + 20+ features.
Features: funding, delta, imbalance, momentum, volatility, volume, trend strength, etc.
"""
import json
import os
import time
import logging
import pickle
from collections import deque
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import numpy as np

logger = logging.getLogger("CryptoBot.ML")

# Try to import sklearn, fallback to simple heuristic if unavailable
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not installed — ML predictor will use heuristic fallback")

class MLPredictor:
    def __init__(self, model_path: str = "logs/ml_model.pkl",
                 data_path: str = "logs/ml_training_data.json",
                 min_training_samples: int = 30):
        self.model_path = model_path
        self.data_path = data_path
        self.min_samples = min_training_samples
        self._model = None
        self._scaler = None
        self._training_data: List[Dict] = []
        self._feature_names = self._get_feature_names()
        self._last_training = 0
        self._training_interval = 3600  # Retrain every hour
        self._prediction_history: deque = deque(maxlen=100)
        self._accuracy_window: deque = deque(maxlen=50)
        self._load()

    def _get_feature_names(self) -> List[str]:
        """Define 20+ features for the model."""
        return [
            # Price action (4)
            "rsi", "macd_hist", "macd_signal", "price_vs_ema20",
            # Trend (3)
            "adx", "di_plus", "di_minus",
            # Volatility (3)
            "atr_percent", "bb_width", "bb_position",
            # Volume (3)
            "volume_ratio", "obv_slope", "vwap_distance",
            # Market microstructure (4)
            "funding_rate", "orderbook_imbalance", "bid_ask_spread", "liquidation_delta",
            # Multi-timeframe (3)
            "mtf_agreement", "higher_tf_trend", "lower_tf_momentum",
            # Time/Context (2)
            "hour_of_day", "market_regime_score",
            # Composite (2)
            "signal_strength", "confidence_score"
        ]

    def _load(self):
        if os.path.exists(self.model_path) and SKLEARN_AVAILABLE:
            try:
                with open(self.model_path, "rb") as f:
                    data = pickle.load(f)
                    self._model = data.get("model")
                    self._scaler = data.get("scaler")
                logger.info("ML model loaded from disk")
            except Exception as e:
                logger.error(f"ML model load error: {e}")
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    self._training_data = json.load(f)
                logger.info(f"ML training data loaded: {len(self._training_data)} samples")
            except Exception as e:
                logger.error(f"ML data load error: {e}")

    def _save(self):
        if SKLEARN_AVAILABLE and self._model is not None:
            try:
                os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
                with open(self.model_path, "wb") as f:
                    pickle.dump({"model": self._model, "scaler": self._scaler}, f)
            except Exception as e:
                logger.error(f"ML model save error: {e}")
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(self._training_data[-500:], f, indent=2)
        except Exception as e:
            logger.error(f"ML data save error: {e}")

    def extract_features(self, candidate: Dict) -> np.ndarray:
        """Extract feature vector from candidate signal."""
        ind = candidate.get("indicators", {})

        features = {
            # Price action
            "rsi": ind.get("rsi", 50),
            "macd_hist": ind.get("macd_hist", 0),
            "macd_signal": 1 if ind.get("macd_hist", 0) > 0 else 0,
            "price_vs_ema20": ind.get("price_vs_ema20", 0),
            # Trend
            "adx": ind.get("adx", 20),
            "di_plus": ind.get("di_plus", 20),
            "di_minus": ind.get("di_minus", 20),
            # Volatility
            "atr_percent": ind.get("atr_percent", 1.0),
            "bb_width": ind.get("bb_width", 2.0),
            "bb_position": ind.get("bb_position", 0.5),
            # Volume
            "volume_ratio": ind.get("volume_ratio", 1.0),
            "obv_slope": ind.get("obv_slope", 0),
            "vwap_distance": ind.get("vwap_distance", 0),
            # Market microstructure
            "funding_rate": ind.get("funding_rate", 0),
            "orderbook_imbalance": ind.get("orderbook_imbalance", 0),
            "bid_ask_spread": ind.get("spread_percent", 0.1),
            "liquidation_delta": ind.get("liquidation_delta", 0),
            # Multi-timeframe
            "mtf_agreement": ind.get("mtf_agreement", 0),
            "higher_tf_trend": ind.get("higher_tf_trend", 0),
            "lower_tf_momentum": ind.get("lower_tf_momentum", 0),
            # Time/Context
            "hour_of_day": datetime.utcnow().hour,
            "market_regime_score": ind.get("regime_score", 50),
            # Composite
            "signal_strength": ind.get("signal_strength", 0.5) * 100,
            "confidence_score": candidate.get("confidence_score", 50),
        }

        return np.array([features.get(f, 0) for f in self._feature_names])

    def predict(self, candidate: Dict) -> Tuple[bool, float, str]:
        """Predict if entry is profitable. Returns (should_enter, probability, reasoning)."""
        features = self.extract_features(candidate)

        if not SKLEARN_AVAILABLE or self._model is None or len(self._training_data) < self.min_samples:
            # Fallback heuristic
            return self._heuristic_predict(features, candidate)

        try:
            X = self._scaler.transform(features.reshape(1, -1))
            proba = self._model.predict_proba(X)[0]
            should_enter = proba[1] > 0.55  # Class 1 = profitable
            confidence = proba[1] if should_enter else proba[0]

            self._prediction_history.append({
                "time": time.time(),
                "probability": proba[1],
                "decision": should_enter,
                "symbol": candidate.get("symbol", "")
            })

            reason = f"RF predicts {proba[1]*100:.0f}% profit probability"
            return should_enter, proba[1], reason
        except Exception as e:
            logger.error(f"ML prediction error: {e}")
            return self._heuristic_predict(features, candidate)

    def _heuristic_predict(self, features: np.ndarray, candidate: Dict) -> Tuple[bool, float, str]:
        """Simple heuristic when ML is not available."""
        ind = candidate.get("indicators", {})
        score = 0
        reasons = []

        # RSI not extreme
        rsi = ind.get("rsi", 50)
        if 30 < rsi < 70:
            score += 1
            reasons.append("RSI neutral")

        # ADX shows trend
        adx = ind.get("adx", 0)
        if adx > 20:
            score += 1
            reasons.append("ADX trend")

        # Signal strength
        ss = ind.get("signal_strength", 0)
        if ss > 0.6:
            score += 1
            reasons.append("Strong signal")

        # ATR reasonable
        atr = ind.get("atr_percent", 1)
        if 0.3 < atr < 5:
            score += 1
            reasons.append("Good volatility")

        should = score >= 3
        prob = score / 4.0
        reason = f"Heuristic: {score}/4 ({', '.join(reasons)})"
        return should, prob, reason

    def record_outcome(self, candidate: Dict, pnl: float):
        """Record trade outcome for training."""
        features = self.extract_features(candidate)
        label = 1 if pnl > 0 else 0

        self._training_data.append({
            "features": features.tolist(),
            "label": label,
            "pnl": pnl,
            "symbol": candidate.get("symbol", ""),
            "time": time.time()
        })

        # Track accuracy
        if len(self._prediction_history) > 0:
            last_pred = self._prediction_history[-1]
            if last_pred.get("symbol") == candidate.get("symbol", ""):
                correct = (last_pred["decision"] and pnl > 0) or (not last_pred["decision"] and pnl <= 0)
                self._accuracy_window.append(1 if correct else 0)

        # Retrain periodically
        now = time.time()
        if now - self._last_training > self._training_interval and len(self._training_data) >= self.min_samples:
            self._retrain()
            self._last_training = now

        if len(self._training_data) % 10 == 0:
            self._save()

    def _retrain(self):
        """Retrain the Random Forest model."""
        if not SKLEARN_AVAILABLE:
            return

        try:
            # Prepare data
            X = np.array([d["features"] for d in self._training_data])
            y = np.array([d["label"] for d in self._training_data])

            # Handle class imbalance
            n_pos = sum(y)
            n_neg = len(y) - n_pos
            class_weight = "balanced" if n_pos > 0 and n_neg > 0 else None

            # Scale features
            self._scaler = StandardScaler()
            X_scaled = self._scaler.fit_transform(X)

            # Train Random Forest
            self._model = RandomForestClassifier(
                n_estimators=50,
                max_depth=8,
                min_samples_split=5,
                min_samples_leaf=2,
                class_weight=class_weight,
                random_state=42,
                n_jobs=-1
            )
            self._model.fit(X_scaled, y)

            # Feature importance
            importance = dict(zip(self._feature_names, self._model.feature_importances_))
            top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]
            logger.info(f"ML RETRAINED: {len(y)} samples | Top features: {top_features}")

            self._save()
        except Exception as e:
            logger.error(f"ML retrain error: {e}")

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from trained model."""
        if self._model is not None and SKLEARN_AVAILABLE:
            return dict(zip(self._feature_names, self._model.feature_importances_))
        return {}

    def get_stats(self) -> Dict[str, Any]:
        accuracy = sum(self._accuracy_window) / len(self._accuracy_window) * 100 if self._accuracy_window else 0
        return {
            "sklearn_available": SKLEARN_AVAILABLE,
            "model_trained": self._model is not None,
            "training_samples": len(self._training_data),
            "min_samples_required": self.min_samples,
            "recent_accuracy": accuracy,
            "predictions_made": len(self._prediction_history),
            "feature_importance": self.get_feature_importance(),
            "top_features": sorted(self.get_feature_importance().items(), key=lambda x: x[1], reverse=True)[:5] if self._model else [],
        }
