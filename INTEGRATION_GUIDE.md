# Интеграция Сессий #4 и #5

## Установка зависимостей
```bash
pip install -r requirements_additions.txt
```

## Сессия #4 — Стратегии + Инфра

### Mode Switcher (D3) — обязательно первым!
```python
from src.core.mode_switcher import ModeSwitcher, BotMode
mode_switcher = ModeSwitcher(state_manager=state)
mode_switcher.add_listener(on_mode_changed)
# В trading_engine перед открытием позиции:
if not mode_switcher.can_trade(): return
```

### Grid Engine (D1)
```python
from src.plugins.grid_engine import GridEngine, GridConfig
config = GridConfig(symbol="BTC-USDT", upper_price=70000, lower_price=60000, grid_count=20)
grid = GridEngine(order_manager=om, config=config, state_manager=state)
grid.initialize()
```

### DCA Engine (D2)
```python
from src.plugins.dca_engine import DCAEngine, DCAConfig
dca = DCAEngine(order_manager=om, position_tracker=pt, config=dca_config, state_manager=state)
dca.start(entry_price=65000, side="buy")
```

### SQLite Database (E1)
```python
from src.data.database import Database
db = Database("data/trades.db")
db.insert_trade({"trade_id": "...", "symbol": "BTC", ...})
```

### Telegram Bot (E2)
```python
from src.notifications.telegram_bot import TelegramControlBot
tg = TelegramControlBot(token="TOKEN", chat_id="CHAT_ID", mode_switcher=mode_switcher, database=db)
await tg.start()
```

### Log Rotator (E3)
```python
from src.utils.log_rotator import LogRotator
handler = LogRotator.setup("logs/bot.log", max_bytes=10*1024*1024, backup_count=10)
logger.addHandler(handler)
```

### Health Endpoint (E4)
```python
from src.web.health_endpoint import HealthEndpoint
health = HealthEndpoint(host="0.0.0.0", port=8080, mode_switcher=mode_switcher, database=db)
await health.start()
```

## Сессия #5 — Оптимизация под РФ

### Performance Profile (F3) — запускать первым!
```python
from src.core.performance_profile import PerformanceProfile, ProfileMode
profile = PerformanceProfile(mode_switcher=mode_switcher)
profile.auto_detect()  # Определит light/standard/full по железу
# или принудительно:
profile.set_mode(ProfileMode.LIGHT)
```

### Proxy Manager (F1) — если API недоступен из РФ
```python
from src.utils.proxy_manager import ProxyManager
pm = ProxyManager()
pm.add_proxy("http://user:pass@host:port")
pm.health_check_all()
proxy = pm.get_best_proxy()
requests.get(url, proxies=proxy)
```

### Offline Cache (F2)
```python
from src.data.offline_cache import OfflineCache
cache = OfflineCache(database=db)
cache.store_candles("BTC-USDT", "1h", candles)
cached = cache.get_cached_candles("BTC-USDT", "1h")
```

### Power Manager (F5) — для ноутбука
```python
from src.utils.power_manager import PowerManager
power = PowerManager(performance_profile=profile, mode_switcher=mode_switcher)
power.start_monitoring()  # Фоновый мониторинг батареи
```

### Local Alerts (F7) — без интернета
```python
from src.notifications.local_alerts import LocalAlerts
alerts = LocalAlerts(enable_sound=True, enable_voice=False, enable_toast=True)
alerts.trade_alert("BTC-USDT", pnl=12.40)
alerts.error_alert("API connection failed")
```

### Terminal UI (F8) — лёгкий интерфейс
```bash
# Запуск вместо GUI
python main.py --terminal
```

### Rate Limiter (F9)
```python
from src.utils.rate_limiter import RateLimiter
limiter = RateLimiter()
limiter.wait()  # Перед каждым API запросом
```

### Tax Report (F10)
```python
from src.analytics.tax_report import TaxReport
report = TaxReport(database=db)
summary = report.generate_quarterly(2026, 2)  # Q2 2026
```

## Порядок инициализации в main.py
```python
async def main():
    # 1. База данных
    db = Database()

    # 2. Performance profile (авто-определение железа)
    profile = PerformanceProfile()
    profile.auto_detect()

    # 3. Mode switcher
    mode = ModeSwitcher(state)

    # 4. Power manager (ноутбук)
    power = PowerManager(profile, mode)
    power.start_monitoring()

    # 5. Proxy manager (если нужен)
    # proxy = ProxyManager()

    # 6. Offline cache
    cache = OfflineCache(db)

    # 7. Локальные алерты
    alerts = LocalAlerts()

    # 8. Exchange, engine, etc.
    # ... твой код ...

    # 9. Telegram (опционально)
    # tg = TelegramControlBot(...)
    # await tg.start()

    # 10. Health endpoint
    health = HealthEndpoint(...)
    await health.start()

    # 11. Terminal UI или GUI
    if args.terminal:
        ui = TerminalUI(mode, pt, db, profile)
        ui.start()  # Блокирующий
    else:
        # Запуск GUI
        pass
```
