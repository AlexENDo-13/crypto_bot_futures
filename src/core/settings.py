"""
Legacy Settings - Backward compatibility wrapper.
"""
from src.core.config import get_config, Config, ExchangeConfig, TradingConfig, RiskConfig, StrategyConfig

__all__ = ["get_config", "Config", "ExchangeConfig", "TradingConfig", "RiskConfig", "StrategyConfig"]

def get_exchange_config() -> ExchangeConfig:
    return get_config().exchange

def get_trading_config() -> TradingConfig:
    return get_config().trading

def get_risk_config() -> RiskConfig:
    return get_config().risk

def get_strategy_config() -> StrategyConfig:
    return get_config().strategy
