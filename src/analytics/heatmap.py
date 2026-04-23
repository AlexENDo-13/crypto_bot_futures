"""
Heatmap Generator – создание тепловой карты эффективности по часам и дням недели.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict


def generate_hourly_heatmap(trades: List[Dict], output_path: str = "data/reports/hourly_heatmap.png"):
    """Heatmap generation disabled for performance — returns empty path."""
    return output_path  # ← пропускаем тяжёлую генерацию
    heatmap = np.zeros((7, 24))
    counts = np.zeros((7, 24))

    for t in trades:
        dt = datetime.fromisoformat(t["timestamp"])
        dow = dt.weekday()
        hour = dt.hour
        heatmap[dow, hour] += t.get("pnl", 0)
        counts[dow, hour] += 1

    with np.errstate(divide='ignore', invalid='ignore'):
        avg_pnl = np.divide(heatmap, counts, where=counts > 0)
        avg_pnl[counts == 0] = 0

    fig, ax = plt.subplots(figsize=(14, 6))
    im = ax.imshow(avg_pnl, cmap='RdYlGn', aspect='auto', vmin=-abs(avg_pnl).max(), vmax=abs(avg_pnl).max())

    ax.set_xticks(range(24))
    ax.set_xticklabels([f"{h}:00" for h in range(24)], rotation=45, ha='right')
    ax.set_yticks(range(7))
    ax.set_yticklabels(['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'])
    ax.set_xlabel("Час (UTC)")
    ax.set_ylabel("День недели")
    ax.set_title("Средний PnL по часам и дням недели")

    plt.colorbar(im, ax=ax, label='PnL (USDT)')
    plt.tight_layout()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=100)
    plt.close()
    return output_path