"""
Страница логов бота
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QPushButton, QComboBox, QLabel, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QTextCursor, QColor

from src.core.logger import BotLogger

class LogsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.logger = BotLogger("LogsUI")
        self.init_ui()

        # Таймер обновления логов
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_logs)
        self.update_timer.start(1000)  # каждую секунду

        self._last_count = 0

    def init_ui(self):
        layout = QVBoxLayout()

        # Панель управления
        controls = QHBoxLayout()

        self.level_filter = QComboBox()
        self.level_filter.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_filter.currentTextChanged.connect(self._filter_logs)
        controls.addWidget(QLabel("Уровень:"))
        controls.addWidget(self.level_filter)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск в логах...")
        self.search_input.textChanged.connect(self._filter_logs)
        controls.addWidget(self.search_input)

        self.btn_clear = QPushButton("🗑️ Очистить")
        self.btn_clear.clicked.connect(self._clear_logs)
        controls.addWidget(self.btn_clear)

        self.btn_pause = QPushButton("⏸ Пауза")
        self.btn_pause.setCheckable(True)
        self.btn_pause.clicked.connect(self._toggle_pause)
        controls.addWidget(self.btn_pause)

        controls.addStretch()
        layout.addLayout(controls)

        # Текстовое поле логов
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.WidgetWidth)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #3c3c3c;
            }
        """)
        layout.addWidget(self.log_text)

        # Статус
        self.status_label = QLabel("Логи: 0 записей")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def _update_logs(self):
        """Обновляет отображение логов из очереди BotLogger"""
        if self.btn_pause.isChecked():
            return

        try:
            queue = self.logger.get_queue()
            current_count = queue.qsize()

            if current_count == self._last_count:
                return

            # Получаем новые сообщения
            messages = []
            temp = []
            while not queue.empty():
                try:
                    item = queue.get_nowait()
                    messages.append(item)
                    temp.append(item)
                except:
                    break

            # Возвращаем обратно в очередь
            for item in temp:
                queue.put(item)

            self._last_count = current_count
            self._filter_logs()

        except Exception as e:
            pass  # Тихо игнорируем ошибки обновления

    def _filter_logs(self):
        """Фильтрует логи по уровню и поиску"""
        level = self.level_filter.currentText()
        search = self.search_input.text().lower()

        try:
            queue = self.logger.get_queue()

            # Собираем все сообщения
            all_messages = []
            temp = []
            while not queue.empty():
                try:
                    item = queue.get_nowait()
                    all_messages.append(item)
                    temp.append(item)
                except:
                    break

            # Возвращаем обратно
            for item in temp:
                queue.put(item)

            # Фильтруем
            filtered = []
            for level_name, msg in all_messages:
                if level != "ALL" and level_name != level:
                    continue
                if search and search not in msg.lower():
                    continue
                filtered.append((level_name, msg))

            # Отображаем
            self.log_text.clear()
            for level_name, msg in filtered[-500:]:  # Последние 500
                self._append_colored_log(level_name, msg)

            self.status_label.setText(f"Логи: {len(filtered)} записей (всего: {len(all_messages)})")

        except Exception:
            pass

    def _append_colored_log(self, level, msg):
        """Добавляет цветную строку лога"""
        colors = {
            "DEBUG": "#808080",
            "INFO": "#4FC1FF",
            "WARNING": "#FFCC00",
            "ERROR": "#F44336",
            "CRITICAL": "#FF1744",
        }
        color = colors.get(level, "#d4d4d4")

        self.log_text.append(f'<span style="color: {color}">[{level}]</span> {msg}')

        # Автоскролл вниз
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _clear_logs(self):
        """Очищает отображение (не очередь)"""
        self.log_text.clear()
        self.status_label.setText("Логи: очищено")

    def _toggle_pause(self, checked):
        """Пауза/возобновление обновления"""
        if checked:
            self.btn_pause.setText("▶ Продолжить")
        else:
            self.btn_pause.setText("⏸ Пауза")
            self._update_logs()
