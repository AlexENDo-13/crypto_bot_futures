#!/usr/bin/env python3
class PerformanceMetrics:
    def __init__(self): self.trades = []
    def add_trade(self, pnl): self.trades.append(pnl)
    def get_sharpe(self): return 0.0
