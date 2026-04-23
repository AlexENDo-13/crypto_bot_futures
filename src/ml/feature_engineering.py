"""
Feature Engineering – расширенный набор признаков для ML.
"""

import numpy as np
import pandas as pd
from typing import Dict


def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['returns'] = df['close'].pct_change()
    df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
    df['volatility_5'] = df['returns'].rolling(5).std()
    df['volatility_20'] = df['returns'].rolling(20).std()
    df['high_low_ratio'] = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-9)
    df['position_in_range'] = (df['close'] - df['low'].rolling(20).min()) / (df['high'].rolling(20).max() - df['low'].rolling(20).min() + 1e-9)
    df['volume_ma_5'] = df['volume'].rolling(5).mean()
    df['volume_ratio'] = df['volume'] / (df['volume_ma_5'] + 1e-9)
    return df


def extract_ml_features(indicators: Dict, df: pd.DataFrame = None) -> np.ndarray:
    feats = [
        indicators.get("atr_percent", 3.0),
        indicators.get("rsi", 50.0),
        indicators.get("adx", 20.0),
        float(indicators.get("trend_score", 0)),
        indicators.get("volume_score", 0.5),
        indicators.get("stoch_k", 50.0) if "stoch_k" in indicators else 50.0,
        indicators.get("macd_histogram", 0.0) if "macd_histogram" in indicators else 0.0,
    ]
    if df is not None and len(df) > 20:
        df_feat = add_technical_features(df.tail(30))
        feats.append(df_feat['volatility_20'].iloc[-1] if not pd.isna(df_feat['volatility_20'].iloc[-1]) else 0.0)
        feats.append(df_feat['position_in_range'].iloc[-1] if not pd.isna(df_feat['position_in_range'].iloc[-1]) else 0.5)
        feats.append(df_feat['volume_ratio'].iloc[-1] if not pd.isna(df_feat['volume_ratio'].iloc[-1]) else 1.0)
    else:
        feats.extend([0.0, 0.5, 1.0])
    return np.array(feats)