#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OrderManager — менеджер ордеров.
"""
import logging
from typing import Optional, Dict, Any

from src.core.logger import BotLogger

logger = logging.getLogger("OrderManager")

class OrderManager:
    """Управляет ордерами и их жизненным циклом."""

    def __init__(self, client, logger: BotLogger):
        self.client = client
        self.logger = logger
        self._orders: Dict[str, Any] = {}

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        leverage: int = None,
        stop_loss: float = None,
        take_profit: float = None,
    ) -> Optional[Dict]:
        """Размещает рыночный ордер."""
        return await self.client.place_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type="MARKET",
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_side="BOTH",
        )

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Отменяет ордер."""
        return await self.client.cancel_order(symbol, order_id)

    async def cancel_all_orders(self, symbol: str = None) -> bool:
        """Отменяет все ордера."""
        return await self.client.cancel_all_orders(symbol)
