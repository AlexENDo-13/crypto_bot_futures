# Быстрый старт

## 1. Установка

```bash
python setup.py
```

Или вручную:
```bash
pip install -r requirements.txt
```

## 2. Настройка

Отредактируйте `config/bot_config.json`:

```json
{
    "demo_mode": true,
    "virtual_balance": 100.0,
    "api_key": "ВАШ_API_KEY",
    "api_secret": "ВАШ_API_SECRET",
    "max_positions": 2,
    "max_risk_per_trade": 1.0,
    "max_leverage": 10
}
```

## 3. Запуск

```bash
python main.py
```

## 4. Обновление на GitHub

### Linux/Mac:
```bash
./update_repo.sh
```

### Windows:
```cmd
update_repo.bat
```

## Важные настройки

| Параметр | Описание | Рекомендация |
|----------|----------|-------------|
| `demo_mode` | Демо-режим | `true` для тестирования |
| `virtual_balance` | Виртуальный баланс | 100-1000 USDT |
| `max_positions` | Макс. позиций | 2-3 |
| `max_risk_per_trade` | Риск на сделку (%) | 0.5-2.0 |
| `max_leverage` | Макс. плечо | 3-10 |
| `timeframe` | Таймфрейм | "15m" или "1h" |
| `daily_loss_limit_percent` | Дневной лимит убытков | 5-10 |

## Требования

- Python 3.8+
- BingX API ключи (для реального режима)
- 2GB RAM минимум
- Стабильное интернет-соединение
