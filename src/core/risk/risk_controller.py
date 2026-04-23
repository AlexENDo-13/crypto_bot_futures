#!/usr/bin/env python3
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
import time
from src.core.trading.position import Position

class RiskController:
    def __init__(self, logger, settings):
        self.logger = logger; self.settings = settings
        self.daily_start_balance = 0.0; self.daily_pnl = 0.0; self.daily_loss = 0.0
        self._daily_reset_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        self._position_count = 0; self._open_symbols = set(); self._circuit_breaker_active = False
        self._circuit_breaker_until = 0; self._correlation_limit = settings.get("correlation_limit_enabled", True)

    def _reset_daily_if_needed(self):
        now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        if now > self._daily_reset_time:
            self.daily_pnl = self.daily_loss = 0.0; self._daily_reset_time = now
            self._circuit_breaker_active = False; self._position_count = 0
            self.logger.info("📅 RiskController: дневная статистика сброшена")

    def check_circuit_breaker(self, balance):
        self._reset_daily_if_needed()
        if self._circuit_breaker_active:
            if time.time() < self._circuit_breaker_until: return False, "Circuit breaker активен"
            self._circuit_breaker_active = False
        daily_loss_limit = float(self.settings.get("daily_loss_limit_percent", 8.0))
        if balance > 0 and self.daily_loss > 0:
            loss_pct = (self.daily_loss / balance) * 100
            if loss_pct >= daily_loss_limit:
                self._circuit_breaker_active = True; self._circuit_breaker_until = time.time() + 3600
                return False, f"Дневной лимит убытков ({loss_pct:.1f}%)"
        max_daily = int(self.settings.get("max_daily_trades", 15))
        if self._position_count >= max_daily: return False, f"Дневной лимит сделок ({max_daily})"
        return True, "OK"

    def filter_signals(self, signals, positions, balance):
        max_positions = int(self.settings.get("max_positions", 3))
        max_total_risk = float(self.settings.get("max_total_risk_percent", 5.0)) / 100
        max_risk_per_trade = float(self.settings.get("max_risk_per_trade", 1.0)) / 100
        if len(positions) >= max_positions:
            self.logger.info(f"Лимит позиций ({max_positions})"); return []
        filtered = []; total_risk = 0.0; open_bases = {p.symbol.split("/")[0] for p in positions}
        for pos in positions:
            if pos.stop_loss_price and pos.entry_price > 0:
                total_risk += pos.quantity * pos.entry_price * (abs(pos.entry_price - pos.stop_loss_price) / pos.entry_price)
        for signal in signals:
            symbol = signal.get("symbol", ""); base = symbol.split("/")[0] if "/" in symbol else symbol.split("-")[0]
            if self._correlation_limit and base in open_bases:
                self.logger.debug(f"⛔ {symbol}: корреляция"); continue
            entry_price = signal.get("indicators", {}).get("close_price", 0)
            quantity = signal.get("quantity", 0); sl_distance = signal.get("stop_loss_distance_pct", 2.0) / 100
            if entry_price <= 0: continue
            if quantity <= 0:
                risk_pct = float(self.settings.get("max_risk_per_trade", 1.0))
                quantity = (balance * (risk_pct / 100)) / (entry_price * sl_distance) if sl_distance > 0 and balance > 0 else 0
            risk = quantity * entry_price * sl_distance if sl_distance > 0 else 0
            if balance > 0 and (total_risk + risk) / balance > max_total_risk: self.logger.info("Превышен общий риск"); break
            if balance > 0 and risk / balance > max_risk_per_trade: self.logger.info(f"Превышен риск на сделку {symbol}"); continue
            filtered.append(signal); total_risk += risk
            if len(positions) + len(filtered) >= max_positions: break
        return filtered

    def add_pnl(self, pnl):
        self._reset_daily_if_needed(); self.daily_pnl += pnl
        if pnl < 0: self.daily_loss += abs(pnl)

    def register_position_open(self, symbol): self._position_count += 1; self._open_symbols.add(symbol)
    def register_position_close(self, symbol): self._open_symbols.discard(symbol)
    def get_stats(self):
        self._reset_daily_if_needed()
        return {"daily_pnl": self.daily_pnl, "daily_loss": self.daily_loss, "position_count": self._position_count,
                "open_symbols": list(self._open_symbols), "circuit_breaker": self._circuit_breaker_active}
