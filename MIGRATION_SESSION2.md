# Миграция на v11.2 (Сессия #2 — "Учись")

## Что добавлено

### B1: Trade Journal Analyzer (`src/intelligence/trade_journal.py`)
- Анализирует закрытые сделки по символам, стратегиям, часам, дням недели
- Выявляет худшие символы (AVOID), лучшие часы торговли
- Анализ причин выхода: SL слишком тight? Time exits прибыльны?
- Данные сохраняются в `logs/trade_journal.json`

### B2: Parameter Optimizer (`src/intelligence/parameter_optimizer.py`)
- Сам настраивает SL/TP на основе истории сделок
- Если много SL-hits убыточны → расширяет SL
- Если цена часто убегает дальше TP → расширяет TP
- Сохраняет настройки в `logs/parameter_optimizer.json`
- Адаптируется каждый час

### B3: Time-Based Learning (`src/intelligence/time_based_learning.py`)
- Запоминает win rate по часам и дням недели
- Блокирует торговлю в "плохие" окна (WR < 40%)
- Показывает лучшие часы и дни для торговли
- Данные в `logs/time_learning.json`

### B4: Market Regime Detector v2 (`src/intelligence/market_regime_v2.py`)
- Определяет режим: TRENDING_UP, TRENDING_DOWN, RANGING, VOLATILE, CHOPPY
- Адаптирует настройки под режим:
  - Тренд → следовать тренду, широкий TP
  - Боковик → tight SL/TP, меньший размер
  - Волатильность → широкие стопы, маленький размер
  - Шум (choppy) → не торговать
- Данные в `logs/market_regime.json`

### B5: Self-Confidence Scorer (`src/intelligence/self_confidence.py`)
- Оценивает каждый сигнал 0-100%
- Факторы: сила сигнала, performance стратегии, режим рынка,
  время суток, история символа, недавний win rate
- Не берёт сделки ниже порога (default: 45%)
- Логирует разбивку по факторам

### B6: Error Pattern Detector (`src/intelligence/error_patterns.py`)
- "3 лосса подряд → пауза 30 мин"
- "6 сделок в час → пауза 15 мин" (overtrading)
- "Дневной лимит убытков достигнут → пауза 1 час"
- Ручное снятие паузы через GUI
- Настройки в `logs/error_patterns.json`

## Изменённые файлы

| Файл | Что изменилось |
|------|---------------|
| `src/intelligence/strategy_engine.py` | Интеграция всех B1-B6 модулей |
| `src/core/engine/trading_engine.py` | Добавлены проверки learning перед сделками, confidence scoring, optimized SL/TP |
| `src/config/settings.py` | Новые параметры: learning_enabled, min_confidence_threshold, auto_optimize_sl_tp, etc. |

## Как обновить

1. Распакуйте zip поверх репозитория
2. Файлы заменятся автоматически
3. Новые модули появятся в `src/intelligence/`
4. При первом запуске создадутся JSON-файлы в `logs/`
5. Настройки добавятся в config автоматически

## Новые параметры в config

```json
{
  "learning_enabled": true,
  "min_confidence_threshold": 45.0,
  "auto_optimize_sl_tp": true,
  "time_filter_enabled": true,
  "regime_filter_enabled": true,
  "error_pattern_pause": true,
  "max_loss_streak": 3,
  "cooldown_minutes": 30,
  "overtrade_threshold": 6
}
```

## Проверка в логах

```
JOURNAL: Recorded BTC-USDT BUY PnL=+12.34
OPTIMIZER ADAPTED: SL=1.80%, TP=3.50%, R:R=1.94
CONFIDENCE: 78% for BTC-USDT | Signal=85 Strategy=70 Regime=80 Time=60 Symbol=90 Recent=65
LEARNING CHECK: PASSED | GOOD time (score=72, hour WR=68%, day WR=55%)
PATTERN TRIGGERED: LOSS STREAK: 3 consecutive losses — PAUSED for 30 minutes
```
