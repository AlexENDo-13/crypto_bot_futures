#!/usr/bin/env python3
from typing import Dict, Any

class AdaptiveRisk:
    def __init__(self, settings):
        self.settings = settings; self.volatility_multiplier = 1.0; self.performance_multiplier = 1.0; self._trade_history = []
    def adjust_for_volatility(self, atr_percent):
        if atr_percent < 0.3: self.volatility_multiplier = 1.2
        elif atr_percent > 2.0: self.volatility_multiplier = 0.7
        else: self.volatility_multiplier = 1.0
        return self.volatility_multiplier
    def adjust_for_performance(self, win_rate, consecutive_losses):
        if consecutive_losses >= 3: self.performance_multiplier = 0.6
        elif win_rate < 0.3 and len(self._trade_history) > 10: self.performance_multiplier = 0.8
        else: self.performance_multiplier = 1.0
        return self.performance_multiplier
    def get_adjusted_risk(self, base_risk, atr_percent, win_rate, consecutive_losses):
        return max(0.1, min(base_risk * self.adjust_for_volatility(atr_percent) * self.adjust_for_performance(win_rate, consecutive_losses), 5.0))
    def record_trade(self, pnl):
        self._trade_history.append(pnl)
        if len(self._trade_history) > 50: self._trade_history = self._trade_history[-50:]
