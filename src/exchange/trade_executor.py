"""
CryptoBot v6.0 - Trade Executor
Order execution with paper/live trading modes.
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
    """Represents a trade order."""
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
    """Executes trades with risk management."""

    def __init__(self, api_client: BingXAPIClient = None,
                 risk_manager: RiskManager = None,
                 paper_trading: bool = True,
                 balance: float = 10000.0):
        self.api = api_client
        self.risk = risk_manager or RiskManager()
        self.paper = paper_trading
        self.balance = balance
        self.logger = logging.getLogger("CryptoBot.Executor")

        self.orders: List[Order] = []
        self.positions: Dict[str, Position] = {}
        self.order_counter = 0

        self.logger.info(f"TradeExecutor v6.0 | paper={paper_trading} balance=${balance:,.2f}")

    def execute_signal(self, signal: Any, price: float = 0) -> Optional[Order]:
        """Execute a trading signal."""
        symbol = getattr(signal, "symbol", "")
        side = "BUY" if getattr(signal, "type", None) and signal.type.value == "buy" else "SELL"
        position_side = "LONG" if side == "BUY" else "SHORT"

        # Calculate position size
        entry_price = price or getattr(signal, "price", 0)
        if entry_price <= 0:
            self.logger.warning(f"Invalid entry price for {symbol}")
            return None

        # Risk check
        can_trade, reason = self.risk.can_open_position(
            symbol, position_side, 1.0, entry_price, 
            leverage=self.risk.limits.max_leverage, balance=self.balance
        )

        if not can_trade:
            self.logger.info(f"Trade rejected for {symbol}: {reason}")
            return None

        # Calculate size
        size = self.risk.calculate_position_size(
            entry_price, 
            entry_price * (1 - self.risk.limits.default_sl_percent / 100),
            self.balance
        )

        # Create order
        order = Order(
            symbol=symbol,
            side=side,
            position_side=position_side,
            order_type="MARKET",
            quantity=size,
            leverage=self.risk.limits.max_leverage,
            metadata={"confidence": getattr(signal, "confidence", 0), 
                     "strategy": getattr(signal, "strategy", "unknown")}
        )

        if self.paper:
            return self._execute_paper(order, entry_price)
        else:
            return self._execute_live(order)

    def _execute_paper(self, order: Order, price: float) -> Order:
        """Execute paper trade."""
        self.order_counter += 1
        order.order_id = f"PAPER_{self.order_counter}"
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
            stop_loss=price * (1 - self.risk.limits.default_sl_percent / 100) if order.position_side == "LONG" 
                      else price * (1 + self.risk.limits.default_sl_percent / 100),
            take_profit=price * (1 + self.risk.limits.default_tp_percent / 100) if order.position_side == "LONG"
                        else price * (1 - self.risk.limits.default_tp_percent / 100),
            margin=margin
        )

        self.positions[order.symbol] = position
        self.risk.add_position(position)
        self.orders.append(order)

        self.logger.info(f"Paper trade executed: {order.symbol} {order.position_side} "
                        f"qty={order.quantity:.4f} @ ${price:.2f}")

        return order

    def _execute_live(self, order: Order) -> Order:
        """Execute live trade via API."""
        if not self.api:
            order.status = OrderStatus.REJECTED
            return order

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
            order.order_id = str(data.get("orderId", ""))
            order.status = OrderStatus.FILLED
            order.fill_price = float(data.get("avgPrice", 0))
            order.fill_time = datetime.now().isoformat()
            self.logger.info(f"Live order placed: {order.order_id}")
        else:
            order.status = OrderStatus.REJECTED
            self.logger.error(f"Order rejected: {result.get('msg', 'unknown')}")

        self.orders.append(order)
        return order

    def close_position(self, symbol: str, price: float = 0) -> Optional[Order]:
        """Close an open position."""
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

            self.logger.info(f"Paper position closed: {symbol} P&L=${pnl:+.2f}")
        else:
            if self.api:
                result = self.api.close_position(symbol, position.side)
                if result.get("code") == 0:
                    order.status = OrderStatus.FILLED

        self.orders.append(order)
        return order

    def update_positions(self, prices: Dict[str, float]):
        """Update positions with current prices."""
        self.risk.update_positions(prices)

        # Check SL/TP
        sl_hits = self.risk.check_stop_losses(prices)
        for symbol in sl_hits:
            self.logger.info(f"Stop loss hit: {symbol}")
            self.close_position(symbol, prices.get(symbol, 0))

        tp_hits = self.risk.check_take_profits(prices)
        for symbol in tp_hits:
            self.logger.info(f"Take profit hit: {symbol}")
            self.close_position(symbol, prices.get(symbol, 0))

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions."""
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
        """Get trade history."""
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
