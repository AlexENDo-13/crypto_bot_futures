# Миграция на v11.1 (Сессия #0 + #1)

## Что изменилось

### Критические фиксы (Сессия #0)
1. **`trading_engine.py`** — `threading.Lock()` заменён на `asyncio.Lock()`
   - Раньше: GUI зависал, API таймаутились из-за блокировки event loop
   - Теперь: корректная работа с async

2. **`trading_engine.py`** — убран `.replace("-", "/")` в символах
   - Раньше: после синхронизации позиций символы становились `BTC/USDT`, и все API-вызовы падали
   - Теперь: сохраняется оригинальный формат `BTC-USDT`

3. **`api_client.py`** — добавлена обработка ошибки `100001` (invalid signature)
   - Авто-retry с fresh timestamp

4. **`api_client.py`** — `asyncio.Lock()` для безопасной работы с сессией
   - Исключены race conditions при обновлении credentials

### Стабильность (Сессия #1)
- **`graceful_shutdown.py`** — корректный выход: сначала останавливается watchdog, потом engine, потом API, потом мониторы
- **`memory_monitor.py`** — следит за RAM, при превышении 512 MB форсирует GC
- **`offline_guard.py`** — проверяет интернет каждые 10 сек, блокирует API при отсутствии связи
- **`watchdog.py`** — если engine не отвечает >60 сек — авто-рестарт (макс 5 раз)
- **`qthread_worker.py`** — запускает тяжёлые операции в QThread, GUI не зависает
- **`circuit_breaker_v2.py`** — умнее старого: CLOSED → OPEN → HALF_OPEN → CLOSED

## Как обновить

1. Скопируйте файлы из zip поверх существующих:
   ```
   main.py  →  заменить
   src/exchange/api_client.py  →  заменить
   src/core/engine/trading_engine.py  →  заменить
   src/core/stability/*.py  →  новые папки/файлы
   ```

2. Установите дополнительные зависимости:
   ```bash
   pip install psutil scikit-learn numpy pandas
   ```

3. Запустите бота как обычно:
   ```bash
   python main.py
   ```

## Проверка

В логах должно появиться:
```
Memory monitor started (threshold: 512 MB...)
Offline guard started (interval: 10s)
Engine watchdog started (threshold: 60s)
Starting TradingEngine v11.1 (STABLE)...
```
