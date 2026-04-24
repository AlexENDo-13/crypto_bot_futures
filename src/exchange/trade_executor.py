"""
CryptoBot v7.1 - Trade Executor
"""
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from exchange.api_client import BingXAPIClient
from risk.risk_manager import RiskManager, Position, RiskLimits


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class Order:
    symbol: str
    side: str
    position_side: str
    order_type: str
    quantity: float
    price: float = 0.0
    stop_price: float = 0.0
    leverage: int = 1
    status: OrderStatus = OrderStatus.PENDING
    order_id: str = ""
    fill_price: float = 0.0
    fill_time: str = ""
    pnl: float = 0.0
    metadata: Dict = field(default_factory=dict)


class TradeExecutor:
    """Executes trades with full live/paper support."""

    def __init__(self, api_client: BingXAPIClient = None,
                 risk_manager: RiskManager = None,
                 paper_trading: bool = True,
                 balance: float = 10000.0,
                 notifier=None):
        self.api = api_client
        self.risk = risk_manager or RiskManager()
        self.paper = paper_trading
        self._balance = balance
        self.notifier = notifier
        self.logger = logging.getLogger("CryptoBot.Executor")

        self.orders: List[Order] = []
        self.positions: Dict[str, Position] = {}
        self.order_counter = 0

        self.logger.info(
            "TradeExecutor v7.1 | paper=%s balance=$%.2f",
            paper_trading, balance
        )

    @property
    def balance(self) -> float:
        """Get current balance (synced from API in live mode)."""
        if not self.paper and self.api:
            try:
                bal = self.api.get_balance()
                if bal.get("code") == 0:
                    data = bal.get("data", {})
                    avail = float(data.get("available", 0))
                    if avail > 0:
                        self._balance = avail
            except Exception:
                pass
        return self._balance

    @balance.setter
    def balance(self, value: float):
        self._balance = value

    def get_balance(self) -> Dict:
        """Return balance info dict for UI."""
        return {"balance": self.balance, "available": self.balance}

    def execute_signal(self, signal: Any, price: float = 0) -> Optional[Order]:
        """Execute a trading signal."""
        symbol = getattr(signal, "symbol", "")
        side = "BUY" if getattr(signal, "type", None) and signal.type.value == "buy" else "SELL"
        position_side = "LONG" if side == "BUY" else "SHORT"

        entry_price = price or getattr(signal, "price", 0)
        if entry_price <= 0:
            self.logger.warning("Invalid entry price for %s", symbol)
            return None

        # Get real balance
        current_balance = self.balance

        can_trade, reason = self.risk.can_open_position(
            symbol, position_side, 1.0, entry_price,
            leverage=self.risk.limits.max_leverage,
            balance=current_balance
        )

        if not can_trade:
            self.logger.info("Trade rejected: %s - %s", symbol, reason)
            return None

        size = self.risk.calculate_position_size(
            entry_price,
            entry_price * (1 - self.risk.limits.default_sl_percent / 100),
            current_balance
        )

        # Validate size
        if size <= 0 or size * entry_price < 5.0:
            self.logger.warning(
                "Trade rejected: %s - calculated size too small (%.6f)",
                symbol, size
            )
            return None

        order = Order(
            symbol=symbol,
            side=side,
            position_side=position_side,
            order_type="MARKET",
            quantity=round(size, 6),
            leverage=self.risk.limits.max_leverage,
            metadata={
                "confidence": getattr(signal, "confidence", 0),
                "strategy": getattr(signal, "strategy", "unknown")
            }
        )

        if self.paper:
            return self._execute_paper(order, entry_price)
        else:
            return self._execute_live(order)

    def _execute_paper(self, order: Order, price: float) -> Order:
        self.order_counter += 1
        order.order_id = "PAPER_%d" % self.order_counter
        order.status = OrderStatus.FILLED
        order.fill_price = price
        order.fill_time = datetime.now().isoformat()

        margin = (order.quantity * price) / order.leverage

        position = Position(
            symbol=order.symbol,
            side=order.position_side,
            size=order.quantity,
            entry_price=price,
            leverage=order.leverage,
            stop_loss=price * (1 - self.risk.limits.default_sl_percent / 100)
            if order.position_side == "LONG"
            else price * (1 + self.risk.limits.default_sl_percent / 100),
            take_profit=price * (1 + self.risk.limits.default_tp_percent / 100)
            if order.position_side == "LONG"
            else price * (1 - self.risk.limits.default_tp_percent / 100),
            margin=margin
        )

        self.positions[order.symbol] = position
        self.risk.add_position(position)
        self.orders.append(order)

        msg = "Paper trade: %s %s qty=%.4f @ $%.2f" % (
            order.symbol, order.position_side, order.quantity, price
        )
        self.logger.info(msg)

        if self.notifier:
            self.notifier.send_trade_open(
                order.symbol, order.position_side, price, order.quantity
            )

        return order

    def _execute_live(self, order: Order) -> Order:
        if not self.api:
            order.status = OrderStatus.REJECTED
            self.logger.error("No API client for live trading")
            return order

        self.logger.info(
            "LIVE ORDER: %s %s qty=%.4f",
            order.symbol, order.side, order.quantity
        )

        result = self.api.place_order(
            symbol=order.symbol,
            side=order.side,
            position_side=order.position_side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            stop_price=order.stop_price,
            leverage=order.leverage
        )

        if result.get("code") == 0:
            data = result.get("data", {})
            order.order_id = str(data.get("orderId", data.get("order_id", "")))
            order.status = OrderStatus.FILLED
            order.fill_price = float(data.get("avgPrice", data.get("price", 0)))
            order.fill_time = datetime.now().isoformat()

            margin = (order.quantity * order.fill_price) / order.leverage
            position = Position(
                symbol=order.symbol,
                side=order.position_side,
                size=order.quantity,
                entry_price=order.fill_price,
                leverage=order.leverage,
                stop_loss=order.fill_price * (
                    1 - self.risk.limits.default_sl_percent / 100
                ) if order.position_side == "LONG" else order.fill_price * (
                    1 + self.risk.limits.default_sl_percent / 100
                ),
                take_profit=order.fill_price * (
                    1 + self.risk.limits.default_tp_percent / 100
                ) if order.position_side == "LONG" else order.fill_price * (
                    1 - self.risk.limits.default_tp_percent / 100
                ),
                margin=margin
            )
            self.positions[order.symbol] = position
            self.risk.add_position(position)

            self.logger.info("LIVE filled: %s @ $%.2f", order.order_id, order.fill_price)

            if self.notifier:
                self.notifier.send_trade_open(
                    order.symbol, order.position_side, order.fill_price, order.quantity
                )
        else:
            order.status = OrderStatus.REJECTED
            err = result.get("msg", result.get("message", "unknown"))
            self.logger.error("LIVE rejected: %s", err)

        self.orders.append(order)
        return order

    def close_position(self, symbol: str, price: float = 0) -> Optional[Order]:
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]

        order = Order(
            symbol=symbol,
            side="SELL" if position.side == "LONG" else "BUY",
            position_side=position.side,
            order_type="MARKET",
            quantity=position.size
        )

        if self.paper:
            close_price = price or position.entry_price
            pnl = position.calculate_pnl(close_price)
            order.status = OrderStatus.FILLED
            order.fill_price = close_price
            order.pnl = pnl
            order.fill_time = datetime.now().isoformat()

            self.risk.remove_position(symbol, close_price)
            del self.positions[symbol]

            self.logger.info("Paper close: %s P&L=$%+.2f", symbol, pnl)
            if self.notifier:
                self.notifier.send_trade_close(
                    symbol, position.side, position.entry_price, close_price, pnl
                )
        else:
            if self.api:
                result = self.api.close_position(symbol, position.side)
                if result.get("code") == 0:
                    order.status = OrderStatus.FILLED
                    data = result.get("data", {})
                    order.fill_price = float(data.get("avgPrice", data.get("price", 0)))
                    order.fill_time = datetime.now().isoformat()

                    pnl = position.calculate_pnl(order.fill_price)
                    order.pnl = pnl
                    self.risk.remove_position(symbol, order.fill_price)
                    del self.positions[symbol]

                    self.logger.info("LIVE close: %s P&L=$%+.2f", symbol, pnl)
                    if self.notifier:
                        self.notifier.send_trade_close(
                            symbol, position.side, position.entry_price,
                            order.fill_price, pnl
                        )
                else:
                    order.status = OrderStatus.REJECTED
                    self.logger.error("Close failed: %s", result.get("msg", "unknown"))

        self.orders.append(order)
        return order

    def update_positions(self, prices: Dict[str, float]):
        self.risk.update_positions(prices)

        # Trailing stop logic
        for symbol, position in list(self.positions.items()):
            if symbol in prices:
                price = prices[symbol]
                if position.side == "LONG":
                    new_sl = price * (1 - self.risk.limits.default_sl_percent / 100)
                    if new_sl > position.stop_loss:
                        position.stop_loss = new_sl
                else:
                    new_sl = price * (1 + self.risk.limits.default_sl_percent / 100)
                    if new_sl < position.stop_loss:
                        position.stop_loss = new_sl

        sl_hits = self.risk.check_stop_losses(prices)
        for symbol in sl_hits:
            self.logger.info("Stop loss: %s", symbol)
            self.close_position(symbol, prices.get(symbol, 0))

        tp_hits = self.risk.check_take_profits(prices)
        for symbol in tp_hits:
            self.logger.info("Take profit: %s", symbol)
            self.close_position(symbol, prices.get(symbol, 0))

    def get_open_positions(self) -> List[Dict]:
        return [
            {
                "symbol": p.symbol,
                "side": p.side,
                "size": p.size,
                "entry": p.entry_price,
                "pnl": p.pnl,
                "pnl_percent": p.pnl_percent,
                "margin": p.margin
            }
            for p in self.positions.values()
        ]

    def get_trade_history(self) -> List[Dict]:
        return [
            {
                "symbol": o.symbol,
                "side": o.position_side,
                "type": o.order_type,
                "qty": o.quantity,
                "price": o.fill_price,
                "pnl": o.pnl,
                "status": o.status.value,
                "time": o.fill_time
            }
            for o in self.orders
        ]
