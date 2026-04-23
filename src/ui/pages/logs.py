"""
Страница отображения логов в GUI
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton, QComboBox
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor, QTextCursor
import logging


class LogsPage(QWidget):
    """Виджет для отображения логов с фильтрацией по уровням"""

    # Сигнал для безопасного добавления лога из другого потока
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.init_ui()
        # Подключаем сигнал к слоту, чтобы обновлять GUI из любого потока
        self.log_signal.connect(self._append_log)

    def init_ui(self):
        layout = QVBoxLayout()

        # Панель управления
        control_layout = QHBoxLayout()

        # Кнопка очистки
        self.btn_clear = QPushButton("Очистить")
        self.btn_clear.clicked.connect(self.clear_logs)
        control_layout.addWidget(self.btn_clear)

        # Фильтр уровня логов
        self.combo_level = QComboBox()
        self.combo_level.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.combo_level.setCurrentText("INFO")
        control_layout.addWidget(self.combo_level)
        control_layout.addStretch()
        layout.addLayout(control_layout)

        # Текстовое поле для логов
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        font = QFont("Courier New", 9)
        self.text_log.setFont(font)
        self.text_log.setStyleSheet("background-color: #1e1e1e; color: #cccccc;")
        layout.addWidget(self.text_log)

        self.setLayout(layout)

    def add_log(self, message: str):
        """
        Основной метод для добавления лога.
        Безопасно вызывается из любого потока (использует сигнал).
        """
        self.log_signal.emit(message)

    def _append_log(self, message: str):
        """Реальное добавление текста в виджет (выполняется в основном потоке)"""
        # Определяем цвет по уровню (можно расширить)
        color_map = {
            "DEBUG": "#888888",
            "INFO": "#cccccc",
            "WARNING": "#e6b800",
            "ERROR": "#ff4444",
            "CRITICAL": "#ff0000",
        }

        # Определяем уровень из сообщения (ожидаем формат как у BotLogger)
        level = "INFO"
        for lvl in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            if lvl in message:
                level = lvl
                break

        # Применяем фильтр
        selected = self.combo_level.currentText()
        if selected != "ALL" and selected != level:
            return

        # Добавляем цветной текст
        color = color_map.get(level, "#cccccc")
        self.text_log.setTextColor(QColor(color))
        self.text_log.append(message)
        # Прокручиваем вниз
        self.text_log.moveCursor(QTextCursor.End)

    def clear_logs(self):
        """Очистка всех логов"""
        self.text_log.clear()
