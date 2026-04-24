"""
Strategy Plugin Base - Extensible strategy system.
All strategies inherit from BaseStrategy.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import pandas as pd

from src.core.config import get_config
from src.core.logger import get_logger

logger = get_logger()


class Signal:
    def __init__(self, symbol: str, direction: str, confidence: float, strategy: str,
                 timeframe: str, entry_price: float = 0, stop_loss: float = 0,
                 take_profit: float = 0, reason: str = ""):
        self.symbol = symbol
        self.direction = direction
        self.confidence = confidence
        self.strategy = strategy
        self.timeframe = timeframe
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.reason = reason

    @property
    def is_valid(self) -> bool:
        return self.confidence >= get_config().strategy.min_signal_confidence


class BaseStrategy(ABC):
    """Base class for all trading strategies"""

    name = "base"

    def __init__(self):
        self.config = get_config().strategy
        self.logger = logger

    @abstractmethod
    def analyze(self, symbol: str, df: pd.DataFrame, timeframe_data: Dict[str, pd.DataFrame]) -> Optional[Signal]:
        """Analyze data and return signal or None"""
        pass

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        hl = df["high"] - df["low"]
        hc = abs(df["high"] - df["close"].shift())
        lc = abs(df["low"] - df["close"].shift())
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
