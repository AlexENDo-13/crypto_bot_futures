"""
Pie Chart Widget – вес стратегий.
"""

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QSizePolicy


class PieChart(FigureCanvas):
    def __init__(self, parent=None, width=4, height=3, dpi=100):
        self.figure = Figure(figsize=(width, height), dpi=dpi, facecolor='#161B22')
        super().__init__(self.figure)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor('#161B22')
        self.ax.set_title("Веса стратегий", color='#C9D1D9', fontsize=10)
        self.figure.tight_layout()

    def set_weights(self, weights: dict):
        self.ax.clear()
        if not weights or sum(weights.values()) == 0:
            self.ax.text(0.5, 0.5, 'Нет данных', ha='center', va='center', color='#8B949E')
            self.draw()
            return

        labels = list(weights.keys())
        sizes = list(weights.values())
        colors = ['#388BFD', '#3FB950', '#D29922', '#F85149', '#8B949E'][:len(labels)]
        explode = [0.05] * len(labels)

        wedges, texts, autotexts = self.ax.pie(
            sizes, explode=explode, labels=labels, autopct='%1.1f%%',
            colors=colors, startangle=90,
            textprops={'color': '#C9D1D9', 'fontsize': 8}
        )
        for autotext in autotexts:
            autotext.set_color('#0D1117')
            autotext.set_fontweight('bold')
        self.ax.set_title("Веса стратегий", color='#C9D1D9', fontsize=10)
        self.draw()