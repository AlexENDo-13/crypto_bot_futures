"""
Crypto Bot Futures v5.0
Main entry point. GUI, CLI, backtest, and train modes.
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.core.config import get_config, Config, TradingMode, set_config
from src.core.logger import get_logger, setup_logging
from src.core.security import KeyManager
from src.trading.data_fetcher import DataFetcher
from src.trading.trade_executor import TradeExecutor
from src.trading.risk_manager import RiskManager
from src.trading.market_scanner import MarketScanner
from src.ai.ml_engine import MLEngine
from src.ai.ai_exporter import AIExporter
from src.backtest.backtester import Backtester


def run_cli():
    logger = setup_logging(console_level=20)
    log = get_logger()
    log.info("=" * 60)
    log.info("Crypto Bot Futures v5.0 - CLI Mode")
    log.info("=" * 60)

    cfg = get_config()
    log.info("Mode: %s | Symbol: %s | Leverage: %dx",
             cfg.mode.value, cfg.trading.primary_symbol, cfg.trading.leverage)

    data_fetcher = DataFetcher()
    executor = TradeExecutor()
    risk = RiskManager()
    scanner = MarketScanner()
    ml = MLEngine()

    executor.set_paper_balance(10000.0)

    log.info("Scanning...")
    signals = scanner.scan_all()
    log.info("Signals found: %d", len(signals))

    for sig in signals[:10]:
        log.info("  %s %s | conf=%.2f | %s | %s",
                sig.symbol, sig.direction, sig.confidence, sig.strategy, sig.reason)

    if ml._models:
        log.info("ML Predictions:")
        for symbol in ["BTC-USDT", "ETH-USDT"]:
            pred = ml.predict(symbol)
            if pred:
                log.info("  %s: %s (conf=%.2f, prob=%.3f)",
                        symbol, pred.direction, pred.confidence, pred.probability)

    log.info("CLI complete.")


def run_gui():
    from PyQt5.QtWidgets import QApplication
    from src.ui.main_window import MainWindow, apply_dark_theme

    app = QApplication(sys.argv)
    apply_dark_theme(app)
    setup_logging(console_level=20)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


def run_backtest():
    logger = setup_logging(console_level=20)
    log = get_logger()
    log.info("Backtest mode")

    from src.plugins.ema_cross import EMACrossStrategy
    bt = Backtester()
    result = bt.run("BTC-USDT", lambda s, df: EMACrossStrategy().analyze(s, df, {}))

    log.info("Return: %.2f%%", result.total_return_pct)
    log.info("Trades: %d (W:%d L:%d)", result.total_trades, result.wins, result.losses)
    log.info("Win Rate: %.1f%%", result.win_rate)
    log.info("Profit Factor: %.2f", result.profit_factor)
    log.info("Sharpe: %.2f", result.sharpe_ratio)
    log.info("Max DD: %.2f%%", result.max_drawdown_pct)


def run_train():
    logger = setup_logging(console_level=20)
    log = get_logger()
    log.info("Training ML models...")

    ml = MLEngine()
    exporter = AIExporter()
    dataset = exporter.build_dataset(
        ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT"],
        samples_per_symbol=400
    )
    ml.train(dataset)
    log.info("Training complete.")


def main():
    parser = argparse.ArgumentParser(description="Crypto Bot Futures v5.0")
    parser.add_argument("--cli", action="store_true", help="CLI mode")
    parser.add_argument("--backtest", action="store_true", help="Backtest mode")
    parser.add_argument("--train", action="store_true", help="Train ML models")
    parser.add_argument("--symbol", type=str, help="Primary symbol")
    parser.add_argument("--leverage", type=int, help="Leverage")
    parser.add_argument("--live", action="store_true", help="LIVE TRADING (DANGER)")
    parser.add_argument("--config", type=str, help="Config file path")
    args = parser.parse_args()

    if args.config and os.path.exists(args.config):
        set_config(Config.load(args.config))

    cfg = get_config()
    if args.symbol:
        cfg.trading.primary_symbol = args.symbol
        cfg.trading.symbols = [args.symbol]
    if args.leverage:
        cfg.trading.leverage = args.leverage
    if args.live:
        cfg.mode = TradingMode.LIVE

    if args.backtest:
        run_backtest()
    elif args.train:
        run_train()
    elif args.cli:
        run_cli()
    else:
        run_gui()


if __name__ == "__main__":
    main()
