#!/usr/bin/env python3
"""
CryptoBot v9.0 - Neural Adaptive Trading System
Async | Self-Healing | Auto-Adaptive | Real-Time
"""
import sys
import os
import argparse
import asyncio
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.logger import BotLogger, get_logger

def ensure_directories():
    for d in ["logs", "data/state", "data/cache", "config", "backtests", "data/trades", "data/models"]:
        Path(d).mkdir(parents=True, exist_ok=True)

async def run_headless(paper: bool = True, interval: int = 60, duration: int = 0):
    from core.settings import BotSettings
    from core.state_manager import StateManager
    from core.notifications import NotificationManager, NotificationConfig
    from core.monitor import SystemMonitor
    from core.autopilot import AutoPilot
    from exchange.api_client import BingXAPIClient
    from exchange.data_fetcher import DataFetcher
    from exchange.market_scanner import MarketScanner
    from exchange.trade_executor import TradeExecutor
    from risk.risk_manager import RiskManager, RiskLimits
    from ml.ml_engine import MLEngine

    log = get_logger("CryptoBot")
    log.info("=" * 60)
    log.info("CryptoBot v9.0 - NEURAL ADAPTIVE SYSTEM")
    log.info("=" * 60)

    settings = BotSettings.load()
    state_mgr = StateManager()
    monitor = SystemMonitor()
    autopilot = AutoPilot()

    if not paper and (not settings.api_key or not settings.api_secret):
        log.error("API keys required for LIVE trading!")
        return 1

    client = BingXAPIClient(
        api_key=settings.api_key, api_secret=settings.api_secret,
        base_url=settings.base_url, testnet=settings.testnet
    )

    fetcher = DataFetcher(api_client=client)
    limits = RiskLimits(
        max_position_size=settings.max_position_size,
        max_risk_per_trade=settings.max_risk_per_trade,
        max_leverage=settings.max_leverage,
        max_daily_loss=settings.max_daily_loss,
        default_sl_percent=settings.default_sl,
        default_tp_percent=settings.default_tp
    )
    risk = RiskManager(limits=limits)
    ml = MLEngine()

    notif = NotificationManager(config=NotificationConfig(
        telegram_enabled=settings.telegram_enabled,
        telegram_token=settings.telegram_token,
        telegram_chat_id=settings.telegram_chat_id
    ))

    executor = TradeExecutor(
        api_client=client, risk_manager=risk,
        paper_trading=paper, balance=10000.0, notifier=notif
    )
    scanner = MarketScanner(data_fetcher=fetcher, ml_engine=ml, max_workers=4)

    mode = "PAPER" if paper else "LIVE"
    log.info("Headless ready | Mode=%s | Interval=%ds", mode, interval)

    start = time.time()
    cycle = 0

    try:
        while True:
            cycle += 1
            log.info("--- Cycle #%d ---", cycle)
            monitor.start_cycle()

            # Self-healing: check API health
            if not client.is_healthy:
                log.warning("API unhealthy, attempting recovery...")
                await asyncio.sleep(2)
                client.update_credentials(settings.api_key, settings.api_secret)

            # Adaptive: adjust parameters based on performance
            if cycle % 10 == 0:
                autopilot.adapt(scanner, executor, risk)

            # Scan
            try:
                signals = await scanner.scan_all(settings.timeframe)
                if signals:
                    log.info("Found %d signals", len(signals))
                    for sig in signals[:3]:
                        log.info("  -> %s %s (%s) conf=%.2f regime=%s",
                                 sig.symbol, sig.type.value.upper(), sig.strategy,
                                 sig.confidence, sig.metadata.get("regime", "unknown") if sig.metadata else "unknown")
                        if executor and settings.auto_trade:
                            await executor.execute_signal(sig)
            except Exception as e:
                log.error("Scan error: %s", e)
                monitor.record_error()

            # Update positions
            if executor and executor.positions:
                try:
                    prices = await fetcher.get_prices_batch(list(executor.positions.keys()))
                    if prices:
                        await executor.update_positions(prices)
                except Exception as e:
                    log.error("Position update error: %s", e)

            # ML online learning
            if cycle % 50 == 0 and ml.trained:
                try:
                    ml.save_model()
                    log.info("ML model checkpoint saved")
                except Exception as e:
                    log.debug("ML save error: %s", e)

            # Stats
            stats = risk.get_stats()
            monitor.record_stats(stats)
            log.info("Stats: Trades=%d | WinRate=%.1f%% | P&L=$%+.2f | Open=%d",
                     stats["total_trades"], stats["win_rate"],
                     stats["total_pnl"], stats["open_positions"])

            state_mgr.save_stat("last_cycle", cycle)
            state_mgr.save_stat("last_run", datetime.now().isoformat())
            monitor.end_cycle()

            if duration > 0 and (time.time() - start) >= duration:
                log.info("Duration limit reached (%ds). Stopping.", duration)
                break

            log.info("Sleeping %d seconds...", interval)
            await asyncio.sleep(interval)

    except KeyboardInterrupt:
        log.info("Interrupted by user")
    finally:
        log.info("Bot stopped. Total cycles: %d", cycle)
        state_mgr.save_stat("total_cycles", cycle)
        if ml.trained:
            ml.save_model()

    return 0

def run_gui():
    try:
        from PyQt6.QtWidgets import QApplication
        PYQT = "PyQt6"
    except ImportError:
        try:
            from PyQt5.QtWidgets import QApplication
            PYQT = "PyQt5"
        except ImportError:
            print("ERROR: Install PyQt6: pip install PyQt6")
            sys.exit(1)

    log = get_logger("CryptoBot")
    log.info("Starting CryptoBot v9.0 GUI | Qt=%s", PYQT)

    app = QApplication(sys.argv)
    app.setApplicationName("CryptoBot v9.0")

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    log.info("MainWindow displayed")
    return app.exec() if hasattr(app, 'exec') else app.exec_()

def main():
    parser = argparse.ArgumentParser(description="CryptoBot v9.0 - Neural Adaptive Trading System")
    parser.add_argument("--headless", action="store_true", help="Run without GUI")
    parser.add_argument("--paper", action="store_true", default=True, help="Paper trading")
    parser.add_argument("--live", action="store_true", help="LIVE trading")
    parser.add_argument("--interval", type=int, default=60, help="Scan interval")
    parser.add_argument("--duration", type=int, default=0, help="Max runtime (0=inf)")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG","INFO","WARNING","ERROR"])
    args = parser.parse_args()

    ensure_directories()
    level_map = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}
    logger = BotLogger(log_dir="logs", level=level_map.get(args.log_level, 20))
    log = logger.get_logger("CryptoBot")

    log.info("=" * 60)
    log.info("CryptoBot v9.0 - Neural Adaptive Trading System")
    log.info("=" * 60)

    try:
        if args.headless:
            paper = not args.live
            return asyncio.run(run_headless(paper=paper, interval=args.interval, duration=args.duration))
        else:
            return run_gui()
    except Exception as e:
        log.error("Fatal: %s", e, exc_info=True)
        print("\nFATAL ERROR: %s" % e)
        print(traceback.format_exc())
        input("\nPress Enter to exit...")
        raise

if __name__ == "__main__":
    import time
    from datetime import datetime
    sys.exit(main())
