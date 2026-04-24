# CryptoBot v7.1 - Professional Futures Trading Bot

## Исправления в v7.1

1. **main.py** — добавлена обработка фатальных ошибок, graceful shutdown
2. **api_client.py** — исправлена генерация подписи BingX, обработка ошибок 100412/100001, retry-логика
3. **data_fetcher.py** — исправлен парсинг klines (error: 0), добавлен fallback на mock-данные
4. **trade_executor.py** — исправлен расчёт qty, валидация volume_24h=0, live/paper режимы
5. **risk_manager.py** — добавлен метод update_pnl, защита от деления на ноль
6. **market_scanner.py** — улучшена обработка ошибок при сканировании
7. **main_window.py** — бот больше не падает при запуске, worker с try/except, убрана бесполезная кнопка темы
8. **settings.py** — добавлен scan_interval, корректная загрузка/сохранение
9. **notifications.py** — исправлены имена полей под settings

## Установка

```bash
pip install -r requirements.txt
python main.py
```

## Структура

```
crypto_bot_futures/
├── main.py
├── requirements.txt
├── config/
│   └── settings.json
├── data/
│   ├── cache/
│   ├── state/
│   └── models/
├── logs/
└── src/
    ├── core/        # logger, settings, config, events, state, security, notifications
    ├── exchange/    # api_client, data_fetcher, market_scanner, trade_executor
    ├── risk/        # risk_manager
    ├── strategies/  # strategies
    ├── ml/          # ml_engine
    └── ui/          # main_window
```

## Важно

- По умолчанию **Paper Trading** — реальные деньги не тратятся
- Для live trading введите API ключи BingX в Settings
- Всегда начинайте с paper trading для проверки
