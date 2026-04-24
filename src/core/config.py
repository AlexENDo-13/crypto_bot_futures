"""
Global Configuration v5.0
"""
import os
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from pathlib import Path
from enum import Enum


class TradingMode(Enum):
    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"


class MarginMode(Enum):
    ISOLATED = "ISOLATED"
    CROSSED = "CROSSED"


@dataclass
class ExchangeConfig:
    api_key: str = ""
    api_secret: str = ""
    base_url: str = "https://open-api.bingx.com"
    ws_url: str = "wss://open-api-ws.bingx.com/market"
    recv_window: int = 5000
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: int = 30
    rate_limit_per_sec: float = 10.0

    def __post_init__(self):
        self.api_key = os.getenv("BINGX_API_KEY", self.api_key)
        self.api_secret = os.getenv("BINGX_API_SECRET", self.api_secret)


@dataclass
class TradingConfig:
    symbols: List[str] = field(default_factory=lambda: ["BTC-USDT", "ETH-USDT"])
    primary_symbol: str = "BTC-USDT"
    leverage: int = 10
    margin_mode: str = "ISOLATED"
    order_type: str = "MARKET"
    max_position_usdt: float = 100.0
    risk_per_trade_pct: float = 1.0
    max_open_positions: int = 5
    max_positions_per_symbol: int = 1
    use_trailing_stop: bool = True
    trailing_stop_pct: float = 0.5
    trailing_stop_atr_mult: float = 2.0
    take_profit_pct: float = 2.0
    stop_loss_pct: float = 1.0
    use_breakeven: bool = True
    breakeven_trigger_pct: float = 0.8
    use_partial_tp: bool = True
    partial_tp_levels: List[Dict] = field(default_factory=lambda: [
        {"pct": 1.0, "close": 0.25},
        {"pct": 2.0, "close": 0.25},
        {"pct": 3.0, "close": 0.25},
    ])
    max_daily_loss_pct: float = 5.0
    cooldown_after_loss_sec: int = 300
    min_volume_24h: float = 500000.0
    max_spread_pct: float = 0.1
    trade_asia: bool = True
    trade_london: bool = True
    trade_new_york: bool = True


@dataclass
class RiskConfig:
    max_daily_trades: int = 20
    max_consecutive_losses: int = 3
    max_drawdown_pct: float = 10.0
    emergency_stop_balance_pct: float = 20.0
    use_kelly: bool = False
    kelly_fraction: float = 0.25
    use_optimal_f: bool = False
    max_atr_pct: float = 5.0
    min_atr_pct: float = 0.05
    max_correlation_positions: int = 2
    correlation_threshold: float = 0.8
    avoid_high_impact_news: bool = True
    news_buffer_minutes: int = 15


@dataclass
class StrategyConfig:
    enabled_strategies: List[str] = field(default_factory=lambda: [
        "ema_cross", "rsi_divergence", "volume_breakout",
        "support_resistance", "macd_momentum", "bollinger_squeeze"
    ])
    timeframes: List[str] = field(default_factory=lambda: ["1m", "5m", "15m", "1h", "4h"])
    primary_timeframe: str = "15m"
    confirmation_timeframe: str = "1h"
    min_signal_confidence: float = 0.65
    ema_fast: int = 9
    ema_slow: int = 21
    ema_trend: int = 50
    ema_long: int = 200
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    volume_ma_period: int = 20
    volume_breakout_mult: float = 2.0
    bb_period: int = 20
    bb_std: float = 2.0
    bb_squeeze_threshold: float = 0.1
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9


@dataclass
class AIConfig:
    enabled: bool = True
    model_path: str = "data/models"
    prediction_threshold: float = 0.6
    retrain_interval_hours: int = 24
    min_samples_for_training: int = 200
    features: List[str] = field(default_factory=lambda: [
        "returns_1m", "returns_5m", "returns_15m", "returns_1h",
        "rsi", "rsi_slope", "macd", "macd_hist", "ema_ratio",
        "atr_pct", "bb_position", "bb_width", "volume_ratio",
        "volume_trend", "support_dist", "resistance_dist"
    ])
    use_ensemble: bool = True
    ensemble_models: List[str] = field(default_factory=lambda: ["rf", "gb", "xgb"])


