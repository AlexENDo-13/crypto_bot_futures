"""
CryptoBot v6.0 - Trading Strategies
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging


class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Signal:
    """Trading signal."""
    symbol: str
    strategy: str
    type: SignalType
    confidence: float  # 0.0 - 1.0
    price: float
    timestamp: str
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseStrategy:
    """Base class for all trading strategies."""

    def __init__(self, name: str, params: Dict = None):
        self.name = name
        self.params = params or {}
        self.logger = logging.getLogger(f"CryptoBot.Strategy.{name}")

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[Signal]:
        """Analyze data and return signal."""
        raise NotImplementedError

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators."""
        return df


class EMACrossStrategy(BaseStrategy):
    """EMA Crossover Strategy."""

    def __init__(self, fast: int = 9, slow: int = 21):
        super().__init__("ema_cross", {"fast": fast, "slow": slow})
        self.fast = fast
        self.slow = slow

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ema_fast"] = df["close"].ewm(span=self.fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.slow, adjust=False).mean()
        df["ema_diff"] = df["ema_fast"] - df["ema_slow"]
        df["ema_signal"] = np.where(df["ema_diff"] > 0, 1, -1)
        return df

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[Signal]:
        df = self.calculate_indicators(df)
        if len(df) < 3:
            return None

        prev_signal = df["ema_signal"].iloc[-2]
        curr_signal = df["ema_signal"].iloc[-1]

        if prev_signal < 0 and curr_signal > 0:
            confidence = min(abs(df["ema_diff"].iloc[-1]) / df["close"].iloc[-1] * 100, 1.0)
            return Signal(
                symbol=symbol,
                strategy=self.name,
                type=SignalType.BUY,
                confidence=confidence,
                price=df["close"].iloc[-1],
                timestamp=str(df.index[-1]),
                metadata={"ema_fast": df["ema_fast"].iloc[-1], 
                         "ema_slow": df["ema_slow"].iloc[-1]}
            )
        elif prev_signal > 0 and curr_signal < 0:
            confidence = min(abs(df["ema_diff"].iloc[-1]) / df["close"].iloc[-1] * 100, 1.0)
            return Signal(
                symbol=symbol,
                strategy=self.name,
                type=SignalType.SELL,
                confidence=confidence,
                price=df["close"].iloc[-1],
                timestamp=str(df.index[-1]),
                metadata={"ema_fast": df["ema_fast"].iloc[-1], 
                         "ema_slow": df["ema_slow"].iloc[-1]}
            )

        return None


class RSIDivergenceStrategy(BaseStrategy):
    """RSI Divergence Strategy."""

    def __init__(self, period: int = 14, overbought: int = 70, oversold: int = 30):
        super().__init__("rsi_divergence", {"period": period, 
                                            "overbought": overbought, 
                                            "oversold": oversold})
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
        return df

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[Signal]:
        df = self.calculate_indicators(df)
        if len(df) < self.period + 5:
            return None

        rsi = df["rsi"].iloc[-1]

        if rsi < self.oversold:
            return Signal(
                symbol=symbol,
                strategy=self.name,
                type=SignalType.BUY,
                confidence=(self.oversold - rsi) / self.oversold,
                price=df["close"].iloc[-1],
                timestamp=str(df.index[-1]),
                metadata={"rsi": rsi}
            )
        elif rsi > self.overbought:
            return Signal(
                symbol=symbol,
                strategy=self.name,
                type=SignalType.SELL,
                confidence=(rsi - self.overbought) / (100 - self.overbought),
                price=df["close"].iloc[-1],
                timestamp=str(df.index[-1]),
                metadata={"rsi": rsi}
            )

        return None


