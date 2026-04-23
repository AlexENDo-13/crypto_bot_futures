"""
Profiler – замеры производительности.
"""

import time
import psutil
from typing import List, Dict
from src.core.logger import BotLogger


class Profiler:
    def __init__(self, logger: BotLogger, config: Dict):
        self.logger = logger
        self.latencies: List[float] = []
        self.cpu_samples: List[float] = []
        self.ram_samples: List[float] = []

    def record_api_latency(self, ms: float):
        self.latencies.append(ms)
        if len(self.latencies) > 10:
            self.latencies.pop(0)

    def record_system_metrics(self):
        self.cpu_samples.append(psutil.cpu_percent(interval=0.1))
        self.ram_samples.append(psutil.virtual_memory().percent)
        if len(self.cpu_samples) > 10:
            self.cpu_samples.pop(0)
            self.ram_samples.pop(0)

    def get_avg_latency(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0.0

    def get_avg_cpu(self) -> float:
        return sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0.0

    def get_avg_ram(self) -> float:
        return sum(self.ram_samples) / len(self.ram_samples) if self.ram_samples else 0.0