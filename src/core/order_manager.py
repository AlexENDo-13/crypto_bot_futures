"""Order execution manager."""
from typing import Optional
from src.core.models import Signal, Order
from src.core.bot_logger import BotLogger


class OrderManager:
    """Управление ордерами."""

    def __init__(self, api_client, logger: BotLogger):
        self.api_client = api_client
        self.logger = logger

    async def open_position(self, signal: Signal) -> Optional[Order]:
        side = "BUY" if signal.side == "LONG" else "SELL"
        quantity = 0.01  # Placeholder - should calculate from risk

        try:
            result = await self.api_client.place_order(
                symbol=signal.symbol,
                side=side,
                order_type="MARKET",
                quantity=quantity
            )
            self.logger.info(f"Order placed: {result}")
            return Order(
                symbol=signal.symbol,
                side=side,
                order_type="MARKET",
                quantity=quantity,
                order_id=result.get("orderId", "")
            )
        except Exception as e:
            self.logger.error(f"Order failed: {e}")
            return None

    async def close_position(self, position) -> bool:
        try:
            side = "SELL" if position.side == "LONG" else "BUY"
            await self.api_client.place_order(
                symbol=position.symbol,
                side=side,
                order_type="MARKET",
                quantity=position.quantity
            )
            return True
        except Exception as e:
            self.logger.error(f"Close position failed: {e}")
            return False
