#!/usr/bin/env python3
"""
Детектор ложных пробоев (ловушек).
"""
class TrapDetector:
    def __init__(self, settings: dict):
        self.settings = settings

    def is_trap(self, symbol: str, indicators: dict, current_price: float) -> bool:
        """
        Возвращает True, если сигнал похож на ловушку.
        """
        # Простая эвристика: экстремальный RSI + низкий относительный объём
        rsi = indicators.get('rsi', 50)
        volume_ratio = indicators.get('volume_ratio', 1.0)
        if (rsi > 70 or rsi < 30) and volume_ratio < 0.7:
            return True
        # Можно добавить другие условия (например, дивергенция)
        return False
