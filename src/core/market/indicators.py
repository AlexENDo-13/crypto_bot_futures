#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Technical Indicators
"""
import pandas as pd
import numpy as np
from typing import Dict, Any


def compute_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or len(df) < 30:
        return {}
    df = df.copy()
    required = ["open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            return {}
    df.dropna(subset=required, inplace=True)
    if len(df) < 30:
        return {}

    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    volume = df["volume"].values
    result = {}
    current_price = float(close[-1])

    # ATR%
    tr1 = high[1:] - low[1:]
    tr2 = np.abs(high[1:] - close[:-1])
    tr3 = np.abs(low[1:] - close[:-1])
    tr = np.maximum(np.maximum(tr1, tr2), tr3)
    atr = float(pd.Series(tr).rolling(window=14).mean().iloc[-1]) if len(tr) >= 14 else float(np.mean(tr[-5:]))
    result["atr"] = atr
    result["atr_percent"] = (atr / current_price * 100) if current_price > 0 else 0.0

    # RSI
    delta = pd.Series(close).diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    result["rsi"] = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

    # EMA
    result["ema_fast"] = float(pd.Series(close).ewm(span=12, adjust=False).mean().iloc[-1])
    result["ema_slow"] = float(pd.Series(close).ewm(span=26, adjust=False).mean().iloc[-1])

    # MACD
    ema_12 = pd.Series(close).ewm(span=12, adjust=False).mean()
    ema_26 = pd.Series(close).ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    result["macd"] = float(macd_line.iloc[-1])
    result["macd_signal"] = float(signal_line.iloc[-1])
    result["macd_histogram"] = float(macd_line.iloc[-1] - signal_line.iloc[-1])

    # ADX (14)
    period = 14
    plus_dm = high[1:] - high[:-1]
    minus_dm = low[:-1] - low[1:]
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)

    atr_series = pd.Series(tr).rolling(window=period).mean()
    plus_di = 100 * pd.Series(plus_dm).rolling(window=period).mean() / atr_series.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm).rolling(window=period).mean() / atr_series.replace(0, np.nan)
    dx = (np.abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx = dx.rolling(window=period).mean()
    result["adx"] = float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0.0
    result["plus_di"] = float(plus_di.iloc[-1]) if not pd.isna(plus_di.iloc[-1]) else 0.0
    result["minus_di"] = float(minus_di.iloc[-1]) if not pd.isna(minus_di.iloc[-1]) else 0.0

    # Trend Score (0..4.5)
    trend_score = 0.0
    if result["ema_fast"] > result["ema_slow"]:
        trend_score += 1.0
    if result["macd_histogram"] > 0:
        trend_score += 1.0
    if result["adx"] > 20:
        trend_score += 1.0
    if result["plus_di"] > result["minus_di"]:
        trend_score += 1.0
    if result["rsi"] > 50:
        trend_score += 0.5
    result["trend_score"] = trend_score

    # Volume
    avg_volume = float(pd.Series(volume).rolling(window=20).mean().iloc[-1]) if len(volume) >= 20 else float(np.mean(volume))
    result["volume"] = float(volume[-1])
    result["volume_avg"] = avg_volume
    result["volume_ratio"] = (result["volume"] / avg_volume) if avg_volume > 0 else 0.0

    # Bollinger Bands (bonus)
    sma_20 = pd.Series(close).rolling(window=20).mean()
    std_20 = pd.Series(close).rolling(window=20).std()
    result["bb_upper"] = float((sma_20 + 2 * std_20).iloc[-1]) if not pd.isna(sma_20.iloc[-1]) else current_price
    result["bb_lower"] = float((sma_20 - 2 * std_20).iloc[-1]) if not pd.isna(sma_20.iloc[-1]) else current_price

    return result
