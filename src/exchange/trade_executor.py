"""
CryptoBot v9.0 - Async Trade Executor
Features: Async execution, partial TP, breakeven SL, 
          funding rate check, max hold time, neural trailing
"""
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio

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
    """Async trade executor with neural trailing."""

    def __init__(self, api_client: BingXAPIClient = None,
                 risk_manager: RiskManager = None,
                 paper_trading: bool = True,
                 balance: float = 10000.0,
                 notifier=None):
        self.api = api_client
        self.risk = risk_manager or RiskManager()
        self.paper = paper_trading
        self._balance = balance
        self._initial_balance = balance
        self.notifier = notifier
        self.logger = logging.getLogger("CryptoBot.Executor")
        self._lock = asyncio.Lock()

        self.orders: List[Order] = []
        self.positions: Dict[str, Position] = {}
        self.order_counter = 0
        self._symbol_info_cache: Dict[str, Dict] = {}
        self._symbol_info_ttl = 300
        self._symbol_info_time: float = 0

        self.partial_tp_enabled = True
        self.partial_tp1_pct = 0.50
        self.partial_tp2_pct = 0.30
        self.breakeven_after_tp1 = True
        self.max_hold_time = timedelta(hours=4)
        self.funding_check_enabled = True
        self.max_funding_rate = 0.001
        self.neural_trailing_pct = 0.5

        self.logger.info("TradeExecutor v9.0 | paper=%s balance=$%.2f", paper_trading, balance)

    @property
    def balance(self) -> float:
        if not self.paper and self.api:
            try:
                bal = self.api.get_balance()
                if isinstance(bal, dict) and bal.get("code") == 0:
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
        return {"balance": self.balance, "available": self.balance}

    def _get_symbol_info(self, symbol: str) -> Dict:
        now = time.time()
        if now - self._symbol_info_time < self._symbol_info_ttl and self._symbol_info_cache:
            cached = self._symbol_info_cache.get(symbol)
            if cached:
                return cached

        if not self.api:
            return {"price_precision": 2, "qty_precision": 4, "min_qty": 0.001, "volume_24h": 0}

        try:
            symbols = self.api.get_symbols()
            self._symbol_info_cache = {}
            for s in symbols:
                sym = s.get("symbol", "")
                if sym:
                    self._symbol_info_cache[sym] = {
                        "price_precision": int(s.get("pricePrecision", 2)),
                        "qty_precision": int(s.get("quantityPrecision", 4)),
                        "min_qty": float(s.get("minQty", 0.001)),
                        "volume_24h": float(s.get("volume", 0)),
                        "tick_size": float(s.get("tickSize", 0.01)),
                    }
            self._symbol_info_time = now
            return self._symbol_info_cache.get(symbol, {"price_precision": 2, "qty_precision": 4, "min_qty": 0.001, "volume_24h": 0})
        except Exception as e:
            self.logger.debug("Symbol info error: %s", e)
            return {"price_precision": 2, "qty_precision": 4, "min_qty": 0.001, "volume_24h": 0}

    async def _check_funding_rate(self, symbol: str) -> bool:
        if not self.funding_check_enabled or not self.api:
            return True
        try:
            resp = await self.api.get_funding_rate(symbol)
            if isinstance(resp, dict) and resp.get("code") == 0:
                data = resp.get("data", {})
                rate = float(data.get("lastFundingRate", 0))
                if abs(rate) > self.max_funding_rate:
                    self.logger.info("Funding rate too high for %s: %.4f%%", symbol, rate * 100)
                    return False
        except Exception as e:
            self.logger.debug("Funding check error: %s", e)
        return True

    async def execute_signal(self, signal: Any, price: float = 0) -> Optional[Order]:
        async with self._lock:
            symbol = getattr(signal, "symbol", "")
            side = "BUY" if getattr(signal, "type", None) and signal.type.value == "buy" else "SELL"
            position_side = "LONG" if side == "BUY" else "SHORT"

            entry_price = price or getattr(signal, "price", 0)
            if entry_price <= 0:
                self.logger.warning("Invalid entry price for %s", symbol)
                return None

            if symbol in self.positions:
                self.logger.info("Trade rejected: %s - already in position", symbol)
                return None

            if not await self._check_funding_rate(symbol):
                self.logger.info("Trade rejected: %s - high funding", symbol)
                return None

            current_balance = self.balance
            can_trade, reason = self.risk.can_open_position(
                symbol, position_side, 1.0, entry_price,
                leverage=self.risk.limits.max_leverage,
                balance=current_balance
            )
            if not can_trade:
                self.logger.info("Trade rejected: %s - %s", symbol, reason)
                return None

            sym_info = self._get_symbol_info(symbol)
            volume_24h = sym_info.get("volume_24h", 0)
            min_qty = sym_info.get("min_qty", 0.001)
            qty_precision = sym_info.get("qty_precision", 4)

            if volume_24h < 50000 and not self.paper:
                self.logger.info("Trade rejected: %s - low 24h volume %.2f", symbol, volume_24h)
                return None

            sl_price = entry_price * (1 - self.risk.limits.default_sl_percent / 100) if position_side == "LONG" else entry_price * (1 + self.risk.limits.default_sl_percent / 100)
            size = self.risk.calculate_position_size(entry_price, sl_price, current_balance)
            size = round(size, qty_precision)
            position_value = size * entry_price

            if size <= 0 or size < min_qty or position_value < 5.0:
                self.logger.warning("Trade rejected: %s - size too small (%.6f, min %.6f)", symbol, size, min_qty)
                return None

            order = Order(
                symbol=symbol, side=side, position_side=position_side,
                order_type="MARKET", quantity=size,
                leverage=self.risk.limits.max_leverage,
                metadata={
                    "confidence": getattr(signal, "confidence", 0),
                    "strategy": getattr(signal, "strategy", "unknown"),
                    "volume_24h": volume_24h,
                    "regime": getattr(signal, "metadata", {}).get("regime", "unknown") if hasattr(signal, "metadata") and signal.metadata else "unknown"
                }
            )

            if self.paper:
                return await self._execute_paper(order, entry_price)
            else:
                return await self._execute_live(order)

    async def _execute_paper(self, order: Order, price: float) -> Order:
        self.order_counter += 1
        order.order_id = "PAPER_%d" % self.order_counter
        order.status = OrderStatus.FILLED
        order.fill_price = price
        order.fill_time = datetime.now().isoformat()

        margin = (order.quantity * price) / order.leverage

        tp1 = price * (1 + self.risk.limits.default_tp_percent / 100) if order.position_side == "LONG" else price * (1 - self.risk.limits.default_tp_percent / 100)
        tp2 = price * (1 + self.risk.limits.default_tp_percent * 1.5 / 100) if order.position_side == "LONG" else price * (1 - self.risk.limits.default_tp_percent * 1.5 / 100)

        position = Position(
            symbol=order.symbol, side=order.position_side, size=order.quantity,
            entry_price=price, leverage=order.leverage,
            stop_loss=price * (1 - self.risk.limits.default_sl_percent / 100) if order.position_side == "LONG" else price * (1 + self.risk.limits.default_sl_percent / 100),
            take_profit=tp1, margin=margin
        )
        position.metadata = {"tp2": tp2, "partial_closed": False, "breakeven_set": False, "open_time": datetime.now()}

        self.positions[order.symbol] = position
        self.risk.add_position(position)
        self.orders.append(order)
        self._balance -= margin

        self.logger.info("Paper trade: %s %s qty=%.4f @ $%.2f margin=$%.2f", 
                         order.symbol, order.position_side, order.quantity, price, margin)
        if self.notifier:
            self.notifier.send_trade_open(order.symbol, order.position_side, price, order.quantity)
        return order

    async def _execute_live(self, order: Order) -> Order:
        if not self.api:
            order.status = OrderStatus.REJECTED
            self.logger.error("No API client for live trading")
            return order

        self.logger.info("LIVE ORDER: %s %s qty=%.4f", order.symbol, order.side, order.quantity)

        try:
            await self.api.set_leverage(order.symbol, order.leverage, order.position_side)
        except Exception as e:
            self.logger.debug("Leverage set skipped: %s", e)

        result = await self.api.place_order(
            symbol=order.symbol, side=order.side, position_side=order.position_side,
            order_type=order.order_type, quantity=order.quantity,
            price=order.price, stop_price=order.stop_price, leverage=order.leverage
        )

        if isinstance(result, dict) and result.get("code") == 0:
            data = result.get("data", {})
            order.order_id = str(data.get("orderId", data.get("order_id", "")))
            order.status = OrderStatus.FILLED
            order.fill_price = float(data.get("avgPrice", data.get("price", 0)))
            order.fill_time = datetime.now().isoformat()

            margin = (order.quantity * order.fill_price) / order.leverage
            tp1 = order.fill_price * (1 + self.risk.limits.default_tp_percent / 100) if order.position_side == "LONG" else order.fill_price * (1 - self.risk.limits.default_tp_percent / 100)
            tp2 = order.fill_price * (1 + self.risk.limits.default_tp_percent * 1.5 / 100) if order.position_side == "LONG" else order.fill_price * (1 - self.risk.limits.default_tp_percent * 1.5 / 100)

            position = Position(
                symbol=order.symbol, side=order.position_side, size=order.quantity,
                entry_price=order.fill_price, leverage=order.leverage,
                stop_loss=order.fill_price * (1 - self.risk.limits.default_sl_percent / 100) if order.position_side == "LONG" else order.fill_price * (1 + self.risk.limits.default_sl_percent / 100),
                take_profit=tp1, margin=margin
            )
            position.metadata = {"tp2": tp2, "partial_closed": False, "breakeven_set": False, "open_time": datetime.now()}

            self.positions[order.symbol] = position
            self.risk.add_position(position)

            self.logger.info("LIVE filled: %s @ $%.2f", order.order_id, order.fill_price)
            if self.notifier:
                self.notifier.send_trade_open(order.symbol, order.position_side, order.fill_price, order.quantity)
        else:
            order.status = OrderStatus.REJECTED
            err = result.get("msg", result.get("message", "unknown")) if isinstance(result, dict) else str(result)
            self.logger.error("LIVE rejected: %s", err)

        self.orders.append(order)
        return order

    async def close_position(self, symbol: str, price: float = 0, close_pct: float = 1.0) -> Optional[Order]:
        if symbol not in self.positions:
            return None

        async with self._lock:
            position = self.positions[symbol]
            close_qty = round(position.size * close_pct, 6)
            if close_qty <= 0:
                return None

            order = Order(
                symbol=symbol,
                side="SELL" if position.side == "LONG" else "BUY",
                position_side=position.side,
                order_type="MARKET",
                quantity=close_qty
            )

            if self.paper:
                close_price = price or position.entry_price
                pnl = position.calculate_pnl(close_price) * close_pct
                order.status = OrderStatus.FILLED
                order.fill_price = close_price
                order.pnl = pnl
                order.fill_time = datetime.now().isoformat()

                if close_pct >= 0.99:
                    self.risk.remove_position(symbol, close_price)
                    del self.positions[symbol]
                else:
                    position.size -= close_qty
                    position.margin = (position.size * position.entry_price) / position.leverage

                self._balance += (position.margin * close_pct) + pnl
                self.logger.info("Paper close: %s %.1f%% P&L=$%+.2f balance=$%.2f", 
                                 symbol, close_pct*100, pnl, self._balance)
                if self.notifier:
                    self.notifier.send_trade_close(symbol, position.side, position.entry_price, close_price, pnl)
            else:
                if self.api:
                    result = await self.api.close_position(symbol, position.side, close_qty)
                    if isinstance(result, dict) and result.get("code") == 0:
                        order.status = OrderStatus.FILLED
                        data = result.get("data", {})
                        order.fill_price = float(data.get("avgPrice", data.get("price", 0)))
                        order.fill_time = datetime.now().isoformat()
                        pnl = position.calculate_pnl(order.fill_price) * close_pct
                        order.pnl = pnl

                        if close_pct >= 0.99:
                            self.risk.remove_position(symbol, order.fill_price)
                            del self.positions[symbol]
                        else:
                            position.size -= close_qty
                            position.margin = (position.size * position.entry_price) / position.leverage

                        self.logger.info("LIVE close: %s %.1f%% P&L=$%+.2f", 
                                         symbol, close_pct*100, pnl)
                        if self.notifier:
                            self.notifier.send_trade_close(symbol, position.side, position.entry_price, order.fill_price, pnl)
                    else:
                        order.status = OrderStatus.REJECTED
                        err = result.get("msg", "unknown") if isinstance(result, dict) else str(result)
                        self.logger.error("Close failed: %s", err)

            self.orders.append(order)
            return order

    async def update_positions(self, prices: Dict[str, float]):
        self.risk.update_positions(prices)
        now = datetime.now()

        for symbol, position in list(self.positions.items()):
            if symbol not in prices:
                continue
            price = prices[symbol]

            # Neural trailing stop
            neural_sl = price * (1 - self.neural_trailing_pct / 100) if position.side == "LONG" else price * (1 + self.neural_trailing_pct / 100)
            if (position.side == "LONG" and neural_sl > position.stop_loss) or \
               (position.side == "SHORT" and neural_sl < position.stop_loss):
                position.stop_loss = neural_sl

            # Partial TP logic
            meta = getattr(position, "metadata", {}) or {}
            tp2 = meta.get("tp2", 0)
            partial_closed = meta.get("partial_closed", False)
            breakeven_set = meta.get("breakeven_set", False)
            open_time = meta.get("open_time", now)

            if self.partial_tp_enabled and not partial_closed:
                if position.side == "LONG" and price >= position.take_profit:
                    self.logger.info("TP1 hit: %s - closing %.0f%%", symbol, self.partial_tp1_pct * 100)
                    await self.close_position(symbol, price, self.partial_tp1_pct)
                    position.metadata["partial_closed"] = True
                    if self.breakeven_after_tp1 and not breakeven_set:
                        position.stop_loss = position.entry_price
                        position.metadata["breakeven_set"] = True
                        self.logger.info("Breakeven SL set for %s", symbol)
                elif position.side == "SHORT" and price <= position.take_profit:
                    self.logger.info("TP1 hit: %s - closing %.0f%%", symbol, self.partial_tp1_pct * 100)
                    await self.close_position(symbol, price, self.partial_tp1_pct)
                    position.metadata["partial_closed"] = True
                    if self.breakeven_after_tp1 and not breakeven_set:
                        position.stop_loss = position.entry_price
                        position.metadata["breakeven_set"] = True

            # TP2 - close remaining
            if tp2 > 0 and partial_closed:
                if position.side == "LONG" and price >= tp2:
                    self.logger.info("TP2 hit: %s - closing remaining", symbol)
                    await self.close_position(symbol, price, 1.0)
                elif position.side == "SHORT" and price <= tp2:
                    self.logger.info("TP2 hit: %s - closing remaining", symbol)
                    await self.close_position(symbol, price, 1.0)

            # Max hold time
            if self.max_hold_time and (now - open_time) > self.max_hold_time:
                self.logger.info("Max hold time reached: %s", symbol)
                await self.close_position(symbol, price, 1.0)

        # Standard SL/TP checks
        sl_hits = self.risk.check_stop_losses(prices)
        for symbol in sl_hits:
            self.logger.info("Stop loss: %s", symbol)
            await self.close_position(symbol, prices.get(symbol, 0), 1.0)

        tp_hits = self.risk.check_take_profits(prices)
        for symbol in tp_hits:
            self.logger.info("Take profit: %s", symbol)
            await self.close_position(symbol, prices.get(symbol, 0), 1.0)

    def get_open_positions(self) -> List[Dict]:
        return [
            {
                "symbol": p.symbol, "side": p.side, "size": p.size,
                "entry": p.entry_price, "pnl": p.pnl,
                "pnl_percent": p.pnl_percent, "margin": p.margin,
                "stop_loss": p.stop_loss, "take_profit": p.take_profit
            }
            for p in self.positions.values()
        ]

    def get_trade_history(self) -> List[Dict]:
        return [
            {
                "symbol": o.symbol, "side": o.position_side,
                "type": o.order_type, "qty": o.quantity,
                "price": o.fill_price, "pnl": o.pnl,
                "status": o.status.value, "time": o.fill_time
            }
            for o in self.orders
        ]
