#!/usr/bin/env python3
"""
Тестер подключения к BingX API.
Проверяет:
- Доступность публичных эндпоинтов (тикер, свечи)
- Корректность API-ключей (баланс, позиции)
- Время ответа сервера
"""
import sys
import time
from pathlib import Path

# Добавляем путь к проекту, чтобы импортировать модули
sys.path.insert(0, str(Path(__file__).parent))

from src.config.settings import Settings
from src.utils.api_client import BingXClient, AsyncBingXClient
from src.core.logger import BotLogger
import asyncio

def test_sync_client():
    """Синхронный тест (быстрый)"""
    print("\n📡 Тестирование синхронного клиента (CCXT)...")
    settings = Settings()
    api_key = settings.get("api_key")
    api_secret = settings.get("api_secret")
    demo_mode = settings.get("demo_mode", True)
    
    if not api_key or not api_secret:
        print("❌ API ключи не найдены в user_config.json")
        return False
    
    client = BingXClient(api_key, api_secret, demo_mode=demo_mode)
    logger = BotLogger()
    
    # 1. Проверка времени сервера (косвенно через тикер BTC)
    print("  ⏱️ Проверка задержки API...")
    start = time.time()
    btc_ticker = client.get_ticker("BTC/USDT")
    latency = (time.time() - start) * 1000
    if btc_ticker and btc_ticker.get("lastPrice", 0) > 0:
        print(f"  ✅ Тикер BTC/USDT получен за {latency:.0f} мс")
        print(f"     Цена: {btc_ticker['lastPrice']} USDT")
    else:
        print("  ❌ Не удалось получить тикер BTC/USDT")
        return False
    
    # 2. Проверка загрузки свечей
    print("  📊 Загрузка свечей 1h (последние 10)...")
    start = time.time()
    klines = client.get_klines("BTC/USDT", interval="1h", limit=10)
    latency_klines = (time.time() - start) * 1000
    if klines and len(klines) > 0:
        print(f"  ✅ Свечи получены за {latency_klines:.0f} мс (всего {len(klines)})")
    else:
        print("  ❌ Не удалось загрузить свечи")
        return False
    
    # 3. Проверка аккаунта (если не демо)
    if not demo_mode:
        print("  👤 Проверка баланса...")
        acc = client.get_account_info()
        if acc:
            print(f"     Баланс: {acc['balance']:.2f} USDT, Доступно: {acc['available']:.2f} USDT")
        else:
            print("  ⚠️ Не удалось получить информацию об аккаунте (проверьте ключи)")
    
    client.close()
    return True

async def test_async_client():
    """Асинхронный тест (как в бою)"""
    print("\n🌐 Тестирование асинхронного клиента (aiohttp)...")
    settings = Settings()
    api_key = settings.get("api_key")
    api_secret = settings.get("api_secret")
    demo_mode = settings.get("demo_mode", True)
    
    if not api_key or not api_secret:
        print("❌ API ключи не найдены")
        return False
    
    client = AsyncBingXClient(api_key, api_secret, demo_mode=demo_mode, settings=settings.data)
    
    try:
        # Тикер
        start = time.time()
        ticker = await client.get_ticker("ETH/USDT")
        latency = (time.time() - start) * 1000
        if ticker and ticker.get("lastPrice", 0) > 0:
            print(f"  ✅ Тикер ETH/USDT: {ticker['lastPrice']} (за {latency:.0f} мс)")
        else:
            print("  ❌ Ошибка получения тикера")
            return False
        
        # Свечи
        start = time.time()
        klines = await client.get_klines("ETH/USDT", interval="1h", limit=5)
        latency = (time.time() - start) * 1000
        if klines and len(klines) > 0:
            print(f"  ✅ Свечи 1h получены за {latency:.0f} мс ({len(klines)} шт)")
        else:
            print("  ⚠️ Свечи не загружены (возможен таймаут)")
        
        # Баланс
        if not demo_mode:
            acc = await client.get_account_info()
            if acc:
                print(f"  👤 Баланс: {acc['balance']:.2f} USDT")
            else:
                print("  ⚠️ Не удалось получить баланс")
        
    finally:
        await client.close()
    return True

def main():
    print("=" * 60)
    print("🔌 ТЕСТЕР ПОДКЛЮЧЕНИЯ К BINGX API")
    print("=" * 60)
    
    settings = Settings()
    demo_mode = settings.get("demo_mode", True)
    print(f"Режим: {'ДЕМО' if demo_mode else 'РЕАЛЬНЫЙ (осторожно!)'}")
    print(f"API Key: {'***' if settings.get('api_key') else 'НЕ ЗАДАН'}")
    
    # Синхронный тест
    if not test_sync_client():
        print("\n❌ Синхронный тест провален. Проверьте соединение с интернетом.")
        return
    
    # Асинхронный тест
    loop = asyncio.get_event_loop()
    if not loop.run_until_complete(test_async_client()):
        print("\n❌ Асинхронный тест провален. Возможны проблемы с aiohttp или таймаутами.")
    
    print("\n" + "=" * 60)
    print("Тестирование завершено.")
    print("Если видны таймауты (>10 сек) – проблема в сети или на стороне биржи.")
    print("=" * 60)

if __name__ == "__main__":
    main()
