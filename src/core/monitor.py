"""
CryptoBot v9.0 - System Monitor
Features: Performance tracking, health checks, anomaly detection,
          automatic recovery suggestions
"""
import logging
import time
from typing import Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

@dataclass
class CycleMetrics:
    cycle_number: int
    start_time: float
    end_time: float = 0
    scan_time: float = 0
    signal_count: int = 0
    trade_count: int = 0
    error_count: int = 0
    api_latency: float = 0
    memory_usage: float = 0

class SystemMonitor:
    """Self-monitoring system for bot health."""

    def __init__(self):
        self.logger = logging.getLogger("CryptoBot.Monitor")
        self.cycles: List[CycleMetrics] = []
        self.current_cycle: CycleMetrics = None
        self.total_errors = 0
        self.total_scans = 0
        self.total_signals = 0
        self.total_trades = 0
        self.anomalies: List[Dict] = []
        self._lock = asyncio.Lock()
        self.logger.info("SystemMonitor v9.0 initialized")

    def start_cycle(self):
        self.current_cycle = CycleMetrics(
            cycle_number=len(self.cycles) + 1,
            start_time=time.time()
        )

    def end_cycle(self):
        if self.current_cycle:
            self.current_cycle.end_time = time.time()
            self.cycles.append(self.current_cycle)
            if len(self.cycles) > 1000:
                self.cycles = self.cycles[-500:]
            self.current_cycle = None

    def record_error(self):
        self.total_errors += 1
        if self.current_cycle:
            self.current_cycle.error_count += 1

    def record_stats(self, stats: Dict[str, Any]):
        if self.current_cycle:
            self.current_cycle.signal_count = stats.get("signals_found", 0)
            self.current_cycle.trade_count = stats.get("trades_executed", 0)

    def get_performance_summary(self) -> Dict[str, Any]:
        if not self.cycles:
            return {}
        recent = self.cycles[-50:]
        avg_scan = sum(c.end_time - c.start_time for c in recent if c.end_time > 0) / len(recent)
        avg_latency = sum(c.api_latency for c in recent) / len(recent)
        error_rate = sum(c.error_count for c in recent) / len(recent)

        return {
            "total_cycles": len(self.cycles),
            "avg_cycle_time": round(avg_scan, 2),
            "avg_api_latency": round(avg_latency * 1000, 1),  # ms
            "error_rate_per_cycle": round(error_rate, 2),
            "total_errors": self.total_errors,
            "uptime_hours": round((time.time() - self.cycles[0].start_time) / 3600, 1) if self.cycles else 0,
            "health_score": max(0, 100 - int(error_rate * 20) - int(avg_latency * 10)),
            "status": "healthy" if error_rate < 0.5 and avg_latency < 2 else "degraded" if error_rate < 2 else "critical"
        }

    def detect_anomalies(self) -> List[Dict]:
        anomalies = []
        if len(self.cycles) < 10:
            return anomalies

        recent = self.cycles[-10:]
        avg_time = sum(c.end_time - c.start_time for c in recent if c.end_time > 0) / len(recent)

        for cycle in recent:
            duration = cycle.end_time - cycle.start_time if cycle.end_time > 0 else 0
            if duration > avg_time * 3:
                anomalies.append({
                    "type": "slow_cycle",
                    "cycle": cycle.cycle_number,
                    "duration": round(duration, 2),
                    "expected": round(avg_time, 2)
                })
            if cycle.error_count > 3:
                anomalies.append({
                    "type": "high_errors",
                    "cycle": cycle.cycle_number,
                    "errors": cycle.error_count
                })

        self.anomalies = anomalies
        return anomalies

    def get_recovery_suggestions(self) -> List[str]:
        suggestions = []
        summary = self.get_performance_summary()

        if summary.get("error_rate_per_cycle", 0) > 1:
            suggestions.append("High error rate detected. Check API connectivity and credentials.")
        if summary.get("avg_api_latency", 0) > 1000:
            suggestions.append("High API latency. Consider reducing scan frequency or symbol count.")
        if summary.get("health_score", 100) < 50:
            suggestions.append("Health score critical. Consider restarting bot or switching to testnet.")

        return suggestions
