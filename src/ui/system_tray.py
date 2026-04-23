from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon

class SystemTray:
    def __init__(self, app, window, logger):
        self.app = app
        self.window = window
        self.logger = logger

    def show(self):
        pass
