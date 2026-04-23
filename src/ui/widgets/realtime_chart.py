"""
Realtime Chart Widget – график PnL.
"""

import pyqtgraph as pg
from collections import deque


class RealtimeChart(pg.PlotWidget):
    def __init__(self, max_points=200, parent=None):
        super().__init__(parent)
        self.max_points = max_points
        self.data = deque(maxlen=max_points)
        self.setLabel('left', 'PnL', units='USDT')
        self.setLabel('bottom', 'Сделки (номер)')
        self.setTitle('Нереализованный PnL')
        self.showGrid(x=True, y=True, alpha=0.3)
        self.setBackground('#161B22')
        self.getAxis('left').setPen('w')
        self.getAxis('bottom').setPen('w')
        self.curve = self.plot(pen=pg.mkPen(color='#3FB950', width=2))

    def update_data(self, pnl_value: float):
        self.data.append(pnl_value)
        self.curve.setData(list(range(len(self.data))), list(self.data))
        if len(self.data) > 1:
            min_y, max_y = min(self.data), max(self.data)
            if min_y == max_y:
                min_y -= 1
                max_y += 1
            self.setYRange(min_y, max_y, padding=0.1)

    def clear_data(self):
        self.data.clear()
        self.curve.clear()