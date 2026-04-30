"""Exchange wrapper."""
import logging
from typing import Dict, Any, Optional, List
from src.exchange.api_client import BingXAPIClient

logger = logging.getLogger(__name__)


class Exchange:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        base_url = "https://open-api-vst.bingx.com" if testnet else "https://open-api.bingx.com"
        self.client = BingXAPIClient(api_key, api_secret, base_url)
        logger.info("Exchange initialized")

    async def get_account_balance(self) -> Dict[str, Any]:
        return await self.client.get_account_balance()

    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self.client.get_positions(symbol)

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self.client.get_open_orders(symbol)

    async def place_order(self, symbol: str, side: str, order_type: str, quantity: float,
                          price: Optional[float] = None, stop_price: Optional[float] = None,
                          leverage: int = 1) -> Dict[str, Any]:
        return await self.client.place_order(symbol, side, order_type, quantity, price, stop_price, leverage)

    async def close_position(self, symbol: str, position_side: str) -> Dict[str, Any]:
        return await self.client.close_position(symbol, position_side)

    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        return await self.client.cancel_order(symbol, order_id)

    async def set_leverage(self, symbol: str, leverage: int, side: str = "BOTH") -> Dict[str, Any]:
        return await self.client.set_leverage(symbol, leverage, side)

    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[list]:
        return await self.client.get_klines(symbol, interval, limit)

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        return await self.client.get_ticker(symbol)

    async def get_symbol_info(self) -> Dict[str, Any]:
        return await self.client.get_symbol_info()

    async def get_symbol_specs(self, symbol: str) -> Dict[str, Any]:
        return await self.client.get_symbol_specs(symbol)

    async def get_health(self) -> Dict[str, Any]:
        return await self.client.get_health()

    async def close(self):
        await self.client.close()
