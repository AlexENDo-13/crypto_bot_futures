"""
Candle Patterns – свечные паттерны.
"""

def evaluate_candle_bonus(open_price: float, high: float, low: float, close: float,
                          prev_open: float = None, prev_close: float = None,
                          direction: str = 'BUY') -> float:
    body = abs(close - open_price)
    total_range = high - low
    if total_range == 0:
        return 0.0

    bonus = 0.0
    if direction == 'BUY':
        lower_shadow = min(open_price, close) - low
        if lower_shadow >= 2 * body and close > open_price:
            bonus = min(0.3, (lower_shadow / total_range) * 0.4)
    elif direction == 'SELL':
        upper_shadow = high - max(open_price, close)
        if upper_shadow >= 2 * body and close < open_price:
            bonus = min(0.3, (upper_shadow / total_range) * 0.4)

    return bonus