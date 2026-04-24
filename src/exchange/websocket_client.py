"""
WebSocket Client - Real-time market data via BingX WebSocket.
Supports auto-reconnect, heartbeat, and multi-subscription.
"""
import json
import time
import threading
import websocket
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from queue import Queue

from src.core.config import get_config
from src.core.logger import get_logger
from src.core.events import get_event_bus, EventType

logger = get_logger()


class BingXWebSocket:
    """
    BingX WebSocket client for real-time data.
    Auto-reconnects on disconnect with exponential backoff.
    """

    def __init__(self):
        self.config = get_config().exchange
        self.url = self.config.ws_url
        self.ws: Optional[websocket.WebSocketApp] = None
        self._running = False
        self._connected = False
        self._subscriptions: set = set()
        self._callbacks: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0
        self._heartbeat_interval = 20
        self._last_ping = 0
        self._thread: Optional[threading.Thread] = None
        self._event_bus = get_event_bus()

    def _on_open(self, ws):
        logger.ws("WebSocket connected")
        self._connected = True
        self._reconnect_delay = 1.0
        self._event_bus.emit_new(EventType.WS_CONNECTED, {"url": self.url})

        # Resubscribe to previous channels
        with self._lock:
            for sub in list(self._subscriptions):
                self._subscribe(sub)

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)

            # Handle pong
            if data.get("ping"):
                ws.send(json.dumps({"pong": data["ping"]}))
                return

            event_type = data.get("e", "")

            if event_type == "trade":
                self._handle_trade(data)
            elif event_type == "kline":
                self._handle_kline(data)
            elif event_type == "depth":
                self._handle_depth(data)
            elif event_type == "ticker":
                self._handle_ticker(data)
            elif "lastPrice" in str(data):
                self._handle_ticker(data)

            # Notify callbacks
            symbol = data.get("s", "")
            callbacks = []
            with self._lock:
                callbacks = list(self._callbacks.get(symbol, []))
                callbacks.extend(self._callbacks.get("*", []))

            for cb in callbacks:
                try:
                    cb(data)
                except Exception as e:
                    logger.error("WS callback error: %s", e)

        except json.JSONDecodeError:
            logger.ws("Invalid WS message: %s", message[:200])
        except Exception as e:
            logger.error("WS message handling error: %s", e)

    def _on_error(self, ws, error):
        logger.error("WebSocket error: %s", error)
        self._event_bus.emit_new(EventType.ERROR, {"source": "websocket", "error": str(error)})

    def _on_close(self, ws, close_status_code, close_msg):
        logger.ws("WebSocket disconnected | code=%s msg=%s", close_status_code, close_msg)
        self._connected = False
        self._event_bus.emit_new(EventType.WS_DISCONNECTED, {"code": close_status_code})

        if self._running:
            self._schedule_reconnect()

    def _schedule_reconnect(self):
        """Schedule reconnection with exponential backoff"""
        def reconnect():
            logger.ws("Reconnecting in %.1fs...", self._reconnect_delay)
            time.sleep(self._reconnect_delay)
            self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)
            if self._running:
                self.connect()

        threading.Thread(target=reconnect, daemon=True).start()

    def _subscribe(self, channel: str):
        """Send subscription message"""
        if self.ws and self._connected:
            msg = json.dumps({"reqType": "sub", "dataType": channel})
            self.ws.send(msg)
            logger.ws("Subscribed: %s", channel)

    def subscribe_kline(self, symbol: str, interval: str = "1m"):
        """Subscribe to kline/candlestick updates"""
        channel = f"{symbol}@kline_{interval}"
        with self._lock:
            self._subscriptions.add(channel)
        if self._connected:
            self._subscribe(channel)

    def subscribe_ticker(self, symbol: str):
        """Subscribe to ticker/price updates"""
        channel = f"{symbol}@ticker"
        with self._lock:
            self._subscriptions.add(channel)
        if self._connected:
            self._subscribe(channel)

    def subscribe_depth(self, symbol: str):
        """Subscribe to order book updates"""
        channel = f"{symbol}@depth"
        with self._lock:
            self._subscriptions.add(channel)
        if self._connected:
            self._subscribe(channel)

    def subscribe_trade(self, symbol: str):
        """Subscribe to trade updates"""
        channel = f"{symbol}@trade"
        with self._lock:
            self._subscriptions.add(channel)
        if self._connected:
            self._subscribe(channel)

    def add_callback(self, symbol: str, callback: Callable):
        """Add callback for symbol updates"""
        with self._lock:
            if symbol not in self._callbacks:
                self._callbacks[symbol] = []
            self._callbacks[symbol].append(callback)

    def _handle_trade(self, data: Dict):
        """Process trade update"""
        self._event_bus.emit_new(EventType.PRICE_UPDATE, {
            "symbol": data.get("s"),
            "price": float(data.get("p", 0)),
            "quantity": float(data.get("q", 0)),
            "timestamp": data.get("T"),
        })

    def _handle_kline(self, data: Dict):
        """Process kline update"""
        k = data.get("k", {})
        self._event_bus.emit_new(EventType.KLINE_UPDATE, {
            "symbol": data.get("s"),
            "interval": k.get("i"),
            "open": float(k.get("o", 0)),
            "high": float(k.get("h", 0)),
            "low": float(k.get("l", 0)),
            "close": float(k.get("c", 0)),
            "volume": float(k.get("v", 0)),
            "is_closed": k.get("x", False),
        })

    def _handle_depth(self, data: Dict):
        """Process order book update"""
        self._event_bus.emit_new(EventType.ORDERBOOK_UPDATE, {
            "symbol": data.get("s"),
            "bids": data.get("b", []),
            "asks": data.get("a", []),
        })

    def _handle_ticker(self, data: Dict):
        """Process ticker update"""
        self._event_bus.emit_new(EventType.TICKER_UPDATE, {
            "symbol": data.get("s", ""),
            "last_price": float(data.get("c", data.get("lastPrice", 0))),
            "volume_24h": float(data.get("v", data.get("volume", 0))),
            "high_24h": float(data.get("h", data.get("highPrice", 0))),
            "low_24h": float(data.get("l", data.get("lowPrice", 0))),
            "change_pct": float(data.get("P", data.get("priceChangePercent", 0))),
        })

    def connect(self):
        """Connect to WebSocket"""
        if self.ws:
            try:
                self.ws.close()
            except:
                pass

        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        self._thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self._thread.start()

    def start(self):
        """Start WebSocket client"""
        self._running = True
        self.connect()
        logger.info("WebSocket client started")

    def stop(self):
        """Stop WebSocket client"""
        self._running = False
        if self.ws:
            self.ws.close()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("WebSocket client stopped")

    @property
    def is_connected(self) -> bool:
        return self._connected
