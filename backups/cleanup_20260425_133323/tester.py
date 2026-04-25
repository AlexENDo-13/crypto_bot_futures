#!/usr/bin/env python3
"""
Тестер для определения допустимой частоты запросов к BingX API.
Помогает подобрать async_concurrency и задержки, чтобы избежать ошибки 109429.
"""
import asyncio
import aiohttp
import time
import sys
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent))

from src.config.settings import Settings
from src.core.logger import BotLogger
from src.config.constants import TimeFrame

BASE_URL = "https://open-api.bingx.com/openApi/swap/v2"

# Список популярных пар для теста
TEST_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT",
    "MATIC/USDT", "SHIB/USDT", "LTC/USDT", "TRX/USDT", "ATOM/USDT"
]

TIMEFRAMES = [TimeFrame.H1.value, TimeFrame.H4.value, TimeFrame.D1.value]

async def fetch_klines(session: aiohttp.ClientSession, symbol: str, interval: str, limit: int = 100):
    """Запрос свечей с измерением времени."""
    params = {
        "symbol": symbol.replace("/", ""),
        "interval": interval,
        "limit": str(limit)
    }
    url = f"{BASE_URL}/quote/klines"
    start = time.time()
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            data = await resp.json()
            elapsed = time.time() - start
            if resp.status == 200 and data.get("code") == 0:
                candles = len(data.get("data", []))
                return {"success": True, "candles": candles, "time": elapsed}
            else:
                return {"success": False, "error": data, "time": elapsed, "status": resp.status}
    except Exception as e:
        elapsed = time.time() - start
        return {"success": False, "error": str(e), "time": elapsed}

async def run_test(concurrency: int, delay_between_batches: float, max_symbols: int = 10):
    """
    concurrency: количество одновременных запросов (семафор)
    delay_between_batches: пауза в секундах между обработкой групп пар
    max_symbols: сколько символов тестировать
    """
    logger = BotLogger(level="INFO")
    logger.info(f"🚀 Тест: concurrency={concurrency}, batch_delay={delay_between_batches}s, symbols={max_symbols}")

    symbols = TEST_SYMBOLS[:max_symbols]
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_with_semaphore(session, symbol, tf):
        async with semaphore:
            return await fetch_klines(session, symbol, tf)

    results = []
    async with aiohttp.ClientSession() as session:
        for i, symbol in enumerate(symbols):
            if i > 0:
                logger.info(f"⏳ Пауза {delay_between_batches}s перед следующей парой...")
                await asyncio.sleep(delay_between_batches)

            tasks = [fetch_with_semaphore(session, symbol, tf) for tf in TIMEFRAMES]
            batch_results = await asyncio.gather(*tasks)

            for tf, res in zip(TIMEFRAMES, batch_results):
                status = "✅" if res["success"] else "❌"
                if res["success"]:
                    logger.info(f"{status} {symbol} {tf}: {res['candles']} candles ({res['time']:.2f}s)")
                else:
                    logger.warning(f"{status} {symbol} {tf}: {res['error']} ({res['time']:.2f}s)")
                results.append({"symbol": symbol, "tf": tf, **res})

    # Статистика
    success_count = sum(1 for r in results if r["success"])
    error_429 = sum(1 for r in results if not r["success"] and "109429" in str(r.get("error", "")))
    avg_time = sum(r["time"] for r in results) / len(results) if results else 0

    logger.info("=" * 60)
    logger.info(f"📊 ИТОГО: Успешно {success_count}/{len(results)} запросов")
    logger.info(f"   Ошибок 109429 (rate limit): {error_429}")
    logger.info(f"   Среднее время ответа: {avg_time:.2f} сек")
    logger.info("=" * 60)
    return results

async def main():
    print("\n🔍 ТЕСТЕР ЧАСТОТЫ ЗАПРОСОВ К BINGX API")
    print("Этот тест поможет найти безопасные настройки для сканера.\n")

    # Рекомендуемые комбинации для проверки
    test_configs = [
        {"concurrency": 3, "delay": 2.0, "symbols": 5},
        {"concurrency": 2, "delay": 3.0, "symbols": 5},
        {"concurrency": 1, "delay": 5.0, "symbols": 5},
        {"concurrency": 1, "delay": 10.0, "symbols": 5},
    ]

    for cfg in test_configs:
        print(f"\n▶ Запуск теста: {cfg}")
        await run_test(
            concurrency=cfg["concurrency"],
            delay_between_batches=cfg["delay"],
            max_symbols=cfg["symbols"]
        )
        print("\n" + "-" * 40)
        await asyncio.sleep(5)  # пауза между тестами

if __name__ == "__main__":
    asyncio.run(main())
