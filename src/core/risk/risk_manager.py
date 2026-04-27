#!/usr/bin/env python3
"""RiskManager v11 — Fixed position sizing for micro balances, better adaptation."""
import logging, math, time
from typing import Dict, Optional
from datetime import datetime
from src.core.trading.position import Position, OrderSide

logger = logging.getLogger("RiskManager")

class AntiChase:
    def __init__(self, max_orders_per_hour=8, cooldown_seconds=180):
        self.max_orders_per_hour = max_orders_per_hour
        self.cooldown_seconds = cooldown_seconds
        self._trade_times = []
        self._last_trade_time = 0

    def can_trade(self):
        now = time.time()
        if now - self._last_trade_time < self.cooldown_seconds:
            return False, f"Cooldown: {self.cooldown_seconds - (now - self._last_trade_time):.0f}s"
        hour_ago = now - 3600
        self._trade_times = [t for t in self._trade_times if t > hour_ago]
        if len(self._trade_times) >= self.max_orders_per_hour:
            return False, f"Hourly limit ({self.max_orders_per_hour})"
        return True, "OK"

    def register_trade(self):
        now = time.time()
        self._trade_times.append(now)
        self._last_trade_time = now

class RiskManager:
    def __init__(self, client, settings):
        self.client = client
        self.settings = settings
        self._cached_balance = 0.0
        self._balance_cache_time = 0
        self._balance_cache_ttl = 30
        self.max_positions = int(settings.get("max_positions", 3))
        self.risk_per_trade = float(settings.get("max_risk_per_trade", 1.0))
        self.max_total_risk = float(settings.get("max_total_risk_percent", 5.0))
        self.max_leverage = int(settings.get("max_leverage", 10))
        self.default_sl_pct = float(settings.get("default_sl_pct", 1.5))
        self.default_tp_pct = float(settings.get("default_tp_pct", 3.0))
        self.daily_loss_limit = float(settings.get("daily_loss_limit_percent", 8.0))
        self.anti_chase_threshold = float(settings.get("anti_chase_threshold_percent", 0.3))
        self.trailing_enabled = settings.get("trailing_stop_enabled", True)
        self.trailing_distance = float(settings.get("trailing_stop_distance_percent", 2.0))
        self.trailing_activation = float(settings.get("trailing_activation", 1.5))
        self.trailing_callback = float(settings.get("trailing_callback", 0.5))
        self.max_hold_time = float(settings.get("max_hold_time_minutes", 240))
        self.anti_martingale = settings.get("anti_martingale_enabled", True)
        self.anti_martingale_reduction = float(settings.get("anti_martingale_risk_reduction", 0.8))
        self.weekend_risk_multiplier = float(settings.get("weekend_risk_multiplier", 0.5))
        self.reduce_weekend = settings.get("reduce_risk_on_weekends", True)
        self.daily_profit_target = float(settings.get("daily_profit_target_percent", 5.0))
        self.stop_on_target = settings.get("stop_on_daily_target", False)
        self.anti_chase = AntiChase(max_orders_per_hour=int(settings.get("max_orders_per_hour", 8)))
        self.daily_pnl = 0.0
        self.daily_loss = 0.0
        self.consecutive_losses = 0
        self.total_risk_exposure = 0.0
        self._daily_reset_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        self._total_trades = 0
        self._winning_trades = 0

        self._base_risk_per_trade = self.risk_per_trade
        self._base_max_positions = self.max_positions
        self._base_max_leverage = self.max_leverage
        self._current_balance_tier = "medium"

    def _reset_daily_if_needed(self):
        now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        if now > self._daily_reset_time:
            self.daily_pnl = self.daily_loss = self.consecutive_losses = self.total_risk_exposure = 0.0
            self._daily_reset_time = now
            logger.info("Daily stats reset")

    def adapt_to_balance(self, balance: float):
        if balance <= 0:
            return
        old_tier = self._current_balance_tier

        if balance < 50:
            self._current_balance_tier = "micro"
            self.risk_per_trade = min(self._base_risk_per_trade, 5.0)
            self.max_positions = 1
            self.max_leverage = min(self._base_max_leverage, 10)
            self.max_total_risk = 10.0
        elif balance < 200:
            self._current_balance_tier = "small"
            self.risk_per_trade = min(self._base_risk_per_trade, 3.0)
            self.max_positions = min(self._base_max_positions, 2)
            self.max_leverage = min(self._base_max_leverage, 15)
            self.max_total_risk = 8.0
        elif balance < 1000:
            self._current_balance_tier = "medium"
            self.risk_per_trade = min(self._base_risk_per_trade, 2.0)
            self.max_positions = min(self._base_max_positions, 3)
            self.max_leverage = min(self._base_max_leverage, 20)
            self.max_total_risk = 6.0
        elif balance < 5000:
            self._current_balance_tier = "large"
            self.risk_per_trade = min(self._base_risk_per_trade, 1.5)
            self.max_positions = min(self._base_max_positions, 5)
            self.max_leverage = min(self._base_max_leverage, 25)
            self.max_total_risk = 8.0
        else:
            self._current_balance_tier = "whale"
            self.risk_per_trade = min(self._base_risk_per_trade, 1.0)
            self.max_positions = min(self._base_max_positions, 7)
            self.max_leverage = min(self._base_max_leverage, 30)
            self.max_total_risk = 10.0

        if old_tier != self._current_balance_tier:
            logger.info(f"Balance tier: {old_tier} -> {self._current_balance_tier} "
                        f"(bal=${balance:.2f}, risk={self.risk_per_trade}%, pos={self.max_positions}, "
                        f"lev={self.max_leverage}x, max_risk={self.max_total_risk}%)")

    async def get_account_balance(self):
        now = time.time()
        if now - self._balance_cache_time < self._balance_cache_ttl and self._cached_balance > 0:
            return {"total_equity": self._cached_balance, "available_balance": self._cached_balance,
                    "used": 0.0, "equity": self._cached_balance}
        try:
            account = await self.client.get_account_balance()
            if account and isinstance(account, dict):
                if "balance" in account and isinstance(account["balance"], dict):
                    balance = float(account["balance"].get("balance", 0))
                else:
                    balance = float(account.get("balance", account.get("totalEquity",
                             account.get("equity", account.get("availableBalance",
                             account.get("totalWalletBalance", 0))))))
                self._cached_balance = balance
                self._balance_cache_time = now
                self.adapt_to_balance(balance)

                available = balance
                if "balance" in account and isinstance(account["balance"], dict):
                    available = float(account["balance"].get("availableMargin", balance))
                else:
                    available = float(account.get("availableMargin", account.get("available",
                             account.get("availableBalance", balance))))

                used = 0.0
                if "balance" in account and isinstance(account["balance"], dict):
                    used = float(account["balance"].get("usedMargin", 0))
                else:
                    used = float(account.get("usedMargin", account.get("used", 0)))

                return {"total_equity": balance, "available_balance": available,
                        "used": used, "equity": float(account.get("equity", balance)) if isinstance(account, dict) else balance,
                        "unrealizedProfit": float(account.get("unrealizedProfit", 0)) if isinstance(account, dict) else 0}
        except Exception as e:
            logger.error(f"Balance error: {e}")
        return {"total_equity": self._cached_balance, "available_balance": self._cached_balance,
                "used": 0.0, "equity": self._cached_balance}

    def calculate_position_size(self, symbol, balance, risk_percent, stop_distance_pct, leverage, atr, current_price, symbol_specs=None):
        self._reset_daily_if_needed()
        if balance <= 0 or current_price <= 0:
            logger.warning(f"Invalid balance/price: balance={balance}, price={current_price}")
            return 0.0

        self.adapt_to_balance(balance)

        is_weekend = datetime.utcnow().weekday() >= 5
        if is_weekend and self.reduce_weekend:
            risk_percent *= self.weekend_risk_multiplier
            leverage = max(1, int(leverage * self.weekend_risk_multiplier))
        if self.consecutive_losses > 0 and self.anti_martingale:
            risk_percent *= self.anti_martingale_reduction ** self.consecutive_losses

        risk_percent = max(0.5, min(risk_percent, 10.0))
        risk_amount = balance * (risk_percent / 100.0)
        risk_amount = max(risk_amount, 0.05)

        stop_distance_pct = max(0.2, min(stop_distance_pct, 15.0))
        position_value = risk_amount / (stop_distance_pct / 100.0)
        margin_required = position_value / leverage if leverage > 0 else position_value

        # For micro balances, allow up to 90% of balance as margin (single position)
        if self._current_balance_tier == "micro":
            max_margin = balance * 0.9
        else:
            max_margin = balance * 0.6

        if margin_required > max_margin:
            margin_required = max_margin
            position_value = margin_required * leverage if leverage > 0 else margin_required

        quantity = position_value / current_price if current_price > 0 else 0

        if symbol_specs:
            step = float(symbol_specs.get("stepSize", symbol_specs.get("size", 0.001)))
            min_notional = float(symbol_specs.get("minNotional", symbol_specs.get("tradeMinUSDT", 5.0)))
            if step > 0:
                quantity = math.floor(quantity / step) * step
            # If below min notional, boost to minimum
            if quantity * current_price < min_notional:
                quantity = math.ceil(min_notional / current_price / step) * step if step > 0 else min_notional / current_price
                # Recalculate margin after min_notional adjustment
                new_position_value = quantity * current_price
                new_margin = new_position_value / leverage if leverage > 0 else new_position_value
                if new_margin > balance * 0.95:
                    logger.warning(f"{symbol}: min notional requires ${new_margin:.2f} margin > 95% balance")
                    return 0.0
                margin_required = new_margin
                position_value = new_position_value
        else:
            step = 0.001
            quantity = math.floor(quantity / step) * step
            if quantity * current_price < 5.0:
                quantity = math.ceil(5.0 / current_price / step) * step

        if quantity <= 0:
            logger.warning(f"{symbol}: qty=0 (bal={balance:.2f}, price={current_price:.6f})")
            return 0.0

        # Final risk check
        total_risk_pct = (self.total_risk_exposure + risk_amount) / balance * 100 if balance > 0 else 0
        if total_risk_pct > self.max_total_risk:
            logger.warning(f"Total risk exceeded ({total_risk_pct:.2f}% > {self.max_total_risk}%) for {symbol}")
            return 0.0

        logger.info(f"{symbol}: qty={quantity:.6f}, value=${quantity*current_price:.2f}, "
                    f"margin=${margin_required:.2f}, risk=${risk_amount:.4f} ({risk_percent:.2f}%), lev={leverage}x")
        return quantity

    def calculate_sl_tp(self, position, atr=None):
        if atr is None:
            atr = position.entry_price * (self.default_sl_pct / 100) if position.entry_price > 0 else 0.01
        atr_mult_sl = 1.5
        atr_mult_tp = 3.0
        if position.side == OrderSide.BUY:
            sl = position.entry_price - (atr * atr_mult_sl)
            tp = position.entry_price + (atr * atr_mult_tp)
        else:
            sl = position.entry_price + (atr * atr_mult_sl)
            tp = position.entry_price - (atr * atr_mult_tp)
        min_sl = position.entry_price * (self.default_sl_pct / 100) if position.entry_price > 0 else 0.01
        min_tp = position.entry_price * (self.default_tp_pct / 100) if position.entry_price > 0 else 0.01
        if position.side == OrderSide.BUY:
            sl = min(sl, position.entry_price - min_sl)
            tp = max(tp, position.entry_price + min_tp)
        else:
            sl = max(sl, position.entry_price + min_sl)
            tp = min(tp, position.entry_price - min_tp)
        return round(sl, 4), round(tp, 4)

    def update_pnl(self, pnl):
        self._reset_daily_if_needed()
        self.daily_pnl += pnl
        if pnl < 0:
            self.daily_loss += abs(pnl)
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
            self._winning_trades += 1
        self._total_trades += 1

    def check_circuit_breaker(self, balance):
        self._reset_daily_if_needed()
        if balance > 0:
            daily_loss_pct = (self.daily_loss / balance) * 100
            if daily_loss_pct >= self.daily_loss_limit:
                return False, f"Daily loss limit ({daily_loss_pct:.1f}%)"
            if self.stop_on_target and self.daily_pnl > 0:
                profit_pct = (self.daily_pnl / balance) * 100
                if profit_pct >= self.daily_profit_target:
                    return False, f"Daily profit target ({profit_pct:.1f}%)"
            if self.consecutive_losses >= 5:
                return False, f"Too many consecutive losses ({self.consecutive_losses})"
        return True, "OK"

    def can_open_position(self, current_count, balance):
        self._reset_daily_if_needed()
        if current_count >= self.max_positions:
            return False, f"Position limit ({self.max_positions})"
        ok, reason = self.check_circuit_breaker(balance)
        if not ok:
            return False, reason
        ok, reason = self.anti_chase.can_trade()
        if not ok:
            return False, reason
        return True, "OK"

    def register_position_open(self, position):
        self.anti_chase.register_trade()
        if position.stop_loss_price and position.entry_price > 0:
            sl_dist = abs(position.entry_price - position.stop_loss_price) / position.entry_price
            self.total_risk_exposure += position.quantity * position.entry_price * sl_dist

    def register_position_close(self, position):
        if position.stop_loss_price and position.entry_price > 0:
            sl_dist = abs(position.entry_price - position.stop_loss_price) / position.entry_price
            self.total_risk_exposure = max(0, self.total_risk_exposure - position.quantity * position.entry_price * sl_dist)

    def get_daily_stats(self):
        self._reset_daily_if_needed()
        return {
            "daily_pnl": self.daily_pnl,
            "daily_loss": self.daily_loss,
            "consecutive_losses": self.consecutive_losses,
            "total_risk_exposure": self.total_risk_exposure,
            "max_positions": self.max_positions,
            "total_trades": self._total_trades,
            "winning_trades": self._winning_trades,
            "win_rate": (self._winning_trades / self._total_trades * 100) if self._total_trades > 0 else 0,
            "balance_tier": self._current_balance_tier,
            "risk_per_trade": self.risk_per_trade,
            "max_leverage": self.max_leverage,
        }
