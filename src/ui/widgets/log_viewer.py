"""
Log Viewer Widget – отображение логов с фильтрацией.
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QComboBox, QPushButton
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QTextCursor


class LogViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.all_logs = []
        self.filter_level = "ALL"
        self.search_text = ""
        self.auto_scroll = True

    def setup_ui(self):
        layout = QVBoxLayout(self)

        filter_layout = QHBoxLayout()
        self.level_combo = QComboBox()
        self.level_combo.addItems(["ALL", "INFO", "WARNING", "ERROR", "SUCCESS", "SIGNALS"])
        self.level_combo.currentTextChanged.connect(self.on_level_changed)
        filter_layout.addWidget(self.level_combo)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск...")
        self.search_edit.textChanged.connect(self.on_search_changed)
        filter_layout.addWidget(self.search_edit)

        self.clear_btn = QPushButton("Очистить")
        self.clear_btn.clicked.connect(self.clear_logs)
        filter_layout.addWidget(self.clear_btn)

        self.auto_scroll_btn = QPushButton("⏸ Автопрокрутка")
        self.auto_scroll_btn.setCheckable(True)
        self.auto_scroll_btn.setChecked(True)
        self.auto_scroll_btn.clicked.connect(self.toggle_autoscroll)
        filter_layout.addWidget(self.auto_scroll_btn)

        layout.addLayout(filter_layout)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.document().setMaximumBlockCount(2000)
        layout.addWidget(self.text_edit)

    def on_level_changed(self, level):
        self.filter_level = level
        self.refresh_display()

    def on_search_changed(self, text):
        self.search_text = text.lower()
        self.refresh_display()

    def refresh_display(self):
        self.text_edit.clear()
        for msg, level in self.all_logs:
            if self.filter_level != "ALL" and level != self.filter_level:
                continue
            if self.search_text and self.search_text not in msg.lower():
                continue
            self._append_colored(msg, level)

    def _append_colored(self, message: str, level: str):
        color_map = {
            "INFO": "#C9D1D9", "WARNING": "#D29922", "ERROR": "#F85149",
            "SUCCESS": "#3FB950", "SIGNALS": "#388BFD"
        }
        color = color_map.get(level, "#C9D1D9")
        html = f'<span style="color:{color};">{message}</span>'
        self.text_edit.append(html)
        if self.auto_scroll:
            self.text_edit.moveCursor(QTextCursor.End)

    def append_log(self, message: str, level: str = "INFO"):
        self.all_logs.append((message, level))
        if self.filter_level == "ALL" or level == self.filter_level:
            if not self.search_text or self.search_text in message.lower():
                self._append_colored(message, level)

    def clear_logs(self):
        self.all_logs.clear()
        self.text_edit.clear()

    def toggle_autoscroll(self):
        self.auto_scroll = not self.auto_scroll
        self.auto_scroll_btn.setText("⏸ Автопрокрутка" if self.auto_scroll else "▶ Автопрокрутка откл")