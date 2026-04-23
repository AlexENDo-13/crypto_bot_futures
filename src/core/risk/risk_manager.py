from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime
from src.utils.api_client import AsyncBingXClient
from src.config.settings import Settings


class Position:
    """
    Модель данных позиции для бизнес-логики (SL/TP/трейлинг).
    Используется ExitManager и RiskManager.
    """

    def __init__(
        self,
        symbol: str,
        side: str,           # "LONG" / "SHORT"
        quantity: float,
        entry_price: float,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        max_price_seen: Optional[float] = None,
        min_price_seen: Optional[float] = None,
        entry_time: Optional[datetime] = None,
        order_id: Optional[str] = None,
    ):
        self.symbol = symbol
        self.side = side.upper()
        self.quantity = quantity
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.max_price_seen = max_price_seen if max_price_seen is not None else entry_price
        self.min_price_seen = min_price_seen if min_price_seen is not None else entry_price
        self.entry_time = entry_time or datetime.utcnow()
        self.order_id = order_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "max_price_seen": self.max_price_seen,
            "min_price_seen": self.min_price_seen,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "order_id": self.order_id,
        }


class RiskManager:
    MIN_NOTIONAL = 5.0  # минимальная стоимость позиции в USDT

    def __init__(self, client: AsyncBingXClient, settings: Settings):
        self.client = client
        self.settings = settings
        self._cached_balance: Optional[float] = None
        self._open_positions: Dict[str, Position] = {}

    async def get_account_balance(self) -> Dict[str, float]:
        try:
            account = await self.client.get_account_info()
            balance = float(account.get("availableBalance", 0))
            self._cached_balance = balance
            return {"total_equity": balance, "available_balance": balance}
        except Exception:
            return {
                "total_equity": self.settings.get("virtual_balance", 100.0),
                "available_balance": self.settings.get("virtual_balance", 100.0),
            }

    async def check_new_position_allowed(
        self, symbol: str, direction: str, confidence: float
    ) -> Tuple[bool, str]:
        positions = await self.client.get_positions()
        max_positions = getattr(self.settings, "max_positions", 3)
        if len(positions) >= max_positions:
            return False, f"Достигнут лимит открытых позиций ({max_positions})"
        return True, "OK"

    async def calculate_position_size(
        self, symbol: str, price: float, confidence: float
    ) -> float:
        """
        Расчёт размера позиции на основе риска.
        ИСПРАВЛЕНО: убран множитель leverage из формулы.
        qty = (balance * risk%) / price — позиция открывается с плечом,
        но размер позиции определяется только риском, а не плечом.
        """
        balance_info = await self.get_account_balance()
        balance = balance_info["available_balance"]
        risk_percent = getattr(self.settings, "max_risk_per_trade", 1.0)
        risk_amount = balance * (risk_percent / 100.0)

        if price <= 0:
            return 0.0

        qty = risk_amount / price
        return round(qty, 6)

    def calculate_position_size_sync(
        self,
        symbol: str,
        balance: float,
        risk_percent: float,
        stop_distance_pct: float,
        leverage: int,
        atr: float,
        current_price: float,
    ) -> float:
        """
        Синхронный расчёт с учётом стоп-лосса.
        ИСПРАВЛЕНО: корректная формула.
        qty = risk_amount / (current_price * stop_distance_pct / 100)
        """
        if stop_distance_pct <= 0 or current_price <= 0 or leverage <= 0:
            return 0.0
        risk_amount = balance * (risk_percent / 100.0)
        risk_per_unit = current_price * (stop_distance_pct / 100.0)
        if risk_per_unit <= 0:
            return 0.0
        qty = risk_amount / risk_per_unit
        return round(qty, 6)

    def register_position(self, position: Position):
        """Зарегистрировать новую позицию для отслеживания."""
        self._open_positions[position.symbol] = position

    def remove_position(self, symbol: str):
        """Удалить позицию из отслеживания."""
        self._open_positions.pop(symbol, None)

    def get_tracked_positions(self) -> Dict[str, Position]:
        """Получить все отслеживаемые позиции."""
        return self._open_positions.copy()

    async def manage_position_risk(self, position_data: Dict[str, Any]) -> Optional[str]:
        """
        Управление рисками открытой позиции.
        Возвращает причину закрытия или None.
        """
        symbol = position_data.get("symbol", "")
        if symbol not in self._open_positions:
            return None

        pos = self._open_positions[symbol]
        current_price = float(position_data.get("markPrice", 0))

        if current_price <= 0:
            return None

        # Обновляем max/min price seen для трейлинг-стопа
        if pos.side == "LONG":
            pos.max_price_seen = max(pos.max_price_seen, current_price)
        else:
            pos.min_price_seen = min(pos.min_price_seen, current_price)

        # Проверка стоп-лосса
        if pos.stop_loss > 0:
            if pos.side == "LONG" and current_price <= pos.stop_loss:
                return "STOP_LOSS"
            elif pos.side == "SHORT" and current_price >= pos.stop_loss:
                return "STOP_LOSS"

        # Проверка тейк-профита
        if pos.take_profit > 0:
            if pos.side == "LONG" and current_price >= pos.take_profit:
                return "TAKE_PROFIT"
            elif pos.side == "SHORT" and current_price <= pos.take_profit:
                return "TAKE_PROFIT"

        # Трейлинг-стоп
        if self.settings.get("trailing_stop_enabled", False):
            activation_pct = self.settings.get("trailing_activation", 1.5)
            callback_pct = self.settings.get("trailing_callback", 0.5)

            if pos.side == "LONG":
                profit_pct = (current_price - pos.entry_price) / pos.entry_price * 100
                if profit_pct >= activation_pct:
                    callback_price = pos.max_price_seen * (1 - callback_pct / 100)
                    if current_price <= callback_price:
                        return f"TRAILING_STOP (max={pos.max_price_seen:.2f})"
            else:
                profit_pct = (pos.entry_price - current_price) / pos.entry_price * 100
                if profit_pct >= activation_pct:
                    callback_price = pos.min_price_seen * (1 + callback_pct / 100)
                    if current_price >= callback_price:
                        return f"TRAILING_STOP (min={pos.min_price_seen:.2f})"

        return None
