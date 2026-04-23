"""
Менеджер ордеров для работы с BingX Futures через AsyncBingXClient.
Использует унифицированные методы клиента, в том числе cancel_order.
"""
import asyncio
import time
import uuid
from typing import Dict, Optional, List
from enum import Enum
from src.utils.api_client import AsyncBingXClient
from src.config.settings import Settings
from src.core.logger import BotLogger


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


class OrderManager:
    """Управление ордерами: создание, отмена, отслеживание"""

    def __init__(self, client: AsyncBingXClient, settings: Settings, logger: BotLogger):
        self.client = client
        self.settings = settings
        self.logger = logger
        self.active_orders: Dict[str, Dict] = {}

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        leverage: int = 1,
        position_side: PositionSide = PositionSide.BOTH,
        client_order_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """Размещение ордера на BingX Futures."""
        if not client_order_id:
            client_order_id = f"bot_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"

        try:
            result = await self.client.place_order(
                symbol=self._clean_symbol(symbol),
                side=side.value,
                quantity=quantity,
                leverage=leverage,
                order_type=order_type.value,
                price=price,
                position_side=position_side.value,
            )
            if result:
                order_id = result.get("orderId", client_order_id)
                self.logger.info(
                    f"Ордер размещён: {symbol} {side.value} {quantity} @ {price or 'MARKET'}, ID: {order_id}"
                )
                self.active_orders[order_id] = {
                    "orderId": order_id,
                    "symbol": symbol,
                    "side": side.value,
                    "quantity": quantity,
                    "price": price,
                    "status": "NEW",
                    "clientOrderId": client_order_id,
                    "timestamp": time.time(),
                }
                return result
            return None
        except Exception as e:
            self.logger.error(f"Ошибка размещения ордера: {e}")
            return None

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Отмена ордера (использует новый метод клиента)."""
        try:
            result = await self.client.cancel_order(
                symbol=self._clean_symbol(symbol),
                order_id=order_id,
            )
            if result and result.get("orderId"):
                self.logger.info(f"Ордер {order_id} отменён")
                if order_id in self.active_orders:
                    del self.active_orders[order_id]
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка отмены ордера {order_id}: {e}")
            return False

    async def get_order_status(self, symbol: str, order_id: str) -> Optional[Dict]:
        """Получение статуса ордера."""
        try:
            response = await self.client._request(
                "GET", "/openApi/swap/v2/trade/order",
                {"symbol": self._clean_symbol(symbol), "orderId": order_id},
                signed=True
            )
            if response and response.get("code") == 0:
                return response.get("data")
            return None
        except Exception as e:
            self.logger.error(f"Ошибка получения статуса ордера {order_id}: {e}")
            return None

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Список открытых ордеров."""
        try:
            params = {}
            if symbol:
                params["symbol"] = self._clean_symbol(symbol)
            response = await self.client._request(
                "GET", "/openApi/swap/v2/trade/openOrders", params, signed=True
            )
            if response and response.get("code") == 0:
                return response.get("data", [])
            return []
        except Exception as e:
            self.logger.error(f"Ошибка получения открытых ордеров: {e}")
            return []

    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Получение информации о позициях."""
        try:
            params = {}
            if symbol:
                params["symbol"] = self._clean_symbol(symbol)
            response = await self.client._request(
                "GET", "/openApi/swap/v2/trade/position", params, signed=True
            )
            if response and response.get("code") == 0:
                return response.get("data", [])
            return []
        except Exception as e:
            self.logger.error(f"Ошибка получения позиций: {e}")
            return []

    async def close_position(self, symbol: str, position_side: PositionSide = PositionSide.BOTH) -> bool:
        """Закрытие позиции рыночным ордером."""
        try:
            positions = await self.get_positions(symbol)
            for pos in positions:
                if pos.get("symbol") == self._clean_symbol(symbol):
                    pos_side = pos.get("positionSide")
                    if position_side != PositionSide.BOTH and pos_side != position_side.value:
                        continue
                    quantity = abs(float(pos.get("positionAmt", 0)))
                    if quantity > 0:
                        side = OrderSide.SELL if pos_side == "LONG" else OrderSide.BUY
                        result = await self.place_order(
                            symbol=symbol,
                            side=side,
                            order_type=OrderType.MARKET,
                            quantity=quantity,
                            position_side=PositionSide(pos_side)
                        )
                        return result is not None
            return False
        except Exception as e:
            self.logger.error(f"Ошибка закрытия позиции {symbol}: {e}")
            return False

    async def _set_leverage(self, symbol: str, leverage: int) -> bool:
        """Установка кредитного плеча для символа."""
        try:
            response = await self.client._request(
                "POST", "/openApi/swap/v2/trade/leverage",
                {"symbol": self._clean_symbol(symbol), "leverage": str(leverage)},
                signed=True
            )
            if response and response.get("code") == 0:
                self.logger.info(f"Плечо для {symbol} установлено: {leverage}x")
                return True
            else:
                self.logger.warning(f"Не удалось установить плечо: {response}")
                return False
        except Exception as e:
            self.logger.error(f"Ошибка установки плеча: {e}")
            return False

    def _clean_symbol(self, symbol: str) -> str:
        """Преобразование символа в формат BingX (BTC-USDT)"""
        s = symbol.replace(":USDT", "").replace("/", "-").upper()
        if not s.endswith("-USDT"):
            s = f"{s}-USDT"
        return s
