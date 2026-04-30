"""Utility helpers."""
from typing import Dict, Any


def format_price(price: float, decimals: int = 2) -> str:
    return f"{price:.{decimals}f}"


def format_percent(value: float) -> str:
    return f"{value:.2f}%"
