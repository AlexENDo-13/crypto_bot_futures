"""
Position Manager v5.0 - Advanced position tracking with partial profits,
breakeven stops, ATR-based trailing, and DCA support.
"""
import uuid
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from src.core.logger import get_logger

logger = get_logger()


class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class PartialTarget:
    trigger_pct: float
    close_pct: float  # % of position to close
    hit: bool = False
    executed_price: float = 0.0


@dataclass
class Position:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    symbol: str = ""
    side: PositionSide = PositionSide.LONG
    entry_price: float = 0.0
    quantity: float = 0.0
    original_quantity: float = 0.0
    leverage: int = 1
    margin: float = 0.0

    # Stops
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    trailing_stop_price: float = 0.0
    trailing_stop_atr_mult: float = 2.0
    use_atr_trailing: bool = False
    atr_value: float = 0.0

    # Breakeven
    breakeven_trigger_price: float = 0.0
    breakeven_price: float = 0.0
    use_breakeven: bool = False
    breakeven_active: bool = False

    # Partial profits
    partial_targets: List[PartialTarget] = field(default_factory=list)
    partial_profits_taken: float = 0.0

    # State
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    commission_paid: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = float("inf")
    opened_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None
    status: str = "OPEN"
    close_reason: str = ""

    # DCA
    dca_entries: List[Tuple[float, float]] = field(default_factory=list)  # (price, qty)
    max_dca_count: int = 3
    dca_trigger_pct: float = 1.0

    @property
    def direction(self) -> int:
        return 1 if self.side == PositionSide.LONG else -1

    @property
    def avg_entry_price(self) -> float:
        total_qty = self.original_quantity + sum(q for _, q in self.dca_entries)
        total_cost = (self.original_quantity * self.entry_price + 
                     sum(p * q for p, q in self.dca_entries))
        return total_cost / total_qty if total_qty > 0 else self.entry_price

    @property
    def remaining_quantity(self) -> float:
        closed = sum(t.close_pct * self.original_quantity for t in self.partial_targets if t.hit)
        return self.quantity - closed

    def calculate_pnl(self, current_price: float) -> float:
        if self.quantity <= 0 or self.avg_entry_price <= 0:
            return 0.0
        return (current_price - self.avg_entry_price) * self.quantity * self.direction

    def calculate_pnl_percent(self, current_price: float) -> float:
        if self.margin <= 0 or self.quantity <= 0:
            return 0.0
        pnl = self.calculate_pnl(current_price)
        return (pnl / self.margin) * 100

    def update_trailing_stop(self, current_price: float, atr: float = 0):
        """Update trailing stop based on price movement and optional ATR"""
        if self.side == PositionSide.LONG:
            if current_price > self.highest_price:
                self.highest_price = current_price
                if self.use_atr_trailing and atr > 0:
                    self.trailing_stop_price = current_price - atr * self.trailing_stop_atr_mult
                else:
                    # Percentage-based trailing
                    trail_dist = self.entry_price * (self.trailing_stop_atr_mult / 100)
                    self.trailing_stop_price = current_price - trail_dist
        else:
            if current_price < self.lowest_price:
                self.lowest_price = current_price
                if self.use_atr_trailing and atr > 0:
                    self.trailing_stop_price = current_price + atr * self.trailing_stop_atr_mult
                else:
                    trail_dist = self.entry_price * (self.trailing_stop_atr_mult / 100)
                    self.trailing_stop_price = current_price + trail_dist

    def check_breakeven(self, current_price: float):
        """Check if breakeven stop should be activated"""
        if not self.use_breakeven or self.breakeven_active:
            return

        if self.side == PositionSide.LONG:
            if current_price >= self.breakeven_trigger_price:
                self.breakeven_active = True
                self.stop_loss_price = max(self.stop_loss_price, self.breakeven_price)
                logger.info("Breakeven activated | %s @ %.2f", self.symbol, self.breakeven_price)
        else:
            if current_price <= self.breakeven_trigger_price:
                self.breakeven_active = True
                self.stop_loss_price = min(self.stop_loss_price, self.breakeven_price)
                logger.info("Breakeven activated | %s @ %.2f", self.symbol, self.breakeven_price)

    def check_partial_targets(self, current_price: float) -> List[PartialTarget]:
        """Check which partial profit targets are hit"""
        hit_targets = []
        for target in self.partial_targets:
            if target.hit:
                continue

            entry = self.avg_entry_price
            if self.side == PositionSide.LONG:
                trigger_price = entry * (1 + target.trigger_pct / 100)
                if current_price >= trigger_price:
                    target.hit = True
                    target.executed_price = current_price
                    hit_targets.append(target)
            else:
                trigger_price = entry * (1 - target.trigger_pct / 100)
                if current_price <= trigger_price:
                    target.hit = True
                    target.executed_price = current_price
                    hit_targets.append(target)

        return hit_targets

    def should_close(self, current_price: float) -> Tuple[bool, str]:
        """Check if position should be closed"""
        if self.quantity <= 0 or self.status != "OPEN":
            return False, ""

        # Stop loss
        if self.stop_loss_price > 0:
            if self.side == PositionSide.LONG and current_price <= self.stop_loss_price:
                return True, "STOP_LOSS"
            if self.side == PositionSide.SHORT and current_price >= self.stop_loss_price:
                return True, "STOP_LOSS"

        # Take profit (only if no partial targets or all hit)
        active_targets = [t for t in self.partial_targets if not t.hit]
        if not active_targets and self.take_profit_price > 0:
            if self.side == PositionSide.LONG and current_price >= self.take_profit_price:
                return True, "TAKE_PROFIT"
            if self.side == PositionSide.SHORT and current_price <= self.take_profit_price:
                return True, "TAKE_PROFIT"

        # Trailing stop
        if self.trailing_stop_price > 0:
            if self.side == PositionSide.LONG and current_price <= self.trailing_stop_price:
                return True, "TRAILING_STOP"
            if self.side == PositionSide.SHORT and current_price >= self.trailing_stop_price:
                return True, "TRAILING_STOP"

        return False, ""

    def should_dca(self, current_price: float) -> bool:
        """Check if DCA entry condition is met"""
        if len(self.dca_entries) >= self.max_dca_count:
            return False

        entry = self.avg_entry_price
        if self.side == PositionSide.LONG:
            drop_pct = (entry - current_price) / entry * 100
            return drop_pct >= self.dca_trigger_pct * (len(self.dca_entries) + 1)
        else:
            rise_pct = (current_price - entry) / entry * 100
            return rise_pct >= self.dca_trigger_pct * (len(self.dca_entries) + 1)

    def duration_seconds(self) -> float:
        if self.closed_at:
            return (self.closed_at - self.opened_at).total_seconds()
        return (datetime.now() - self.opened_at).total_seconds()
