#!/usr/bin/env python3
"""
Parameter Optimizer (B2) — self-tunes SL/TP based on trade history.
Uses recent trade outcomes to adapt stop loss and take profit distances.
"""
import json
import os
import time
import logging
from collections import deque
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("CryptoBot.Optimizer")

class ParameterOptimizer:
    def __init__(self, optimizer_path: str = "logs/parameter_optimizer.json",
                 min_samples: int = 5, adaptation_rate: float = 0.15):
        self.optimizer_path = optimizer_path
        self.min_samples = min_samples
        self.adaptation_rate = adaptation_rate
        self._sl_history: deque = deque(maxlen=50)
        self._tp_history: deque = deque(maxlen=50)
        self._optimal_sl_pct = 1.5
        self._optimal_tp_pct = 3.0
        self._optimal_rr_ratio = 2.0
        self._last_adaptation = 0
        self._adaptation_interval = 3600  # Adapt every hour
        self._load()

    def _load(self):
        if os.path.exists(self.optimizer_path):
            try:
                with open(self.optimizer_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._optimal_sl_pct = data.get("sl_pct", 1.5)
                    self._optimal_tp_pct = data.get("tp_pct", 3.0)
                    self._optimal_rr_ratio = data.get("rr_ratio", 2.0)
                    self._sl_history = deque(data.get("sl_history", []), maxlen=50)
                    self._tp_history = deque(data.get("tp_history", []), maxlen=50)
                logger.info(f"Optimizer loaded: SL={self._optimal_sl_pct:.2f}%, TP={self._optimal_tp_pct:.2f}%")
            except Exception as e:
                logger.error(f"Optimizer load error: {e}")

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.optimizer_path), exist_ok=True)
            with open(self.optimizer_path, "w", encoding="utf-8") as f:
                json.dump({
                    "sl_pct": self._optimal_sl_pct,
                    "tp_pct": self._optimal_tp_pct,
                    "rr_ratio": self._optimal_rr_ratio,
                    "sl_history": list(self._sl_history),
                    "tp_history": list(self._tp_history),
                    "last_update": time.time()
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Optimizer save error: {e}")

    def record_trade_outcome(self, sl_pct: float, tp_pct: float, pnl: float, 
                             exit_reason: str, max_profit_pct: float = 0.0, max_loss_pct: float = 0.0):
        """Record outcome to learn optimal SL/TP."""
        self._sl_history.append({
            "sl_pct": sl_pct, "tp_pct": tp_pct, "pnl": pnl,
            "exit_reason": exit_reason, "max_profit": max_profit_pct,
            "max_loss": max_loss_pct, "time": time.time()
        })
        self._tp_history.append({
            "sl_pct": sl_pct, "tp_pct": tp_pct, "pnl": pnl,
            "exit_reason": exit_reason, "max_profit": max_profit_pct,
            "max_loss": max_loss_pct, "time": time.time()
        })
        logger.debug(f"Optimizer recorded: SL={sl_pct:.2f}%, TP={tp_pct:.2f}%, PnL={pnl:+.4f}, Reason={exit_reason}")

    def adapt(self) -> Tuple[float, float]:
        """Adapt SL/TP based on recent history. Returns (sl_pct, tp_pct)."""
        now = time.time()
        if now - self._last_adaptation < self._adaptation_interval:
            return self._optimal_sl_pct, self._optimal_tp_pct

        if len(self._sl_history) < self.min_samples:
            return self._optimal_sl_pct, self._optimal_tp_pct

        # Analyze SL performance
        sl_wins = [h for h in self._sl_history if h["pnl"] > 0]
        sl_losses = [h for h in self._sl_history if h["pnl"] < 0]

        # If many SL hits are losses, SL might be too tight
        sl_hits = [h for h in self._sl_history if h["exit_reason"] == "STOP_LOSS"]
        if len(sl_hits) >= 3:
            sl_hit_wr = sum(1 for h in sl_hits if h["pnl"] > 0) / len(sl_hits)
            if sl_hit_wr < 0.2:  # Less than 20% of SL hits are wins
                # SL is too tight — widen it
                self._optimal_sl_pct = min(5.0, self._optimal_sl_pct * (1 + self.adaptation_rate))
                logger.info(f"OPTIMIZER: Widening SL to {self._optimal_sl_pct:.2f}% (SL hit WR too low)")
            elif sl_hit_wr > 0.5 and len(sl_hits) >= 5:
                # SL is generous — can tighten for better R:R
                self._optimal_sl_pct = max(0.5, self._optimal_sl_pct * (1 - self.adaptation_rate * 0.5))
                logger.info(f"OPTIMIZER: Tightening SL to {self._optimal_sl_pct:.2f}% (SL hit WR good)")

        # Analyze TP performance
        tp_hits = [h for h in self._tp_history if h["exit_reason"] == "TAKE_PROFIT"]
        if len(tp_hits) >= 3:
            avg_tp_pnl = sum(h["pnl"] for h in tp_hits) / len(tp_hits)
            if avg_tp_pnl > 0:
                # TP is working well
                # Check if price often goes much further after TP
                runners = [h for h in tp_hits if h["max_profit"] > h["tp_pct"] * 1.5]
                if len(runners) / len(tp_hits) > 0.4:
                    # Price runs after TP — consider wider TP
                    self._optimal_tp_pct = min(8.0, self._optimal_tp_pct * (1 + self.adaptation_rate))
                    logger.info(f"OPTIMIZER: Widening TP to {self._optimal_tp_pct:.2f}% (runners detected)")
                else:
                    # TP is well-calibrated
                    pass
            else:
                # TP hits are losing — very unusual, widen TP
                self._optimal_tp_pct = min(8.0, self._optimal_tp_pct * (1 + self.adaptation_rate * 2))
                logger.info(f"OPTIMIZER: Widening TP to {self._optimal_tp_pct:.2f}% (TP hits losing)")

        # Adjust based on missed profits (trades that hit SL but had higher max profit)
        missed = [h for h in self._sl_history if h["exit_reason"] == "STOP_LOSS" and h["max_profit"] > h["tp_pct"]]
        if len(missed) >= 3:
            # Trades that could have hit TP but hit SL instead
            # Might need wider SL or tighter entry
            avg_missed = sum(h["max_profit"] for h in missed) / len(missed)
            if avg_missed > self._optimal_tp_pct:
                self._optimal_sl_pct = min(5.0, self._optimal_sl_pct * 1.1)
                logger.info(f"OPTIMIZER: Widening SL to {self._optimal_sl_pct:.2f}% (missed profits)")

        # Ensure R:R stays reasonable
        self._optimal_rr_ratio = self._optimal_tp_pct / max(self._optimal_sl_pct, 0.1)
        if self._optimal_rr_ratio < 1.5:
            self._optimal_tp_pct = self._optimal_sl_pct * 1.5
            logger.info(f"OPTIMIZER: Adjusted TP to maintain R:R = 1.5")
        elif self._optimal_rr_ratio > 4.0:
            self._optimal_tp_pct = self._optimal_sl_pct * 4.0
            logger.info(f"OPTIMIZER: Capped TP to maintain R:R = 4.0")

        self._last_adaptation = now
        self._save()
        logger.info(f"OPTIMIZER ADAPTED: SL={self._optimal_sl_pct:.2f}%, TP={self._optimal_tp_pct:.2f}%, R:R={self._optimal_rr_ratio:.2f}")
        return self._optimal_sl_pct, self._optimal_tp_pct

    def get_recommended_sl_tp(self, volatility_atr_pct: float = None) -> Tuple[float, float]:
        """Get recommended SL/TP, optionally adjusted for current volatility."""
        sl = self._optimal_sl_pct
        tp = self._optimal_tp_pct
        if volatility_atr_pct:
            # Adjust SL based on ATR — if ATR is high, need wider SL
            if volatility_atr_pct > sl * 1.5:
                sl = volatility_atr_pct * 1.2
                logger.info(f"OPTIMIZER: Volatility-adjusted SL={sl:.2f}% (ATR={volatility_atr_pct:.2f}%)")
            elif volatility_atr_pct < sl * 0.3:
                sl = max(0.5, volatility_atr_pct * 2.0)
                logger.info(f"OPTIMIZER: Tightened SL={sl:.2f}% (low ATR={volatility_atr_pct:.2f}%)")
        return round(sl, 2), round(tp, 2)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "optimal_sl_pct": self._optimal_sl_pct,
            "optimal_tp_pct": self._optimal_tp_pct,
            "rr_ratio": self._optimal_rr_ratio,
            "samples": len(self._sl_history),
            "last_adaptation": self._last_adaptation,
        }
