"""
Market Scanner v9.0
Scans symbols for strategy signals using adaptive concurrency.
Uses AsyncExecutor bridge for GUI-safe async execution.
"""
import asyncio
import logging
import time
from typing import List, Dict, Optional, Any, Set

from src.exchange.api_client import BingXAPIClient
from src.utils.async_bridge import AsyncExecutor


class MarketScanner:
    """
    Orchestrates scanning of multiple symbols across selected strategies.
    Designed to work both as a pure coroutine (when called from asyncio)
    and via AsyncExecutor for synchronous GUI contexts.
    """

    def __init__(
        self,
        api_client: BingXAPIClient,
        symbols: List[str],
        async_executor: Optional[AsyncExecutor] = None,
        max_workers: int = 5
    ):
        self.api = api_client
        self.symbols = symbols
        self.async_executor = async_executor
        self.max_workers = max_workers
        self.logger = logging.getLogger("CryptoBot.Scanner")

        # Strategy registry (to be populated by StrategyManager)
        self.strategies: Dict[str, Any] = {}
        self._last_scan_time: float = 0.0
        self._min_scan_interval: float = 2.0  # seconds

    def register_strategy(self, name: str, strategy):
        self.strategies[name] = strategy

    async def scan_all(
        self,
        timeframe: str = "15m",
        min_confidence: float = 0.3,
        enabled_strategies: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Scan all symbols with all (or selected) strategies.
        Returns unified list of signal dicts.
        """
        # Rate limiting
        now = time.time()
        if now - self._last_scan_time < self._min_scan_interval:
            self.logger.info(f"Scan skipped: too soon ({now - self._last_scan_time:.1f}s)")
            return []
        self._last_scan_time = now

        if not enabled_strategies:
            enabled_strategies = set(self.strategies.keys())

        self.logger.info(f"Scanning {len(self.symbols)} symbols on {timeframe} (min_conf={min_confidence:.2f})...")

        # Fetch klines for all symbols in parallel (with concurrency limit)
        klines_data = await self._fetch_klines_batch(timeframe, limit=100)

        # Scan each symbol with selected strategies
        sem = asyncio.Semaphore(self.max_workers)
        tasks = []
        for symbol in self.symbols:
            tasks.append(self._scan_symbol(
                symbol, timeframe, min_confidence, enabled_strategies, klines_data.get(symbol, []), sem
            ))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten signals
        all_signals = []
        for res in results:
            if isinstance(res, Exception):
                self.logger.error(f"Unexpected error during scan: {res}")
            elif isinstance(res, list):
                all_signals.extend(res)

        unique = self._deduplicate_signals(all_signals)
        self.logger.info(
            f"Scan complete | {len(unique)} unique signals (from {len(all_signals)} raw)")
        return unique

    async def _fetch_klines_batch(self, timeframe: str, limit: int) -> Dict[str, List]:
        """Concurrently fetch klines for all symbols with robust error handling."""
        result = {}
        sem = asyncio.Semaphore(min(self.max_workers, 10))  # limit parallel API calls

        async def fetch_single(symbol):
            async with sem:
                try:
                    candles = await self.api.get_klines(symbol, interval=timeframe, limit=limit)
                    if candles and len(candles) >= 20:  # minimum required
                        return symbol, candles
                    else:
                        self.logger.debug(f"{symbol}: insufficient data ({len(candles)} candles)")
                        return symbol, []
                except RuntimeError as e:
                    if "Event loop" in str(e):
                        self.logger.warning(f"Event loop error for {symbol}, retrying via new loop")
                        # Attempt recovery by calling API through a fresh loop
                        # This case should be rare with new api_client, but handle gracefully
                        return symbol, await self._fetch_with_new_loop(symbol, timeframe, limit)
                    self.logger.error(f"Klines error for {symbol}: {e}")
                    return symbol, []
                except Exception as e:
                    self.logger.error(f"Klines error for {symbol}: {e}")
                    return symbol, []

        tasks = [fetch_single(sym) for sym in self.symbols]
        responses = await asyncio.gather(*tasks)
        for symbol, candles in responses:
            result[symbol] = candles
        return result

    async def _fetch_with_new_loop(self, symbol: str, timeframe: str, limit: int) -> List:
        """Fallback: run API call in a fresh event loop."""
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return await self.api.get_klines(symbol, interval=timeframe, limit=limit)
        finally:
            loop.close()

    async def _scan_symbol(
        self,
        symbol: str,
        timeframe: str,
        min_confidence: float,
        strategies: Set[str],
        candles: List,
        sem: asyncio.Semaphore
    ) -> List[Dict]:
        async with sem:
            if not candles:
                return []
            signals = []
            for strat_name in strategies:
                strategy = self.strategies.get(strat_name)
                if not strategy:
                    continue
                try:
                    sig = strategy.analyze(symbol, candles, timeframe)
                    if sig and sig.get("confidence", 0) >= min_confidence:
                        sig["strategy"] = strat_name
                        sig["symbol"] = symbol
                        sig["timeframe"] = timeframe
                        signals.append(sig)
                except Exception as e:
                    self.logger.debug(f"Strategy {strat_name} error for {symbol}: {e}")
            return signals

    def _deduplicate_signals(self, signals: List[Dict]) -> List[Dict]:
        """Remove duplicate signals based on symbol+strategy."""
        seen = set()
        unique = []
        for s in signals:
            key = (s.get("symbol"), s.get("strategy"))
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique

    # Synchronous wrapper for GUI via AsyncExecutor
    def start_scan(self, callback, timeframe="15m", min_confidence=0.3, enabled_strategies=None):
        """
        Launch scan asynchronously using the dedicated executor.
        `callback(signals)` will be called in the GUI thread when done.
        """
        if not self.async_executor:
            self.logger.error("AsyncExecutor not set; cannot run scan from sync context")
            return

        def on_done(future):
            try:
                signals = future.result()
            except Exception as e:
                self.logger.error(f"Scan failed: {e}")
                signals = []
            callback(signals)

        future = self.async_executor.run_coroutine(
            self.scan_all(timeframe, min_confidence, enabled_strategies)
        )
        future.add_done_callback(on_done)
