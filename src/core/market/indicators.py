#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enhanced Technical Indicators — Swing/Trend focused, no scalping."""
import pandas as pd
import numpy as np
from typing import Dict, Any

def compute_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    if len(df) < 50:
        return {}

    close = df["close"].values.astype(float)
    high = df["high"].values.astype(float)
    low = df["low"].values.astype(float)
    volume = df["volume"].values.astype(float) if "volume" in df.columns else np.ones(len(close))

    # EMAs
    ema12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
    ema26 = pd.Series(close).ewm(span=26, adjust=False).mean().values
    ema50 = pd.Series(close).ewm(span=50, adjust=False).mean().values
    ema200 = pd.Series(close).ewm(span=200, adjust=False).mean().values
    macd_line = ema12 - ema26
    signal_line = pd.Series(macd_line).ewm(span=9, adjust=False).mean().values
    macd_hist = macd_line - signal_line

    # RSI
    delta = pd.Series(close).diff().values
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = pd.Series(gain).rolling(window=14).mean().values
    avg_loss = pd.Series(loss).rolling(window=14).mean().values
    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # ATR
    tr1 = high[1:] - low[1:]
    tr2 = np.abs(high[1:] - close[:-1])
    tr3 = np.abs(low[1:] - close[:-1])
    tr = np.maximum(np.maximum(tr1, tr2), tr3)
    atr_raw = pd.Series(tr).rolling(window=14).mean().values
    atr = np.concatenate([[np.nan], atr_raw])

    # ADX
    plus_dm = np.where(
        (high[1:] - high[:-1]) > (low[:-1] - low[1:]),
        np.maximum(high[1:] - high[:-1], 0.0), 0.0
    )
    minus_dm = np.where(
        (low[:-1] - low[1:]) > (high[1:] - high[:-1]),
        np.maximum(low[:-1] - low[1:], 0.0), 0.0
    )
    plus_di = 100.0 * pd.Series(plus_dm).rolling(window=14).mean().values / (atr[1:] + 1e-10)
    minus_di = 100.0 * pd.Series(minus_dm).rolling(window=14).mean().values / (atr[1:] + 1e-10)
    dx = 100.0 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx_raw = pd.Series(dx).rolling(window=14).mean().values
    adx = np.concatenate([[np.nan], adx_raw])

    # Bollinger Bands
    sma20 = pd.Series(close).rolling(window=20).mean().values
    std20 = pd.Series(close).rolling(window=20).std().values
    upper_band = sma20 + 2.0 * std20
    lower_band = sma20 - 2.0 * std20
    bb_width = (upper_band - lower_band) / sma20 if sma20[-1] != 0 else 0

    # VWAP
    typical_price = (high + low + close) / 3.0
    vwap = np.cumsum(typical_price * volume) / (np.cumsum(volume) + 1e-10)

    # Stochastic
    lowest_low = pd.Series(low).rolling(window=14).min().values
    highest_high = pd.Series(high).rolling(window=14).max().values
    stoch_k = 100.0 * (close - lowest_low) / (highest_high - lowest_low + 1e-10)
    stoch_d = pd.Series(stoch_k).rolling(window=3).mean().values

    # OBV
    obv = np.zeros(len(close))
    for i in range(1, len(close)):
        if close[i] > close[i - 1]:
            obv[i] = obv[i - 1] + volume[i]
        elif close[i] < close[i - 1]:
            obv[i] = obv[i - 1] - volume[i]
        else:
            obv[i] = obv[i - 1]

    # Ichimoku
    tenkan_sen = (pd.Series(high).rolling(window=9).max().values + pd.Series(low).rolling(window=9).min().values) / 2.0
    kijun_sen = (pd.Series(high).rolling(window=26).max().values + pd.Series(low).rolling(window=26).min().values) / 2.0
    senkou_span_a = (tenkan_sen + kijun_sen) / 2.0
    senkou_span_b = (pd.Series(high).rolling(window=52).max().values + pd.Series(low).rolling(window=52).min().values) / 2.0

    # Volume profile (simple)
    vol_sma20 = pd.Series(volume).rolling(window=20).mean().values
    vol_ratio = volume / (vol_sma20 + 1e-10)

    # Current values
    idx = -1
    current_close = float(close[idx])
    current_atr = float(atr[idx]) if not np.isnan(atr[idx]) else current_close * 0.01
    current_adx = float(adx[idx]) if not np.isnan(adx[idx]) else 0.0
    current_rsi = float(rsi[idx]) if not np.isnan(rsi[idx]) else 50.0
    current_macd = float(macd_line[idx]) if not np.isnan(macd_line[idx]) else 0.0
    current_signal = float(signal_line[idx]) if not np.isnan(signal_line[idx]) else 0.0
    current_macd_hist = float(macd_hist[idx]) if not np.isnan(macd_hist[idx]) else 0.0
    current_stoch_k = float(stoch_k[idx]) if not np.isnan(stoch_k[idx]) else 50.0
    current_stoch_d = float(stoch_d[idx]) if not np.isnan(stoch_d[idx]) else 50.0
    current_vwap = float(vwap[idx]) if not np.isnan(vwap[idx]) else current_close
    current_obv = float(obv[idx]) if not np.isnan(obv[idx]) else 0.0
    current_tenkan = float(tenkan_sen[idx]) if not np.isnan(tenkan_sen[idx]) else current_close
    current_kijun = float(kijun_sen[idx]) if not np.isnan(kijun_sen[idx]) else current_close
    current_ema50 = float(ema50[idx]) if not np.isnan(ema50[idx]) else current_close
    current_ema200 = float(ema200[idx]) if not np.isnan(ema200[idx]) else current_close
    current_vol_ratio = float(vol_ratio[idx]) if not np.isnan(vol_ratio[idx]) else 1.0
    current_bb_width = float(bb_width[idx]) if not np.isnan(bb_width[idx]) else 0.0

    # === SIGNAL SCORING (Swing/Trend focused, NO scalping) ===
    bullish_signals = 0
    bearish_signals = 0
    signal_details = []

    # 1. MACD trend
    if current_macd > current_signal and current_macd_hist > 0:
        bullish_signals += 1
        signal_details.append("MACD bullish")
    elif current_macd < current_signal and current_macd_hist < 0:
        bearish_signals += 1
        signal_details.append("MACD bearish")

    # 2. RSI momentum (not overbought/oversold extremes)
    if 50 < current_rsi < 75:
        bullish_signals += 1
        signal_details.append("RSI bullish momentum")
    elif 25 < current_rsi < 50:
        bearish_signals += 1
        signal_details.append("RSI bearish momentum")

    # 3. Price vs VWAP
    if current_close > current_vwap:
        bullish_signals += 1
        signal_details.append("Price > VWAP")
    elif current_close < current_vwap:
        bearish_signals += 1
        signal_details.append("Price < VWAP")

    # 4. Ichimoku cloud
    if current_close > current_tenkan and current_tenkan > current_kijun:
        bullish_signals += 1
        signal_details.append("Ichimoku bullish")
    elif current_close < current_tenkan and current_tenkan < current_kijun:
        bearish_signals += 1
        signal_details.append("Ichimoku bearish")

    # 5. Stochastic
    if current_stoch_k > current_stoch_d and current_stoch_k > 20 and current_stoch_k < 80:
        bullish_signals += 1
        signal_details.append("Stoch bullish")
    elif current_stoch_k < current_stoch_d and current_stoch_k < 80 and current_stoch_k > 20:
        bearish_signals += 1
        signal_details.append("Stoch bearish")

    # 6. Bollinger Bands (trend confirmation, not mean reversion)
    if current_close > upper_band[idx] and current_adx > 20:
        bullish_signals += 1
        signal_details.append("BB breakout bullish")
    elif current_close < lower_band[idx] and current_adx > 20:
        bearish_signals += 1
        signal_details.append("BB breakout bearish")

    # 7. EMA trend
    if current_close > current_ema50 > current_ema200:
        bullish_signals += 1
        signal_details.append("EMA trend bullish")
    elif current_close < current_ema50 < current_ema200:
        bearish_signals += 1
        signal_details.append("EMA trend bearish")

    # 8. Volume confirmation
    if current_vol_ratio > 1.2:
        if bullish_signals > bearish_signals:
            bullish_signals += 0.5
            signal_details.append("Volume confirming bullish")
        elif bearish_signals > bullish_signals:
            bearish_signals += 0.5
            signal_details.append("Volume confirming bearish")

    # Direction determination (need strong consensus for swing trading)
    total_checks = bullish_signals + bearish_signals
    if bullish_signals >= 4 and bearish_signals <= 2 and current_adx >= 15:
        direction = "LONG"
    elif bearish_signals >= 4 and bullish_signals <= 2 and current_adx >= 15:
        direction = "SHORT"
    else:
        direction = "NEUTRAL"

    signal_strength = max(bullish_signals, bearish_signals) / max(total_checks, 1)

    # Market regime
    if current_adx > 30:
        regime = "STRONG_TREND"
    elif current_adx > 20:
        regime = "TRENDING"
    elif current_adx > 15:
        regime = "WEAK_TREND"
    else:
        regime = "RANGING"

    # Entry type classification
    if current_macd > current_signal and 50 < current_rsi < 70 and current_adx > 25:
        entry_type = "trend_momentum"
    elif current_close < lower_band[idx] and current_rsi < 35 and current_adx > 20:
        entry_type = "oversold_bounce"
    elif current_close > upper_band[idx] and current_rsi > 65 and current_adx > 20:
        entry_type = "overbought_short"
    elif current_adx > 25 and current_vol_ratio > 1.5:
        entry_type = "volume_breakout"
    else:
        entry_type = "mixed"

    atr_percent = (current_atr / current_close) * 100.0 if current_close > 0 else 0.0

    return {
        "adx": current_adx,
        "atr": current_atr,
        "atr_percent": atr_percent,
        "rsi": current_rsi,
        "macd": current_macd,
        "macd_signal": current_signal,
        "macd_hist": current_macd_hist,
        "stoch_k": current_stoch_k,
        "stoch_d": current_stoch_d,
        "vwap": current_vwap,
        "obv": current_obv,
        "tenkan_sen": current_tenkan,
        "kijun_sen": current_kijun,
        "ema50": current_ema50,
        "ema200": current_ema200,
        "vol_ratio": current_vol_ratio,
        "bb_width": current_bb_width,
        "bollinger_upper": float(upper_band[idx]) if not np.isnan(upper_band[idx]) else current_close,
        "bollinger_lower": float(lower_band[idx]) if not np.isnan(lower_band[idx]) else current_close,
        "signal_direction": direction,
        "signal_strength": round(signal_strength, 2),
        "market_regime": regime,
        "entry_type": entry_type,
        "close_price": current_close,
        "bullish_score": bullish_signals,
        "bearish_score": bearish_signals,
        "signal_details": signal_details,
    }
