# src/core/executor/trade_executor.py
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from src.utils.api_client import AsyncBingXClient
from src.config.settings import Settings
from src.core.logger import Logger

logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str] = None
    executed_price: float = 0.0
    executed_qty: float = 0.0
    error: Optional[str] = None


class TradeExecutor:
    """Исполнитель торговых приказов (работает с AsyncBingXClient)."""

    def __init__(self, client: AsyncBingXClient, settings: Settings, logger: Logger):
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
        """Открытие позиции."""
        normalized_symbol = symbol.replace("/", "-").upper()
        if not normalized_symbol.endswith("-USDT"):
            normalized_symbol = f"{normalized_symbol}-USDT"

        order_side = "BUY" if side.upper() == "LONG" else "SELL"
        order_type = "LIMIT" if price is not None else "MARKET"

        try:
            params = {
                "symbol": normalized_symbol,
                "side": order_side,
                "type": order_type,
                "quantity": str(quantity),
            }
            if price is not None:
                params["price"] = str(price)

            response = await self.client._request("POST", "/openApi/swap/v2/trade/order", params)
            return {"success": True, "order_id": response.get("orderId"), "avg_price": float(response.get("avgPrice", 0))}
        except Exception as e:
            self.logger.error(f"Ошибка открытия позиции {symbol}: {e}")
            return {"success": False, "error": str(e)}

    async def close_position(self, symbol: str, side: str, quantity: float) -> bool:
        """Закрытие позиции."""
        normalized_symbol = symbol.replace("/", "-").upper()
        if not normalized_symbol.endswith("-USDT"):
            normalized_symbol = f"{normalized_symbol}-USDT"

        order_side = "SELL" if side.upper() == "LONG" else "BUY"
        try:
            params = {"symbol": normalized_symbol, "side": order_side, "type": "MARKET", "quantity": str(quantity)}
            await self.client._request("POST", "/openApi/swap/v2/trade/order", params)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка закрытия позиции {symbol}: {e}")
            return False

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        try:
            response = await self.client._request("GET", "/openApi/swap/v2/user/positions", {})
            return response if isinstance(response, list) else []
        except Exception:
            return []
