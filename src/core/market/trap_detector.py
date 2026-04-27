#!/usr/bin/env python3
def detect_trap(indicators: dict) -> dict:
    """Detect potential bull/bear traps."""
    adx = indicators.get("adx", 0)
    rsi = indicators.get("rsi", 50)
    atr_pct = indicators.get("atr_percent", 1.0)
    direction = indicators.get("signal_direction", "NEUTRAL")

    is_trap = False
    confidence = 0.0

    # Bear trap: price drops hard but RSI oversold + low ADX (weak trend)
    if direction == "SHORT" and rsi < 25 and adx < 20:
        is_trap = True
        confidence = 0.6

    # Bull trap: price spikes but RSI overbought + low ADX
    if direction == "LONG" and rsi > 75 and adx < 20:
        is_trap = True
        confidence = 0.6

    # Extreme ATR spike trap
    if atr_pct > 3.0 and adx < 15:
        is_trap = True
        confidence = max(confidence, 0.5)

    return {"is_trap": is_trap, "confidence": confidence, "reason": "adx_rsi_divergence"}
