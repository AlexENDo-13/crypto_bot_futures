import logging
from typing import Dict

class RiskManager:
    def __init__(self, client, settings):
        self.client = client
        self.settings = settings
        self.logger = logging.getLogger("RiskManager")
        self._cached_balance = 0.0
        self.max_positions = settings.get("max_positions", 3)
        self.risk_per_trade = settings.get("risk_per_trade", 1.0)

    async def get_account_balance(self) -> Dict[str, float]:
        try:
            account = await self.client.get_account_info()
            balance = float(account.get("data", {}).get("availableBalance", 0))
            self._cached_balance = balance
            return {"total_equity": balance, "available_balance": balance}
        except Exception as e:
            self.logger.error(f"КРИТИЧЕСКАЯ ОШИБКА ПОЛУЧЕНИЯ БАЛАНСА: {e}")
            # Больше НЕ подменяем на virtual_balance!
            return {"total_equity": 0.0, "available_balance": 0.0}

    def check_risk(self, symbol: str, quantity: float, price: float) -> bool:
        """Пример проверки – не превышен ли риск на сделку."""
        available = self._cached_balance
        if available <= 0:
            return False
        exposure = quantity * price
        return exposure <= available * self.risk_per_trade / 100

    def can_open_position(self) -> bool:
        # Заглушка – в реальном коде нужно объект positions
        return True
