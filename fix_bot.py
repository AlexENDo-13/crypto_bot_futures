#!/usr/bin/env python3
"""
Ищет файл trade_executor.py (или любой .py с методом close_position) и исправляет
метод close_position — добавляет конвертацию side в position_side.
"""

import re
from pathlib import Path

def find_trade_executor(root="."):
    """
    Ищет файл, содержащий одновременно 'def close_position' и 'close_position_async'.
    Возвращает первый подходящий путь.
    """
    for py_file in Path(root).rglob("*.py"):
        if any(part.startswith('.') or part in ('venv','env','__pycache__','.git') for part in py_file.parts):
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
        except:
            continue
        if "def close_position" in content and "close_position_async" in content:
            return py_file
    return None

def fix_close_position_method(filepath):
    path = Path(filepath)
    content = path.read_text(encoding="utf-8")

    # Ищем метод close_position (синхронная обёртка)
    # Ожидаем что-то вроде:
    # def close_position(self, symbol, side, quantity=None):
        """
        Закрыть позицию (синхронная обертка). Поддерживает side как BUY/SELL
        или LONG/SHORT. Конвертирует BUY/SELL в соответствующее position_side.
        """
        # Конвертация side (направление ордера) в position_side (сторона позиции)
        if side == "BUY":
            position_side = "SHORT"
        elif side == "SELL":
            position_side = "LONG"
        else:
            position_side = side  # уже LONG или SHORT

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.close_position_async(symbol, position_side, quantity))
            else:
                loop.run_until_complete(self.close_position_async(symbol, position_side, quantity))
        except Exception as e:
            self.logger.error(f"Close position error: {e}")