import logging
import math
from typing import Optional, Dict, Any, List
from src.utils.api_client import AsyncBingXClient
from src.config.settings import Settings
from src.core.logger import BotLogger

logger = logging.getLogger(__name__)


class TradeExecutor:
    """
    Исполнитель торговых приказов (работает с AsyncBingXClient).
    С проверкой MIN_NOTIONAL и округлением до stepSize.
    """

    MIN_NOTIONAL = 5.0  # минимальная стоимость позиции в USDT

    def __init__(self, client: AsyncBingXClient, settings: Settings, logger: BotLogger):
        self.client = client
        self.settings = settings
        self.logger = logger

    def _round_quantity(self, symbol: str, quantity: float) -> float:
        """
        Округляет количество до stepSize.
        Использует настройки QTY_STEP из Settings.
        """
        step_map = getattr(self.settings, 'QTY_STEP', None)
        if step_map and isinstance(step_map, dict):
            step = step_map.get(symbol, step_map.get("default", 0.001))
        else:
            step = 0.001

        # Округляем вниз до ближайшего step
        qty = math.floor(quantity / step) * step
        return max(qty, step)  # Минимум 1 шаг

    def _check_min_notional(self, quantity: float, price: float) -> bool:
        """Проверяет, что стоимость позиции >= MIN_NOTIONAL."""
        return (quantity * price) >= self.MIN_NOTIONAL

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

        # Округляем количество
        qty = self._round_quantity(symbol, quantity)

        # Проверяем MIN_NOTIONAL
        ticker = None
        try:
            ticker_data = await self.client.get_ticker(normalized_symbol)
            if ticker_data:
                ticker = ticker_data
        except Exception:
            pass

        current_price = price or (float(ticker.get("lastPrice", 0)) if ticker else 0)
        if not self._check_min_notional(qty, current_price):
            self.logger.warning(
                f"Позиция {symbol} не проходит MIN_NOTIONAL: "
                f"qty={qty}, price={current_price}, notional={qty * current_price:.2f}"
            )
            # Увеличиваем количество до минимального
            if current_price > 0:
                qty = self._round_quantity(symbol, self.MIN_NOTIONAL / current_price * 1.01)
                self.logger.info(f"Увеличено количество до {qty} для соблюдения MIN_NOTIONAL")

        order_side = "BUY" if side.upper() == "LONG" else "SELL"
        order_type = "LIMIT" if price is not None else "MARKET"
        leverage = getattr(self.settings, 'max_leverage', 3)

        try:
            result = await self.client.place_order(
                symbol=normalized_symbol,
                side=order_side,
                quantity=qty,
                leverage=leverage,
                order_type=order_type,
                price=price
            )
            return {
                "success": True,
                "order_id": result.get("orderId"),
                "avg_price": float(result.get("avgPrice", current_price)),
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
        qty = self._round_quantity(symbol, quantity)

        try:
            await self.client.place_order(
                symbol=normalized_symbol,
                side=order_side,
                quantity=qty,
                order_type="MARKET"
            )
            return True
        except Exception as e:
            self.logger.error(f"Ошибка закрытия позиции {symbol}: {e}")
            return False
