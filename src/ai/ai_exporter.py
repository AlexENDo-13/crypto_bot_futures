"""
AI Exporter v5.0 - Feature engineering, dataset builder, and signal exporter.
"""
import os
import json
import pickle
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np

from src.trading.data_fetcher import DataFetcher
from src.core.config import get_config
from src.core.logger import get_logger

logger = get_logger()


@dataclass
class FeatureVector:
    symbol: str
    timestamp: datetime
    returns_1m: float = 0
    returns_5m: float = 0
    returns_15m: float = 0
    returns_1h: float = 0
    rsi: float = 50
    rsi_slope: float = 0
    macd: float = 0
    macd_signal: float = 0
    macd_hist: float = 0
    ema_ratio: float = 1
    atr_pct: float = 0
    bb_position: float = 0.5
    bb_width: float = 0
    volume_ratio: float = 1
    volume_trend: float = 0
    support_dist: float = 0
    resistance_dist: float = 0
    future_return_15m: float = 0
    label: int = 0

    def to_dict(self):
        return asdict(self)

    def to_list(self):
        return [
            self.returns_1m, self.returns_5m, self.returns_15m, self.returns_1h,
            self.rsi, self.rsi_slope, self.macd, self.macd_signal, self.macd_hist,
            self.ema_ratio, self.atr_pct, self.bb_position, self.bb_width,
            self.volume_ratio, self.volume_trend, self.support_dist, self.resistance_dist,
        ]


class AIExporter:
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.config = get_config().ai
        self.model_dir = Path(self.config.model_path)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        logger.info("AIExporter v5.0 initialized")

    def extract_features(self, symbol: str, timeframe: str = "15m") -> Optional[FeatureVector]:
        try:
            tf_data = self.data_fetcher.get_multi_timeframe(symbol)
            if timeframe not in tf_data:
                return None

            df = self.data_fetcher.calculate_indicators(tf_data[timeframe])
            if len(df) < 50:
                return None

            latest = df.iloc[-1]
            fv = FeatureVector(symbol=symbol, timestamp=latest.name)

            for tf, label in [("1m", "1m"), ("5m", "5m"), ("15m", "15m"), ("1h", "1h")]:
                if tf in tf_data and len(tf_data[tf]) > 1:
                    setattr(fv, f"returns_{label}", float(tf_data[tf]["close"].pct_change().iloc[-1]))

            fv.rsi = float(latest.get("rsi", 50))
            fv.rsi_slope = float(latest.get("rsi_slope", 0))
            fv.macd = float(latest.get("macd", 0))
            fv.macd_signal = float(latest.get("macd_signal", 0))
            fv.macd_hist = float(latest.get("macd_hist", 0))
            fv.ema_ratio = float(latest.get("ema_ratio", 1))
            fv.atr_pct = float(latest.get("atr_pct", 0))
            fv.bb_position = float(latest.get("bb_position", 0.5))
            fv.bb_width = float(latest.get("bb_width", 0))
            fv.volume_ratio = float(latest.get("volume_ratio", 1))
            fv.volume_trend = float(latest.get("volume_trend", 0))
            fv.support_dist = float(latest.get("support_dist", 0))
            fv.resistance_dist = float(latest.get("resistance_dist", 0))

            return fv
        except Exception as e:
            logger.error("Feature extraction error: %s", e)
            return None

    def build_dataset(self, symbols: List[str], samples_per_symbol: int = 500, save: bool = True) -> pd.DataFrame:
        logger.info("Building dataset | symbols=%d samples=%d", len(symbols), samples_per_symbol)
        all_features = []

        for symbol in symbols:
            try:
                df = self.data_fetcher.get_klines(symbol, "15m", limit=samples_per_symbol + 50)
                if len(df) < samples_per_symbol + 20:
                    continue

                df = self.data_fetcher.calculate_indicators(df)

                for i in range(50, len(df) - 4):
                    window = df.iloc[i-50:i+1]
                    fv = self._extract_from_window(symbol, window)
                    if fv is None:
                        continue

                    future_price = df["close"].iloc[i + 4]
                    current_price = df["close"].iloc[i]
                    fv.future_return_15m = (future_price - current_price) / current_price * 100

                    threshold = 0.3
                    if fv.future_return_15m > threshold:
                        fv.label = 1
                    elif fv.future_return_15m < -threshold:
                        fv.label = -1
                    else:
                        fv.label = 0

                    all_features.append(fv.to_dict())

            except Exception as e:
                logger.error("Dataset build error %s: %s", symbol, e)

        if not all_features:
            return pd.DataFrame()

        dataset = pd.DataFrame(all_features)
        if save:
            self._save_dataset(dataset)

        logger.info("Dataset built | samples=%d", len(dataset))
        return dataset

    def _extract_from_window(self, symbol: str, df: pd.DataFrame) -> Optional[FeatureVector]:
        if len(df) < 20:
            return None
        latest = df.iloc[-1]
        fv = FeatureVector(symbol=symbol, timestamp=latest.name)

        try:
            fv.returns_15m = float(df["close"].pct_change().iloc[-1])
            delta = df["close"].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            fv.rsi = float((100 - (100 / (1 + rs))).iloc[-1])

            ema_12 = df["close"].ewm(span=12, adjust=False).mean()
            ema_26 = df["close"].ewm(span=26, adjust=False).mean()
            fv.macd = float((ema_12 - ema_26).iloc[-1])

            ema_fast = df["close"].ewm(span=9, adjust=False).mean()
            ema_slow = df["close"].ewm(span=21, adjust=False).mean()
            fv.ema_ratio = float(ema_fast.iloc[-1] / ema_slow.iloc[-1]) if ema_slow.iloc[-1] != 0 else 1.0

            hl = df["high"] - df["low"]
            hc = abs(df["high"] - df["close"].shift())
            lc = abs(df["low"] - df["close"].shift())
            tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean()
            fv.atr_pct = float((atr / df["close"] * 100).iloc[-1])

            vol_ma = df["volume"].rolling(window=20).mean()
            fv.volume_ratio = float(latest["volume"] / vol_ma.iloc[-1]) if vol_ma.iloc[-1] > 0 else 1.0

            return fv
        except Exception:
            return None

    def _save_dataset(self, dataset: pd.DataFrame):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dataset.to_csv(self.model_dir / f"dataset_{ts}.csv", index=False)
        dataset.to_pickle(self.model_dir / f"dataset_{ts}.pkl")
        logger.info("Dataset saved")

    def load_latest_dataset(self) -> Optional[pd.DataFrame]:
        try:
            files = sorted(self.model_dir.glob("dataset_*.pkl"))
            if files:
                return pd.read_pickle(files[-1])
        except Exception as e:
            logger.error("Load error: %s", e)
        return None
