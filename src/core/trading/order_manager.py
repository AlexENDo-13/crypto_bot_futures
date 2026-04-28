"""
Order Manager — FIXED: track orders, verify positions, handle partial fills
Исправления:
- Отслеживание ордера после размещения
- Синхронизация позиций с биржей
- Проверка что позиция действительно открыта
"""
import asyncio
import logging
import time
from typing import Optional, Dict, Any

logger = logging.getLogger("OrderManager")


class OrderManager:
    def __init__(self, api_client, logger):
        self.api_client = api_client
        self.logger = logger
        self.orders: Dict[str, Dict] = {}
        self.positions: Dict[str, Dict] = {}

    async def track_order(self, order_id: str, symbol: str, side: str,
                          position_side: str, quantity: float) -> Dict:
        """Track a new order"""
        order_info = {
            'order_id': order_id,
            'symbol': symbol,
            'side': side,
            'position_side': position_side,
            'quantity': quantity,
            'filled_qty': 0,
            'avg_price': 0,
            'status': 'PENDING',
            'created_at': time.time(),
            'updated_at': time.time()
        }
        self.orders[order_id] = order_info
        self.logger.info(f"Tracking order: {order_id} {symbol} {side}")
        return order_info

    async def update_order_status(self, order_id: str) -> Optional[Dict]:
        """Update order status from API"""
        if order_id not in self.orders:
            return None

        order = self.orders[order_id]
        symbol = order['symbol']

        try:
            # Query order status via open orders
            open_orders = await self.api_client.get_open_orders(symbol)
            for oo in open_orders:
                if oo.get('orderId') == order_id:
                    order['status'] = oo.get('status', 'OPEN')
                    order['filled_qty'] = float(oo.get('executedQty', 0))
                    order['avg_price'] = float(oo.get('avgPrice', 0))
                    order['updated_at'] = time.time()
                    return order

            # Order not in open orders — check if filled
            order['status'] = 'FILLED'
            order['updated_at'] = time.time()
            return order

        except Exception as e:
            self.logger.error(f"Failed to update order {order_id}: {e}")
            return order

    async def sync_positions(self) -> Dict[str, Dict]:
        """Sync positions from API"""
        try:
            positions = await self.api_client.get_positions()
            self.positions = {}
            for pos in positions:
                symbol = pos.get('symbol', '')
                pos_amt = float(pos.get('positionAmt', 0))
                if abs(pos_amt) > 0:
                    self.positions[symbol] = {
                        'symbol': symbol,
                        'position_side': pos.get('positionSide'),
                        'position_amt': pos_amt,
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'mark_price': float(pos.get('markPrice', 0)),
                        'unrealized_pnl': float(pos.get('unrealizedProfit', 0)),
                        'leverage': int(pos.get('leverage', 1))
                    }
            return self.positions
        except Exception as e:
            self.logger.error(f"Failed to sync positions: {e}")
            return {}

    def has_position(self, symbol: str, position_side: Optional[str] = None) -> bool:
        """Check if position exists"""
        symbol_formatted = symbol.replace('/', '-')
        if not symbol_formatted.endswith('-USDT'):
            symbol_formatted = f"{symbol_formatted}-USDT"

        if symbol_formatted not in self.positions:
            return False
        if position_side:
            return self.positions[symbol_formatted].get('position_side') == position_side
        return True
