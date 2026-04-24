"""
Base strategy for crypto trading bot.
All strategies should inherit from BaseStrategy.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class BaseStrategy:
    """
    Base class for all trading strategies.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logger

    def calculate_signal_strength(self, indicators: Dict[str, Any]) -> float:
        """
        Calculate overall signal strength based on technical indicators.
        Returns a value between -1 (strong sell) and 1 (strong buy).
        """
        # Extract indicators with fallback to 0
        rsi = indicators.get('rsi', 50)
        adx = indicators.get('adx', 0)
        atr_percent = indicators.get('atr_percent', 0)
        trend_score = indicators.get('trend_score', 0)

        # Normalize indicators
        rsi_score = (rsi - 50) / 50  # -1 to 1
        adx_score = min(adx / 50, 1) * (1 if trend_score >= 0 else -1)
        atr_score = min(atr_percent / 5, 1) * (1 if trend_score >= 0 else -1)

        # Combine scores
        strength = (rsi_score + adx_score + atr_score) / 3
        strength = max(-1, min(1, strength))  # Clamp to [-1, 1]

        self.logger.debug(
            "Signal strength calculation: RSI=%.2f, ADX=%.2f, ATR=%.2f, Trend=%d => %.2f",
            rsi, adx, atr_percent, trend_score, strength
        )
        return strength

    def generate_signal(self, symbol: str, indicators: Dict[str, Any]) -> str:
        """
        Generate a trading signal for the given symbol.
        Returns 'BUY', 'SELL', or 'HOLD'.
        """
        strength = self.calculate_signal_strength(indicators)

        if strength > self.config.get('strength_threshold', 0.2):
            return 'BUY'
        elif strength < -self.config.get('strength_threshold', 0.2):
            return 'SELL'
        else:
            return 'HOLD'

    def validate_signal(self, indicators: Dict[str, Any]) -> bool:
        """
        Validate if the signal meets basic criteria.
        """
        # Ensure required indicators are present
        required = ['rsi', 'adx', 'atr_percent', 'trend_score']
        for key in required:
            if key not in indicators:
                return False
        return True

    def get_position_size(self, account_balance: float, price: float) -> float:
        """
        Calculate position size based on risk management rules.
        """
        # Simple position sizing: risk 1% of balance
        risk_pct = self.config.get('risk_percent', 1.0)
        risk_amount = account_balance * (risk_pct / 100)
        # Assume 1% risk per trade, calculate quantity
        quantity = risk_amount / price
        return max(quantity, 0)
