"""
Backtester v5.0 - Walk-forward analysis with detailed metrics.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd
import numpy as np

from src.trading.data_fetcher import DataFetcher
from src.trading.position_manager import Position, PositionSide
from src.core.config import get_config
from src.core.logger import get_logger

logger = get_logger()


@dataclass
class BacktestResult:
    total_return_pct: float = 0
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0
    profit_factor: float = 0
    sharpe_ratio: float = 0
    max_drawdown_pct: float = 0
    avg_trade: float = 0
    avg_win: float = 0
    avg_loss: float = 0
    equity_curve: List[float] = field(default_factory=list)
    trades: List[Dict] = field(default_factory=list)


class Backtester:
    """Strategy backtester with walk-forward optimization"""

    def __init__(self):
        self.config = get_config().backtest
        self.data_fetcher = DataFetcher()
        logger.info("Backtester v5.0 initialized")

    def run(self, symbol: str, strategy_fn, start_idx: int = 50, 
            initial_balance: float = 10000) -> BacktestResult:
        """Run backtest on historical data"""
        df = self.data_fetcher.get_klines(symbol, "15m", limit=2000)
        if len(df) < start_idx + 100:
            logger.error("Insufficient data for backtest")
            return BacktestResult()

        df = self.data_fetcher.calculate_indicators(df)

        balance = initial_balance
        equity = [balance]
        position: Optional[Position] = None
        trades = []

        commission_pct = self.config.commission_pct / 100
        slippage_pct = self.config.slippage_pct / 100

        for i in range(start_idx, len(df) - 1):
            current_price = float(df["close"].iloc[i])

            # Update position
            if position:
                position.unrealized_pnl = position.calculate_pnl(current_price)

                if self.config.use_trailing_stop:
                    atr = float(df["atr"].iloc[i]) if "atr" in df.columns else 0
                    position.update_trailing_stop(current_price, atr)

                should_close, reason = position.should_close(current_price)
                if should_close:
                    # Apply slippage
                    slip = current_price * slippage_pct * (1 if position.side == PositionSide.LONG else -1)
                    exit_price = current_price + slip

                    pnl = (exit_price - position.entry_price) * position.quantity * position.direction
                    commission = position.quantity * exit_price * commission_pct * 2
                    net_pnl = pnl - commission

                    balance += net_pnl
                    trades.append({
                        "symbol": symbol, "side": position.side.value,
                        "entry": position.entry_price, "exit": exit_price,
                        "pnl": net_pnl, "reason": reason,
                    })
                    position = None

            # Check for entry signal
            if not position:
                window = df.iloc[:i+1]
                signal = strategy_fn(symbol, window)

                if signal:
                    slip = current_price * slippage_pct * (-1 if signal.direction == "LONG" else 1)
                    entry_price = current_price + slip

                    # Risk-based sizing
                    risk_amount = balance * 0.01
                    sl_dist = abs(entry_price - signal.stop_loss)
                    if sl_dist > 0:
                        qty = risk_amount / sl_dist
                        notional = qty * entry_price
                        margin = notional / 10  # leverage

                        if balance >= margin:
                            position = Position(
                                symbol=symbol,
                                side=PositionSide.LONG if signal.direction == "LONG" else PositionSide.SHORT,
                                entry_price=entry_price,
                                quantity=qty,
                                original_quantity=qty,
                                leverage=10,
                                margin=margin,
                                stop_loss_price=signal.stop_loss,
                                take_profit_price=signal.take_profit,
                            )
                            balance -= margin

            # Track equity
            open_pnl = position.unrealized_pnl if position else 0
            equity.append(balance + open_pnl)

        # Calculate metrics
        result = BacktestResult()
        result.equity_curve = equity
        result.total_return_pct = (equity[-1] - initial_balance) / initial_balance * 100
        result.total_trades = len(trades)
        result.wins = sum(1 for t in trades if t["pnl"] > 0)
        result.losses = result.total_trades - result.wins
        result.win_rate = (result.wins / result.total_trades * 100) if result.total_trades > 0 else 0

        gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
        gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 1

        returns = pd.Series(equity).pct_change().dropna()
        result.sharpe_ratio = (returns.mean() / returns.std() * np.sqrt(252 * 96)) if returns.std() > 0 else 0

        peak = initial_balance
        max_dd = 0
        for eq in equity:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100
            max_dd = max(max_dd, dd)
        result.max_drawdown_pct = max_dd

        result.avg_trade = sum(t["pnl"] for t in trades) / len(trades) if trades else 0
        result.avg_win = np.mean([t["pnl"] for t in trades if t["pnl"] > 0]) if any(t["pnl"] > 0 for t in trades) else 0
        result.avg_loss = np.mean([t["pnl"] for t in trades if t["pnl"] < 0]) if any(t["pnl"] < 0 for t in trades) else 0
        result.trades = trades

        logger.info("Backtest complete | return=%.2f%% trades=%d win_rate=%.1f%% pf=%.2f",
                   result.total_return_pct, result.total_trades, result.win_rate, result.profit_factor)

        return result
