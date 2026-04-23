#!/usr/bin/env python3
import logging
from typing import Optional, Dict, Any
logger = logging.getLogger("OrderManager")

class OrderManager:
    def __init__(self, client, logger):
        self.client = client
        self.logger = logger
        self._pending_orders = {}
    async def place_market_order(self, symbol, side, quantity, position_side="BOTH"):
        result = await self.client.place_order(symbol=symbol, side=side, quantity=quantity, order_type="MARKET", position_side=position_side)
        if result and not result.get("error") and result.get("orderId"):
            self._pending_orders[result["orderId"]] = {"symbol":symbol,"side":side,"quantity":quantity,"status":"PENDING","type":"MARKET"}
            self.logger.info(f"📤 Маркет-ордер: {symbol} {side} {quantity}")
            return result
        err = result.get("msg","Unknown") if result else "No response"
        self.logger.error(f"❌ Маркет-ордер отклонён {symbol}: {err}")
        return None
    async def place_stop_order(self, symbol, side, stop_price, order_type="STOP_MARKET", position_side="BOTH", close_position=True):
        result = await self.client.place_stop_order(symbol=symbol, side=side, stop_price=stop_price, order_type=order_type, position_side=position_side, close_position=close_position)
        if result and not result.get("error") and result.get("orderId"):
            self.logger.info(f"🛡️ Стоп-ордер: {symbol} {side} @ {stop_price:.4f}")
            return result
        err = result.get("msg","Unknown") if result else "No response"
        self.logger.warning(f"⚠️ Стоп-ордер отклонён {symbol}: {err}")
        return None
    async def cancel_order(self, symbol, order_id):
        ok = await self.client.cancel_order(symbol, order_id)
        if ok: self._pending_orders.pop(order_id, None)
        return ok
    async def cancel_all_orders(self, symbol=None):
        ok = await self.client.cancel_all_orders(symbol)
        if ok:
            if symbol: self._pending_orders = {k:v for k,v in self._pending_orders.items() if v.get("symbol") != symbol}
            else: self._pending_orders.clear()
        return ok
    def get_pending_orders(self): return dict(self._pending_orders)
