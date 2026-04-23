import time
from typing import Dict, Optional

from src.utils.api_client import BingXClient
from src.core.logger import BotLogger
from src.core.risk.risk_manager import RiskManager
from src.config.constants import OrderSide, PositionSide

class OrderManager:
    def __init__(self, client: BingXClient, logger: BotLogger,
                 risk_manager: RiskManager, demo_mode: bool = True):
        self.client = client
        self.logger = logger
        self.risk_manager = risk_manager
        self.demo_mode = demo_mode
        self.active_orders: Dict[str, int] = {}
        self._close_attempts: Dict[str, int] = {}

    def open_position(self, symbol: str, side: OrderSide, quantity: float,
                      leverage: int, stop_loss_price: Optional[float] = None,
                      take_profit_price: Optional[float] = None,
                      trailing_stop_enabled: bool = False,
                      trailing_stop_distance: float = 0.015) -> Optional[Dict]:
        try:
            ticker = self.client.get_ticker(symbol)
            current_price = float(ticker.get("lastPrice", 0))
            if current_price <= 0:
                self.logger.error(f"Не удалось получить цену {symbol}")
                return None

            # Расчёт минимального номинала
            min_notional = getattr(self.risk_manager, 'MIN_NOTIONAL', 5.0)
            order_value_usdt = quantity * current_price
            if order_value_usdt < min_notional:
                quantity = (min_notional * 1.05) / current_price

            position_side = PositionSide.LONG if side == OrderSide.BUY else PositionSide.SHORT

            if self.demo_mode:
                self.logger.info(f"[ДЕМО] Открыта {side.value} {symbol} qty={quantity:.4f} @ {current_price:.6f}")
                return {"orderId": int(time.time() * 1000), "demo": True}

            self.client.set_margin_mode(symbol, 'cross')
            time.sleep(0.1)
            self.client.set_leverage(symbol, leverage, side=position_side.value)

            if side == OrderSide.BUY:
                order = self.client.place_market_buy(symbol, order_value_usdt, position_side.value,
                                                     stop_loss=stop_loss_price, take_profit=take_profit_price)
            else:
                order = self.client.place_market_sell(symbol, quantity, position_side.value,
                                                      stop_loss=stop_loss_price, take_profit=take_profit_price)

            self.active_orders[symbol] = order.get("orderId")
            self.logger.info(f"✅ Ордер выполнен: ID={order.get('orderId')}")
            self._close_attempts[symbol] = 0
            return order
        except Exception as e:
            self.logger.error(f"❌ Ошибка открытия {symbol}: {e}")
            return None

    def close_position(self, symbol: str) -> bool:
        if self.demo_mode:
            self.logger.info(f"[ДЕМО] Позиция {symbol} закрыта")
            return True

        if symbol not in self._close_attempts:
            self._close_attempts[symbol] = 0

        self._close_attempts[symbol] += 1
        attempt = self._close_attempts[symbol]

        success = self.client.close_position_with_cleanup(symbol)

        if success:
            if symbol in self._close_attempts:
                del self._close_attempts[symbol]
            if symbol in self.active_orders:
                del self.active_orders[symbol]
            return True
        else:
            if attempt >= 3:
                self.logger.error(f"🚨 Не удалось закрыть {symbol} после {attempt} попыток")
            return False

    def reset_close_attempts(self, symbol: str = None):
        if symbol:
            if symbol in self._close_attempts:
                del self._close_attempts[symbol]
        else:
            self._close_attempts.clear()
