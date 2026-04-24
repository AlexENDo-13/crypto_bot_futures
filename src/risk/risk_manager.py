"""
CryptoBot v7.1 - Risk Manager
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
    max_position_size: float = 1000.0
    max_risk_per_trade: float = 2.0
    max_leverage: int = 10
    max_daily_loss: float = 5.0
    max_total_risk: float = 10.0
    default_sl_percent: float = 2.0
    default_tp_percent: float = 4.0
    min_risk_reward: float = 1.5
    max_drawdown: float = 15.0
    max_correlation: float = 0.8


@dataclass
class Position:
    symbol: str
    side: str
    size: float
    entry_price: float
    leverage: int = 1
    stop_loss: float = 0.0
    take_profit: float = 0.0
    trailing_stop: float = 0.0
    margin: float = 0.0
    open_time: datetime = field(default_factory=datetime.now)
    pnl: float = 0.0
    pnl_percent: float = 0.0
    max_profit: float = 0.0

    def calculate_pnl(self, mark_price: float) -> float:
        if self.side == "LONG":
            self.pnl = (mark_price - self.entry_price) * self.size
        else:
            self.pnl = (self.entry_price - mark_price) * self.size

        if self.margin > 0:
            self.pnl_percent = (self.pnl / self.margin) * 100
        else:
            self.pnl_percent = 0.0

        # Track max profit for trailing stop
        if self.pnl > self.max_profit:
            self.max_profit = self.pnl

        return self.pnl

    def calculate_pnl_percent(self, mark_price: float) -> float:
        """Calculate P&L percentage safely."""
        pnl = self.calculate_pnl(mark_price)
        if self.margin > 0:
            return (pnl / self.margin) * 100
        return 0.0

    def is_stop_loss_hit(self, price: float) -> bool:
        if self.stop_loss <= 0:
            return False
        if self.side == "LONG":
            return price <= self.stop_loss
        return price >= self.stop_loss

    def is_take_profit_hit(self, price: float) -> bool:
        if self.take_profit <= 0:
            return False
        if self.side == "LONG":
            return price >= self.take_profit
        return price <= self.take_profit

    def update_trailing_stop(self, price: float, trail_pct: float = 1.0):
        """Update trailing stop based on current price."""
        if self.side == "LONG":
            new_sl = price * (1 - trail_pct / 100)
            if new_sl > self.stop_loss:
                self.stop_loss = new_sl
        else:
            new_sl = price * (1 + trail_pct / 100)
            if new_sl < self.stop_loss or self.stop_loss == 0:
                self.stop_loss = new_sl


class RiskManager:
    """Advanced risk management."""

    def __init__(self, limits: RiskLimits = None):
        self.limits = limits or RiskLimits()
        self.logger = logging.getLogger("CryptoBot.Risk")
        self.positions: Dict[str, Position] = {}
        self.daily_pnl: float = 0.0
        self.daily_loss: float = 0.0
        self.total_risk: float = 0.0
        self.peak_balance: float = 0.0
        self.trade_history: List[Dict] = []
        self.risk_events: List[Dict] = []

        self.logger.info("RiskManager v7.1 initialized")

    def can_open_position(self, symbol: str, side: str, size: float,
                          price: float, leverage: int = 1,
                          balance: float = 10000.0) -> tuple:
        if leverage > self.limits.max_leverage:
            return False, "Leverage %dx exceeds max %dx" % (leverage, self.limits.max_leverage)

        position_value = size * price
        if position_value > self.limits.max_position_size:
            return False, "Position $%.2f exceeds max $%.2f" % (
                position_value, self.limits.max_position_size
            )

        if self.daily_loss >= balance * (self.limits.max_daily_loss / 100):
            return False, "Daily loss limit reached: $%.2f" % self.daily_loss

        if len(self.positions) >= 5:
            return False, "Max concurrent positions (5) reached"

        if symbol in self.positions:
            return False, "Already in position: %s" % symbol

        # Drawdown check
        if self.peak_balance > 0:
            drawdown = (self.peak_balance - (balance + self.daily_pnl)) / self.peak_balance * 100
            if drawdown > self.limits.max_drawdown:
                return False, "Max drawdown reached: %.1f%%" % drawdown

        risk_amount = position_value * (self.limits.max_risk_per_trade / 100)
        if self.total_risk + risk_amount > balance * (self.limits.max_total_risk / 100):
            return False, "Total risk limit exceeded"

        return True, "OK"

    def calculate_position_size(self, price: float, stop_loss: float,
                                balance: float = 10000.0,
                                risk_percent: float = None) -> float:
        risk_pct = risk_percent or self.limits.max_risk_per_trade
        risk_amount = balance * (risk_pct / 100)

        if stop_loss > 0 and price > 0:
            sl_distance = abs(price - stop_loss) / price
            if sl_distance > 0:
                size = risk_amount / (price * sl_distance)
                return min(size, self.limits.max_position_size / price)

        return self.limits.max_position_size / price

    def add_position(self, position: Position) -> bool:
        # Validate entry price
        if position.entry_price <= 0:
            self.logger.warning(
                "Invalid entry price for %s: %s",
                position.symbol, position.entry_price
            )
            return False
        if position.size <= 0:
            self.logger.warning(
                "Invalid size for %s: %s",
                position.symbol, position.size
            )
            return False

        self.positions[position.symbol] = position
        self.total_risk += position.margin * (self.limits.max_risk_per_trade / 100)
        self.logger.info(
            "Position added: %s %s @ %.2f",
            position.symbol, position.side, position.entry_price
        )
        return True

    def remove_position(self, symbol: str, exit_price: float = 0) -> Optional[Position]:
        if symbol not in self.positions:
            return None

        pos = self.positions.pop(symbol)
        pnl = 0.0
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

        self.logger.info("Position closed: %s P&L=$%+.2f", symbol, pnl)

        return pos

    def update_positions(self, prices: Dict[str, float]):
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.calculate_pnl(prices[symbol])
                # Update trailing stop
                position.update_trailing_stop(
                    prices[symbol], self.limits.default_sl_percent
                )

    def check_stop_losses(self, prices: Dict[str, float]) -> List[str]:
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
        total_trades = len(self.trade_history)
        winning = sum(1 for t in self.trade_history if t["pnl"] > 0)
        win_rate = (winning / total_trades * 100) if total_trades > 0 else 0
        total_pnl = sum(t["pnl"] for t in self.trade_history)

        return {
            "total_trades": total_trades,
            "winning_trades": winning,
            "losing_trades": total_trades - winning,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "daily_pnl": self.daily_pnl,
            "daily_loss": self.daily_loss,
            "open_positions": len(self.positions),
            "total_risk": self.total_risk,
            "risk_events": len(self.risk_events)
        }

    def reset_daily(self):
        self.daily_pnl = 0.0
        self.daily_loss = 0.0
        self.logger.info("Daily stats reset")

    def update_pnl(self, symbol: str, pnl: float):
        if symbol in self.positions:
            self.positions[symbol].pnl = pnl
            if self.positions[symbol].margin > 0:
                self.positions[symbol].pnl_percent = (
                    pnl / self.positions[symbol].margin
                ) * 100
