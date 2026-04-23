import logging
from typing import Optional, Dict, Any, List

from src.utils.api_client import AsyncBingXClient
from src.config.settings import Settings
from src.core.logger import BotLogger

logger = logging.getLogger(__name__)

class TradeExecutor:
    """Исполнитель торговых приказов (работает с AsyncBingXClient)."""

    def __init__(self, client: AsyncBingXClient, settings: Settings, logger: BotLogger):
        self.client = client
        self.settings = settings
        self.logger = logger

    async def open_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Открытие позиции. side = 'LONG'/'SHORT'."""
        normalized_symbol = symbol.replace("/", "-").upper()
        if not normalized_symbol.endswith("-USDT"):
            normalized_symbol = f"{normalized_symbol}-USDT"

        order_side = "BUY" if side.upper() == "LONG" else "SELL"
        order_type = "LIMIT" if price is not None else "MARKET"
        leverage = getattr(self.settings, 'max_leverage', 3)

        try:
            result = await self.client.place_order(
                symbol=normalized_symbol,
                side=order_side,
                quantity=quantity,
                leverage=leverage,
                order_type=order_type,
                price=price
            )
            return {
                "success": True,
                "order_id": result.get("orderId"),
                "avg_price": float(result.get("avgPrice", 0)),
            }
        except Exception as e:
            self.logger.error(f"Ошибка открытия позиции {symbol}: {e}")
            return {"success": False, "error": str(e)}

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Получить список открытых позиций."""
        try:
            return await self.client.get_positions()
        except Exception:
            return []

    async def close_position(self, symbol: str, side: str, quantity: float) -> bool:
        """Закрыть позицию полностью или частично."""
        normalized_symbol = symbol.replace("/", "-").upper()
        if not normalized_symbol.endswith("-USDT"):
            normalized_symbol = f"{normalized_symbol}-USDT"

        order_side = "SELL" if side.upper() == "LONG" else "BUY"
        try:
            await self.client.place_order(
                symbol=normalized_symbol,
                side=order_side,
                quantity=quantity,
                order_type="MARKET"
            )
            return True
        except Exception as e:
            self.logger.error(f"Ошибка закрытия позиции {symbol}: {e}")
            return False
