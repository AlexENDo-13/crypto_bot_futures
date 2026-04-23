#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
indicators.py — адаптивный расчёт индикаторов.
Работает на тренде И в боковике.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any

def compute_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    result = {}
    if len(df) < 30:
        return result

    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    volume = df["volume"].values if "volume" in df.columns else np.ones(len(close))

    result["close_price"] = float(close[-1])

    # 1. ATR
    tr1 = high[1:] - low[1:]
    tr2 = np.abs(high[1:] - close[:-1])
    tr3 = np.abs(low[1:] - close[:-1])
    tr = np.maximum(np.maximum(tr1, tr2), tr3)

    atr = np.zeros(len(close))
    atr[14] = np.mean(tr[:14])
    for i in range(15, len(close)):
        atr[i] = (atr[i-1] * 13 + tr[i-1]) / 14

    result["atr"] = float(atr[-1])
    result["atr_percent"] = float((atr[-1] / close[-1]) * 100) if close[-1] > 0 else 0.0

    # 2. RSI
    diff = np.diff(close)
    gains = np.where(diff > 0, diff, 0)
    losses = np.where(diff < 0, -diff, 0)

    avg_gain = np.mean(gains[:14])
    avg_loss = np.mean(losses[:14])

    for i in range(14, len(diff)):
        avg_gain = (avg_gain * 13 + gains[i]) / 14
        avg_loss = (avg_loss * 13 + losses[i]) / 14

    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

    result["rsi"] = float(rsi)

    # 3. ADX
    plus_dm = high[1:] - high[:-1]
    minus_dm = low[:-1] - low[1:]
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0)

    tr_smooth = np.zeros(len(tr))
    plus_dm_smooth = np.zeros(len(plus_dm))
    minus_dm_smooth = np.zeros(len(minus_dm))

    tr_smooth[13] = np.sum(tr[:14])
    plus_dm_smooth[13] = np.sum(plus_dm[:14])
    minus_dm_smooth[13] = np.sum(minus_dm[:14])

    for i in range(14, len(tr)):
        tr_smooth[i] = tr_smooth[i-1] - tr_smooth[i-1]/14 + tr[i]
        plus_dm_smooth[i] = plus_dm_smooth[i-1] - plus_dm_smooth[i-1]/14 + plus_dm[i]
        minus_dm_smooth[i] = minus_dm_smooth[i-1] - minus_dm_smooth[i-1]/14 + minus_dm[i]

    plus_di = 100 * plus_dm_smooth / (tr_smooth + 1e-10)
    minus_di = 100 * minus_dm_smooth / (tr_smooth + 1e-10)

    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)

    adx = np.zeros(len(dx))
    adx[13] = np.mean(dx[:14])
    for i in range(14, len(dx)):
        adx[i] = (adx[i-1] * 13 + dx[i]) / 14

    result["adx"] = float(adx[-1])
    result["plus_di"] = float(plus_di[-1])
    result["minus_di"] = float(minus_di[-1])

    # 4. MACD
    ema12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
    ema26 = pd.Series(close).ewm(span=26, adjust=False).mean().values
    macd_line = ema12 - ema26
    signal_line = pd.Series(macd_line).ewm(span=9, adjust=False).mean().values
    histogram = macd_line - signal_line

    result["macd"] = float(macd_line[-1])
    result["macd_signal"] = float(signal_line[-1])
    result["macd_hist"] = float(histogram[-1])

    # 5. Bollinger Bands
    sma20 = pd.Series(close).rolling(window=20).mean().values
    std20 = pd.Series(close).rolling(window=20).std().values
    upper_band = sma20 + 2 * std20
    lower_band = sma20 - 2 * std20

    result["bb_upper"] = float(upper_band[-1]) if not np.isnan(upper_band[-1]) else 0
    result["bb_lower"] = float(lower_band[-1]) if not np.isnan(lower_band[-1]) else 0
    result["bb_width"] = float((upper_band[-1] - lower_band[-1]) / sma20[-1] * 100) if sma20[-1] > 0 else 0
    result["bb_position"] = float((close[-1] - lower_band[-1]) / (upper_band[-1] - lower_band[-1] + 1e-10))

    # 6. Volume
    vol_sma20 = pd.Series(volume).rolling(window=20).mean().values
    vol_ratio = volume[-1] / (vol_sma20[-1] + 1e-10) if len(vol_sma20) > 0 else 1.0
    result["volume_ratio"] = float(vol_ratio)

    # 7. Ichimoku
    if len(high) >= 52 and len(low) >= 52:
        tenkan_sen = (np.max(high[-9:]) + np.min(low[-9:])) / 2
        kijun_sen = (np.max(high[-26:]) + np.min(low[-26:])) / 2
        senkou_span_a = (tenkan_sen + kijun_sen) / 2
        senkou_span_b = (np.max(high[-52:]) + np.min(low[-52:])) / 2

        result["ichimoku_tenkan"] = float(tenkan_sen)
        result["ichimoku_kijun"] = float(kijun_sen)
        result["ichimoku_cloud_top"] = float(max(senkou_span_a, senkou_span_b))
        result["ichimoku_cloud_bottom"] = float(min(senkou_span_a, senkou_span_b))
        result["ichimoku_above_cloud"] = close[-1] > max(senkou_span_a, senkou_span_b)
        result["ichimoku_below_cloud"] = close[-1] < min(senkou_span_a, senkou_span_b)

    # 8. EMA alignment
    ema8 = pd.Series(close).ewm(span=8, adjust=False).mean().values[-1]
    ema21 = pd.Series(close).ewm(span=21, adjust=False).mean().values[-1]
    ema55 = pd.Series(close).ewm(span=55, adjust=False).mean().values[-1]

    result["ema8"] = float(ema8)
    result["ema21"] = float(ema21)
    result["ema55"] = float(ema55)
    result["ema_trend"] = "UP" if ema8 > ema21 > ema55 else "DOWN" if ema8 < ema21 < ema55 else "NEUTRAL"

    # 9. Market regime detection
    bb_width = result["bb_width"]
    adx_val = result["adx"]
    if bb_width < 2.0 and adx_val < 20:
        result["market_regime"] = "SIDEWAYS"
    elif adx_val >= 25:
        result["market_regime"] = "TRENDING"
    else:
        result["market_regime"] = "TRANSITION"

    # --- SIGNAL GENERATION (ADAPTIVE) ---
    current_hist = histogram[-1]
    prev_hist = histogram[-2] if len(histogram) > 1 else 0
    current_rsi = result["rsi"]
    current_adx = result["adx"]
    current_plus_di = result["plus_di"]
    current_minus_di = result["minus_di"]
    bb_pos = result["bb_position"]
    regime = result["market_regime"]

    trend_score = 0
    signal_strength = 0.0
    direction = "NEUTRAL"
    entry_type = "none"

    volume_ok = vol_ratio >= 0.8

    # === TRENDING MARKET SIGNALS ===
    if regime == "TRENDING":
        long_conditions = []
        if current_hist > 0 and prev_hist <= 0:
            long_conditions.append("macd_cross")
        if current_hist > 0:
            long_conditions.append("macd_positive")
        if current_rsi < 70:
            long_conditions.append("rsi_ok")
        if current_adx >= 15:
            long_conditions.append("adx_ok")
        if current_plus_di > current_minus_di:
            long_conditions.append("di_plus")
        if close[-1] > lower_band[-1]:
            long_conditions.append("bb_ok")
        if volume_ok:
            long_conditions.append("volume_ok")
        if ema8 > ema21:
            long_conditions.append("ema_bull")

        short_conditions = []
        if current_hist < 0 and prev_hist >= 0:
            short_conditions.append("macd_cross")
        if current_hist < 0:
            short_conditions.append("macd_negative")
        if current_rsi > 30:
            short_conditions.append("rsi_ok")
        if current_adx >= 15:
            short_conditions.append("adx_ok")
        if current_minus_di > current_plus_di:
            short_conditions.append("di_minus")
        if close[-1] < upper_band[-1]:
            short_conditions.append("bb_ok")
        if volume_ok:
            short_conditions.append("volume_ok")
        if ema8 < ema21:
            short_conditions.append("ema_bear")

        if len(long_conditions) >= 4 and ("macd_cross" in long_conditions or "macd_positive" in long_conditions):
            direction = "LONG"
            signal_strength = min(1.0, len(long_conditions) / 7.0 + 0.15)
            entry_type = "trend_long"
            trend_score = 1
        elif len(short_conditions) >= 4 and ("macd_cross" in short_conditions or "macd_negative" in short_conditions):
            direction = "SHORT"
            signal_strength = min(1.0, len(short_conditions) / 7.0 + 0.15)
            entry_type = "trend_short"
            trend_score = -1

    # === SIDEWAYS MARKET SIGNALS (Bollinger Bounce) ===
    elif regime == "SIDEWAYS":
        long_conditions = []
        if bb_pos < 0.15 and close[-1] > close[-2]:
            long_conditions.append("bb_bounce_up")
        if current_rsi < 45:
            long_conditions.append("rsi_oversold")
        if current_rsi > 30:
            long_conditions.append("rsi_not_extreme")
        if volume_ok:
            long_conditions.append("volume_ok")
        if close[-1] > ema21:
            long_conditions.append("above_ema21")
        if current_hist > prev_hist:
            long_conditions.append("macd_rising")

        short_conditions = []
        if bb_pos > 0.85 and close[-1] < close[-2]:
            short_conditions.append("bb_bounce_down")
        if current_rsi > 55:
            short_conditions.append("rsi_overbought")
        if current_rsi < 70:
            short_conditions.append("rsi_not_extreme")
        if volume_ok:
            short_conditions.append("volume_ok")
        if close[-1] < ema21:
            short_conditions.append("below_ema21")
        if current_hist < prev_hist:
            short_conditions.append("macd_falling")

        if len(long_conditions) >= 4:
            direction = "LONG"
            signal_strength = min(1.0, len(long_conditions) / 6.0 + 0.1)
            entry_type = "sideways_long"
            trend_score = 1
        elif len(short_conditions) >= 4:
            direction = "SHORT"
            signal_strength = min(1.0, len(short_conditions) / 6.0 + 0.1)
            entry_type = "sideways_short"
            trend_score = -1

    # === TRANSITION MARKET (mixed signals) ===
    else:
        long_conditions = []
        if current_hist > 0 and prev_hist <= 0:
            long_conditions.append("macd_cross")
        if current_rsi < 60:
            long_conditions.append("rsi_ok")
        if current_adx >= 15:
            long_conditions.append("adx_ok")
        if current_plus_di > current_minus_di:
            long_conditions.append("di_plus")
        if volume_ok:
            long_conditions.append("volume_ok")
        if ema8 > ema21:
            long_conditions.append("ema_bull")

        short_conditions = []
        if current_hist < 0 and prev_hist >= 0:
            short_conditions.append("macd_cross")
        if current_rsi > 40:
            short_conditions.append("rsi_ok")
        if current_adx >= 15:
            short_conditions.append("adx_ok")
        if current_minus_di > current_plus_di:
            short_conditions.append("di_minus")
        if volume_ok:
            short_conditions.append("volume_ok")
        if ema8 < ema21:
            short_conditions.append("ema_bear")

        if len(long_conditions) >= 4 and "macd_cross" in long_conditions:
            direction = "LONG"
            signal_strength = min(1.0, len(long_conditions) / 6.0)
            entry_type = "transition_long"
            trend_score = 1
        elif len(short_conditions) >= 4 and "macd_cross" in short_conditions:
            direction = "SHORT"
            signal_strength = min(1.0, len(short_conditions) / 6.0)
            entry_type = "transition_short"
            trend_score = -1

    # Boost signal strength with ADX
    if direction != "NEUTRAL" and current_adx > 25:
        signal_strength = min(1.0, signal_strength + 0.15)

    result["trend_score"] = trend_score
    result["signal_direction"] = direction
    result["signal_strength"] = signal_strength
    result["entry_type"] = entry_type
    result["signal_conditions"] = long_conditions if direction == "LONG" else short_conditions
    result["macd_cross"] = (current_hist > 0 and prev_hist <= 0) or (current_hist < 0 and prev_hist >= 0)

    return result
