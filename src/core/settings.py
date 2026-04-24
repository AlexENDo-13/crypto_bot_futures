"""
CryptoBot v6.0 - Settings & Configuration
"""
import json
import os
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass, asdict, field


@dataclass
class BotSettings:
    """Bot configuration settings."""
    # API
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True
    base_url: str = "https://open-api.bingx.com"

    # Trading
    paper_trading: bool = True
    symbol_count: int = 15
    timeframe: str = "15m"
    max_positions: int = 5

    # Risk
    max_position_size: float = 1000.0
    max_risk_per_trade: float = 2.0
    max_leverage: int = 10
    max_daily_loss: float = 5.0
    default_sl: float = 2.0
    default_tp: float = 4.0

    # Strategies
    min_confidence: float = 0.65
    strategies_enabled: list = field(default_factory=lambda: [
        "ema_cross", "rsi_divergence", "volume_breakout",
        "support_resistance", "macd_momentum", "bollinger_squeeze"
    ])

    # Scanner
    scan_interval: int = 60  # seconds

    # Notifications
    telegram_enabled: bool = False
    telegram_token: str = ""
    telegram_chat_id: str = ""
    discord_enabled: bool = False
    discord_webhook: str = ""
    email_enabled: bool = False

    # UI
    dark_theme: bool = True

    @classmethod
    def load(cls, path: str = "config/settings.json") -> "BotSettings":
        """Load settings from file."""
        p = Path(path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**data)
        return cls()

    def save(self, path: str = "config/settings.json"):
        """Save settings to file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