@dataclass
class BacktestConfig:
    enabled: bool = False
    start_date: str = ""
    end_date: str = ""
    initial_balance: float = 10000.0
    commission_pct: float = 0.04
    slippage_pct: float = 0.01
    walk_forward: bool = True
    walk_forward_window: int = 30
    walk_forward_step: int = 7


@dataclass
class NotificationConfig:
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_enabled: bool = False
    discord_webhook_url: str = ""
    notify_on_trade: bool = True
    notify_on_error: bool = True
    notify_on_drawdown: bool = True
    drawdown_threshold_pct: float = 5.0


@dataclass
class UIConfig:
    window_title: str = "Crypto Bot Futures v5.0"
    window_width: int = 1600
    window_height: int = 1000
    refresh_interval_ms: int = 500
    chart_candles: int = 300
    dark_theme: bool = True
    show_pnl_chart: bool = True
    show_equity_curve: bool = True
    show_drawdown_chart: bool = True
    auto_scroll_logs: bool = True


@dataclass
class Config:
    version: str = "5.0.0"
    mode: TradingMode = TradingMode.PAPER
    debug: bool = False
    data_dir: str = "data"
    log_dir: str = "logs"
    state_db: str = "data/state/bot_state.db"

    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    ui: UIConfig = field(default_factory=UIConfig)

    def validate(self) -> List[str]:
        errors = []
        if self.mode == TradingMode.LIVE:
            if not self.exchange.api_key or not self.exchange.api_secret:
                errors.append("API keys required for live trading")
            if self.trading.leverage < 1 or self.trading.leverage > 125:
                errors.append("Leverage must be 1-125")
            if self.trading.risk_per_trade_pct <= 0:
                errors.append("Risk per trade must be > 0")
        return errors

    def to_dict(self) -> Dict:
        return asdict(self)

    def save(self, path: str = "config.json"):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @classmethod
    def load(cls, path: str = "config.json") -> "Config":
        if not Path(path).exists():
            return cls()
        with open(path) as f:
            data = json.load(f)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: Dict) -> "Config":
        cfg = cls()
        for key, val in data.items():
            if hasattr(cfg, key) and key not in [
                "exchange", "trading", "risk", "strategy", "ai", "backtest", "notifications", "ui"
            ]:
                if key == "mode":
                    cfg.mode = TradingMode(val) if isinstance(val, str) else val
                else:
                    setattr(cfg, key, val)

        if "exchange" in data:
            cfg.exchange = ExchangeConfig(**{
                k: v for k, v in data["exchange"].items()
                if k in ExchangeConfig.__dataclass_fields__
            })
        if "trading" in data:
            cfg.trading = TradingConfig(**{
                k: v for k, v in data["trading"].items()
                if k in TradingConfig.__dataclass_fields__
            })
        if "risk" in data:
            cfg.risk = RiskConfig(**{
                k: v for k, v in data["risk"].items()
                if k in RiskConfig.__dataclass_fields__
            })
        if "strategy" in data:
            cfg.strategy = StrategyConfig(**{
                k: v for k, v in data["strategy"].items()
                if k in StrategyConfig.__dataclass_fields__
            })
        if "ai" in data:
            cfg.ai = AIConfig(**{
                k: v for k, v in data["ai"].items()
                if k in AIConfig.__dataclass_fields__
            })
        if "backtest" in data:
            cfg.backtest = BacktestConfig(**{
                k: v for k, v in data["backtest"].items()
                if k in BacktestConfig.__dataclass_fields__
            })
        if "notifications" in data:
            cfg.notifications = NotificationConfig(**{
                k: v for k, v in data["notifications"].items()
                if k in NotificationConfig.__dataclass_fields__
            })
        if "ui" in data:
            cfg.ui = UIConfig(**{
                k: v for k, v in data["ui"].items()
                if k in UIConfig.__dataclass_fields__
            })
        return cfg


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(cfg: Config):
    global _config
    _config = cfg
