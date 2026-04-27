#!/usr/bin/env python3
"""OrderManager — handles order lifecycle."""
import logging
from typing import Optional, Dict, Any

class OrderManager:
    def __init__(self, client, logger):
        self.client = client
        self.logger = logger
        self._open_order_ids: Dict[str, str] = {}

    async def place_market_order(self, symbol: str, side: str, quantity: float, position_side: str = "BOTH") -> Dict[str, Any]:
        bingx_symbol = symbol.replace("/", "-")
        result = await self.client.place_order(
            symbol=bingx_symbol, side=side, position_side=position_side,
            quantity=quantity, order_type="MARKET"
        )
        if result and not result.get("error") and result.get("orderId"):
            self._open_order_ids[bingx_symbol] = result.get("orderId")
        return result

    async def place_limit_order(self, symbol: str, side: str, quantity: float, price: float, position_side: str = "BOTH") -> Dict[str, Any]:
        bingx_symbol = symbol.replace("/", "-")
        return await self.client.place_order(
            symbol=bingx_symbol, side=side, position_side=position_side,
            quantity=quantity, order_type="LIMIT", price=price
        )

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        return await self.client.cancel_order(symbol.replace("/", "-"), order_id)

    async def cancel_all_orders(self, symbol: str) -> bool:
        return await self.client.cancel_all_orders(symbol.replace("/", "-"))

    def get_open_order(self, symbol: str) -> Optional[str]:
        return self._open_order_ids.get(symbol.replace("/", "-"))
