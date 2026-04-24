"""
CryptoBot v9.0 - AutoPilot (Self-Adaptive System)
Features: Automatic parameter tuning, strategy weight adjustment,
          risk level adaptation, market condition response
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio

class AutoPilot:
    """Self-adaptive trading parameters based on performance."""

    def __init__(self):
        self.logger = logging.getLogger("CryptoBot.AutoPilot")
        self.performance_history: Dict[str, list] = {
            "win_rates": [],
            "pnls": [],
            "drawdowns": [],
            "volatilities": []
        }
        self.adaptation_log: list = []
        self.is_adapting = False
        self.logger.info("AutoPilot v9.0 initialized")

    def adapt(self, scanner, executor, risk_manager):
        """Adapt parameters based on recent performance."""
        if self.is_adapting:
            return
        self.is_adapting = True

        try:
            stats = risk_manager.get_stats()
            win_rate = stats.get("win_rate", 50)
            total_pnl = stats.get("total_pnl", 0)
            daily_loss = stats.get("daily_loss", 0)

            self.performance_history["win_rates"].append(win_rate)
            self.performance_history["pnls"].append(total_pnl)
            if len(self.performance_history["win_rates"]) > 100:
                self.performance_history["win_rates"] = self.performance_history["win_rates"][-50:]
                self.performance_history["pnls"] = self.performance_history["pnls"][-50:]

            changes = []

            # Adapt confidence threshold
            if win_rate < 40 and len(self.performance_history["win_rates"]) > 10:
                scanner._min_confidence_adj = 0.7  # Require stronger signals
                changes.append("Raised min confidence to 0.7 (low win rate)")
            elif win_rate > 65:
                scanner._min_confidence_adj = 0.4  # Allow more signals
                changes.append("Lowered min confidence to 0.4 (high win rate)")

            # Adapt risk per trade
            if daily_loss > risk_manager.limits.max_daily_loss * 0.8:
                risk_manager.limits.max_risk_per_trade *= 0.8
                changes.append("Reduced risk per trade by 20% (near daily loss limit)")
            elif win_rate > 60 and total_pnl > 0:
                risk_manager.limits.max_risk_per_trade = min(
                    risk_manager.limits.max_risk_per_trade * 1.1,
                    5.0  # Cap at 5%
                )
                changes.append("Increased risk per trade by 10% (good performance)")

            # Adapt position size
            if stats.get("total_trades", 0) > 20:
                avg_pnl = total_pnl / max(stats["total_trades"], 1)
                if avg_pnl < -5:
                    risk_manager.limits.max_position_size *= 0.9
                    changes.append("Reduced max position size by 10% (negative avg P&L)")
                elif avg_pnl > 20:
                    risk_manager.limits.max_position_size = min(
                        risk_manager.limits.max_position_size * 1.1,
                        5000.0  # Cap at $5000
                    )
                    changes.append("Increased max position size by 10% (positive avg P&L)")

            # Adapt trailing stop
            if executor:
                recent_volatility = self._estimate_volatility(scanner)
                if recent_volatility > 0.04:
                    executor.neural_trailing_pct = 1.0
                    changes.append("Widened trailing stop to 1.0% (high volatility)")
                elif recent_volatility < 0.01:
                    executor.neural_trailing_pct = 0.3
                    changes.append("Tightened trailing stop to 0.3% (low volatility)")

            if changes:
                self.adaptation_log.append({
                    "time": datetime.now().isoformat(),
                    "changes": changes,
                    "win_rate": win_rate,
                    "total_pnl": total_pnl
                })
                for change in changes:
                    self.logger.info("AutoPilot: %s", change)

        except Exception as e:
            self.logger.error("AutoPilot adaptation error: %s", e)
        finally:
            self.is_adapting = False

    def _estimate_volatility(self, scanner) -> float:
        """Estimate recent market volatility from scanner data."""
        try:
            if hasattr(scanner, '_volatility_cache') and scanner._volatility_cache:
                return sum(scanner._volatility_cache.values()) / len(scanner._volatility_cache)
        except Exception:
            pass
        return 0.02  # Default 2%

    def get_adaptation_history(self) -> list:
        return self.adaptation_log[-20:]
