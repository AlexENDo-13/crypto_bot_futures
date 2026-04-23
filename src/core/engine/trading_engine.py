import asyncio
import logging
from src.utils.api_client import AsyncBingXClient
from src.core.risk.risk_manager import RiskManager
# Другие импорты вашего движка (стратегии, индикаторы и т.д.)

class TradingEngine:
    def __init__(self, settings):
        self.settings = settings
        self.logger = logging.getLogger("TradingEngine")
        # Создаём клиент согласно текущему demo_mode
        self.client = AsyncBingXClient(
            api_key=settings.get("api_key"),
            api_secret=settings.get("api_secret"),
            demo_mode=settings.get("demo_mode", True)
        )
        self.risk_manager = RiskManager(self.client, settings)
        self.is_running = False

    async def start(self):
        self.is_running = True
        self.logger.info("Торговый движок запущен")
        while self.is_running:
            try:
                # Получаем реальный баланс
                balance = await self.risk_manager.get_account_balance()
                self.logger.info(f"Баланс: {balance['available_balance']} USDT")
                # Здесь ваша логика поиска пар и открытия сделок
                await asyncio.sleep(10)
            except Exception as e:
                self.logger.error(f"Ошибка в главном цикле: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        self.is_running = False
        await self.client.close()
        self.logger.info("Торговый движок остановлен")

    # 👇 НОВЫЙ МЕТОД
    def apply_new_settings(self, new_settings: dict):
        """Принимает настройки от UI и применяет их на лету."""
        self.settings.update(new_settings)

        # Переключение demo_mode
        if 'demo_mode' in new_settings:
            self.client.set_demo_mode(new_settings['demo_mode'])
            self.logger.info(f"Demo mode переключён на: {new_settings['demo_mode']}")

        # Можно обновить другие параметры (max_positions, risk и т.д.)
        if 'max_positions' in new_settings:
            self.risk_manager.max_positions = new_settings['max_positions']
        if 'risk_per_trade' in new_settings:
            self.risk_manager.risk_per_trade = new_settings['risk_per_trade']

        self.logger.info("Новые настройки применены")