class VolumeBreakoutStrategy(BaseStrategy):
    """Volume Breakout Strategy."""

    def __init__(self, volume_mult: float = 2.0, lookback: int = 20):
        super().__init__("volume_breakout", {"volume_mult": volume_mult, "lookback": lookback})
        self.volume_mult = volume_mult
        self.lookback = lookback

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["volume_sma"] = df["volume"].rolling(window=self.lookback).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"]
        df["atr"] = self._calculate_atr(df)
        return df

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(period).mean()

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[Signal]:
        df = self.calculate_indicators(df)
        if len(df) < self.lookback + 1:
            return None

        vol_ratio = df["volume_ratio"].iloc[-1]
        prev_close = df["close"].iloc[-2]
        curr_close = df["close"].iloc[-1]
        atr = df["atr"].iloc[-1]

        if vol_ratio > self.volume_mult:
            if curr_close > prev_close + atr * 0.5:
                return Signal(
                    symbol=symbol,
                    strategy=self.name,
                    type=SignalType.BUY,
                    confidence=min((vol_ratio - self.volume_mult) / self.volume_mult, 1.0),
                    price=curr_close,
                    timestamp=str(df.index[-1]),
                    metadata={"volume_ratio": vol_ratio, "atr": atr}
                )
            elif curr_close < prev_close - atr * 0.5:
                return Signal(
                    symbol=symbol,
                    strategy=self.name,
                    type=SignalType.SELL,
                    confidence=min((vol_ratio - self.volume_mult) / self.volume_mult, 1.0),
                    price=curr_close,
                    timestamp=str(df.index[-1]),
                    metadata={"volume_ratio": vol_ratio, "atr": atr}
                )

        return None


class SupportResistanceStrategy(BaseStrategy):
    """Support and Resistance Strategy."""

    def __init__(self, lookback: int = 50, threshold: float = 0.02):
        super().__init__("support_resistance", {"lookback": lookback, "threshold": threshold})
        self.lookback = lookback
        self.threshold = threshold

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["support"] = df["low"].rolling(window=self.lookback).min()
        df["resistance"] = df["high"].rolling(window=self.lookback).max()
        df["mid"] = (df["support"] + df["resistance"]) / 2
        return df

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[Signal]:
        df = self.calculate_indicators(df)
        if len(df) < self.lookback:
            return None

        price = df["close"].iloc[-1]
        support = df["support"].iloc[-1]
        resistance = df["resistance"].iloc[-1]

        if support > 0 and price <= support * (1 + self.threshold):
            return Signal(
                symbol=symbol,
                strategy=self.name,
                type=SignalType.BUY,
                confidence=0.7,
                price=price,
                timestamp=str(df.index[-1]),
                metadata={"support": support, "resistance": resistance}
            )
        elif resistance > 0 and price >= resistance * (1 - self.threshold):
            return Signal(
                symbol=symbol,
                strategy=self.name,
                type=SignalType.SELL,
                confidence=0.7,
                price=price,
                timestamp=str(df.index[-1]),
                metadata={"support": support, "resistance": resistance}
            )

        return None


class MACDMomentumStrategy(BaseStrategy):
    """MACD Momentum Strategy."""

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        super().__init__("macd_momentum", {"fast": fast, "slow": slow, "signal": signal})
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        ema_fast = df["close"].ewm(span=self.fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=self.slow, adjust=False).mean()
        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = df["macd"].ewm(span=self.signal, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]
        return df

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[Signal]:
        df = self.calculate_indicators(df)
        if len(df) < self.slow + self.signal:
            return None

        prev_hist = df["macd_hist"].iloc[-2]
        curr_hist = df["macd_hist"].iloc[-1]

        if prev_hist < 0 and curr_hist > 0:
            return Signal(
                symbol=symbol,
                strategy=self.name,
                type=SignalType.BUY,
                confidence=min(abs(curr_hist) / df["close"].iloc[-1] * 100, 1.0),
                price=df["close"].iloc[-1],
                timestamp=str(df.index[-1]),
                metadata={"macd": df["macd"].iloc[-1], 
                         "signal": df["macd_signal"].iloc[-1]}
            )
        elif prev_hist > 0 and curr_hist < 0:
            return Signal(
                symbol=symbol,
                strategy=self.name,
                type=SignalType.SELL,
                confidence=min(abs(curr_hist) / df["close"].iloc[-1] * 100, 1.0),
                price=df["close"].iloc[-1],
                timestamp=str(df.index[-1]),
                metadata={"macd": df["macd"].iloc[-1], 
                         "signal": df["macd_signal"].iloc[-1]}
            )

        return None


