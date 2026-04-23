#!/usr/bin/env python3
"""
Оценщик торговых сигналов на основе индикаторов.
"""
from enum import Enum

class SignalDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"

class SignalEvaluator:
    def __init__(self, settings: dict):
        self.settings = settings

    def evaluate(self, indicators: dict, multi_tf_data: dict = None) -> tuple:
        """
        Возвращает (direction, strength, details).
        direction: SignalDirection
        strength: 0.0 .. 1.0
        details: dict с дополнительной информацией
        """
        if multi_tf_data is None:
            multi_tf_data = {}

        adx = indicators.get('adx', 20)
        rsi = indicators.get('rsi', 50)
        trend_score = indicators.get('trend_score', 0)
        atr_percent = indicators.get('atr_percent', 1.0)

        strength = 0.0
        direction = SignalDirection.NEUTRAL

        # ADX фильтр
        if adx > 20:
            if trend_score > 1:
                direction = SignalDirection.LONG
                strength = min(1.0, (adx - 20) / 30)
            elif trend_score < -1:
                direction = SignalDirection.SHORT
                strength = min(1.0, (adx - 20) / 30)

        # Учёт RSI
        if direction != SignalDirection.NEUTRAL:
            if direction == SignalDirection.LONG and rsi > 70:
                strength *= 0.7
            elif direction == SignalDirection.SHORT and rsi < 30:
                strength *= 0.7

        details = {
            'adx': adx,
            'rsi': rsi,
            'trend_score': trend_score,
            'atr_percent': atr_percent
        }
        return direction, strength, details
