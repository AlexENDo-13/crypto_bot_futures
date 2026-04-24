# Crypto Bot Futures v5.0

## Что нового в v5.0

### Архитектура
- **Event Bus** — централизованная шина событий, все компоненты общаются через типизированные события
- **Plugin System** — стратегии как плагины, легко добавлять новые
- **State Persistence** — SQLite-база для позиций, ордеров, сделок (переживает рестарт)
- **Security** — шифрование API-ключей через Fernet (AES-256)

### WebSocket
- **Real-time данные** — цены, стакан, свечи через WebSocket
- **Auto-reconnect** — экспоненциальный backoff при разрыве
- **Multi-subscription** — параллельная подписка на несколько символов

### Торговля
- **Partial Profits** — частичное закрытие позиции на 3 уровнях (25%/25%/25%)
- **Breakeven Stop** — автоматический перенос SL в безубыток
- **ATR Trailing Stop** — трейлинг-стоп на основе ATR
- **DCA** — усреднение позиции при просадке
- **Kelly Criterion / Optimal F** — продвинутый расчёт размера позиции

### Стратегии (6 штук)
1. EMA Crossover (9/21/50/200)
2. RSI Divergence (14)
3. Volume Breakout (2x MA)
4. Support/Resistance Bounce
5. MACD Momentum (гистограмма)
6. Bollinger Squeeze (волатильность)

### ML / AI
- **Ensemble Model** — Random Forest + Gradient Boosting
- **Feature Engineering** — 17 признаков из мультитаймфреймных данных
- **Auto-retrain** — автоматическое переобучение каждые 24 часа
- **Feature Importance** — анализ важности признаков

### Risk Management
- **Session Filters** — торговля только в выбранных сессиях (Asia/London/NY)
- **Correlation Filter** — ограничение коррелированных позиций
- **Volatility Filter** — фильтр по ATR (min/max)
- **Drawdown Control** — emergency stop при превышении просадки
- **Cooldown** — пауза после серии убытков

### Notifications
- **Telegram** — сигналы, сделки, алерты
- **Discord** — webhook-уведомления

### Backtester
- **Walk-forward Analysis** — оптимизация с валидацией
- **Slippage & Commission** — реалистичная симуляция
- **Equity Curve** — полная кривая доходности
- **Sharpe Ratio** — risk-adjusted returns

### GUI
- **4 вкладки** — Позиции, Сигналы, История, ML Predictions
- **Menu Bar** — Export/Import конфига
- **Real-time** — обновление каждую секунду
- **Color-coded** — зелёный прибыль, красный убыток

## Установка
```bash
pip install -r requirements.txt
```

## Запуск
```bash
# GUI (по умолчанию)
python main.py

# CLI
python main.py --cli

# Backtest
python main.py --backtest

# Train ML
python main.py --train

# Live (ОПАСНО!)
python main.py --live --symbol BTC-USDT --leverage 10
```

## Структура
```
crypto_bot_futures_v5/
├── main.py
├── requirements.txt
├── README.md
└── src/
    ├── core/
    │   ├── config.py
    │   ├── logger.py
    │   ├── events.py
    │   ├── state.py
    │   ├── security.py
    │   └── settings.py
    ├── exchange/
    │   ├── api_client.py
    │   └── websocket_client.py
    ├── trading/
    │   ├── data_fetcher.py
    │   ├── position_manager.py
    │   ├── trade_executor.py
    │   ├── risk_manager.py
    │   └── market_scanner.py
    ├── plugins/
    │   ├── strategy_base.py
    │   ├── ema_cross.py
    │   ├── rsi_divergence.py
    │   ├── volume_breakout.py
    │   ├── support_resistance.py
    │   ├── macd_momentum.py
    │   └── bollinger_squeeze.py
    ├── ai/
    │   ├── ai_exporter.py
    │   └── ml_engine.py
    ├── backtest/
    │   └── backtester.py
    ├── notifications/
    │   ├── telegram.py
    │   └── discord.py
    └── ui/
        └── main_window.py
```
