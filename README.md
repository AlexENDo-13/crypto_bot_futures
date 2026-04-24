# CryptoBot v7.0

## Исправления
- Дублирование логов устранено (singleton lock)
- Стратегии работают корректно (pandas validation)
- API ключ передаётся правильно
- Сканер находит сигналы
- Live trading работает

## Фичи v7.0
- 7 стратегий (EMA, RSI, Volume, S/R, MACD, Bollinger, DCA)
- ML-фильтрация сигналов
- Trailing stop
- Авто-исполнение сигналов
- Telegram/Discord/Email
- SQLite state management
- Dark theme

## Запуск
```bash
pip install -r requirements.txt
python main.py
```

## Настройка
1. Settings → API: введите ключи BingX
2. Settings → Notifications: настройте алерты
3. Выберите Paper или Live mode
4. Нажмите START BOT
