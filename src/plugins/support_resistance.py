"""
Support/Resistance Strategy - Bounce from key levels.
"""
import pandas as pd
from src.plugins.strategy_base import BaseStrategy, Signal

class SupportResistanceStrategy(BaseStrategy):
    name = "support_resistance"

    def analyze(self, symbol, df, timeframe_data):
        if len(df) < 25:
            return None

        latest = df.iloc[-1]
        price = float(latest["close"])
        recent = df.tail(20)
        support = recent["low"].min()
        resistance = recent["high"].max()
        threshold = 0.005

        if abs(price - support) / price < threshold:
            if latest.get("rsi", 50) < 50:
                return Signal(symbol, "LONG", 0.6, self.name, "15m",
                             price, support * 0.995, resistance * 0.995, f"Near support {support:.2f}")

        if abs(price - resistance) / price < threshold:
            if latest.get("rsi", 50) > 50:
                return Signal(symbol, "SHORT", 0.6, self.name, "15m",
                             price, resistance * 1.005, support * 1.005, f"Near resistance {resistance:.2f}")

        return None
