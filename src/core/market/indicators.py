#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
from typing import Dict, Any

def compute_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Универсальный расчет индикаторов.
    Полностью автономный математический блок, который находит точки входа (MACD + RSI + BB).
    """
    result = {}
    if len(df) < 26:
        return result
        
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    
    result['close_price'] = float(close[-1])
    
    # 1. ATR (Волатильность)
    tr = np.maximum(high[1:] - low[1:], 
         np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))
    atr = np.zeros(len(close))
    atr[14] = np.mean(tr[:14])
    for i in range(15, len(close)):
        atr[i] = (atr[i-1] * 13 + tr[i-1]) / 14
        
    result['atr'] = float(atr[-1])
    result['atr_percent'] = float((atr[-1] / close[-1]) * 100) if close[-1] > 0 else 0.0

    # 2. RSI (Зоны перекупленности)
    diff = np.diff(close)
    up = np.where(diff > 0, diff, 0)
    down = np.where(diff < 0, -diff, 0)
    
    avg_up = np.mean(up[:14])
    avg_down = np.mean(down[:14])
    rsi = np.zeros(len(close))
    
    for i in range(14, len(close)):
        avg_up = (avg_up * 13 + up[i-1]) / 14
        avg_down = (avg_down * 13 + down[i-1]) / 14
        rs = (avg_up / avg_down) if avg_down != 0 else 999
        rsi[i] = 100.0 - (100.0 / (1.0 + rs)) if avg_down != 0 else 100.0
            
    result['rsi'] = float(rsi[-1])

    # 3. ADX (Сила тренда)
    plus_dm = high[1:] - high[:-1]
    minus_dm = low[:-1] - low[1:]
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0)
    
    tr_sum = np.sum(tr[-14:]) + 1e-10
    plus_di = 100 * (np.sum(plus_dm[-14:]) / tr_sum)
    minus_di = 100 * (np.sum(minus_dm[-14:]) / tr_sum)
    adx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    result['adx'] = float(adx)
    
    # 4. MACD (Моментум)
    ema12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
    ema26 = pd.Series(close).ewm(span=26, adjust=False).mean().values
    macd = ema12 - ema26
    signal = pd.Series(macd).ewm(span=9, adjust=False).mean().values
    hist = macd - signal
    
    result['macd'] = float(macd[-1])
    result['macd_signal'] = float(signal[-1])
    result['macd_hist'] = float(hist[-1])
    
    # --- БОЕВАЯ ЛОГИКА ОПРЕДЕЛЕНИЯ СИГНАЛА ---
    # Бот торгует смену моментума MACD при подтверждении от RSI
    trend_score = 0
    current_rsi = result['rsi']
    current_hist = result['macd_hist']
    prev_hist = hist[-2] if len(hist) > 1 else 0
    
    # LONG СИГНАЛ: гистограмма MACD растет (разворот вверх), RSI не перегрет
    if current_hist > 0 and prev_hist <= 0 and current_rsi < 65:
        trend_score = 1
    # SHORT СИГНАЛ: гистограмма MACD падает (разворот вниз), RSI не на дне
    elif current_hist < 0 and prev_hist >= 0 and current_rsi > 35:
        trend_score = -1
        
    result['trend_score'] = trend_score
    
    if trend_score == 1:
        result['signal_direction'] = 'LONG'
        result['signal_strength'] = 0.8
    elif trend_score == -1:
        result['signal_direction'] = 'SHORT'
        result['signal_strength'] = 0.8
    else:
        result['signal_direction'] = 'NEUTRAL'
        result['signal_strength'] = 0.0
        
    return result
