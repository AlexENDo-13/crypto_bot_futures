#!/usr/bin/env python3
import pandas as pd, numpy as np
from typing import Dict, Any

def compute_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    result = {}
    if len(df) < 30: return result
    close = df["close"].values; high = df["high"].values; low = df["low"].values
    volume = df["volume"].values if "volume" in df.columns else np.ones(len(close))
    result["close_price"] = float(close[-1])
    tr1 = high[1:] - low[1:]; tr2 = np.abs(high[1:] - close[:-1]); tr3 = np.abs(low[1:] - close[:-1])
    tr = np.maximum(np.maximum(tr1, tr2), tr3)
    atr = np.zeros(len(close)); atr[14] = np.mean(tr[:14])
    for i in range(15, len(close)): atr[i] = (atr[i-1]*13 + tr[i-1])/14
    result["atr"] = float(atr[-1]); result["atr_percent"] = float((atr[-1]/close[-1])*100) if close[-1] > 0 else 0.0
    diff = np.diff(close); gains = np.where(diff > 0, diff, 0); losses = np.where(diff < 0, -diff, 0)
    avg_gain = np.mean(gains[:14]); avg_loss = np.mean(losses[:14])
    for i in range(14, len(diff)): avg_gain = (avg_gain*13 + gains[i])/14; avg_loss = (avg_loss*13 + losses[i])/14
    rsi = 100.0 if avg_loss == 0 else 100.0 - (100.0/(1.0 + avg_gain/avg_loss))
    result["rsi"] = float(rsi)
    plus_dm = np.where((high[1:] - high[:-1]) > (low[:-1] - low[1:]), np.maximum(high[1:] - high[:-1], 0), 0)
    minus_dm = np.where((low[:-1] - low[1:]) > (high[1:] - high[:-1]), np.maximum(low[:-1] - low[1:], 0), 0)
    tr_s = np.zeros(len(tr)); pdm_s = np.zeros(len(plus_dm)); mdm_s = np.zeros(len(minus_dm))
    tr_s[13] = np.sum(tr[:14]); pdm_s[13] = np.sum(plus_dm[:14]); mdm_s[13] = np.sum(minus_dm[:14])
    for i in range(14, len(tr)):
        tr_s[i] = tr_s[i-1] - tr_s[i-1]/14 + tr[i]
        pdm_s[i] = pdm_s[i-1] - pdm_s[i-1]/14 + plus_dm[i]
        mdm_s[i] = mdm_s[i-1] - mdm_s[i-1]/14 + minus_dm[i]
    plus_di = 100 * pdm_s / (tr_s + 1e-10); minus_di = 100 * mdm_s / (tr_s + 1e-10)
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx = np.zeros(len(dx)); adx[13] = np.mean(dx[:14])
    for i in range(14, len(dx)): adx[i] = (adx[i-1]*13 + dx[i])/14
    result["adx"] = float(adx[-1]); result["plus_di"] = float(plus_di[-1]); result["minus_di"] = float(minus_di[-1])
    ema12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
    ema26 = pd.Series(close).ewm(span=26, adjust=False).mean().values
    macd_line = ema12 - ema26; signal_line = pd.Series(macd_line).ewm(span=9, adjust=False).mean().values
    histogram = macd_line - signal_line
    result["macd"] = float(macd_line[-1]); result["macd_signal"] = float(signal_line[-1]); result["macd_hist"] = float(histogram[-1])
    sma20 = pd.Series(close).rolling(window=20).mean().values; std20 = pd.Series(close).rolling(window=20).std().values
    ub = sma20 + 2*std20; lb = sma20 - 2*std20
    result["bb_upper"] = float(ub[-1]) if not np.isnan(ub[-1]) else 0
    result["bb_lower"] = float(lb[-1]) if not np.isnan(lb[-1]) else 0
    result["bb_width"] = float((ub[-1]-lb[-1])/sma20[-1]*100) if sma20[-1] > 0 else 0
    result["bb_position"] = float((close[-1]-lb[-1])/(ub[-1]-lb[-1]+1e-10))
    vol_sma20 = pd.Series(volume).rolling(window=20).mean().values
    result["volume_ratio"] = float(volume[-1]/(vol_sma20[-1]+1e-10)) if len(vol_sma20) > 0 else 1.0
    tp = (high + low + close)/3; vwap = np.cumsum(tp*volume)/np.cumsum(volume)
    result["vwap"] = float(vwap[-1]); result["above_vwap"] = close[-1] > vwap[-1]
    lowest_14 = pd.Series(low).rolling(window=14).min().values; highest_14 = pd.Series(high).rolling(window=14).max().values
    k_line = 100*(close - lowest_14)/(highest_14 - lowest_14 + 1e-10)
    d_line = pd.Series(k_line).rolling(window=3).mean().values
    result["stoch_k"] = float(k_line[-1]) if not np.isnan(k_line[-1]) else 50
    result["stoch_d"] = float(d_line[-1]) if not np.isnan(d_line[-1]) else 50
    obv = np.zeros(len(close)); obv[0] = volume[0]
    for i in range(1, len(close)):
        if close[i] > close[i-1]: obv[i] = obv[i-1] + volume[i]
        elif close[i] < close[i-1]: obv[i] = obv[i-1] - volume[i]
        else: obv[i] = obv[i-1]
    obv_sma20 = pd.Series(obv).rolling(window=20).mean().values
    result["obv"] = float(obv[-1]); result["obv_trend"] = "UP" if obv[-1] > obv_sma20[-1] else "DOWN"
    if len(high) >= 52 and len(low) >= 52:
        tenkan = (np.max(high[-9:]) + np.min(low[-9:]))/2
        kijun = (np.max(high[-26:]) + np.min(low[-26:]))/2
        senkou_a = (tenkan + kijun)/2; senkou_b = (np.max(high[-52:]) + np.min(low[-52:]))/2
        result["ichimoku_tenkan"] = float(tenkan); result["ichimoku_kijun"] = float(kijun)
        result["ichimoku_cloud_top"] = float(max(senkou_a, senkou_b))
        result["ichimoku_cloud_bottom"] = float(min(senkou_a, senkou_b))
        result["ichimoku_above_cloud"] = close[-1] > max(senkou_a, senkou_b)
        result["ichimoku_below_cloud"] = close[-1] < min(senkou_a, senkou_b)
    ema8 = pd.Series(close).ewm(span=8, adjust=False).mean().values[-1]
    ema21 = pd.Series(close).ewm(span=21, adjust=False).mean().values[-1]
    ema55 = pd.Series(close).ewm(span=55, adjust=False).mean().values[-1]
    result["ema8"] = float(ema8); result["ema21"] = float(ema21); result["ema55"] = float(ema55)
    result["ema_trend"] = "UP" if ema8 > ema21 > ema55 else "DOWN" if ema8 < ema21 < ema55 else "NEUTRAL"
    bb_w = result["bb_width"]; adx_v = result["adx"]
    result["market_regime"] = "SIDEWAYS" if bb_w < 2.0 and adx_v < 20 else "TRENDING" if adx_v >= 25 else "TRANSITION"
    curr_hist = histogram[-1]; prev_hist = histogram[-2] if len(histogram) > 1 else 0
    curr_rsi = result["rsi"]; curr_adx = result["adx"]; curr_plus = result["plus_di"]; curr_minus = result["minus_di"]
    bb_pos = result["bb_position"]; vol_ok = result["volume_ratio"] >= 0.7; above_vwap = result.get("above_vwap", False)
    stoch_k = result.get("stoch_k", 50); obv_up = result.get("obv_trend", "NEUTRAL") == "UP"
    def score_long():
        conds = []
        if curr_hist > 0 and prev_hist <= 0: conds.append("macd_cross")
        if curr_hist > 0: conds.append("macd_pos")
        if curr_rsi < 70: conds.append("rsi_ok")
        if curr_adx >= 12: conds.append("adx_ok")
        if curr_plus > curr_minus: conds.append("di_plus")
        if close[-1] > lb[-1]: conds.append("bb_ok")
        if vol_ok: conds.append("vol_ok")
        if ema8 > ema21: conds.append("ema_bull")
        if above_vwap: conds.append("vwap_ok")
        if stoch_k < 80: conds.append("stoch_ok")
        if obv_up: conds.append("obv_up")
        return conds
    def score_short():
        conds = []
        if curr_hist < 0 and prev_hist >= 0: conds.append("macd_cross")
        if curr_hist < 0: conds.append("macd_neg")
        if curr_rsi > 30: conds.append("rsi_ok")
        if curr_adx >= 12: conds.append("adx_ok")
        if curr_minus > curr_plus: conds.append("di_minus")
        if close[-1] < ub[-1]: conds.append("bb_ok")
        if vol_ok: conds.append("vol_ok")
        if ema8 < ema21: conds.append("ema_bear")
        if not above_vwap: conds.append("vwap_ok")
        if stoch_k > 20: conds.append("stoch_ok")
        if not obv_up: conds.append("obv_down")
        return conds
    long_conds = score_long(); short_conds = score_short()
    direction = "NEUTRAL"; signal_strength = 0.0; entry_type = "none"; trend_score = 0
    regime = result["market_regime"]
    if regime == "TRENDING":
        if len(long_conds) >= 5 and ("macd_cross" in long_conds or "macd_pos" in long_conds):
            direction = "LONG"; signal_strength = min(1.0, len(long_conds)/10.0 + 0.15); entry_type = "trend_long"; trend_score = 1
        elif len(short_conds) >= 5 and ("macd_cross" in short_conds or "macd_neg" in short_conds):
            direction = "SHORT"; signal_strength = min(1.0, len(short_conds)/10.0 + 0.15); entry_type = "trend_short"; trend_score = -1
    elif regime == "SIDEWAYS":
        if len(long_conds) >= 4 and bb_pos < 0.2 and close[-1] > close[-2]:
            direction = "LONG"; signal_strength = min(1.0, len(long_conds)/8.0 + 0.1); entry_type = "sideways_long"; trend_score = 1
        elif len(short_conds) >= 4 and bb_pos > 0.8 and close[-1] < close[-2]:
            direction = "SHORT"; signal_strength = min(1.0, len(short_conds)/8.0 + 0.1); entry_type = "sideways_short"; trend_score = -1
    else:
        if len(long_conds) >= 5 and "macd_cross" in long_conds:
            direction = "LONG"; signal_strength = min(1.0, len(long_conds)/9.0); entry_type = "transition_long"; trend_score = 1
        elif len(short_conds) >= 5 and "macd_cross" in short_conds:
            direction = "SHORT"; signal_strength = min(1.0, len(short_conds)/9.0); entry_type = "transition_short"; trend_score = -1
    if direction != "NEUTRAL" and curr_adx > 25: signal_strength = min(1.0, signal_strength + 0.15)
    result["trend_score"] = trend_score; result["signal_direction"] = direction
    result["signal_strength"] = round(signal_strength, 3); result["entry_type"] = entry_type
    result["signal_conditions"] = long_conds if direction == "LONG" else short_conds
    result["macd_cross"] = (curr_hist > 0 and prev_hist <= 0) or (curr_hist < 0 and prev_hist >= 0)
    return result
