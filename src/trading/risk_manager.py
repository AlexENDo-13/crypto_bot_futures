"""
Risk Manager v5.0 - Kelly Criterion, Optimal F, correlation filtering,
volatility regime detection, and session-based trading.
"""
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import numpy as np

from src.core.config import get_config
from src.core.logger import get_logger
from src.core.state import StateManager

logger = get_logger()


@dataclass
class TradeRecord:
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    closed_at: datetime = field(default_factory=datetime.now)
    reason: str = ""
    duration_sec: float = 0


class RiskManager:
    """Advanced risk management with Kelly and Optimal F"""

    def __init__(self):
        self.config = get_config().risk
        self.trading_config = get_config().trading
        self.state = StateManager()

        self._trade_history: deque = deque(maxlen=2000)
        self._daily_stats: Dict[str, Dict] = {}
        self._consecutive_losses = 0
        self._max_consecutive_losses = 0
        self._peak_balance = 0.0
        self._current_drawdown = 0.0
        self._max_drawdown = 0.0
        self._cooldown_until: Optional[datetime] = None
        self._emergency_stop = False
        self._today = datetime.now().date()
        self._daily_trades = 0
        self._daily_pnl = 0.0

        logger.info("RiskManager v5.0 initialized")

    def update_pnl(self, pnl: float):
        today = datetime.now().date()
        if today != self._today:
            self._today = today
            self._daily_trades = 0
            self._daily_pnl = 0.0

        self._daily_pnl += pnl
        self._daily_trades += 1

        if pnl < 0:
            self._consecutive_losses += 1
            self._max_consecutive_losses = max(self._max_consecutive_losses, self._consecutive_losses)
        else:
            self._consecutive_losses = 0

    def record_trade(self, trade: TradeRecord):
        self._trade_history.append(trade)
        self.update_pnl(trade.pnl)

        today_str = trade.closed_at.strftime("%Y-%m-%d")
        if today_str not in self._daily_stats:
            self._daily_stats[today_str] = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0}
        s = self._daily_stats[today_str]
        s["trades"] += 1
        s["pnl"] += trade.pnl
        if trade.pnl > 0:
            s["wins"] += 1
        else:
            s["losses"] += 1

    def can_trade(self, balance: float, symbol: str = "") -> Tuple[bool, str]:
        if self._emergency_stop:
            return False, "EMERGENCY_STOP"

        if self._cooldown_until and datetime.now() < self._cooldown_until:
            return False, f"COOLDOWN: {(self._cooldown_until - datetime.now()).seconds}s"

        if self._daily_trades >= self.config.max_daily_trades:
            return False, "DAILY_LIMIT"

        daily_loss_limit = -(balance * self.trading_config.max_daily_loss_pct / 100)
        if self._daily_pnl <= daily_loss_limit:
            return False, "DAILY_LOSS"

        if self._consecutive_losses >= self.config.max_consecutive_losses:
            self._cooldown_until = datetime.now() + timedelta(seconds=self.trading_config.cooldown_after_loss_sec)
            return False, f"MAX_LOSSES: cooldown"

        if self._peak_balance > 0:
            dd = (self._peak_balance - balance) / self._peak_balance * 100
            if dd >= self.config.max_drawdown_pct:
                self._emergency_stop = True
                return False, f"MAX_DRAWDOWN: {dd:.1f}%"

        # Session check
        if not self._is_trading_session_allowed():
            return False, "SESSION_CLOSED"

        return True, "OK"

    def _is_trading_session_allowed(self) -> bool:
        """Check if current trading session is allowed"""
        now = datetime.utcnow()
        hour = now.hour

        # Asia: 00:00-08:00 UTC
        # London: 08:00-16:00 UTC
        # NY: 13:00-21:00 UTC

        in_asia = 0 <= hour < 8
        in_london = 8 <= hour < 16
        in_ny = 13 <= hour < 21

        if in_asia and not self.trading_config.trade_asia:
            return False
        if in_london and not self.trading_config.trade_london:
            return False
        if in_ny and not self.trading_config.trade_new_york:
            return False

        return True

    def calculate_position_size(self, balance: float, entry_price: float,
                                stop_loss_price: float, symbol: str = "") -> Tuple[float, str]:
        """Calculate position size with optional Kelly/Optimal F"""
        cfg = self.trading_config

        if entry_price <= 0 or stop_loss_price <= 0:
            return 0.0, "Invalid price"

        price_risk = abs(entry_price - stop_loss_price)
        if price_risk == 0:
            return 0.0, "Zero risk"

        risk_amount = balance * (cfg.risk_per_trade_pct / 100)

        # Kelly Criterion
        if self.config.use_kelly and len(self._trade_history) >= 20:
            kelly_size = self._calculate_kelly_size(balance, entry_price, stop_loss_price)
            if kelly_size > 0:
                risk_amount = min(risk_amount, kelly_size)

        # Optimal F
        if self.config.use_optimal_f and len(self._trade_history) >= 20:
            optimal_f = self._calculate_optimal_f()
            if optimal_f > 0:
                risk_amount = min(risk_amount, balance * optimal_f)

        quantity = risk_amount / price_risk
        notional = quantity * entry_price
        margin = notional / cfg.leverage

        max_notional = cfg.max_position_usdt
        if notional > max_notional:
            quantity = max_notional / entry_price
            margin = max_notional / cfg.leverage

        max_margin = balance * 0.95
        if margin > max_margin:
            quantity = (max_margin * cfg.leverage) / entry_price

        if quantity <= 0:
            return 0.0, "Zero qty"

        return quantity, f"qty={quantity:.6f} margin={margin:.2f}"

    def _calculate_kelly_size(self, balance: float, entry: float, sl: float) -> float:
        """Kelly Criterion position sizing"""
        wins = [t.pnl_pct for t in self._trade_history if t.pnl > 0]
        losses = [abs(t.pnl_pct) for t in self._trade_history if t.pnl < 0]

        if not wins or not losses:
            return 0

        W = len(wins) / (len(wins) + len(losses))
        R = np.mean(wins) / np.mean(losses) if np.mean(losses) > 0 else 1

        kelly = (W * R - (1 - W)) / R
        kelly = max(0, min(kelly, 0.5))  # Cap at 50%

        # Fractional Kelly
        kelly *= self.config.kelly_fraction

        price_risk = abs(entry - sl)
        return balance * kelly * self.trading_config.leverage / price_risk if price_risk > 0 else 0

    def _calculate_optimal_f(self) -> float:
        """Ralph Vince Optimal F"""
        pnls = [t.pnl for t in self._trade_history]
        if not pnls:
            return 0

        worst_loss = abs(min(pnls))
        if worst_loss == 0:
            return 0

        # Simplified Optimal F
        avg_win = np.mean([p for p in pnls if p > 0]) if any(p > 0 for p in pnls) else 0
        avg_loss = abs(np.mean([p for p in pnls if p < 0])) if any(p < 0 for p in pnls) else 0

        if avg_loss == 0:
            return 0.1

        W = sum(1 for p in pnls if p > 0) / len(pnls)
        optimal_f = (W * avg_win - (1 - W) * avg_loss) / avg_win if avg_win > 0 else 0
        return max(0, min(optimal_f, 0.25))

    def check_correlation(self, symbol: str, open_positions: List[str]) -> bool:
        """Check if new symbol is too correlated with existing positions"""
        # Simplified: check if same base asset
        base = symbol.split("-")[0]
        correlated = [p for p in open_positions if p.split("-")[0] == base]
        return len(correlated) < self.config.max_correlation_positions

    def check_volatility(self, atr_pct: float) -> Tuple[bool, str]:
        """Check if volatility is within acceptable range"""
        if atr_pct > self.config.max_atr_pct:
            return False, f"ATR too high: {atr_pct:.2f}%"
        if atr_pct < self.config.min_atr_pct:
            return False, f"ATR too low: {atr_pct:.2f}%"
        return True, "OK"

    def update_balance(self, balance: float):
        if balance > self._peak_balance:
            self._peak_balance = balance
        if self._peak_balance > 0:
            self._current_drawdown = (self._peak_balance - balance) / self._peak_balance * 100
            self._max_drawdown = max(self._max_drawdown, self._current_drawdown)

    def get_stats(self) -> Dict:
        total = len(self._trade_history)
        wins = sum(1 for t in self._trade_history if t.pnl > 0)
        losses = total - wins
        total_pnl = sum(t.pnl for t in self._trade_history)
        gross_profit = sum(t.pnl for t in self._trade_history if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self._trade_history if t.pnl < 0))
        pf = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1)

        return {
            "total_trades": total, "wins": wins, "losses": losses,
            "win_rate": (wins / total * 100) if total > 0 else 0,
            "total_pnl": total_pnl, "profit_factor": pf,
            "avg_pnl": total_pnl / total if total > 0 else 0,
            "consecutive_losses": self._consecutive_losses,
            "max_consecutive_losses": self._max_consecutive_losses,
            "current_drawdown": self._current_drawdown,
            "max_drawdown": self._max_drawdown,
            "daily_trades": self._daily_trades,
            "daily_pnl": self._daily_pnl,
            "emergency_stop": self._emergency_stop,
        }

    def reset_emergency_stop(self):
        self._emergency_stop = False
        self._cooldown_until = None
        logger.warning("Emergency stop RESET")
