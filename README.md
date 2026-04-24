# CryptoBot v6.0 - Professional Futures Trading Bot

## Исправления v6.0

- **Исправлена критическая ошибка QtLogHandler** — убран конфликт MRO (multiple inheritance), теперь используется композиция вместо множественного наследования от QObject и logging.Handler.
- **Полноценный GUI** — 7 вкладок: Dashboard, Positions, Market Scanner, Strategies, Risk Manager, Settings, Backtest.
- **Тёмная тема** — профессиональный тёмный интерфейс.
- **Улучшенная архитектура** — все модули разделены по пакетам.

## Структура проекта

```
crypto_bot_futures/
├── main.py                  # Точка входа
├── requirements.txt         # Зависимости
├── src/
│   ├── core/
│   │   ├── logger.py        # Логирование (исправлено!)
│   │   └── settings.py      # Конфигурация
│   ├── ui/
│   │   └── main_window.py   # Главное окно GUI
│   ├── exchange/
│   │   ├── api_client.py    # BingX API клиент
│   │   ├── data_fetcher.py  # Загрузка данных
│   │   ├── market_scanner.py # Сканер рынка
│   │   └── trade_executor.py # Исполнитель сделок
│   ├── strategies/
│   │   └── strategies.py    # 6 торговых стратегий
│   ├── risk/
│   │   └── risk_manager.py  # Управление рисками
│   └── ml/
│       └── ml_engine.py     # ML-фильтрация сигналов
├── config/                  # Настройки (создаётся автоматически)
├── data/
│   ├── state/               # Состояние бота
│   └── cache/               # Кэш данных
└── logs/                    # Логи
```

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

```bash
python main.py
```

## Основные функции

- **Paper Trading** — тестирование без реальных денег
- **6 стратегий** — EMA Cross, RSI Divergence, Volume Breakout, Support/Resistance, MACD Momentum, Bollinger Squeeze
- **ML-фильтрация** — случайный лес для отсева слабых сигналов
- **Риск-менеджмент** — лимиты позиций, стоп-лоссы, тейк-профиты
- **Мульти-таймфрейм** — анализ 15m, 1h, 4h
- **Real-time GUI** — мониторинг позиций, P&L, сигналов

## API BingX

Введите API ключи во вкладке **Settings → API Configuration**.
Для тестирования включите **Testnet**.
