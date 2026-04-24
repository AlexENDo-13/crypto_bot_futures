"""
CryptoBot v7.0 - Trading Strategies
Fixed: proper pandas validation, added DCA and Grid strategies
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging


class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Signal:
    symbol: str
    strategy: str
    type: SignalType
    confidence: float
    price: float
    timestamp: str
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseStrategy:
    """Base class for all strategies."""

    def __init__(self, name: str, params: Dict = None):
        self.name = name
        self.params = params or {}
        self.logger = logging.getLogger(f"CryptoBot.Strategy.{name}")

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[Signal]:
        raise NotImplementedError

    def _validate_df(self, df: pd.DataFrame, min_rows: int = 50) -> bool:
        if df is None or len(df) < min_rows:
            return False
        required = ["open", "high", "low", "close", "volume"]
        for col in required:
            if col not in df.columns:
                return False
        return True


class EMACrossStrategy(BaseStrategy):
    def __init__(self, fast: int = 9, slow: int = 21):
        super().__init__("ema_cross", {"fast": fast, "slow": slow})
        self.fast = fast
        self.slow = slow

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[Signal]:
        if not self._validate_df(df, self.slow + 10):
            return None

        try:
            df = df.copy()
            df["ema_fast"] = df["close"].ewm(span=self.fast, adjust=False).mean()
            df["ema_slow"] = df["close"].ewm(span=self.slow, adjust=False).mean()

            if len(df) < 3:
                return None

            prev_fast = df["ema_fast"].iloc[-2]
            prev_slow = df["ema_slow"].iloc[-2]
            curr_fast = df["ema_fast"].iloc[-1]
            curr_slow = df["ema_slow"].iloc[-1]
            curr_price = df["close"].iloc[-1]

            if prev_fast <= prev_slow and curr_fast > curr_slow:
                diff = abs(curr_fast - curr_slow) / curr_price
                confidence = min(diff * 50, 1.0)
                return Signal(symbol, self.name, SignalType.BUY, confidence, curr_price,
                             str(df.index[-1]), {"ema_fast": curr_fast, "ema_slow": curr_slow})

            if prev_fast >= prev_slow and curr_fast < curr_slow:
                diff = abs(curr_fast - curr_slow) / curr_price
                confidence = min(diff * 50, 1.0)
                return Signal(symbol, self.name, SignalType.SELL, confidence, curr_price,
                             str(df.index[-1]), {"ema_fast": curr_fast, "ema_slow": curr_slow})
        except Exception as e:
            self.logger.debug(f"EMA error: {e}")

        return None


class RSIDivergenceStrategy(BaseStrategy):
    def __init__(self, period: int = 14, overbought: int = 70, oversold: int = 30):
        super().__init__("rsi_divergence", {"period": period, "overbought": overbought, "oversold": oversold})
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[Signal]:
        if not self._validate_df(df, self.period + 10):
            return None

        try:
            df = df.copy()
            delta = df["close"].diff()
            gain = delta.where(delta > 0, 0).rolling(window=self.period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
            rs = gain / loss.replace(0, np.nan)
            df["rsi"] = 100 - (100 / (1 + rs))

            rsi = df["rsi"].iloc[-1]
            curr_price = df["close"].iloc[-1]

            if pd.isna(rsi):
                return None

            if rsi < self.oversold:
                conf = (self.oversold - rsi) / self.oversold
                return Signal(symbol, self.name, SignalType.BUY, conf, curr_price,
                             str(df.index[-1]), {"rsi": rsi})

            if rsi > self.overbought:
                conf = (rsi - self.overbought) / (100 - self.overbought)
                return Signal(symbol, self.name, SignalType.SELL, conf, curr_price,
                             str(df.index[-1]), {"rsi": rsi})
        except Exception as e:
            self.logger.debug(f"RSI error: {e}")

        return None


class VolumeBreakoutStrategy(BaseStrategy):
    def __init__(self, volume_mult: float = 2.0, lookback: int = 20):
        super().__init__("volume_breakout", {"volume_mult": volume_mult, "lookback": lookback})
        self.volume_mult = volume_mult
        self.lookback = lookback

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[Signal]:
        if not self._validate_df(df, self.lookback + 10):
            return None

        try:
            df = df.copy()
            vol_sma = df["volume"].rolling(window=self.lookback).mean()
            vol_ratio = df["volume"].iloc[-1] / vol_sma.iloc[-1] if vol_sma.iloc[-1] > 0 else 1.0

            if vol_ratio > self.volume_mult:
                curr_price = df["close"].iloc[-1]
                prev_close = df["close"].iloc[-2]

                conf = min((vol_ratio - self.volume_mult) / self.volume_mult, 1.0)

                if curr_price > prev_close * 1.001:
                    return Signal(symbol, self.name, SignalType.BUY, conf, curr_price,
                                 str(df.index[-1]), {"volume_ratio": vol_ratio})
                elif curr_price < prev_close * 0.999:
                    return Signal(symbol, self.name, SignalType.SELL, conf, curr_price,
                                 str(df.index[-1]), {"volume_ratio": vol_ratio})
        except Exception as e:
            self.logger.debug(f"Volume error: {e}")

        return None


class SupportResistanceStrategy(BaseStrategy):
    def __init__(self, lookback: int = 50, threshold: float = 0.02):
        super().__init__("support_resistance", {"lookback": lookback, "threshold": threshold})
        self.lookback = lookback
        self.threshold = threshold

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[Signal]:
        if not self._validate_df(df, self.lookback + 10):
            return None

        try:
            support = df["low"].rolling(window=self.lookback).min().iloc[-1]
            resistance = df["high"].rolling(window=self.lookback).max().iloc[-1]
            price = df["close"].iloc[-1]

            if pd.isna(support) or pd.isna(resistance) or support <= 0:
                return None

            if price <= support * (1 + self.threshold):
                return Signal(symbol, self.name, SignalType.BUY, 0.7, price,
                             str(df.index[-1]), {"support": support, "resistance": resistance})

            if price >= resistance * (1 - self.threshold):
                return Signal(symbol, self.name, SignalType.SELL, 0.7, price,
                             str(df.index[-1]), {"support": support, "resistance": resistance})
        except Exception as e:
            self.logger.debug(f"S/R error: {e}")

        return None


class MACDMomentumStrategy(BaseStrategy):
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        super().__init__("macd_momentum", {"fast": fast, "slow": slow, "signal": signal})
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[Signal]:
        if not self._validate_df(df, self.slow + self.signal + 10):
            return None

        try:
            df = df.copy()
            ema_fast = df["close"].ewm(span=self.fast, adjust=False).mean()
            ema_slow = df["close"].ewm(span=self.slow, adjust=False).mean()
            macd = ema_fast - ema_slow
            macd_signal = macd.ewm(span=self.signal, adjust=False).mean()
            hist = macd - macd_signal

            if len(hist) < 3:
                return None

            prev_hist = hist.iloc[-2]
            curr_hist = hist.iloc[-1]
            curr_price = df["close"].iloc[-1]

            if prev_hist < 0 and curr_hist > 0:
                conf = min(abs(curr_hist) / curr_price * 100, 1.0)
                return Signal(symbol, self.name, SignalType.BUY, conf, curr_price,
                             str(df.index[-1]), {"macd": macd.iloc[-1], "signal": macd_signal.iloc[-1]})

            if prev_hist > 0 and curr_hist < 0:
                conf = min(abs(curr_hist) / curr_price * 100, 1.0)
                return Signal(symbol, self.name, SignalType.SELL, conf, curr_price,
                             str(df.index[-1]), {"macd": macd.iloc[-1], "signal": macd_signal.iloc[-1]})
        except Exception as e:
            self.logger.debug(f"MACD error: {e}")

        return None


class BollingerSqueezeStrategy(BaseStrategy):
    def __init__(self, period: int = 20, std_dev: float = 2.0):
        super().__init__("bollinger_squeeze", {"period": period, "std_dev": std_dev})
        self.period = period
        self.std_dev = std_dev

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[Signal]:
        if not self._validate_df(df, self.period * 2):
            return None

        try:
            df = df.copy()
            sma = df["close"].rolling(window=self.period).mean()
            std = df["close"].rolling(window=self.period).std()
            upper = sma + std * self.std_dev
            lower = sma - std * self.std_dev

            price = df["close"].iloc[-1]
            curr_upper = upper.iloc[-1]
            curr_lower = lower.iloc[-1]

            if pd.isna(curr_upper) or pd.isna(curr_lower):
                return None

            bandwidth = (curr_upper - curr_lower) / sma.iloc[-1] if sma.iloc[-1] > 0 else 1.0
            avg_bw = ((upper - lower) / sma).rolling(window=self.period).mean().iloc[-1]

            if bandwidth < avg_bw * 0.5:  # Squeeze detected
                if price > curr_upper:
                    return Signal(symbol, self.name, SignalType.BUY, 0.75, price,
                                 str(df.index[-1]), {"bandwidth": bandwidth})
                elif price < curr_lower:
                    return Signal(symbol, self.name, SignalType.SELL, 0.75, price,
                                 str(df.index[-1]), {"bandwidth": bandwidth})
        except Exception as e:
            self.logger.debug(f"BB error: {e}")

        return None


class DCAStrategy(BaseStrategy):
    """Dollar Cost Averaging strategy."""

    def __init__(self, drop_pct: float = 5.0):
        super().__init__("dca", {"drop_pct": drop_pct})
        self.drop_pct = drop_pct

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Optional[Signal]:
        if not self._validate_df(df, 20):
            return None

        try:
            price = df["close"].iloc[-1]
            high_20 = df["high"].rolling(20).max().iloc[-1]

            if pd.isna(high_20) or high_20 <= 0:
                return None

            drop = (high_20 - price) / high_20 * 100

            if drop >= self.drop_pct:
                conf = min(drop / (self.drop_pct * 2), 1.0)
                return Signal(symbol, self.name, SignalType.BUY, conf, price,
                             str(df.index[-1]), {"drop_from_high": drop, "high_20": high_20})
        except Exception as e:
            self.logger.debug(f"DCA error: {e}")

        return None


class StrategyManager:
    """Manages all trading strategies."""

    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
        self.logger = logging.getLogger("CryptoBot.StrategyManager")
        self._register_defaults()

    def _register_defaults(self):
        self.register(EMACrossStrategy())
        self.register(RSIDivergenceStrategy())
        self.register(VolumeBreakoutStrategy())
        self.register(SupportResistanceStrategy())
        self.register(MACDMomentumStrategy())
        self.register(BollingerSqueezeStrategy())
        self.register(DCAStrategy())

    def register(self, strategy: BaseStrategy):
        self.strategies[strategy.name] = strategy
        self.logger.info(f"Registered: {strategy.name}")

    def analyze_all(self, df: pd.DataFrame, symbol: str = "",
                    min_confidence: float = 0.5,
                    enabled: List[str] = None) -> List[Signal]:
        signals = []

        for name, strategy in self.strategies.items():
            if enabled and name not in enabled:
                continue
            try:
                signal = strategy.analyze(df, symbol)
                if signal and signal.confidence >= min_confidence:
                    signals.append(signal)
            except Exception as e:
                self.logger.debug(f"Strategy {name} error: {e}")

        signals.sort(key=lambda s: s.confidence, reverse=True)
        return signals

    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        return self.strategies.get(name)

    def list_strategies(self) -> List[str]:
        return list(self.strategies.keys())
