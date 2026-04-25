# CryptoBot v9.1 — Исправленная версия

## Быстрый старт

1. Распакуй архив в папку `crypto_bot_futures/`
2. Установи зависимости: `pip install -r requirements.txt`
3. Запусти: `python main.py`

## Что исправлено

- `main.py` — убран конфликт event loop
- `src/ui/main_window.py` — QTextEdit → QPlainTextEdit
- `src/core/logger.py` — добавлены proxy-методы info(), warning(), error()
- `src/exchange/api_client.py` — добавлены методы для реальной торговли + логирование баланса
- `src/core/risk/risk_manager.py` — добавлен update_pnl(), исправлен get_account_info()
- `src/core/scanner/market_scanner.py` — fallback для volume_24h=0
- `src/core/market/data_fetcher.py` — нормализация тикеров BingX
- `src/core/executor/trade_executor.py` — исправлены вызовы API

## Для LIVE торговли

1. Получи API ключи на BingX
2. Установи в `config/bot_config.json`:
   ```json
   "demo_mode": false,
   "api_key": "YOUR_KEY",
   "api_secret": "YOUR_SECRET"
   ```
3. Или через переменные окружения:
   ```bash
   set BINGX_API_KEY=your_key
   set BINGX_API_SECRET=your_secret
   ```

## Внимание

- **Всегда начинай с `demo_mode: true`**
- Протестируй минимум 1-2 дня на бумаге
- Не коммить API ключи в Git!
