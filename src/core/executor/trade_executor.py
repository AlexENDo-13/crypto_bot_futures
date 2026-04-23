#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trade Executor — полный исполнитель сделок
"""
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

from src.core.risk.risk_manager import Position
from src.core.signals.signal_evaluator import Signal
from src.config.settings import Settings
from src.utils.api_client import BingXClient


logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str] = None
    executed_price: float = 0.0
    executed_qty: float = 0.0
    error: Optional[str] = None


class TradeExecutor:
    """Исполнитель торговых приказов"""

    def __init__(self, api: BingXClient, settings: Settings):
        self.api = api
        self.settings = settings

    async def open_position(self, position: Position, signal: Signal) -> bool:
        """Открытие позиции"""
        symbol = position.symbol
        side = "BUY" if signal.direction == "LONG" else "SELL"
        
        # Рассчитать qty с учётом шага лота
        qty = self._normalize_qty(symbol, position.qty)
        if qty <= 0:
            logger.error(f"{symbol}: qty после нормализации = 0 (было {position.qty})")
            return False
        
        position.qty = qty  # Обновить в позиции
        
        logger.info(f"{symbol}: Открытие {side} qty={qty:.6f} @ ~{signal.entry_price:.2f}")
        
        try:
            # Рыночный вход
            result = await self._place_market_order(symbol, side, qty)
            
            if not result.success:
                logger.error(f"{symbol}: Ошибка входа: {result.error}")
                return False
            
            # Обновить позицию фактическими данными
            position.entry_price = result.executed_price if result.executed_price > 0 else signal.entry_price
            position.entry_time = __import__('datetime').datetime.utcnow()
            position.order_id = result.order_id
            
            # Установить SL/TP
            await self._set_sl_tp(position, signal)
            
            logger.info(f"{symbol}: Вход выполнен #{result.order_id} @ {position.entry_price:.2f}")
            return True
            
        except Exception as e:
            logger.exception(f"{symbol}: Исключение при входе: {e}")
            return False

    async def close_position(self, position: Position, reason: str) -> bool:
        """Закрытие позиции"""
        symbol = position.symbol
        side = "SELL" if position.side == "LONG" else "BUY"
        qty = position.qty
        
        logger.info(f"{symbol}: Закрытие {side} qty={qty:.6f} (причина: {reason})")
        
        try:
            result = await self._place_market_order(symbol, side, qty)
            
            if not result.success:
                logger.error(f"{symbol}: Ошибка выхода: {result.error}")
                return False
            
            position.exit_price = result.executed_price
            position.exit_time = __import__('datetime').datetime.utcnow()
            position.exit_reason = reason
            
            logger.info(f"{symbol}: Выход выполнен @ {result.executed_price:.2f}")
            return True
            
        except Exception as e:
            logger.exception(f"{symbol}: Исключение при выходе: {e}")
            return False

    async def _place_market_order(self, symbol: str, side: str, qty: float) -> OrderResult:
        """Размещение рыночного ордера"""
        try:
            response = await self.api.place_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=qty
            )
            
            if response.get("code") != 0:
                return OrderResult(
                    success=False,
                    error=f"API error: {response.get('msg', 'Unknown')}"
                )
            
            data = response.get("data", {})
            return OrderResult(
                success=True,
                order_id=str(data.get("orderId", "")),
                executed_price=float(data.get("avgPrice", 0)),
                executed_qty=float(data.get("executedQty", qty))
            )
            
        except Exception as e:
            return OrderResult(success=False, error=str(e))

    async def _set_sl_tp(self, position: Position, signal: Signal):
        """Установка стоп-лосса и тейк-профита"""
        symbol = position.symbol
        
        try:
            # SL
            if position.stop_loss > 0:
                sl_side = "SELL" if position.side == "LONG" else "BUY"
                await self.api.set_stop_loss(
                    symbol=symbol,
                    side=sl_side,
                    stop_price=position.stop_loss,
                    quantity=position.qty
                )
                logger.info(f"{symbol}: SL установлен @ {position.stop_loss:.2f}")
            
            # TP
            if position.take_profit > 0:
                tp_side = "SELL" if position.side == "LONG" else "BUY"
                await self.api.set_take_profit(
                    symbol=symbol,
                    side=tp_side,
                    trigger_price=position.take_profit,
                    quantity=position.qty
                )
                logger.info(f"{symbol}: TP установлен @ {position.take_profit:.2f}")
                
        except Exception as e:
            logger.warning(f"{symbol}: Не удалось установить SL/TP: {e}")

    def _normalize_qty(self, symbol: str, qty: float) -> float:
        """Нормализация qty под шаг лота биржи"""
        step = self.settings.QTY_STEP.get(symbol, 0.001)
        normalized = __import__('math').floor(qty / step) * step
        
        min_qty = self.settings.MIN_QTY.get(symbol, 0.001)
        if normalized < min_qty:
            logger.warning(f"{symbol}: qty {normalized} < min {min_qty}, устанавливаем минимум")
            normalized = min_qty
        
        decimals = len(str(step).split(".")[-1]) if "." in str(step) else 0
        normalized = round(normalized, decimals)
        
        return normalized
