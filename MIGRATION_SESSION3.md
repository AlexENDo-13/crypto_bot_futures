# Миграция на v11.3 (Сессия #3 — "Предсказывай" ML)

## Что добавлено

### C1+C2: ML Predictor (`src/intelligence/ml/ml_predictor.py`)
- **Random Forest** классификатор: входить / не входить
- **20+ фичей**:
  - RSI, MACD, цена vs EMA20
  - ADX, DI+, DI-
  - ATR%, ширина Bollinger, позиция в BB
  - Объём, OBV slope, VWAP distance
  - Funding rate, orderbook imbalance, спред, liquidation delta
  - MTF agreement, higher TF trend, lower TF momentum
  - Час дня, market regime score
  - Signal strength, confidence score
- **Автообучение**: переобучается каждый час на последних сделках
- **Feature importance**: показывает какие фичи важнее всего
- **Fallback**: если sklearn не установлен — работает эвристика
- Данные: `logs/ml_model.pkl`, `logs/ml_training_data.json`

### C3: Volatility Forecast (`src/intelligence/ml/volatility_forecast.py`)
- Прогнозирует ATR на основе EWMA + GARCH-like подхода
- **Position size adjustment**: при росте волатильности уменьшает размер позиции
- **Avoid symbol**: блокирует символы с exploding volatility (>5%)
- Данные: `logs/volatility_forecast.json`

### C4: Correlation Matrix (`src/intelligence/ml/correlation_matrix.py`)
- Отслеживает корреляцию между всеми парами
- **Portfolio diversification score** 0-100
- **Correlation filter**: не открывает позицию если корреляция с существующей > 0.8
- Обновляется каждые 5 минут
- Данные: `logs/correlation_matrix.json`

## Изменённые файлы

| Файл | Что изменилось |
|------|---------------|
| `src/intelligence/strategy_engine.py` | + ML predictor, volatility forecaster, correlation matrix |
| `src/core/engine/trading_engine.py` | + Correlation filter, vol adjustment, ML price feeding |

## Новые параметры в config (автодобавятся)

```json
{
  "ml_enabled": true,
  "correlation_filter_enabled": true,
  "max_correlation": 0.8
}
```

## Как обновить

1. Установите зависимость (опционально, но рекомендуется):
   ```bash
   pip install scikit-learn numpy
   ```
   Без sklearn ML будет работать в heuristic-режиме.

2. Распакуйте zip поверх репозитория
3. Запустите бота

## Проверка в логах

```
ML model loaded from disk
ML RETRAINED: 45 samples | Top features: [('atr_percent', 0.15), ('signal_strength', 0.12)...]
ML BOOST: BTC-USDT +8.5% — RF predicts 72% profit probability
VOLATILITY ADJUSTMENT: BTC-USDT size multiplier=0.75
CORRELATION REJECT: ETH-USDT vs BTC-USDT = 0.87 (max 0.8)
```
