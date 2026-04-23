#!/usr/bin/env python3
from typing import Dict, Any

def detect_trap(indicators: Dict[str, Any], df=None) -> Dict[str, Any]:
    result = {"is_trap": False, "confidence": 0.0, "reason": ""}
    if not indicators: return result
    adx = indicators.get("adx", 0); vol_ratio = indicators.get("volume_ratio", 1.0)
    bb_pos = indicators.get("bb_position", 0.5); rsi = indicators.get("rsi", 50)
    signal_strength = indicators.get("signal_strength", 0)
    if adx < 15 and vol_ratio > 3.0:
        return {"is_trap": True, "confidence": 0.6, "reason": "low_adx_high_vol"}
    if (rsi > 85 or rsi < 15) and signal_strength < 0.4:
        return {"is_trap": True, "confidence": 0.5, "reason": "extreme_rsi_weak_signal"}
    if (bb_pos > 0.95 or bb_pos < 0.05) and vol_ratio < 0.5:
        return {"is_trap": True, "confidence": 0.4, "reason": "bb_extreme_low_vol"}
    return result
