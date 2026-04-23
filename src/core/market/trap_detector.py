#!/usr/bin/env python3

def detect_trap(indicators: dict) -> dict:
    """Детектор ловушек рынка (bull/bear traps)."""
    adx = indicators.get("adx", 0)
    rsi = indicators.get("rsi", 50)
    direction = indicators.get("signal_direction", "NEUTRAL")
    atr_percent = indicators.get("atr_percent", 0)
    stoch_k = indicators.get("stoch_k", 50)
    stoch_d = indicators.get("stoch_d", 50)

    is_trap = False
    reason = ""
    confidence = 0.0

    # Bear trap: цена падает, но RSI и Stochastic в зоне перепроданности с дивергенцией
    if direction == "SHORT" and rsi < 30 and stoch_k < 20 and stoch_k > stoch_d:
        is_trap = True
        reason = "bear_trap_oversold"
        confidence = 0.6 + (30 - rsi) / 100

    # Bull trap: цена растёт, но RSI и Stochastic в зоне перекупленности с дивергенцией
    if direction == "LONG" and rsi > 70 and stoch_k > 80 and stoch_k < stoch_d:
        is_trap = True
        reason = "bull_trap_overbought"
        confidence = 0.6 + (rsi - 70) / 100

    # Low ADX trap — сигнал при слабом тренде
    if adx < 12 and direction != "NEUTRAL":
        is_trap = True
        reason = "low_adx_chop"
        confidence = 0.5

    # Extreme ATR — слишком высокая волатильность
    if atr_percent > 8 and direction != "NEUTRAL":
        is_trap = True
        reason = "extreme_volatility"
        confidence = min(0.9, atr_percent / 10)

    return {"is_trap": is_trap, "reason": reason, "confidence": round(min(confidence, 1.0), 2)}
