from typing import Optional, Dict, Any, Tuple

from src.utils.api_client import AsyncBingXClient
from src.config.settings import Settings

class RiskManager:
    MIN_NOTIONAL = 5.0

    def __init__(self, client: AsyncBingXClient, settings: Settings):
        self.client = client
        self.settings = settings
        self._cached_balance: Optional[float] = None

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
        balance_info = await self.get_account_balance()
        balance = balance_info["available_balance"]
        risk_percent = getattr(self.settings, "max_risk_per_trade", 1.0)
        leverage = getattr(self.settings, "max_leverage", 3)
        risk_amount = balance * (risk_percent / 100.0)
        # Учитываем плечо: qty = (risk_amount * leverage) / price
        qty = (risk_amount * leverage) / price if price > 0 else 0.0
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
        if stop_distance_pct <= 0 or current_price <= 0 or leverage <= 0:
            return 0.0
        risk_amount = balance * (risk_percent / 100.0)
        stop_loss_price = current_price * (1 - stop_distance_pct / 100.0)
        risk_per_unit = abs(current_price - stop_loss_price)
        if risk_per_unit <= 0:
            return 0.0
        qty = risk_amount / risk_per_unit
        return round(qty * leverage, 6)

    async def manage_position_risk(self, position: Dict[str, Any]) -> None:
        """Заглушка для управления рисками позиции."""
        pass
