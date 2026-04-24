"""
Data Fetcher v5.0 - Multi-source data (REST + WebSocket), advanced caching,
order book analysis, and funding rate monitoring.
"""
import time
import threading
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque
import pandas as pd
import numpy as np

from src.exchange.api_client import BingXAPIClient
from src.exchange.websocket_client import BingXWebSocket
from src.core.config import get_config
from src.core.logger import get_logger
from src.core.events import get_event_bus, EventType

logger = get_logger()


@dataclass
class MarketDepth:
    bids: List[Tuple[float, float]]
    asks: List[Tuple[float, float]]
    timestamp: datetime

    @property
    def best_bid(self) -> float:
        return self.bids[0][0] if self.bids else 0

    @property
    def best_ask(self) -> float:
        return self.asks[0][0] if self.asks else 0

    @property
    def spread(self) -> float:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return 0

    @property
    def spread_pct(self) -> float:
        mid = (self.best_bid + self.best_ask) / 2
        return (self.spread / mid * 100) if mid else 0

    def get_liquidity(self, depth_usd: float = 10000) -> Dict:
        """Calculate available liquidity up to depth_usd"""
        bid_liq = ask_liq = 0.0
        bid_usd = ask_usd = 0.0

        for p, q in self.bids:
            usd = p * q
            if bid_usd + usd > depth_usd:
                q = (depth_usd - bid_usd) / p
            bid_liq += q
            bid_usd += p * q
            if bid_usd >= depth_usd:
                break

        for p, q in self.asks:
            usd = p * q
            if ask_usd + usd > depth_usd:
                q = (depth_usd - ask_usd) / p
            ask_liq += q
            ask_usd += p * q
            if ask_usd >= depth_usd:
                break

        return {
            "bid_liquidity": bid_liq,
            "ask_liquidity": ask_liq,
            "spread_pct": self.spread_pct,
            "mid_price": (self.best_bid + self.best_ask) / 2,
        }


class DataCache:
    """Thread-safe LRU cache with TTL"""

    def __init__(self, ttl_seconds: int = 60, max_size: int = 1000):
        self._cache: Dict[str, Dict] = {}
        self._lock = threading.RLock()
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._access_times: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if time.time() - entry["time"] > self._ttl:
                del self._cache[key]
                self._access_times.pop(key, None)
                return None
            self._access_times[key] = time.time()
            return entry["data"]

    def set(self, key: str, data: Any):
        with self._lock:
            if len(self._cache) >= self._max_size:
                # Evict oldest
                oldest = min(self._access_times, key=self._access_times.get)
                self._cache.pop(oldest, None)
                self._access_times.pop(oldest, None)
            self._cache[key] = {"data": data, "time": time.time()}
            self._access_times[key] = time.time()

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._access_times.clear()


