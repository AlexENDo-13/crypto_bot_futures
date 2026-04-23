"""
Менеджер ордеров для работы с BingX Futures через AsyncBingXClient
"""
import asyncio
import time
import uuid
from typing import Dict, Optional, List
from enum import Enum

from src.utils.api_client import AsyncBingXClient
from src.config.settings import Settings
from src.core.logger import Logger


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

    def __init__(self, client: AsyncBingXClient, settings: Settings, logger: Logger):
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
        """
        Размещение ордера на BingX Futures.
        Возвращает ответ биржи или None при ошибке.
        """
        if not client_order_id:
            client_order_id = f"bot_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"

        # Установка плеча
        try:
            await self._set_leverage(symbol, leverage)
        except Exception as e:
            self.logger.error(f"Ошибка установки плеча: {e}")
            return None

        # Преобразование символа
        symbol_clean = self._clean_symbol(symbol)

        endpoint = "/api/v1/trade/order"
        params = {
            "symbol": symbol_clean,
            "side": side.value,
            "positionSide": position_side.value,
            "type": order_type.value,
            "quantity": str(quantity),
            "newClientOrderId": client_order_id,
        }

        if price and order_type in (OrderType.LIMIT,):
            params["price"] = str(price)
        if stop_price and order_type in (OrderType.STOP_MARKET, OrderType.TAKE_PROFIT_MARKET):
            params["stopPrice"] = str(stop_price)

        try:
            response = await self.client._request("POST", endpoint, params, signed=True)
            if response and response.get("code") == 0:
                data = response.get("data", {})
                order_id = data.get("orderId")
                self.logger.info(f"Ордер размещён: {symbol} {side.value} {quantity} @ {price or 'MARKET'}, ID: {order_id}")
                # Сохраняем в активные
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
                return data
            else:
                self.logger.error(f"Ошибка размещения ордера: {response}")
                return None
        except Exception as e:
            self.logger.error(f"Исключение при размещении ордера: {e}")
            return None

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Отмена ордера"""
        symbol_clean = self._clean_symbol(symbol)
        endpoint = "/api/v1/trade/cancel"
        params = {"symbol": symbol_clean, "orderId": order_id}
        try:
            response = await self.client._request("DELETE", endpoint, params, signed=True)
            if response and response.get("code") == 0:
                self.logger.info(f"Ордер {order_id} отменён")
                if order_id in self.active_orders:
                    del self.active_orders[order_id]
                return True
            return False
        except Exception as e:
            self.logger.error(f"Ошибка отмены ордера {order_id}: {e}")
            return False

    async def get_order_status(self, symbol: str, order_id: str) -> Optional[Dict]:
        """Получение статуса ордера"""
        symbol_clean = self._clean_symbol(symbol)
        endpoint = "/api/v1/trade/order"
        params = {"symbol": symbol_clean, "orderId": order_id}
        try:
            response = await self.client._request("GET", endpoint, params, signed=True)
            if response and response.get("code") == 0:
                return response.get("data")
            return None
        except Exception as e:
            self.logger.error(f"Ошибка получения статуса ордера {order_id}: {e}")
            return None

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Список открытых ордеров"""
        endpoint = "/api/v1/trade/openOrders"
        params = {}
        if symbol:
            params["symbol"] = self._clean_symbol(symbol)
        try:
            response = await self.client._request("GET", endpoint, params, signed=True)
            if response and response.get("code") == 0:
                return response.get("data", [])
            return []
        except Exception as e:
            self.logger.error(f"Ошибка получения открытых ордеров: {e}")
            return []

    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Получение информации о позициях"""
        endpoint = "/api/v1/trade/position"
        params = {}
        if symbol:
            params["symbol"] = self._clean_symbol(symbol)
        try:
            response = await self.client._request("GET", endpoint, params, signed=True)
            if response and response.get("code") == 0:
                return response.get("data", [])
            return []
        except Exception as e:
            self.logger.error(f"Ошибка получения позиций: {e}")
            return []

    async def close_position(self, symbol: str, position_side: PositionSide = PositionSide.BOTH) -> bool:
        """
        Закрытие позиции рыночным ордером.
        position_side: LONG или SHORT, если точно знаем какое направление.
        """
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
                        return await self.place_order(
                            symbol=symbol,
                            side=side,
                            order_type=OrderType.MARKET,
                            quantity=quantity,
                            position_side=PositionSide(pos_side)
                        ) is not None
            return False
        except Exception as e:
            self.logger.error(f"Ошибка закрытия позиции {symbol}: {e}")
            return False

    async def _set_leverage(self, symbol: str, leverage: int) -> bool:
        """Установка кредитного плеча для символа"""
        symbol_clean = self._clean_symbol(symbol)
        endpoint = "/api/v1/trade/leverage"
        params = {
            "symbol": symbol_clean,
            "leverage": str(leverage),
        }
        try:
            response = await self.client._request("POST", endpoint, params, signed=True)
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
