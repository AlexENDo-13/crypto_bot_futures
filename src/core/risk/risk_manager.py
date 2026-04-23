#!/usr/bin/env python3
"""
Менеджер рисков и расчёта размера позиции.
"""
from typing import Optional

class RiskManager:
    MIN_NOTIONAL = 5.0  # минимальный номинал позиции в USDT

    def __init__(self, client, settings: dict):
        self.client = client
        self.settings = settings
        self._cached_balance: Optional[float] = None

    async def _get_available_balance_async(self, force_refresh: bool = False) -> float:
        """Асинхронно получает доступный баланс с биржи."""
        if self._cached_balance is None or force_refresh:
            try:
                account = await self.client.get_account_info()
                self._cached_balance = float(account.get('availableBalance', 0))
            except Exception:
                self._cached_balance = self.settings.get('virtual_balance', 100.0)
        return self._cached_balance

    def calculate_position_size(self, symbol: str, balance: float, risk_percent: float,
                                stop_distance_pct: float, leverage: int,
                                atr: float, current_price: float) -> float:
        """
        Рассчитывает количество контрактов (qty) на основе риска.
        """
        if stop_distance_pct <= 0 or current_price <= 0 or leverage <= 0:
            return 0.0

        risk_amount = balance * (risk_percent / 100.0)
        stop_loss_price = current_price * (1 - stop_distance_pct / 100.0)
        risk_per_unit = abs(current_price - stop_loss_price)

        if risk_per_unit <= 0:
            return 0.0

        qty = risk_amount / risk_per_unit
        # Корректировка на плечо (для фьючерсов)
        qty = qty * leverage

        notional = qty * current_price
        min_notional = self._get_min_notional(symbol)
        if notional < min_notional:
            return 0.0

        return round(qty, 6)

    def _get_min_notional(self, symbol: str) -> float:
        # Для BingX обычно 5 USDT
        return self.MIN_NOTIONAL
