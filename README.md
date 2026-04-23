# Crypto Bot Futures — BingX Trading Bot

## Что исправлено

### 1. API Client (api_client.py)
- ✅ Правильные эндпоинты BingX API v2
- ✅ Обработка всех ошибок BingX (100412, 100001, и др.)
- ✅ Retry-логика с exponential backoff
- ✅ Синхронизация времени сервера
- ✅ Кэширование спецификаций символов (stepSize, minNotional)
- ✅ Rate limiting

### 2. Risk Manager (risk_manager.py)
- ✅ Полноценный расчёт размера позиции
- ✅ Адаптация под любой депозит (даже $10-50)
- ✅ Anti-martingale (снижение риска после убытков)
- ✅ Weekend risk reduction
- ✅ Расчёт SL/TP на основе ATR
- ✅ Circuit breaker
- ✅ Anti-chase (защита от погони)

### 3. Trade Executor (trade_executor.py)
- ✅ Корректное округление qty через stepSize из биржи
- ✅ Проверка minNotional
- ✅ Установка плеча перед ордером
- ✅ Установка margin mode
- ✅ Прикрепление SL/TP к ордеру

### 4. Market Scanner (market_scanner.py)
- ✅ Фильтры по объёму, funding rate, спреду
- ✅ Whitelist/blacklist
- ✅ Адаптивные пороги
- ✅ Multi-timeframe confirmation

### 5. Indicators (indicators.py)
- ✅ MACD + RSI + ADX (Wilder's smoothing)
- ✅ Bollinger Bands
- ✅ Ichimoku Cloud
- ✅ EMA alignment (8/21/55)
- ✅ Объёмный анализ
- ✅ Композитный скоринг сигналов

### 6. Exit Manager (exit_manager.py)
- ✅ SL/TP проверка
- ✅ Trailing stop
- ✅ Dead weight exit (time-based)
- ✅ Асинхронное закрытие через order_manager
- ✅ Интеграция с sqlite_history

### 7. Trading Engine (trading_engine.py)
- ✅ Совместимость всех компонентов
- ✅ Синхронизация позиций с биржей
- ✅ Emergency close
- ✅ UI callbacks

### 8. Main Window (main_window.py)
- ✅ Корректные импорты
- ✅ Совместимость с TradingEngine
- ✅ Обновление позиций в реальном времени

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

```bash
python main.py
```

## Настройка

Отредактируйте `config/bot_config.json`:
- `demo_mode: true` — демо-режим (рекомендуется для тестирования)
- `virtual_balance` — стартовый баланс для демо
- `api_key` / `api_secret` — ключи BingX (для реального режима)
- `max_positions` — максимум одновременных позиций
- `max_risk_per_trade` — риск на сделку (%)
- `max_leverage` — максимальное плечо

## Структура

```
├── main.py                 # Точка входа
├── config/
│   └── bot_config.json     # Настройки
├── src/
│   ├── core/
│   │   ├── engine/         # Торговый движок
│   │   ├── executor/       # Исполнитель сделок
│   │   ├── exit/           # Менеджер выходов
│   │   ├── market/         # Данные и индикаторы
│   │   ├── risk/           # Риск-менеджмент
│   │   ├── scanner/        # Сканер рынка
│   │   ├── signals/        # Генератор сигналов
│   │   └── trading/        # Позиции и ордера
│   ├── config/             # Константы и настройки
│   ├── intelligence/       # Стратегии
│   ├── ui/                 # PyQt5 интерфейс
│   └── utils/              # Утилиты
```