class DataFetcher:
    """Unified data fetcher with REST fallback and WS real-time"""

    def __init__(self):
        self.client = BingXAPIClient()
        self.ws = BingXWebSocket()
        self.cache = DataCache(ttl_seconds=30, max_size=2000)
        self._symbol_info: Dict[str, Dict] = {}
        self._price_cache: Dict[str, deque] = {}
        self._event_bus = get_event_bus()
        self._lock = threading.Lock()

        self._load_symbol_info()
        self._setup_event_handlers()

        logger.info("DataFetcher v5.0 initialized")

    def _setup_event_handlers(self):
        """Listen to WS events for real-time updates"""
        self._event_bus.subscribe(EventType.PRICE_UPDATE, self._on_price_update)
        self._event_bus.subscribe(EventType.TICKER_UPDATE, self._on_ticker_update)

    def _on_price_update(self, event):
        data = event.data
        symbol = data.get("symbol")
        price = data.get("price")
        if symbol and price:
            self.cache.set(f"price_{symbol}", price)
            if symbol not in self._price_cache:
                self._price_cache[symbol] = deque(maxlen=1000)
            self._price_cache[symbol].append((time.time(), price))

    def _on_ticker_update(self, event):
        data = event.data
        symbol = data.get("symbol")
        if symbol:
            self.cache.set(f"ticker_{symbol}", data)
            self.cache.set(f"price_{symbol}", data.get("last_price"))

    def _load_symbol_info(self):
        resp = self.client.get_symbols()
        if resp.is_ok and resp.data:
            for sym in resp.data:
                symbol = sym.get("symbol", "")
                if symbol:
                    self._symbol_info[symbol] = {
                        "pricePrecision": sym.get("pricePrecision", 2),
                        "quantityPrecision": sym.get("quantityPrecision", 3),
                        "minQty": float(sym.get("minQty", 0)),
                        "maxQty": float(sym.get("maxQty", 999999)),
                        "stepSize": float(sym.get("stepSize", 0.001)),
                        "tickSize": float(sym.get("tickSize", 0.01)),
                        "volume24h": float(sym.get("volume24h", 0)),
                        "quoteAsset": sym.get("quoteAsset", "USDT"),
                    }
            logger.info("Loaded %d symbols", len(self._symbol_info))

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        return self._symbol_info.get(symbol)

    def get_volume_24h(self, symbol: str) -> float:
        info = self.get_symbol_info(symbol)
        if info:
            return info.get("volume24h", 0)
        cache_key = f"ticker_{symbol}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached.get("volume_24h", 0)
        resp = self.client.get_ticker(symbol)
        if resp.is_ok:
            ticker = resp.data[0] if isinstance(resp.data, list) else resp.data
            volume = float(ticker.get("volume", 0))
            self.cache.set(cache_key, ticker)
            return volume
        return 0.0

    def get_klines(self, symbol: str, interval: str, limit: int = 500, use_cache: bool = True) -> pd.DataFrame:
        cache_key = f"klines_{symbol}_{interval}_{limit}"
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None and isinstance(cached, pd.DataFrame):
                return cached

        resp = self.client.get_klines(symbol, interval, limit)
        if not resp.is_ok:
            logger.error("Klines failed | %s %s | %s", symbol, interval, resp.error_msg)
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        data = resp.data
        if not data:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        candles = []
        for item in data:
            if isinstance(item, list) and len(item) >= 6:
                candles.append({
                    "timestamp": pd.to_datetime(int(item[0]), unit="ms"),
                    "open": float(item[1]), "high": float(item[2]),
                    "low": float(item[3]), "close": float(item[4]),
                    "volume": float(item[5]),
                })

        df = pd.DataFrame(candles)
        if df.empty:
            return df
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)

        if use_cache:
            self.cache.set(cache_key, df)
        return df

    def get_multi_timeframe(self, symbol: str, timeframes: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
        if timeframes is None:
            timeframes = get_config().strategy.timeframes
        result = {}
        for tf in timeframes:
            try:
                df = self.get_klines(symbol, tf)
                if not df.empty:
                    result[tf] = df
            except Exception as e:
                logger.error("Error %s %s: %s", symbol, tf, e)
        return result

    def get_current_price(self, symbol: str) -> float:
        cache_key = f"price_{symbol}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        resp = self.client.get_ticker(symbol)
        if resp.is_ok:
            ticker = resp.data[0] if isinstance(resp.data, list) else resp.data
            price = float(ticker.get("lastPrice", 0))
            self.cache.set(cache_key, price)
            return price

        df = self.get_klines(symbol, "1m", limit=1, use_cache=False)
        if not df.empty:
            return float(df["close"].iloc[-1])
        return 0.0

    def get_orderbook(self, symbol: str, limit: int = 20) -> MarketDepth:
        resp = self.client.get_depth(symbol, limit)
        if resp.is_ok:
            data = resp.data or {}
            bids = [(float(b[0]), float(b[1])) for b in data.get("bids", []) if len(b) >= 2]
            asks = [(float(a[0]), float(a[1])) for a in data.get("asks", []) if len(a) >= 2]
            return MarketDepth(bids=bids, asks=asks, timestamp=datetime.now())
        return MarketDepth(bids=[], asks=[], timestamp=datetime.now())

    def get_funding_rate(self, symbol: str) -> Dict:
        resp = self.client.get_funding_rate(symbol)
        if resp.is_ok and resp.data:
            data = resp.data[0] if isinstance(resp.data, list) else resp.data
            return {
                "rate": float(data.get("lastFundingRate", 0)),
                "next_time": data.get("nextFundingTime", 0),
                "mark_price": float(data.get("markPrice", 0)),
            }
        return {"rate": 0, "next_time": 0, "mark_price": 0}

    def get_open_interest(self, symbol: str) -> float:
        resp = self.client.get_open_interest(symbol)
        if resp.is_ok and resp.data:
            return float(resp.data.get("openInterest", 0)) if isinstance(resp.data, dict) else 0
        return 0.0

    def get_price_history(self, symbol: str, seconds: int = 60) -> List[Tuple[float, float]]:
        """Get recent price history from WS cache"""
        cache = self._price_cache.get(symbol, deque())
        cutoff = time.time() - seconds
        return [(t, p) for t, p in cache if t >= cutoff]

    def round_quantity(self, symbol: str, quantity: float) -> float:
        info = self.get_symbol_info(symbol)
        if not info:
            return round(quantity, 3)
        step = info.get("stepSize", 0.001)
        precision = info.get("quantityPrecision", 3)
        rounded = round(quantity / step) * step
        return round(rounded, precision)

    def round_price(self, symbol: str, price: float) -> float:
        info = self.get_symbol_info(symbol)
        if not info:
            return round(price, 2)
        tick = info.get("tickSize", 0.01)
        precision = info.get("pricePrecision", 2)
        rounded = round(price / tick) * tick
        return round(rounded, precision)

    def calculate_indicators(self, df: pd.DataFrame, cfg=None) -> pd.DataFrame:
        """Calculate all technical indicators"""
        if cfg is None:
            cfg = get_config().strategy

        # EMAs
        df["ema_fast"] = df["close"].ewm(span=cfg.ema_fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=cfg.ema_slow, adjust=False).mean()
        df["ema_trend"] = df["close"].ewm(span=cfg.ema_trend, adjust=False).mean()
        df["ema_long"] = df["close"].ewm(span=cfg.ema_long, adjust=False).mean()

        # RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=cfg.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=cfg.rsi_period).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
        df["rsi_slope"] = df["rsi"].diff(3)

        # MACD
        ema_12 = df["close"].ewm(span=cfg.macd_fast, adjust=False).mean()
        ema_26 = df["close"].ewm(span=cfg.macd_slow, adjust=False).mean()
        df["macd"] = ema_12 - ema_26
        df["macd_signal"] = df["macd"].ewm(span=cfg.macd_signal, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # Bollinger
        df["bb_middle"] = df["close"].rolling(window=cfg.bb_period).mean()
        bb_std = df["close"].rolling(window=cfg.bb_period).std()
        df["bb_upper"] = df["bb_middle"] + bb_std * cfg.bb_std
        df["bb_lower"] = df["bb_middle"] - bb_std * cfg.bb_std
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]
        df["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
        df["bb_squeeze"] = df["bb_width"] < cfg.bb_squeeze_threshold

        # ATR
        hl = df["high"] - df["low"]
        hc = abs(df["high"] - df["close"].shift())
        lc = abs(df["low"] - df["close"].shift())
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=14).mean()
        df["atr_pct"] = df["atr"] / df["close"] * 100

        # Volume
        df["volume_ma"] = df["volume"].rolling(window=cfg.volume_ma_period).mean()
        df["volume_ratio"] = df["volume"] / df["volume_ma"]
        df["volume_trend"] = df["volume"].diff(3)

        # Returns
        df["returns"] = df["close"].pct_change()
        df["returns_1m"] = df["returns"]

        # Support/Resistance
        df["support"] = df["low"].rolling(window=20).min()
        df["resistance"] = df["high"].rolling(window=20).max()
        df["support_dist"] = (df["close"] - df["support"]) / df["close"] * 100
        df["resistance_dist"] = (df["resistance"] - df["close"]) / df["close"] * 100

        return df
