"""
Logs Page – просмотр логов.
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout
from src.ui.widgets.log_viewer import LogViewer


class LogsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.log_viewer = LogViewer()
        layout.addWidget(self.log_viewer)

    def append_log(self, message: str, level: str = "INFO"):
        self.log_viewer.append_log(message, level)