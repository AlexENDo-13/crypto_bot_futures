"""
CryptoBot v7.0 - Settings
"""
import json
from pathlib import Path
from typing import List
from dataclasses import dataclass, asdict, field


@dataclass
class BotSettings:
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True
    base_url: str = "https://open-api.bingx.com"

    paper_trading: bool = True
    symbol_count: int = 15
    timeframe: str = "15m"
    max_positions: int = 5
    auto_start: bool = False
    scan_interval: int = 60

    max_position_size: float = 1000.0
    max_risk_per_trade: float = 2.0
    max_leverage: int = 10
    max_daily_loss: float = 5.0
    default_sl: float = 2.0
    default_tp: float = 4.0
    trailing_stop: bool = True

    min_confidence: float = 0.5
    strategies_enabled: List[str] = field(default_factory=lambda: [
        "ema_cross", "rsi_divergence", "volume_breakout",
        "support_resistance", "macd_momentum", "bollinger_squeeze", "dca"
    ])

    telegram_enabled: bool = False
    telegram_token: str = ""
    telegram_chat_id: str = ""

    discord_enabled: bool = False
    discord_webhook: str = ""

    email_enabled: bool = False
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_login: str = ""
    email_password: str = ""
    email_to: str = ""

    dark_theme: bool = True

    @classmethod
    def load(cls, path: str = "config/settings.json") -> "BotSettings":
        p = Path(path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            known = {f.name for f in cls.__dataclass_fields__.values()}
            filtered = {k: v for k, v in data.items() if k in known}
            return cls(**filtered)
        return cls()

    def save(self, path: str = "config/settings.json"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
