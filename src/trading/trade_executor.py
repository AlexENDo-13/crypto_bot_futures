"""
Trade Executor v5.0 - Full-featured execution with partial profits,
DCA, breakeven, ATR trailing, and paper trading.
"""
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from src.exchange.api_client import BingXAPIClient, APIResponse
from src.trading.data_fetcher import DataFetcher
from src.trading.position_manager import Position, PositionSide, PartialTarget
from src.trading.risk_manager import RiskManager
from src.core.config import get_config
from src.core.logger import get_logger
from src.core.state import StateManager
from src.core.events import get_event_bus, EventType

logger = get_logger()


@dataclass
class ExecutionResult:
    success: bool
    message: str
    position: Optional[Position] = None
    pnl: float = 0.0
    order_id: str = ""


class TradeExecutor:
    """Advanced trade execution engine"""

    def __init__(self):
        self.client = BingXAPIClient()
        self.data_fetcher = DataFetcher()
        self.config = get_config().trading
        self.risk = RiskManager()
        self.state = StateManager()
        self.event_bus = get_event_bus()
        self.paper_mode = get_config().mode.value == "paper"

        self._paper_balance: float = 10000.0
        self._paper_positions: Dict[str, Position] = {}
        self._live_positions: Dict[str, Position] = {}
        self._order_history: List[Dict] = []

        logger.info("TradeExecutor v5.0 | paper=%s", self.paper_mode)

    def set_paper_balance(self, balance: float):
        self._paper_balance = balance
        logger.info("Paper balance: %.2f USDT", balance)

    def get_balance(self) -> float:
        if self.paper_mode:
            return self._paper_balance
        resp = self.client.get_balance()
        if resp.is_ok and resp.data:
            balances = resp.data if isinstance(resp.data, list) else [resp.data]
            for bal in balances:
                if bal.get("asset") == "USDT":
                    return float(bal.get("balance", 0))
        return 0.0

    def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        if self.paper_mode:
            if symbol:
                pos = self._paper_positions.get(symbol)
                return [pos] if pos and pos.status == "OPEN" else []
            return [p for p in self._paper_positions.values() if p.status == "OPEN"]

        resp = self.client.get_positions(symbol)
        positions = []
        if resp.is_ok and resp.data:
            for pos_data in resp.data:
                qty = float(pos_data.get("positionAmt", 0))
                if abs(qty) > 0:
                    pos = Position(
                        symbol=pos_data.get("symbol", ""),
                        side=PositionSide.LONG if qty > 0 else PositionSide.SHORT,
                        entry_price=float(pos_data.get("entryPrice", 0)),
                        quantity=abs(qty),
                        original_quantity=abs(qty),
                        leverage=int(pos_data.get("leverage", 1)),
                        margin=float(pos_data.get("isolatedMargin", 0)),
                        unrealized_pnl=float(pos_data.get("unrealizedProfit", 0)),
                    )
                    positions.append(pos)
                    self._live_positions[pos.symbol] = pos
        return positions

    def open_position(self, symbol: str, side: PositionSide, quantity: float,
                      price: Optional[float] = None, stop_loss: Optional[float] = None,
                      take_profit: Optional[float] = None, atr: float = 0) -> ExecutionResult:
        """Open a new position with full risk management"""
        cfg = self.config

        if quantity <= 0:
            return ExecutionResult(False, "Quantity must be positive")

        existing = self.get_positions(symbol)
        for pos in existing:
            if pos.side == side:
                return ExecutionResult(False, f"{side.value} position exists", pos)

        current_price = price or self.data_fetcher.get_current_price(symbol)
        if current_price <= 0:
            return ExecutionResult(False, "Cannot get price")

        qty = self.data_fetcher.round_quantity(symbol, quantity)
        if qty <= 0:
            return ExecutionResult(False, "Rounded qty is zero")

        notional = qty * current_price
        margin = notional / cfg.leverage

        balance = self.get_balance()
        if balance < margin:
            return ExecutionResult(False, f"Insufficient: {balance:.2f} < {margin:.2f}")

        # Calculate stops
        sl_price = stop_loss or 0
        tp_price = take_profit or 0

        if not sl_price:
            sl_pct = cfg.stop_loss_pct / 100
            sl_price = current_price * (1 - sl_pct) if side == PositionSide.LONG else current_price * (1 + sl_pct)
        if not tp_price:
            tp_pct = cfg.take_profit_pct / 100
            tp_price = current_price * (1 + tp_pct) if side == PositionSide.LONG else current_price * (1 - tp_pct)

        sl_price = self.data_fetcher.round_price(symbol, sl_price)
        tp_price = self.data_fetcher.round_price(symbol, tp_price)

        # Breakeven
        be_trigger = 0
        be_price = 0
        if cfg.use_breakeven:
            be_pct = cfg.breakeven_trigger_pct / 100
            be_trigger = current_price * (1 + be_pct) if side == PositionSide.LONG else current_price * (1 - be_pct)
            be_price = current_price * 1.001 if side == PositionSide.LONG else current_price * 0.999

        # Partial targets
        partials = []
        if cfg.use_partial_tp:
            for level in cfg.partial_tp_levels:
                partials.append(PartialTarget(
                    trigger_pct=level["pct"],
                    close_pct=level["close"]
                ))

        if self.paper_mode:
            return self._paper_open(symbol, side, qty, current_price, margin,
                                    sl_price, tp_price, be_trigger, be_price, partials, atr)
        else:
            return self._live_open(symbol, side, qty, current_price, margin,
                                   sl_price, tp_price, be_trigger, be_price, partials, atr)

    def _paper_open(self, symbol, side, qty, price, margin, sl, tp, be_trigger, be_price, partials, atr) -> ExecutionResult:
        if self._paper_balance < margin:
            return ExecutionResult(False, "Insufficient paper balance")

        self._paper_balance -= margin

        pos = Position(
            symbol=symbol, side=side, entry_price=price, quantity=qty,
            original_quantity=qty, leverage=self.config.leverage, margin=margin,
            stop_loss_price=sl, take_profit_price=tp,
            use_breakeven=self.config.use_breakeven,
            breakeven_trigger_price=be_trigger, breakeven_price=be_price,
            partial_targets=partials,
            use_atr_trailing=self.config.use_trailing_stop,
            trailing_stop_atr_mult=self.config.trailing_stop_atr_mult,
            atr_value=atr,
            highest_price=price if side == PositionSide.LONG else 0,
            lowest_price=price if side == PositionSide.SHORT else float("inf"),
        )

        if self.config.use_trailing_stop:
            pos.trailing_stop_price = sl

        self._paper_positions[symbol] = pos

        self.event_bus.emit_new(EventType.POSITION_OPENED, {
            "symbol": symbol, "side": side.value, "qty": qty, "price": price, "margin": margin
        })

        logger.trade(f"PAPER OPEN | {symbol} {side.value} qty={qty} @ {price} margin={margin:.2f}")
        return ExecutionResult(True, "Opened (paper)", pos)

    def _live_open(self, symbol, side, qty, price, margin, sl, tp, be_trigger, be_price, partials, atr) -> ExecutionResult:
        self.client.set_leverage(symbol, self.config.leverage, side.value)
        order_side = "BUY" if side == PositionSide.LONG else "SELL"
        resp = self.client.place_market_order(symbol, order_side, side.value, qty)

        if not resp.is_ok:
            return ExecutionResult(False, f"Order failed: {resp.error_msg}")

        order_data = resp.data or {}
        avg_price = float(order_data.get("avgPrice", price))
        filled_qty = float(order_data.get("executedQty", qty))

        pos = Position(
            symbol=symbol, side=side, entry_price=avg_price, quantity=filled_qty,
            original_quantity=filled_qty, leverage=self.config.leverage, margin=margin,
            stop_loss_price=sl, take_profit_price=tp,
            use_breakeven=self.config.use_breakeven,
            breakeven_trigger_price=be_trigger, breakeven_price=be_price,
            partial_targets=partials,
            use_atr_trailing=self.config.use_trailing_stop,
            trailing_stop_atr_mult=self.config.trailing_stop_atr_mult,
            atr_value=atr,
        )

        if self.config.use_trailing_stop:
            pos.trailing_stop_price = sl

        self._live_positions[symbol] = pos

        self.event_bus.emit_new(EventType.POSITION_OPENED, {
            "symbol": symbol, "side": side.value, "qty": filled_qty, "price": avg_price
        })

        logger.trade(f"LIVE OPEN | {symbol} {side.value} qty={filled_qty} @ {avg_price}")
        return ExecutionResult(True, "Opened (live)", pos)

    def close_position(self, symbol: str, reason: str = "MANUAL", qty: Optional[float] = None) -> ExecutionResult:
        """Close position (full or partial)"""
        positions = self.get_positions(symbol)
        if not positions:
            return ExecutionResult(False, f"No position for {symbol}")

        pos = positions[0]
        current_price = self.data_fetcher.get_current_price(symbol)
        close_qty = qty or pos.quantity

        if self.paper_mode:
            return self._paper_close(pos, current_price, close_qty, reason)
        else:
            return self._live_close(pos, current_price, close_qty, reason)

    def _paper_close(self, pos, current_price, qty, reason) -> ExecutionResult:
        pnl = (current_price - pos.avg_entry_price) * qty * pos.direction
        commission = qty * current_price * 0.0004  # 0.04%
        net_pnl = pnl - commission

        pos.realized_pnl += net_pnl
        pos.quantity -= qty
        self._paper_balance += (qty / pos.original_quantity) * pos.margin + net_pnl

        if pos.quantity <= 0.0001:
            pos.status = "CLOSED"
            pos.closed_at = datetime.now()
            pos.close_reason = reason
            pos.quantity = 0
            if pos.symbol in self._paper_positions:
                del self._paper_positions[pos.symbol]

        self.event_bus.emit_new(EventType.POSITION_CLOSED, {
            "symbol": pos.symbol, "side": pos.side.value, "pnl": net_pnl,
            "reason": reason, "price": current_price
        })

        self.state.save_trade({
            "symbol": pos.symbol, "side": pos.side.value,
            "entry_price": pos.avg_entry_price, "exit_price": current_price,
            "quantity": qty, "pnl": net_pnl, "reason": reason,
            "duration_sec": pos.duration_seconds(),
        })

        logger.trade(f"PAPER CLOSE | {pos.symbol} {reason} PnL={net_pnl:+.2f}")
        return ExecutionResult(True, f"Closed (paper) PnL={net_pnl:+.2f}", pos, net_pnl)

    def _live_close(self, pos, current_price, qty, reason) -> ExecutionResult:
        resp = self.client.close_position(pos.symbol, pos.side.value)
        if not resp.is_ok:
            return ExecutionResult(False, f"Close failed: {resp.error_msg}")

        order_data = resp.data or {}
        avg_price = float(order_data.get("avgPrice", current_price))
        pnl = (avg_price - pos.avg_entry_price) * qty * pos.direction

        pos.status = "CLOSED"
        pos.closed_at = datetime.now()
        pos.close_reason = reason

        if pos.symbol in self._live_positions:
            del self._live_positions[pos.symbol]

        self.event_bus.emit_new(EventType.POSITION_CLOSED, {
            "symbol": pos.symbol, "side": pos.side.value, "pnl": pnl, "reason": reason
        })

        self.state.save_trade({
            "symbol": pos.symbol, "side": pos.side.value,
            "entry_price": pos.avg_entry_price, "exit_price": avg_price,
            "quantity": qty, "pnl": pnl, "reason": reason,
        })

        logger.trade(f"LIVE CLOSE | {pos.symbol} {reason} PnL={pnl:+.2f}")
        return ExecutionResult(True, f"Closed (live) PnL={pnl:+.2f}", pos, pnl)

    def update_positions(self) -> List[Tuple[str, str, float]]:
        """Update all positions - check stops, trailing, partials, breakeven"""
        closed = []
        positions = self.get_positions()

        for pos in positions:
            current_price = self.data_fetcher.get_current_price(pos.symbol)
            if current_price <= 0:
                continue

            # Update trailing stop
            if self.config.use_trailing_stop:
                atr = pos.atr_value
                if atr == 0:
                    df = self.data_fetcher.get_klines(pos.symbol, "15m", limit=20)
                    if not df.empty and "atr" in df.columns:
                        atr = float(df["atr"].iloc[-1])
                pos.update_trailing_stop(current_price, atr)

            # Check breakeven
            if self.config.use_breakeven:
                pos.check_breakeven(current_price)

            # Check partial targets
            if self.config.use_partial_tp:
                hit = pos.check_partial_targets(current_price)
                for target in hit:
                    close_qty = target.close_pct * pos.original_quantity
                    result = self.close_position(pos.symbol, "PARTIAL_PROFIT", close_qty)
                    if result.success:
                        logger.trade(f"PARTIAL | {pos.symbol} +{target.trigger_pct}% closed {target.close_pct*100:.0f}%")

            # Check close conditions
            should_close, reason = pos.should_close(current_price)
            if should_close:
                result = self.close_position(pos.symbol, reason)
                if result.success:
                    closed.append((pos.symbol, reason, result.pnl))
            else:
                pos.unrealized_pnl = pos.calculate_pnl(current_price)

        return closed

    def get_paper_state(self) -> Dict:
        return {"balance": self._paper_balance, "positions": self._paper_positions}
