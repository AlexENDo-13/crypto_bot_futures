"""Exit management: TP, SL, trailing stop."""
from typing import List
from src.core.models import Position
from src.core.bot_logger import BotLogger


class ExitManager:
    """Управление выходами из позиций."""

    def __init__(self, api_client, logger: BotLogger, settings):
        self.api_client = api_client
        self.logger = logger
        self.settings = settings

    async def check_exits(self, positions: List[Position]):
        for pos in positions[:]:
            try:
                ticker = await self.api_client.get_ticker(pos.symbol)
                current_price = float(ticker.get("lastPrice", 0))
                pnl_pct = pos.calculate_pnl_percent(current_price)

                # Stop Loss
                if pos.side == "LONG" and current_price <= pos.stop_loss:
                    await self._close(pos, "STOP_LOSS")
                elif pos.side == "SHORT" and current_price >= pos.stop_loss:
                    await self._close(pos, "STOP_LOSS")

                # Take Profit
                elif pos.side == "LONG" and current_price >= pos.take_profit:
                    await self._close(pos, "TAKE_PROFIT")
                elif pos.side == "SHORT" and current_price <= pos.take_profit:
                    await self._close(pos, "TAKE_PROFIT")

            except Exception as e:
                self.logger.error(f"Exit check error for {pos.symbol}: {e}")

    async def _close(self, pos: Position, reason: str):
        self.logger.info(f"Closing {pos.symbol} due to {reason}")
        try:
            side = "SELL" if pos.side == "LONG" else "BUY"
            await self.api_client.place_order(
                symbol=pos.symbol,
                side=side,
                order_type="MARKET",
                quantity=pos.quantity
            )
            pos.status = "CLOSED"
        except Exception as e:
            self.logger.error(f"Failed to close position: {e}")
