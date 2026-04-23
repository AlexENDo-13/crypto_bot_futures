#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List, Dict, Any
from src.core.logger import BotLogger
from src.core.trading.position import Position


class RiskController:
    """Контроль рисков: лимиты на количество позиций, максимальный риск и т.д."""

    def __init__(self, logger: BotLogger, settings: Dict[str, Any]):
        self.logger = logger
        self.settings = settings

    def filter_signals(self, signals: List[Dict[str, Any]], positions: List[Position], balance: float) -> List[Dict[str, Any]]:
        """
        Фильтрует сигналы в соответствии с риск-параметрами.
        Возвращает список сигналов, которые можно исполнить.
        """
        max_positions = self.settings.get('max_positions', 2)
        max_total_risk = self.settings.get('max_total_risk_percent', 30.0) / 100
        max_risk_per_trade = self.settings.get('max_risk_per_trade', 2.0) / 100

        # Ограничение по количеству открытых позиций
        if len(positions) >= max_positions:
            self.logger.info(f"Достигнут лимит открытых позиций ({max_positions})")
            return []

        # Фильтрация по дневному лимиту убытков и т.д. (упрощённо)
        filtered = []
        total_risk = 0.0
        for pos in positions:
            # Грубая оценка риска по позиции (стоп-лосс расстояние)
            if pos.stop_loss_price:
                sl_distance = abs(pos.entry_price - pos.stop_loss_price) / pos.entry_price
                risk = pos.quantity * pos.entry_price * sl_distance
                total_risk += risk

        for signal in signals:
            # Оцениваем риск новой позиции
            entry_price = signal['entry_price']
            quantity = signal['quantity']
            sl_distance = signal.get('stop_loss_distance_pct', 2.0) / 100
            risk = quantity * entry_price * sl_distance
            if (total_risk + risk) / balance > max_total_risk:
                self.logger.info(f"Превышен общий риск ({max_total_risk*100:.1f}%)")
                break
            if risk / balance > max_risk_per_trade:
                self.logger.info(f"Превышен риск на сделку для {signal['symbol']}")
                continue
            filtered.append(signal)
            total_risk += risk
            if len(positions) + len(filtered) >= max_positions:
                break

        return filtered
