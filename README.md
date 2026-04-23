# Crypto Trading Bot v4.0

## Что нового в v4.0
- ✅ **Исправлена критическая ошибка**: `MainWindow` теперь корректно принимает `logger`
- ✅ **UI-логгер**: все логи бота в реальном времени отображаются во вкладке "Логи"
- ✅ **Аварийная остановка**: кнопка 🚨 закрывает все позиции и останавливает бота
- ✅ **CSV-экспорт**: авто-запись сделок в `logs/trades.csv` + ручной экспорт из UI
- ✅ **Улучшенный SelfHealing**: мониторинг с реальными проверками
- ✅ **Защита от деления на ноль**: в `RiskManager`, `Position` и `TradeExecutor`
- ✅ **Улучшенный scanner**: корректный расчёт volume_24h, лучшая фильтрация
- ✅ **Trap Detector**: детекция ловушек рынка (bull/bear traps)
- ✅ **Улучшенные индикаторы**: RSI, MACD, ADX, Bollinger, VWAP, Stochastic, OBV, Ichimoku

## Установка
```bash
pip install PyQt5 pandas numpy aiohttp python-telegram-bot
```

## Запуск
```bash
python main.py
```

## Структура
```
crypto_bot_futures/
├── main.py
├── config/
│   └── bot_config.json
├── src/
│   ├── config/settings.py
│   ├── core/
│   │   ├── logger.py
│   │   ├── engine/trading_engine.py
│   │   ├── market/
│   │   │   ├── data_fetcher.py
│   │   │   ├── indicators.py
│   │   │   └── trap_detector.py
│   │   ├── scanner/market_scanner.py
│   │   ├── executor/trade_executor.py
│   │   ├── exit/exit_manager.py
│   │   ├── risk/
│   │   │   ├── risk_manager.py
│   │   │   └── risk_controller.py
│   │   └── trading/
│   │       ├── position.py
│   │       └── order_manager.py
│   ├── intelligence/strategy_engine.py
│   ├── notifications/telegram_notifier.py
│   ├── ui/main_window.py
│   └── utils/
│       ├── api_client.py
│       └── self_healing.py
└── logs/
```
