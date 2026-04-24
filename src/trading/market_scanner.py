"""
Market Scanner v5.0 - Plugin-based strategy system with parallel scanning,
multi-timeframe confirmation, and AI ensemble scoring.
"""
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import pandas as pd

from src.trading.data_fetcher import DataFetcher
from src.plugins.strategy_base import BaseStrategy, Signal
from src.plugins.ema_cross import EMACrossStrategy
from src.plugins.rsi_divergence import RSIStrategy
from src.plugins.volume_breakout import VolumeBreakoutStrategy
from src.plugins.support_resistance import SupportResistanceStrategy
from src.plugins.macd_momentum import MACDMomentumStrategy
from src.plugins.bollinger_squeeze import BollingerSqueezeStrategy
from src.core.config import get_config
from src.core.logger import get_logger
from src.core.events import get_event_bus, EventType

logger = get_logger()


class MarketScanner:
    """Advanced market scanner with plugin architecture"""

    STRATEGY_REGISTRY = {
        "ema_cross": EMACrossStrategy,
        "rsi_divergence": RSIStrategy,
        "volume_breakout": VolumeBreakoutStrategy,
        "support_resistance": SupportResistanceStrategy,
        "macd_momentum": MACDMomentumStrategy,
        "bollinger_squeeze": BollingerSqueezeStrategy,
    }

    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.config = get_config().strategy
        self.trading_config = get_config().trading
        self.event_bus = get_event_bus()

        self._scanning = False
        self._scan_thread: Optional[threading.Thread] = None
        self._signals: List[Signal] = []
        self._signal_callbacks: List[Callable] = []
        self._lock = threading.Lock()

        self._strategies: Dict[str, BaseStrategy] = {}
        self._load_strategies()

        self._symbols = [
            "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT",
            "DOGE-USDT", "ADA-USDT", "AVAX-USDT", "LINK-USDT", "MATIC-USDT",
            "DOT-USDT", "LTC-USDT", "UNI-USDT", "ATOM-USDT", "ETC-USDT"
        ]

        logger.info("MarketScanner v5.0 | strategies=%d symbols=%d",
                   len(self._strategies), len(self._symbols))

    def _load_strategies(self):
        """Load enabled strategies"""
        for name in self.config.enabled_strategies:
            if name in self.STRATEGY_REGISTRY:
                self._strategies[name] = self.STRATEGY_REGISTRY[name]()
                logger.info("Loaded strategy: %s", name)

    def set_symbols(self, symbols: List[str]):
        self._symbols = symbols

    def add_signal_callback(self, callback: Callable):
        self._signal_callbacks.append(callback)

    def scan_symbol(self, symbol: str) -> List[Signal]:
        """Scan single symbol with all strategies"""
        signals = []

        try:
            volume_24h = self.data_fetcher.get_volume_24h(symbol)
            if volume_24h < self.trading_config.min_volume_24h:
                return signals

            tf_data = self.data_fetcher.get_multi_timeframe(symbol)
            if not tf_data or self.config.primary_timeframe not in tf_data:
                return signals

            df = tf_data[self.config.primary_timeframe]
            if len(df) < 50:
                return signals

            # Calculate indicators
            df = self.data_fetcher.calculate_indicators(df)

            # Multi-timeframe confirmation
            confirmation_ok = True
            if self.config.confirmation_timeframe in tf_data:
                conf_df = self.data_fetcher.calculate_indicators(tf_data[self.config.confirmation_timeframe])
                if len(conf_df) > 0:
                    conf_latest = conf_df.iloc[-1]
                    # Require trend alignment
                    if conf_latest["ema_fast"] < conf_latest["ema_slow"]:
                        # Downtrend on higher TF - filter LONG signals
                        pass  # Will filter per signal

            # Run strategies
            for name, strategy in self._strategies.items():
                try:
                    signal = strategy.analyze(symbol, df, tf_data)
                    if signal and signal.is_valid:
                        # Multi-TF filter
                        if self.config.confirmation_timeframe in tf_data:
                            conf_df = tf_data[self.config.confirmation_timeframe]
                            conf_df = self.data_fetcher.calculate_indicators(conf_df)
                            if len(conf_df) > 0:
                                conf_latest = conf_df.iloc[-1]
                                if signal.direction == "LONG" and conf_latest["ema_fast"] < conf_latest["ema_slow"]:
                                    signal.confidence *= 0.7
                                elif signal.direction == "SHORT" and conf_latest["ema_fast"] > conf_latest["ema_slow"]:
                                    signal.confidence *= 0.7

                        signals.append(signal)
                except Exception as e:
                    logger.error("Strategy %s error on %s: %s", name, symbol, e)

            # Aggregate
            if signals:
                signals = self._aggregate_signals(signals)

        except Exception as e:
            logger.error("Scan error %s: %s", symbol, e)

        return signals

    def _aggregate_signals(self, signals: List[Signal]) -> List[Signal]:
        """Aggregate and boost confidence for agreeing strategies"""
        if not signals:
            return []

        longs = [s for s in signals if s.direction == "LONG"]
        shorts = [s for s in signals if s.direction == "SHORT"]

        result = []

        for direction, group in [("LONG", longs), ("SHORT", shorts)]:
            if not group:
                continue

            # Group by strategy, keep highest confidence per strategy
            best_by_strategy = {}
            for s in group:
                if s.strategy not in best_by_strategy or s.confidence > best_by_strategy[s.strategy].confidence:
                    best_by_strategy[s.strategy] = s

            # Take best overall
            best = max(best_by_strategy.values(), key=lambda x: x.confidence)

            # Boost if multiple strategies agree
            num_strategies = len(best_by_strategy)
            if num_strategies > 1:
                boost = 0.05 * (num_strategies - 1)
                best.confidence = min(best.confidence + boost, 0.99)
                best.reason += f" (+{num_strategies} strategies)"

            result.append(best)

        return result

    def scan_all(self, parallel: bool = True) -> List[Signal]:
        """Scan all symbols"""
        all_signals = []

        if parallel and len(self._symbols) > 1:
            with ThreadPoolExecutor(max_workers=min(8, len(self._symbols))) as executor:
                futures = {executor.submit(self.scan_symbol, sym): sym for sym in self._symbols}
                for future in as_completed(futures):
                    try:
                        signals = future.result(timeout=30)
                        all_signals.extend(signals)
                    except Exception as e:
                        logger.error("Parallel scan error: %s", e)
        else:
            for symbol in self._symbols:
                try:
                    signals = self.scan_symbol(symbol)
                    all_signals.extend(signals)
                except Exception as e:
                    logger.error("Scan error %s: %s", symbol, e)

        all_signals.sort(key=lambda s: s.confidence, reverse=True)

        with self._lock:
            self._signals = all_signals

        for callback in self._signal_callbacks:
            try:
                callback(all_signals)
            except Exception as e:
                logger.error("Callback error: %s", e)

        self.event_bus.emit_new(EventType.SIGNAL_GENERATED, {
            "count": len(all_signals), "top": all_signals[0].symbol if all_signals else ""
        })

        return all_signals

    def get_latest_signals(self) -> List[Signal]:
        with self._lock:
            return list(self._signals)

    def start_continuous_scan(self, interval_sec: int = 60):
        if self._scanning:
            return
        self._scanning = True

        def loop():
            while self._scanning:
                try:
                    self.scan_all(parallel=True)
                except Exception as e:
                    logger.error("Scan loop: %s", e)
                time.sleep(interval_sec)

        self._scan_thread = threading.Thread(target=loop, daemon=True)
        self._scan_thread.start()
        logger.info("Continuous scan started | interval=%ds", interval_sec)

    def stop_continuous_scan(self):
        self._scanning = False
        if self._scan_thread:
            self._scan_thread.join(timeout=5)
        logger.info("Continuous scan stopped")