class BollingerSqueezeStrategy(BaseStrategy):
    """Bollinger Band Squeeze Strategy."""

    def __init__(self, period: int = 20, std_dev: float = 2.0, squeeze_mult: float = 1.5):
        super().__init__("bollinger_squeeze", {"period": period, "std_dev": std_dev, 
                                               "squeeze_mult": squeeze_mult})
        self.period = period
        self.std_dev = std_dev
        self.squeeze_mult = squeeze_mult

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["sma"] = df["close"].rolling(window=self.period).mean()
        df["std"] = df["close"].rolling(window=self.period).std()
        df["upper"] = df["sma"] + (df["std"] * self.std_dev)
        df["lower"] = df["sma"] - (df["std"] * self.std_dev)
        df["bandwidth"] = (df["upper"] - df["lower"]) / df["sma"]
        df["avg_bandwidth"] = df["bandwidth"].rolling(window=self.period).mean()
        return df

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[Signal]:
        df = self.calculate_indicators(df)
        if len(df) < self.period * 2:
            return None

        curr_bw = df["bandwidth"].iloc[-1]
        avg_bw = df["avg_bandwidth"].iloc[-1]
        price = df["close"].iloc[-1]
        upper = df["upper"].iloc[-1]
        lower = df["lower"].iloc[-1]

        # Squeeze breakout
        if curr_bw < avg_bw / self.squeeze_mult:
            if price > upper:
                return Signal(
                    symbol=symbol,
                    strategy=self.name,
                    type=SignalType.BUY,
                    confidence=0.75,
                    price=price,
                    timestamp=str(df.index[-1]),
                    metadata={"bandwidth": curr_bw, "upper": upper, "lower": lower}
                )
            elif price < lower:
                return Signal(
                    symbol=symbol,
                    strategy=self.name,
                    type=SignalType.SELL,
                    confidence=0.75,
                    price=price,
                    timestamp=str(df.index[-1]),
                    metadata={"bandwidth": curr_bw, "upper": upper, "lower": lower}
                )

        return None


class StrategyManager:
    """Manages all trading strategies."""

    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
        self.logger = logging.getLogger("CryptoBot.StrategyManager")
        self._register_default_strategies()

    def _register_default_strategies(self):
        """Register default strategies."""
        self.register(EMACrossStrategy())
        self.register(RSIDivergenceStrategy())
        self.register(VolumeBreakoutStrategy())
        self.register(SupportResistanceStrategy())
        self.register(MACDMomentumStrategy())
        self.register(BollingerSqueezeStrategy())

    def register(self, strategy: BaseStrategy):
        """Register a strategy."""
        self.strategies[strategy.name] = strategy
        self.logger.info(f"Registered strategy: {strategy.name}")

    def analyze_all(self, df: pd.DataFrame, symbol: str = "",
                    min_confidence: float = 0.5) -> List[Signal]:
        """Run all strategies and collect signals."""
        signals = []
        for name, strategy in self.strategies.items():
            try:
                signal = strategy.analyze(df, symbol)
                if signal and signal.confidence >= min_confidence:
                    signals.append(signal)
            except Exception as e:
                self.logger.error(f"Strategy {name} error: {e}")

        return signals

    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        """Get a strategy by name."""
        return self.strategies.get(name)

    def list_strategies(self) -> List[str]:
        """List all registered strategy names."""
        return list(self.strategies.keys())
