from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox,
    QFormLayout, QMessageBox, QFileDialog, QTabWidget, QScrollArea,
    QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
    QInputDialog
)
from PyQt5.QtCore import pyqtSignal
from src.config.settings import Settings
from pathlib import Path
import json
import asyncio
from src.utils.ai_exporter import AIExporter

class ConfigPanel(QWidget):
    config_updated = pyqtSignal()

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        main_layout = QVBoxLayout()

        quick_group = QGroupBox("Интерфейс")
        quick_layout = QHBoxLayout()
        self.sound_enabled_check = QCheckBox("Звуки")
        quick_layout.addWidget(self.sound_enabled_check)
        self.voice_enabled_check = QCheckBox("Голосовые оповещения")
        quick_layout.addWidget(self.voice_enabled_check)
        quick_layout.addStretch()
        quick_group.setLayout(quick_layout)
        main_layout.addWidget(quick_group)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_api_trading_tab(), "🔑 API & Торговля")
        self.tabs.addTab(self._create_filters_risk_tab(), "📊 Фильтры & Риски")
        self.tabs.addTab(self._create_timeframe_tab(), "📈 Таймфреймы")
        self.tabs.addTab(self._create_advanced_tab(), "🧠 Стратегии")
        self.tabs.addTab(self._create_notifications_tab(), "📱 Уведомления")

        main_layout.addWidget(self.tabs)

        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 Сохранить")
        self.save_btn.clicked.connect(self.save_settings)
        self.export_btn = QPushButton("📁 Экспорт конфига")
        self.export_btn.clicked.connect(self.export_config)
        self.import_btn = QPushButton("📂 Импорт конфига")
        self.import_btn.clicked.connect(self.import_config)
        self.ai_export_btn = QPushButton("📄 Экспорт для ИИ")
        self.ai_export_btn.clicked.connect(self.export_for_ai)
        self.ai_export_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")

        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(self.ai_export_btn)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)

    def _create_scrollable_widget(self, content_widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)
        return scroll

    def _create_api_trading_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()

        api_group = QGroupBox("API Ключи BingX")
        api_layout = QFormLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        api_layout.addRow("API Key:", self.api_key_input)
        self.api_secret_input = QLineEdit()
        self.api_secret_input.setEchoMode(QLineEdit.Password)
        api_layout.addRow("API Secret:", self.api_secret_input)
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        trade_group = QGroupBox("Торговые параметры")
        trade_layout = QFormLayout()
        self.demo_mode_check = QCheckBox()
        self.demo_mode_check.setChecked(True)
        trade_layout.addRow("Демо-режим:", self.demo_mode_check)
        self.virtual_balance_input = QDoubleSpinBox()
        self.virtual_balance_input.setRange(10, 100000)
        self.virtual_balance_input.setDecimals(2)
        trade_layout.addRow("Виртуальный баланс (USDT):", self.virtual_balance_input)
        self.risk_per_trade_input = QDoubleSpinBox()
        self.risk_per_trade_input.setRange(0.5, 20)
        self.risk_per_trade_input.setDecimals(1)
        self.risk_per_trade_input.setSuffix("%")
        trade_layout.addRow("Риск на сделку:", self.risk_per_trade_input)
        self.max_leverage_input = QSpinBox()
        self.max_leverage_input.setRange(1, 20)
        trade_layout.addRow("Макс. плечо:", self.max_leverage_input)
        self.scan_interval_input = QSpinBox()
        self.scan_interval_input.setRange(1, 240)
        self.scan_interval_input.setSuffix(" мин")
        trade_layout.addRow("Интервал сканирования:", self.scan_interval_input)
        self.max_positions_input = QSpinBox()
        self.max_positions_input.setRange(1, 10)
        trade_layout.addRow("Макс. открытых позиций:", self.max_positions_input)
        self.max_daily_trades_input = QSpinBox()
        self.max_daily_trades_input.setRange(1, 100)
        trade_layout.addRow("Макс. сделок в день:", self.max_daily_trades_input)
        self.daily_profit_target_input = QDoubleSpinBox()
        self.daily_profit_target_input.setRange(0, 100)
        self.daily_profit_target_input.setDecimals(1)
        self.daily_profit_target_input.setSuffix("%")
        trade_layout.addRow("Дневная цель прибыли:", self.daily_profit_target_input)
        self.stop_on_target_check = QCheckBox("Останавливать бота при достижении цели")
        trade_layout.addRow("", self.stop_on_target_check)
        self.force_ignore_session_check = QCheckBox("Игнорировать торговую сессию (для тестов)")
        trade_layout.addRow("", self.force_ignore_session_check)
        trade_group.setLayout(trade_layout)
        layout.addWidget(trade_group)

        layout.addStretch()
        widget.setLayout(layout)
        return self._create_scrollable_widget(widget)

    def _create_filters_risk_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()

        filter_group = QGroupBox("Фильтры отбора пар")
        filter_layout = QFormLayout()
        self.min_volume_input = QDoubleSpinBox()
        self.min_volume_input.setRange(100_000, 100_000_000)
        self.min_volume_input.setDecimals(0)
        self.min_volume_input.setSuffix(" USDT")
        filter_layout.addRow("Мин. объем 24ч:", self.min_volume_input)
        self.min_atr_input = QDoubleSpinBox()
        self.min_atr_input.setRange(0.5, 10)
        self.min_atr_input.setDecimals(1)
        self.min_atr_input.setSuffix("%")
        filter_layout.addRow("Мин. ATR %:", self.min_atr_input)
        self.max_funding_input = QDoubleSpinBox()
        self.max_funding_input.setRange(-0.1, 0.01)
        self.max_funding_input.setDecimals(4)
        self.max_funding_input.setSingleStep(0.001)
        filter_layout.addRow("Макс. ставка финанс.:", self.max_funding_input)
        funding_hint = QLabel(" (положительное значение разрешает вход при фандинге > 0)")
        funding_hint.setStyleSheet("color: #8B949E; font-size: 8pt;")
        filter_layout.addRow("", funding_hint)
        self.min_adx_input = QSpinBox()
        self.min_adx_input.setRange(10, 40)
        filter_layout.addRow("Мин. ADX:", self.min_adx_input)
        self.spread_filter_check = QCheckBox("Фильтр по спреду")
        self.spread_filter_check.setChecked(True)
        filter_layout.addRow("", self.spread_filter_check)
        self.max_spread_input = QDoubleSpinBox()
        self.max_spread_input.setRange(0.05, 5.0)
        self.max_spread_input.setDecimals(2)
        self.max_spread_input.setSuffix("%")
        filter_layout.addRow("Макс. спред:", self.max_spread_input)
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        risk_group = QGroupBox("Управление рисками")
        risk_layout = QVBoxLayout()
        self.anti_martingale_check = QCheckBox("Анти-мартингейл (снижать риск после убытка)")
        self.anti_martingale_check.setChecked(True)
        risk_layout.addWidget(self.anti_martingale_check)
        self.anti_martingale_reduction_input = QDoubleSpinBox()
        self.anti_martingale_reduction_input.setRange(0.1, 1.0)
        self.anti_martingale_reduction_input.setDecimals(2)
        self.anti_martingale_reduction_input.setSingleStep(0.05)
        risk_layout.addWidget(QLabel("Коэф. снижения риска:"))
        risk_layout.addWidget(self.anti_martingale_reduction_input)
        self.weekend_risk_check = QCheckBox("Снижать риск на выходных")
        self.weekend_risk_check.setChecked(True)
        risk_layout.addWidget(self.weekend_risk_check)
        self.weekend_risk_multiplier_input = QDoubleSpinBox()
        self.weekend_risk_multiplier_input.setRange(0.1, 1.0)
        self.weekend_risk_multiplier_input.setDecimals(2)
        risk_layout.addWidget(QLabel("Множитель риска на выходных:"))
        risk_layout.addWidget(self.weekend_risk_multiplier_input)
        self.correlation_limit_check = QCheckBox("Корреляционный лимит (не более 1 в группе)")
        self.correlation_limit_check.setChecked(True)
        risk_layout.addWidget(self.correlation_limit_check)

        risk_form = QFormLayout()
        self.daily_loss_limit_input = QDoubleSpinBox()
        self.daily_loss_limit_input.setRange(1, 30)
        self.daily_loss_limit_input.setDecimals(1)
        self.daily_loss_limit_input.setSuffix("%")
        risk_form.addRow("Дневной лимит убытка:", self.daily_loss_limit_input)
        self.max_orders_per_hour_input = QSpinBox()
        self.max_orders_per_hour_input.setRange(1, 50)
        risk_form.addRow("Макс. ордеров в час:", self.max_orders_per_hour_input)
        self.max_total_risk_input = QDoubleSpinBox()
        self.max_total_risk_input.setRange(5, 50)
        self.max_total_risk_input.setDecimals(1)
        self.max_total_risk_input.setSuffix("%")
        risk_form.addRow("Макс. общий риск:", self.max_total_risk_input)
        self.anti_chase_threshold_input = QDoubleSpinBox()
        self.anti_chase_threshold_input.setRange(0.1, 2.0)
        self.anti_chase_threshold_input.setDecimals(2)
        self.anti_chase_threshold_input.setSuffix("%")
        risk_form.addRow("Anti-chase порог:", self.anti_chase_threshold_input)
        risk_layout.addLayout(risk_form)
        risk_group.setLayout(risk_layout)
        layout.addWidget(risk_group)

        layout.addStretch()
        widget.setLayout(layout)
        return self._create_scrollable_widget(widget)

    def _create_timeframe_tab(self) -> QWidget:
        """Вкладка мультитаймфреймных настроек"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Основной таймфрейм
        main_tf_group = QGroupBox("Основной таймфрейм")
        main_tf_layout = QFormLayout()
        self.timeframe_input = QLineEdit()
        self.timeframe_input.setPlaceholderText("15m")
        main_tf_layout.addRow("Таймфрейм по умолчанию:", self.timeframe_input)
        main_tf_group.setLayout(main_tf_layout)
        layout.addWidget(main_tf_group)

        # Мультитаймфрейм
        mtf_group = QGroupBox("Мультитаймфреймный анализ")
        mtf_layout = QVBoxLayout()

        self.multi_timeframe_check = QCheckBox("Включить мультитаймфрейм")
        self.multi_timeframe_check.setChecked(True)
        mtf_layout.addWidget(self.multi_timeframe_check)

        # Список таймфреймов
        tf_list_layout = QHBoxLayout()
        tf_list_layout.addWidget(QLabel("Таймфреймы:"))
        self.timeframes_list = QListWidget()
        self.timeframes_list.setMaximumHeight(100)
        tf_list_layout.addWidget(self.timeframes_list)

        tf_btn_layout = QVBoxLayout()
        self.add_tf_btn = QPushButton("+ Добавить")
        self.add_tf_btn.clicked.connect(self._add_timeframe)
        self.remove_tf_btn = QPushButton("- Удалить")
        self.remove_tf_btn.clicked.connect(self._remove_timeframe)
        tf_btn_layout.addWidget(self.add_tf_btn)
        tf_btn_layout.addWidget(self.remove_tf_btn)
        tf_list_layout.addLayout(tf_btn_layout)
        mtf_layout.addLayout(tf_list_layout)

        # Веса таймфреймов
        weights_group = QGroupBox("Веса таймфреймов (должны суммироваться в 1.0)")
        weights_layout = QFormLayout()
        self.tf_weights = {}
        for tf in ["15m", "1h", "4h", "1d"]:
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 1.0)
            spin.setDecimals(2)
            spin.setSingleStep(0.1)
            self.tf_weights[tf] = spin
            weights_layout.addRow(f"{tf}:", spin)
        weights_group.setLayout(weights_layout)
        mtf_layout.addWidget(weights_group)

        # Минимальное согласие
        agreement_layout = QFormLayout()
        self.min_agreement_input = QSpinBox()
        self.min_agreement_input.setRange(1, 4)
        self.min_agreement_input.setSuffix(" таймфрейм(ов)")
        agreement_layout.addRow("Мин. согласие для сигнала:", self.min_agreement_input)
        mtf_layout.addLayout(agreement_layout)

        mtf_group.setLayout(mtf_layout)
        layout.addWidget(mtf_group)

        layout.addStretch()
        widget.setLayout(layout)
        return self._create_scrollable_widget(widget)

    def _create_advanced_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()

        ind_group = QGroupBox("Технические индикаторы")
        ind_layout = QVBoxLayout()
        self.bollinger_check = QCheckBox("Bollinger Bands")
        self.bollinger_check.setChecked(True)
        ind_layout.addWidget(self.bollinger_check)
        self.candle_patterns_check = QCheckBox("Свечные паттерны")
        self.candle_patterns_check.setChecked(True)
        ind_layout.addWidget(self.candle_patterns_check)
        self.use_macd_indicator_check = QCheckBox("MACD")
        self.use_macd_indicator_check.setChecked(True)
        ind_layout.addWidget(self.use_macd_indicator_check)
        self.use_ichimoku_indicator_check = QCheckBox("Ichimoku")
        self.use_ichimoku_indicator_check.setChecked(True)
        ind_layout.addWidget(self.use_ichimoku_indicator_check)
        ind_group.setLayout(ind_layout)
        layout.addWidget(ind_group)

        exit_group = QGroupBox("Управление выходом")
        exit_layout = QVBoxLayout()
        self.trailing_stop_check = QCheckBox("Трейлинг-стоп")
        self.trailing_stop_check.setChecked(True)
        exit_layout.addWidget(self.trailing_stop_check)
        self.trailing_stop_distance_input = QDoubleSpinBox()
        self.trailing_stop_distance_input.setRange(0.5, 20.0)
        self.trailing_stop_distance_input.setDecimals(1)
        self.trailing_stop_distance_input.setSuffix("%")
        exit_layout.addWidget(QLabel("Дистанция трейлинга:"))
        exit_layout.addWidget(self.trailing_stop_distance_input)
        self.stepped_tp_check = QCheckBox("Ступенчатый тейк-профит")
        self.stepped_tp_check.setChecked(True)
        exit_layout.addWidget(self.stepped_tp_check)
        self.anti_chase_check = QCheckBox("Анти-догонялка")
        self.anti_chase_check.setChecked(True)
        exit_layout.addWidget(self.anti_chase_check)
        self.dead_weight_check = QCheckBox("Выход по Dead Weight")
        self.dead_weight_check.setChecked(True)
        exit_layout.addWidget(self.dead_weight_check)
        self.adaptive_tp_check = QCheckBox("Адаптивный тейк-профит")
        self.adaptive_tp_check.setChecked(True)
        exit_layout.addWidget(self.adaptive_tp_check)
        exit_group.setLayout(exit_layout)
        layout.addWidget(exit_group)

        pred_group = QGroupBox("Предиктивные модули")
        pred_layout = QVBoxLayout()
        self.trap_detector_check = QCheckBox("Детектор ловушек")
        self.trap_detector_check.setChecked(True)
        pred_layout.addWidget(self.trap_detector_check)
        self.predictive_entry_check = QCheckBox("Предиктивный вход")
        self.predictive_entry_check.setChecked(True)
        pred_layout.addWidget(self.predictive_entry_check)
        self.neural_filter_check = QCheckBox("Нейро-фильтр")
        self.neural_filter_check.setChecked(True)
        pred_layout.addWidget(self.neural_filter_check)
        self.use_neural_predictor_check = QCheckBox("Использовать нейропредиктор (после 50 сделок)")
        self.use_neural_predictor_check.setChecked(True)
        pred_layout.addWidget(self.use_neural_predictor_check)
        pred_group.setLayout(pred_layout)
        layout.addWidget(pred_group)

        perf_group = QGroupBox("Производительность и эволюция")
        perf_layout = QVBoxLayout()
        self.async_scan_check = QCheckBox("Асинхронное сканирование")
        self.async_scan_check.setChecked(True)
        perf_layout.addWidget(self.async_scan_check)
        self.genetic_optimizer_check = QCheckBox("Генетический оптимизатор весов")
        self.genetic_optimizer_check.setChecked(True)
        perf_layout.addWidget(self.genetic_optimizer_check)
        self.self_healing_check = QCheckBox("Самовосстановление")
        self.self_healing_check.setChecked(True)
        perf_layout.addWidget(self.self_healing_check)
        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)

        data_group = QGroupBox("Данные и экспорт")
        data_layout = QVBoxLayout()
        self.export_csv_check = QCheckBox("Экспорт сделок в CSV")
        self.export_csv_check.setChecked(True)
        data_layout.addWidget(self.export_csv_check)
        self.json_logging_check = QCheckBox("Логирование в JSON")
        self.json_logging_check.setChecked(True)
        data_layout.addWidget(self.json_logging_check)
        data_group.setLayout(data_layout)
        layout.addWidget(data_group)

        layout.addStretch()
        widget.setLayout(layout)
        return self._create_scrollable_widget(widget)

    def _create_notifications_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()

        telegram_group = QGroupBox("Telegram")
        telegram_layout = QFormLayout()
        self.telegram_enabled_check = QCheckBox()
        telegram_layout.addRow("Включить:", self.telegram_enabled_check)
        self.telegram_token_input = QLineEdit()
        self.telegram_token_input.setPlaceholderText("Токен бота")
        telegram_layout.addRow("Bot Token:", self.telegram_token_input)
        self.telegram_chat_id_input = QLineEdit()
        self.telegram_chat_id_input.setPlaceholderText("Chat ID")
        telegram_layout.addRow("Chat ID:", self.telegram_chat_id_input)
        self.telegram_commands_check = QCheckBox("Включить команды (/status, /close, ...)")
        telegram_layout.addRow("", self.telegram_commands_check)
        self.telegram_daily_report_check = QCheckBox("Ежедневный отчёт")
        telegram_layout.addRow("", self.telegram_daily_report_check)

        self.telegram_proxy_url = QLineEdit()
        self.telegram_proxy_url.setPlaceholderText("socks5://user:pass@host:port или http://host:port")
        telegram_layout.addRow("Прокси URL:", self.telegram_proxy_url)

        self.telegram_proxy_rotate = QCheckBox("Авто-ротация прокси (использовать список из интернета)")
        telegram_layout.addRow("", self.telegram_proxy_rotate)

        self.test_telegram_btn = QPushButton("🔔 Проверить Telegram")
        self.test_telegram_btn.clicked.connect(self.test_telegram)
        telegram_layout.addRow("", self.test_telegram_btn)

        telegram_group.setLayout(telegram_layout)
        layout.addWidget(telegram_group)

        discord_group = QGroupBox("Discord")
        discord_layout = QFormLayout()
        self.discord_enabled_check = QCheckBox()
        discord_layout.addRow("Включить:", self.discord_enabled_check)
        self.discord_webhook_input = QLineEdit()
        self.discord_webhook_input.setPlaceholderText("Webhook URL")
        discord_layout.addRow("Webhook URL:", self.discord_webhook_input)
        discord_group.setLayout(discord_layout)
        layout.addWidget(discord_group)

        web_group = QGroupBox("Веб-интерфейс")
        web_layout = QFormLayout()
        self.web_enabled_check = QCheckBox()
        web_layout.addRow("Включить веб-сервер:", self.web_enabled_check)
        self.web_port_input = QSpinBox()
        self.web_port_input.setRange(1000, 65535)
        self.web_port_input.setValue(5000)
        web_layout.addRow("Порт:", self.web_port_input)
        web_group.setLayout(web_layout)
        layout.addWidget(web_group)

        layout.addStretch()
        widget.setLayout(layout)
        return self._create_scrollable_widget(widget)

    def _add_timeframe(self):
        """Добавить таймфрейм в список"""
        tf, ok = QInputDialog.getText(self, "Добавить таймфрейм", 
                                       "Таймфрейм (например: 30m, 2h, 1d):")
        if ok and tf:
            item = QListWidgetItem(tf)
            self.timeframes_list.addItem(item)

    def _remove_timeframe(self):
        """Удалить выбранный таймфрейм"""
        current_row = self.timeframes_list.currentRow()
        if current_row >= 0:
            self.timeframes_list.takeItem(current_row)

    def load_settings(self):
        data = self.settings.data
        self.api_key_input.setText(data.get("api_key", ""))
        self.api_secret_input.setText(data.get("api_secret", ""))
        self.demo_mode_check.setChecked(data.get("demo_mode", True))
        self.virtual_balance_input.setValue(data.get("virtual_balance", 100.0))
        self.risk_per_trade_input.setValue(data.get("max_risk_per_trade", 1.0))
        self.max_leverage_input.setValue(data.get("max_leverage", 2))
        self.scan_interval_input.setValue(data.get("scan_interval_minutes", 5))
        self.max_positions_input.setValue(data.get("max_positions", 2))
        self.max_daily_trades_input.setValue(data.get("max_daily_trades", 10))
        self.daily_profit_target_input.setValue(data.get("daily_profit_target_percent", 5.0))
        self.stop_on_target_check.setChecked(data.get("stop_on_daily_target", True))
        self.force_ignore_session_check.setChecked(data.get("force_ignore_session", False))

        # Таймфреймы
        self.timeframe_input.setText(data.get("timeframe", "15m"))
        self.multi_timeframe_check.setChecked(data.get("use_multi_timeframe", True))

        # Загрузка списка таймфреймов
        self.timeframes_list.clear()
        for tf in data.get("timeframes", ["15m", "1h", "4h"]):
            self.timeframes_list.addItem(QListWidgetItem(tf))

        # Загрузка весов
        weights = data.get("timeframe_weights", {"15m": 0.2, "1h": 0.5, "4h": 0.3})
        for tf, spin in self.tf_weights.items():
            spin.setValue(weights.get(tf, 0.0))

        self.min_agreement_input.setValue(data.get("min_timeframe_agreement", 2))

        self.min_volume_input.setValue(data.get("min_volume_24h_usdt", 200_000))
        self.min_atr_input.setValue(data.get("min_atr_percent", 1.5))
        self.max_funding_input.setValue(data.get("max_funding_rate", 0.0))
        self.min_adx_input.setValue(data.get("min_adx", 20))
        self.spread_filter_check.setChecked(data.get("use_spread_filter", True))
        self.max_spread_input.setValue(data.get("max_spread_percent", 0.3))
        self.anti_martingale_check.setChecked(data.get("anti_martingale_enabled", True))
        self.anti_martingale_reduction_input.setValue(data.get("anti_martingale_risk_reduction", 0.8))
        self.weekend_risk_check.setChecked(data.get("reduce_risk_on_weekends", True))
        self.weekend_risk_multiplier_input.setValue(data.get("weekend_risk_multiplier", 0.5))
        self.correlation_limit_check.setChecked(data.get("correlation_limit_enabled", True))
        self.daily_loss_limit_input.setValue(data.get("daily_loss_limit_percent", 8.0))
        self.max_orders_per_hour_input.setValue(data.get("max_orders_per_hour", 6))
        self.max_total_risk_input.setValue(data.get("max_total_risk_percent", 15.0))
        self.anti_chase_threshold_input.setValue(data.get("anti_chase_threshold_percent", 0.3))
        self.bollinger_check.setChecked(data.get("use_bollinger_filter", True))
        self.candle_patterns_check.setChecked(data.get("use_candle_patterns", True))
        self.use_macd_indicator_check.setChecked(data.get("use_macd_indicator", True))
        self.use_ichimoku_indicator_check.setChecked(data.get("use_ichimoku_indicator", True))
        self.trailing_stop_check.setChecked(data.get("trailing_stop_enabled", True))
        self.trailing_stop_distance_input.setValue(data.get("trailing_stop_distance_percent", 2.0))
        self.stepped_tp_check.setChecked(data.get("use_stepped_take_profit", True))
        self.anti_chase_check.setChecked(data.get("anti_chase_enabled", True))
        self.dead_weight_check.setChecked(data.get("dead_weight_exit_enabled", True))
        self.adaptive_tp_check.setChecked(data.get("adaptive_tp_enabled", True))
        self.trap_detector_check.setChecked(data.get("trap_detector_enabled", True))
        self.predictive_entry_check.setChecked(data.get("predictive_entry_enabled", True))
        self.neural_filter_check.setChecked(data.get("use_neural_filter", True))
        self.use_neural_predictor_check.setChecked(data.get("use_neural_predictor", False))
        self.async_scan_check.setChecked(data.get("use_async_scan", True))
        self.genetic_optimizer_check.setChecked(data.get("use_genetic_optimizer", True))
        self.self_healing_check.setChecked(data.get("self_healing_enabled", True))
        self.export_csv_check.setChecked(data.get("export_trades_csv", True))
        self.json_logging_check.setChecked(data.get("json_logging_enabled", True))
        self.telegram_enabled_check.setChecked(data.get("telegram_enabled", False))
        self.telegram_token_input.setText(data.get("telegram_bot_token", ""))
        self.telegram_chat_id_input.setText(data.get("telegram_chat_id", ""))
        self.telegram_commands_check.setChecked(data.get("telegram_commands_enabled", True))
        self.telegram_daily_report_check.setChecked(data.get("telegram_daily_report_enabled", False))
        self.telegram_proxy_url.setText(data.get("telegram_proxy_url", ""))
        self.telegram_proxy_rotate.setChecked(data.get("telegram_proxy_auto_rotate", False))
        self.discord_enabled_check.setChecked(data.get("discord_enabled", False))
        self.discord_webhook_input.setText(data.get("discord_webhook_url", ""))
        self.web_enabled_check.setChecked(data.get("web_interface_enabled", False))
        self.web_port_input.setValue(data.get("web_interface_port", 5000))
        self.sound_enabled_check.setChecked(data.get("sound_enabled", True))
        self.voice_enabled_check.setChecked(data.get("voice_enabled", False))

    def save_settings(self):
        # Собираем таймфреймы из списка
        timeframes = []
        for i in range(self.timeframes_list.count()):
            timeframes.append(self.timeframes_list.item(i).text())

        # Собираем веса
        weights = {}
        for tf, spin in self.tf_weights.items():
            weights[tf] = spin.value()

        updates = {
            "api_key": self.api_key_input.text(),
            "api_secret": self.api_secret_input.text(),
            "demo_mode": self.demo_mode_check.isChecked(),
            "virtual_balance": self.virtual_balance_input.value(),
            "max_risk_per_trade": self.risk_per_trade_input.value(),
            "max_leverage": self.max_leverage_input.value(),
            "scan_interval_minutes": self.scan_interval_input.value(),
            "max_positions": self.max_positions_input.value(),
            "max_daily_trades": self.max_daily_trades_input.value(),
            "daily_profit_target_percent": self.daily_profit_target_input.value(),
            "stop_on_daily_target": self.stop_on_target_check.isChecked(),
            "force_ignore_session": self.force_ignore_session_check.isChecked(),

            # Таймфреймы
            "timeframe": self.timeframe_input.text(),
            "use_multi_timeframe": self.multi_timeframe_check.isChecked(),
            "timeframes": timeframes,
            "timeframe_weights": weights,
            "min_timeframe_agreement": self.min_agreement_input.value(),

            "min_volume_24h_usdt": self.min_volume_input.value(),
            "min_atr_percent": self.min_atr_input.value(),
            "max_funding_rate": self.max_funding_input.value(),
            "min_adx": self.min_adx_input.value(),
            "use_spread_filter": self.spread_filter_check.isChecked(),
            "max_spread_percent": self.max_spread_input.value(),
            "anti_martingale_enabled": self.anti_martingale_check.isChecked(),
            "anti_martingale_risk_reduction": self.anti_martingale_reduction_input.value(),
            "reduce_risk_on_weekends": self.weekend_risk_check.isChecked(),
            "weekend_risk_multiplier": self.weekend_risk_multiplier_input.value(),
            "correlation_limit_enabled": self.correlation_limit_check.isChecked(),
            "daily_loss_limit_percent": self.daily_loss_limit_input.value(),
            "max_orders_per_hour": self.max_orders_per_hour_input.value(),
            "max_total_risk_percent": self.max_total_risk_input.value(),
            "anti_chase_threshold_percent": self.anti_chase_threshold_input.value(),
            "use_bollinger_filter": self.bollinger_check.isChecked(),
            "use_candle_patterns": self.candle_patterns_check.isChecked(),
            "use_macd_indicator": self.use_macd_indicator_check.isChecked(),
            "use_ichimoku_indicator": self.use_ichimoku_indicator_check.isChecked(),
            "trailing_stop_enabled": self.trailing_stop_check.isChecked(),
            "trailing_stop_distance_percent": self.trailing_stop_distance_input.value(),
            "use_stepped_take_profit": self.stepped_tp_check.isChecked(),
            "anti_chase_enabled": self.anti_chase_check.isChecked(),
            "dead_weight_exit_enabled": self.dead_weight_check.isChecked(),
            "adaptive_tp_enabled": self.adaptive_tp_check.isChecked(),
            "trap_detector_enabled": self.trap_detector_check.isChecked(),
            "predictive_entry_enabled": self.predictive_entry_check.isChecked(),
            "use_neural_filter": self.neural_filter_check.isChecked(),
            "use_neural_predictor": self.use_neural_predictor_check.isChecked(),
            "use_async_scan": self.async_scan_check.isChecked(),
            "use_genetic_optimizer": self.genetic_optimizer_check.isChecked(),
            "self_healing_enabled": self.self_healing_check.isChecked(),
            "export_trades_csv": self.export_csv_check.isChecked(),
            "json_logging_enabled": self.json_logging_check.isChecked(),
            "telegram_enabled": self.telegram_enabled_check.isChecked(),
            "telegram_bot_token": self.telegram_token_input.text(),
            "telegram_chat_id": self.telegram_chat_id_input.text(),
            "telegram_commands_enabled": self.telegram_commands_check.isChecked(),
            "telegram_daily_report_enabled": self.telegram_daily_report_check.isChecked(),
            "telegram_proxy_url": self.telegram_proxy_url.text(),
            "telegram_proxy_auto_rotate": self.telegram_proxy_rotate.isChecked(),
            "discord_enabled": self.discord_enabled_check.isChecked(),
            "discord_webhook_url": self.discord_webhook_input.text(),
            "web_interface_enabled": self.web_enabled_check.isChecked(),
            "web_interface_port": self.web_port_input.value(),
            "sound_enabled": self.sound_enabled_check.isChecked(),
            "voice_enabled": self.voice_enabled_check.isChecked(),
            "dark_theme": True,
        }
        self.settings.update(updates)

        # Обновить движок если он есть
        main_window = self.window()
        if main_window and hasattr(main_window, 'engine') and main_window.engine:
            main_window.engine.settings = self.settings
            if hasattr(main_window.engine, 'max_positions'):
                main_window.engine.max_positions = self.settings.get("max_positions", 2)
            main_window.engine.logger.info(f"⚙️ Конфиг обновлён. max_positions = {self.settings.get('max_positions', 2)}")

        QMessageBox.information(self, "Успех", "Настройки сохранены")
        self.config_updated.emit()

    def export_config(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Экспорт конфигурации", "bot_config.json", "JSON (*.json)")
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings.data, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, "Экспорт", f"Конфигурация сохранена в {file_path}")

    def import_config(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Импорт конфигурации", "", "JSON (*.json)")
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported = json.load(f)
            self.settings.update(imported)
            self.load_settings()
            QMessageBox.information(self, "Импорт", "Конфигурация загружена")
            self.config_updated.emit()

    def export_for_ai(self):
        """Экспорт данных для ИИ-анализа. Использует _stats вместо async вызовов."""
        weights_path = Path("data/models/strategy_weights.json")
        weights_data = {}
        if weights_path.exists():
            try:
                with open(weights_path, 'r', encoding='utf-8') as f:
                    weights_data = json.load(f)
            except:
                pass

        engine_state = None
        main_window = self.window()
        if main_window and hasattr(main_window, 'engine') and main_window.engine:
            eng = main_window.engine

            # Используем _stats вместо async вызовов
            positions_summary = {}
            try:
                # Получаем позиции из _stats если есть
                positions_count = eng._stats.get("positions", 0)
                if positions_count > 0:
                    # Пытаемся получить через executor (только если не async)
                    pass  # Пропускаем async вызов в sync методе
            except Exception:
                pass

            engine_state = {
                "virtual_balance": eng._stats.get("balance", 0),
                "real_balance": 0,
                "demo_mode": eng.settings.get("demo_mode", True),
                "positions_count": eng._stats.get("positions", 0),
                "positions": positions_summary,
                "signals_found": eng._stats.get("signals_found", 0),
                "trades_executed": eng._stats.get("trades_executed", 0),
            }

        exporter = AIExporter(self.settings.data, weights_data, engine_state)
        file_path = exporter.generate_export()
        if file_path:
            QMessageBox.information(self, "Экспорт для ИИ", f"Полный отчёт создан:\n{file_path}")
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось создать экспорт")

    def test_telegram(self):
        if not self.telegram_enabled_check.isChecked():
            QMessageBox.warning(self, "Тест Telegram", "Сначала включите Telegram (поставьте галочку).")
            return

        token = self.telegram_token_input.text().strip()
        chat_id = self.telegram_chat_id_input.text().strip()

        if not token or not chat_id:
            QMessageBox.warning(self, "Тест Telegram", "Введите Bot Token и Chat ID.")
            return

        if ':' not in token or len(token.split(':')) != 2:
            QMessageBox.warning(self, "Тест Telegram", "Неверный формат токена. Должен быть вида: 123456:ABCdef...")
            return

        try:
            int_chat_id = int(chat_id)
        except ValueError:
            QMessageBox.warning(self, "Тест Telegram", "Chat ID должен быть числом (например, 123456789 или -1001234567890).")
            return

        proxy_url = self.telegram_proxy_url.text().strip() or None
        proxy_rotate = self.telegram_proxy_rotate.isChecked()
        use_proxy = bool(proxy_url) or proxy_rotate

        try:
            from src.notifications.telegram_notifier import TelegramNotifier
            from src.core.logger import BotLogger

            logger = BotLogger(level="INFO")

            notifier = TelegramNotifier(
                bot_token=token,
                chat_id=chat_id,
                logger=logger,
                commands_enabled=False,
                proxy_url=proxy_url,
                proxy_auto_rotate=proxy_rotate
            )

            if proxy_rotate:
                from src.utils.auto_recovery import ProxyListUpdater
                updater = ProxyListUpdater(logger)
                proxies = updater.get_proxies()
                if proxies:
                    notifier.set_proxy_list(proxies)
                    logger.info(f"Загружено {len(proxies)} прокси для теста")
                else:
                    reply = QMessageBox.question(
                        self, "Тест Telegram",
                        "Не удалось загрузить список прокси.\n"
                        "Попробовать отправить напрямую (без прокси)?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.Yes:
                        use_proxy = False
                    else:
                        return

            import requests

            def test_api_connection(use_proxy_flag: bool):
                test_url = f"https://api.telegram.org/bot{token}/getMe"
                session = requests.Session()

                if use_proxy_flag:
                    if proxy_rotate and notifier._proxy_list:
                        test_proxy = notifier._get_next_proxy()
                    else:
                        test_proxy = proxy_url

                    if test_proxy:
                        session.proxies = {'http': test_proxy, 'https': test_proxy}
                        logger.debug(f"Тест через прокси: {test_proxy}")

                try:
                    resp = session.get(test_url, timeout=20)
                    return resp, None
                except requests.exceptions.ProxyError as e:
                    return None, f"Ошибка прокси: {str(e)[:200]}..."
                except requests.exceptions.ConnectionError as e:
                    return None, f"Нет соединения: {str(e)[:200]}..."
                except Exception as e:
                    return None, str(e)

            resp = None
            error_msg = None

            if use_proxy:
                resp, error_msg = test_api_connection(True)
                if resp is None and proxy_rotate:
                    for _ in range(min(3, len(notifier._proxy_list))):
                        resp, error_msg = test_api_connection(True)
                        if resp is not None:
                            break

                if resp is None:
                    reply = QMessageBox.question(
                        self, "Тест Telegram",
                        f"Не удалось подключиться через прокси.\n{error_msg}\n\n"
                        "Попробовать отправить напрямую (без прокси)?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.Yes:
                        use_proxy = False
                        resp, error_msg = test_api_connection(False)
                    else:
                        return

            if not use_proxy:
                resp, error_msg = test_api_connection(False)

            if resp is None:
                QMessageBox.critical(self, "Тест Telegram",
                    f"❌ Не удалось соединиться с Telegram API.\n\n{error_msg}")
                return

            if resp.status_code != 200:
                error_data = resp.json()
                error_desc = error_data.get('description', 'Неизвестная ошибка')
                QMessageBox.critical(self, "Тест Telegram",
                    f"❌ Ошибка API Telegram ({resp.status_code}): {error_desc}\n\n"
                    "Проверьте токен. Если ошибка 401 — токен недействителен.")
                return

            bot_info = resp.json()
            if not bot_info.get('ok'):
                QMessageBox.critical(self, "Тест Telegram", f"Ошибка: {bot_info.get('description')}")
                return
            bot_username = bot_info['result']['username']

            success = notifier.send_sync(
                f"✅ **Тестовое сообщение от BingX Bot**\n"
                f"Бот @{bot_username} работает!\n"
                f"{'🔒 Через прокси' if use_proxy else '🌐 Напрямую'}"
            )

            if success:
                QMessageBox.information(self, "Тест Telegram",
                    f"✅ Сообщение успешно отправлено боту @{bot_username}!\n"
                    f"{'Использован прокси.' if use_proxy else 'Соединение напрямую.'}")
            else:
                QMessageBox.critical(self, "Тест Telegram",
                    "❌ Не удалось отправить сообщение.\n"
                    "Убедитесь, что:\n"
                    "• Бот запущен и не заблокирован\n"
                    "• Вы начали диалог с ботом (отправьте /start в личку)\n"
                    "• Chat ID введён верно")

        except Exception as e:
            QMessageBox.critical(self, "Тест Telegram", f"Непредвиденная ошибка: {str(e)}")

class SettingsDialog(QDialog):
    config_updated = pyqtSignal()

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Настройки бота")
        self.setMinimumSize(900, 600)
        self.setModal(True)

        main_layout = QVBoxLayout(self)

        self.config_panel = ConfigPanel(settings)
        self.config_panel.config_updated.connect(self._on_config_updated)
        main_layout.addWidget(self.config_panel)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _on_config_updated(self):
        self.config_updated.emit()

    def accept(self):
        self.config_panel.save_settings()
        super().accept()

    def reject(self):
        super().reject()
