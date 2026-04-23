"""
System Monitor Page – CPU, RAM, диск, API latency.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QProgressBar, QGroupBox)
from PyQt5.QtCore import QTimer
import psutil


class SystemMonitorPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_metrics)
        self.timer.start(2000)
        self.engine = None

    def setup_ui(self):
        layout = QVBoxLayout(self)

        cpu_group = QGroupBox("Процессор")
        cpu_layout = QGridLayout()
        self.cpu_label = QLabel("0%")
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setTextVisible(False)
        cpu_layout.addWidget(QLabel("Загрузка:"), 0, 0)
        cpu_layout.addWidget(self.cpu_label, 0, 1)
        cpu_layout.addWidget(self.cpu_bar, 0, 2)
        cpu_group.setLayout(cpu_layout)
        layout.addWidget(cpu_group)

        ram_group = QGroupBox("Оперативная память")
        ram_layout = QGridLayout()
        self.ram_label = QLabel("0/0 GB")
        self.ram_bar = QProgressBar()
        self.ram_bar.setTextVisible(False)
        ram_layout.addWidget(QLabel("Использовано:"), 0, 0)
        ram_layout.addWidget(self.ram_label, 0, 1)
        ram_layout.addWidget(self.ram_bar, 0, 2)
        ram_group.setLayout(ram_layout)
        layout.addWidget(ram_group)

        disk_group = QGroupBox("Диск (C:)")
        disk_layout = QGridLayout()
        self.disk_label = QLabel("0/0 GB")
        self.disk_bar = QProgressBar()
        self.disk_bar.setTextVisible(False)
        disk_layout.addWidget(QLabel("Занято:"), 0, 0)
        disk_layout.addWidget(self.disk_label, 0, 1)
        disk_layout.addWidget(self.disk_bar, 0, 2)
        disk_group.setLayout(disk_layout)
        layout.addWidget(disk_group)

        api_group = QGroupBox("API BingX")
        api_layout = QGridLayout()
        self.api_latency_label = QLabel("— ms")
        api_layout.addWidget(QLabel("Задержка:"), 0, 0)
        api_layout.addWidget(self.api_latency_label, 0, 1)
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        layout.addStretch()

    def set_engine(self, engine):
        self.engine = engine

    def update_metrics(self):
        cpu = psutil.cpu_percent()
        self.cpu_label.setText(f"{cpu:.1f}%")
        self.cpu_bar.setValue(int(cpu))

        mem = psutil.virtual_memory()
        used_gb = mem.used / (1024**3)
        total_gb = mem.total / (1024**3)
        self.ram_label.setText(f"{used_gb:.1f}/{total_gb:.1f} GB")
        self.ram_bar.setValue(int(mem.percent))

        disk = psutil.disk_usage('C:\\')
        used_gb = disk.used / (1024**3)
        total_gb = disk.total / (1024**3)
        self.disk_label.setText(f"{used_gb:.1f}/{total_gb:.1f} GB")
        self.disk_bar.setValue(int(disk.percent))

        if self.engine and hasattr(self.engine, 'profiler'):
            latency = self.engine.profiler.get_avg_latency()
            self.api_latency_label.setText(f"{latency:.0f} ms")