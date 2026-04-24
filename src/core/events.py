"""
CryptoBot v7.1 - Event System
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List, Callable


class EventType(Enum):
    SIGNAL = "signal"
    TRADE = "trade"
    POSITION_UPDATE = "position_update"
    PRICE_UPDATE = "price_update"
    RISK_EVENT = "risk_event"
    ERROR = "error"
    STATUS = "status"


@dataclass
class Event:
    type: EventType
    timestamp: datetime
    data: Dict[str, Any]
    source: str = ""
    priority: int = 0


class EventBus:
    """Simple event bus for decoupled communication."""

    def __init__(self):
        self._handlers = {}
        self._history = []

    def subscribe(self, event_type: EventType, handler: Callable):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable):
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    def publish(self, event: Event):
        self._history.append(event)
        if len(self._history) > 1000:
            self._history = self._history[-500:]

        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                pass

    def get_history(self, event_type: EventType = None, limit: int = 100) -> List[Event]:
        filtered = self._history
        if event_type:
            filtered = [e for e in filtered if e.type == event_type]
        return filtered[-limit:]
