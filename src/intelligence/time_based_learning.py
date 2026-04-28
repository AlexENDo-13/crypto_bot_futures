#!/usr/bin/env python3
"""
Time-Based Learning (B3) — knows the best time to trade.
Tracks win rate by hour and weekday, blocks trading in bad windows.
"""
import json
import os
import time
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger("CryptoBot.TimeLearning")

class TimeBasedLearning:
    def __init__(self, data_path: str = "logs/time_learning.json",
                 min_samples_per_slot: int = 3,
                 bad_wr_threshold: float = 35.0):
        self.data_path = data_path
        self.min_samples = min_samples_per_slot
        self.bad_wr_threshold = bad_wr_threshold
        self._hour_stats: Dict[int, Dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0.0})
        self._weekday_stats: Dict[int, Dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0.0})
        self._month_stats: Dict[int, Dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0.0})
        self._session_scores: Dict[str, float] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.get("hours", {}).items():
                        self._hour_stats[int(k)] = v
                    for k, v in data.get("weekdays", {}).items():
                        self._weekday_stats[int(k)] = v
                logger.info(f"Time learning loaded: {len(self._hour_stats)} hours, {len(self._weekday_stats)} weekdays")
            except Exception as e:
                logger.error(f"Time learning load error: {e}")

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump({
                    "hours": {str(k): v for k, v in self._hour_stats.items()},
                    "weekdays": {str(k): v for k, v in self._weekday_stats.items()},
                    "last_update": time.time()
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Time learning save error: {e}")

    def record_trade(self, pnl: float, entry_time_iso: str = ""):
        """Record trade outcome with its entry time."""
        try:
            if entry_time_iso:
                dt = datetime.fromisoformat(entry_time_iso.replace("Z", "+00:00"))
            else:
                dt = datetime.utcnow()
            hour = dt.hour
            weekday = dt.weekday()
        except Exception:
            dt = datetime.utcnow()
            hour = dt.hour
            weekday = dt.weekday()

        is_win = pnl > 0
        self._hour_stats[hour]["trades"] += 1
        self._hour_stats[hour]["wins"] += 1 if is_win else 0
        self._hour_stats[hour]["pnl"] += pnl

        self._weekday_stats[weekday]["trades"] += 1
        self._weekday_stats[weekday]["wins"] += 1 if is_win else 0
        self._weekday_stats[weekday]["pnl"] += pnl

        if sum(self._hour_stats[h]["trades"] for h in self._hour_stats) % 10 == 0:
            self._save()

    def get_current_score(self) -> float:
        """Return 0-100 score for current time window."""
        now = datetime.utcnow()
        hour = now.hour
        weekday = now.weekday()

        hour_wr = self._get_win_rate(self._hour_stats, hour)
        day_wr = self._get_win_rate(self._weekday_stats, weekday)

        # Weight: hour 60%, day 40%
        score = hour_wr * 0.6 + day_wr * 0.4
        return min(100, max(0, score))

    def _get_win_rate(self, stats_dict, key):
        stats = stats_dict.get(key, {"trades": 0, "wins": 0})
        if stats["trades"] < self.min_samples:
            return 50.0  # Neutral if not enough data
        return (stats["wins"] / stats["trades"]) * 100

    def is_good_time_to_trade(self) -> Tuple[bool, str]:
        """Check if current time is good for trading."""
        score = self.get_current_score()
        now = datetime.utcnow()
        hour = now.hour
        weekday = now.weekday()

        hour_wr = self._get_win_rate(self._hour_stats, hour)
        day_wr = self._get_win_rate(self._weekday_stats, weekday)

        if score >= 55:
            return True, f"GOOD time (score={score:.0f}, hour WR={hour_wr:.0f}%, day WR={day_wr:.0f}%)"
        elif score >= 40:
            return True, f"NEUTRAL time (score={score:.0f}, hour WR={hour_wr:.0f}%, day WR={day_wr:.0f}%)"
        else:
            return False, f"BAD time (score={score:.0f}, hour WR={hour_wr:.0f}%, day WR={day_wr:.0f}%) — trading paused"

    def get_best_windows(self) -> Dict[str, Any]:
        """Return best trading windows."""
        hours = []
        for h in range(24):
            wr = self._get_win_rate(self._hour_stats, h)
            trades = self._hour_stats.get(h, {}).get("trades", 0)
            hours.append({"hour": h, "win_rate": wr, "trades": trades})
        hours.sort(key=lambda x: x["win_rate"], reverse=True)

        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        weekdays = []
        for d in range(7):
            wr = self._get_win_rate(self._weekday_stats, d)
            trades = self._weekday_stats.get(d, {}).get("trades", 0)
            weekdays.append({"day": days[d], "win_rate": wr, "trades": trades})
        weekdays.sort(key=lambda x: x["win_rate"], reverse=True)

        return {
            "best_hours": [h for h in hours if h["win_rate"] > 55][:5],
            "worst_hours": [h for h in hours if h["win_rate"] < 40][:5],
            "best_days": [d for d in weekdays if d["win_rate"] > 55][:3],
            "worst_days": [d for d in weekdays if d["win_rate"] < 40][:3],
            "current_score": self.get_current_score(),
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "current_score": self.get_current_score(),
            "hours_tracked": len(self._hour_stats),
            "weekdays_tracked": len(self._weekday_stats),
            "best_windows": self.get_best_windows(),
        }
