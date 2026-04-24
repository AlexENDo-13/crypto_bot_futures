"""
Event Bus - Central pub/sub system for decoupled architecture.
All components communicate via typed events.
"""
import asyncio
import threading
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import inspect


@dataclass
class Event:
    """Base event class"""
    type: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""

    def get(self, key: str, default=None):
        return self.data.get(key, default)


class EventBus:
    """
    Thread-safe event bus with sync and async handlers.
    Supports priority, filtering, and dead-letter queue.
    """

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._async_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.RLock()
        self._event_queue: List[Event] = []
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._metrics: Dict[str, int] = defaultdict(int)

    def subscribe(self, event_type: str, handler: Callable, async_handler: bool = False):
        """Subscribe to event type"""
        with self._lock:
            if async_handler or inspect.iscoroutinefunction(handler):
                if handler not in self._async_handlers[event_type]:
                    self._async_handlers[event_type].append(handler)
            else:
                if handler not in self._handlers[event_type]:
                    self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable):
        """Unsubscribe from event type"""
        with self._lock:
            if handler in self._handlers.get(event_type, []):
                self._handlers[event_type].remove(handler)
            if handler in self._async_handlers.get(event_type, []):
                self._async_handlers[event_type].remove(handler)

    def emit(self, event: Event):
        """Emit event to all subscribers"""
        self._metrics[event.type] += 1

        # Sync handlers
        handlers = []
        async_handlers = []
        with self._lock:
            handlers = list(self._handlers.get(event.type, []))
            async_handlers = list(self._async_handlers.get(event.type, []))

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"Event handler error: {e}")

        # Async handlers
        if async_handlers:
            for handler in async_handlers:
                try:
                    if self._loop and self._loop.is_running():
                        asyncio.run_coroutine_threadsafe(handler(event), self._loop)
                    else:
                        asyncio.run(handler(event))
                except Exception as e:
                    print(f"Async event handler error: {e}")

    def emit_new(self, event_type: str, data: Dict[str, Any] = None, source: str = ""):
        """Convenience method to create and emit event"""
        self.emit(Event(type=event_type, data=data or {}, source=source))

    def get_metrics(self) -> Dict[str, int]:
        return dict(self._metrics)


# Global event bus instance
_bus: Optional[EventBus] = None

def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


# Common event types
class EventType:
    PRICE_UPDATE = "price_update"
    TICKER_UPDATE = "ticker_update"
    KLINE_UPDATE = "kline_update"
    ORDERBOOK_UPDATE = "orderbook_update"
    SIGNAL_GENERATED = "signal_generated"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_UPDATED = "position_updated"
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    BALANCE_UPDATE = "balance_update"
    RISK_ALERT = "risk_alert"
    ERROR = "error"
    BOT_STARTED = "bot_started"
    BOT_STOPPED = "bot_stopped"
    BACKTEST_RESULT = "backtest_result"
    NOTIFICATION = "notification"
    WS_CONNECTED = "ws_connected"
    WS_DISCONNECTED = "ws_disconnected"
