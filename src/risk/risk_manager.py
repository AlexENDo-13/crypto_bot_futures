"""
CryptoBot v6.0 - Risk Manager
Advanced risk management with position sizing and drawdown protection.
"""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskLimits:
    """Risk limit configuration."""
    max_position_size: float = 1000.0
    max_risk_per_trade: float = 2.0  # %
    max_leverage: int = 10
    max_daily_loss: float = 5.0  # %
    max_total_risk: float = 10.0  # %
    default_sl_percent: float = 2.0
    default_tp_percent: float = 4.0
    min_risk_reward: float = 1.5


@dataclass
class Position:
    """Represents an open position."""
    symbol: str
    side: str  # LONG or SHORT
    size: float
    entry_price: float
    leverage: int = 1
    stop_loss: float = 0.0
    take_profit: float = 0.0
    margin: float = 0.0
    open_time: datetime = field(default_factory=datetime.now)
    pnl: float = 0.0
    pnl_percent: float = 0.0

    def calculate_pnl(self, mark_price: float) -> float:
        """Calculate P&L in absolute terms."""
        if self.side == "LONG":
            self.pnl = (mark_price - self.entry_price) * self.size
        else:
            self.pnl = (self.entry_price - mark_price) * self.size

        if self.margin > 0:
            self.pnl_percent = (self.pnl / self.margin) * 100
        else:
            self.pnl_percent = 0.0

        return self.pnl

    def is_stop_loss_hit(self, price: float) -> bool:
        """Check if stop loss is hit."""
        if self.stop_loss <= 0:
            return False
        if self.side == "LONG":
            return price <= self.stop_loss
        return price >= self.stop_loss

    def is_take_profit_hit(self, price: float) -> bool:
        """Check if take profit is hit."""
        if self.take_profit <= 0:
            return False
        if self.side == "LONG":
            return price >= self.take_profit
        return price <= self.take_profit


class RiskManager:
    """Manages all risk-related calculations and checks."""

    def __init__(self, limits: RiskLimits = None):
        self.limits = limits or RiskLimits()
        self.logger = logging.getLogger("CryptoBot.Risk")
        self.positions: Dict[str, Position] = {}
        self.daily_pnl: float = 0.0
        self.daily_loss: float = 0.0
        self.total_risk: float = 0.0
        self.trade_history: List[Dict] = []
        self.risk_events: List[Dict] = []

        self.logger.info("RiskManager v6.0 initialized")

    def can_open_position(self, symbol: str, side: str, size: float,
                         price: float, leverage: int = 1,
                         balance: float = 10000.0) -> tuple[bool, str]:
        """Check if a new position can be opened."""
        # Check leverage
        if leverage > self.limits.max_leverage:
            return False, f"Leverage {leverage}x exceeds max {self.limits.max_leverage}x"

        # Check position size
        position_value = size * price
        if position_value > self.limits.max_position_size:
            return False, f"Position size ${position_value:.2f} exceeds max ${self.limits.max_position_size:.2f}"

        # Check daily loss limit
        if self.daily_loss >= balance * (self.limits.max_daily_loss / 100):
            return False, f"Daily loss limit reached: ${self.daily_loss:.2f}"

        # Check max positions
        if len(self.positions) >= 5:
            return False, "Max concurrent positions (5) reached"

        # Check if already in position for this symbol
        if symbol in self.positions:
            return False, f"Already have position in {symbol}"

        # Check total risk
        risk_amount = position_value * (self.limits.max_risk_per_trade / 100)
        if self.total_risk + risk_amount > balance * (self.limits.max_total_risk / 100):
            return False, "Total risk limit would be exceeded"

        return True, "OK"

    def calculate_position_size(self, price: float, stop_loss: float,
                                balance: float = 10000.0,
                                risk_percent: float = None) -> float:
        """Calculate optimal position size based on risk."""
        risk_pct = risk_percent or self.limits.max_risk_per_trade
        risk_amount = balance * (risk_pct / 100)

        if stop_loss > 0 and price > 0:
            sl_distance = abs(price - stop_loss) / price
            if sl_distance > 0:
                size = risk_amount / (price * sl_distance)
                return min(size, self.limits.max_position_size / price)

        # Fallback: use max position size
        return self.limits.max_position_size / price

    def add_position(self, position: Position) -> bool:
        """Add a new position."""
        self.positions[position.symbol] = position
        self.total_risk += position.margin * (self.limits.max_risk_per_trade / 100)
        self.logger.info(f"Position added: {position.symbol} {position.side} "
                        f"size={position.size:.4f} @ {position.entry_price:.2f}")
        return True

    def remove_position(self, symbol: str, exit_price: float = 0) -> Optional[Position]:
        """Remove a position and record P&L."""
        if symbol not in self.positions:
            return None

        pos = self.positions.pop(symbol)
        if exit_price > 0:
            pnl = pos.calculate_pnl(exit_price)
            self.daily_pnl += pnl
            if pnl < 0:
                self.daily_loss += abs(pnl)

            self.trade_history.append({
                "symbol": symbol,
                "side": pos.side,
                "entry": pos.entry_price,
                "exit": exit_price,
                "pnl": pnl,
                "pnl_percent": pos.pnl_percent,
                "close_time": datetime.now().isoformat()
            })

            self.logger.info(f"Position closed: {symbol} P&L=${pnl:+.2f}")

        return pos

    def update_positions(self, prices: Dict[str, float]):
        """Update all positions with current prices."""
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.calculate_pnl(prices[symbol])

    def check_stop_losses(self, prices: Dict[str, float]) -> List[str]:
        """Check for stop loss hits."""
        triggered = []
        for symbol, position in list(self.positions.items()):
            if symbol in prices:
                if position.is_stop_loss_hit(prices[symbol]):
                    triggered.append(symbol)
                    self.risk_events.append({
                        "type": "stop_loss",
                        "symbol": symbol,
                        "price": prices[symbol],
                        "time": datetime.now().isoformat()
                    })
        return triggered

    def check_take_profits(self, prices: Dict[str, float]) -> List[str]:
        """Check for take profit hits."""
        triggered = []
        for symbol, position in list(self.positions.items()):
            if symbol in prices:
                if position.is_take_profit_hit(prices[symbol]):
                    triggered.append(symbol)
                    self.risk_events.append({
                        "type": "take_profit",
                        "symbol": symbol,
                        "price": prices[symbol],
                        "time": datetime.now().isoformat()
                    })
        return triggered

    def get_stats(self) -> Dict[str, Any]:
        """Get risk statistics."""
        total_trades = len(self.trade_history)
        winning_trades = sum(1 for t in self.trade_history if t["pnl"] > 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        total_pnl = sum(t["pnl"] for t in self.trade_history)

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": total_trades - winning_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "daily_pnl": self.daily_pnl,
            "daily_loss": self.daily_loss,
            "open_positions": len(self.positions),
            "total_risk": self.total_risk,
            "risk_events": len(self.risk_events)
        }

    def reset_daily(self):
        """Reset daily statistics."""
        self.daily_pnl = 0.0
        self.daily_loss = 0.0
        self.logger.info("Daily risk statistics reset")

    def update_pnl(self, symbol: str, pnl: float):
        """Update P&L for a position."""
        if symbol in self.positions:
            self.positions[symbol].pnl = pnl
            if self.positions[symbol].margin > 0:
                self.positions[symbol].pnl_percent = (pnl / self.positions[symbol].margin) * 100
