#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BingX Symbol Diagnostic Tool
Проверяет несоответствие символов между CCXT и нативным API BingX
"""

import asyncio
import json
import time
import traceback
from typing import List, Dict, Set, Tuple

try:
    import ccxt
except ImportError:
    raise ImportError("pip install ccxt")

try:
    import aiohttp
except ImportError:
    raise ImportError("pip install aiohttp")

try:
    import pandas as pd
except ImportError:
    raise ImportError("pip install pandas")


class BingXDiagnostic:
    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.exchange = None
        self.native_symbols: Set[str] = set()
        self.ccxt_symbols: Dict[str, dict] = {}
        self.problematic_symbols: List[str] = []

        self.test_symbols = [
            "BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT",
            "MOVR/USDT", "ONG/USDT", "1000BONK/USDT", "BEAM/USDT"
        ]

    def init_ccxt(self) -> bool:
        print("\n" + "="*70)
        print("МЕТОД 1: Инициализация CCXT BingX")
        print("="*70)
        try:
            config = {
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap',
                }
            }
            self.exchange = ccxt.bingx(config)
            print(f"✅ CCXT версия: {ccxt.__version__}")
            print(f"✅ Exchange ID: {self.exchange.id}")
            # Безопасная проверка — в разных версиях CCXT атрибуты разные
            has_swap = hasattr(self.exchange, 'has') and self.exchange.has.get('swap', False)
            print(f"✅ Поддерживает swap: {has_swap}")
            return True
        except Exception as e:
            print(f"❌ Ошибка инициализации CCXT: {e}")
            traceback.print_exc()
            return False

    def load_ccxt_markets(self) -> Dict[str, dict]:
        print("\n" + "="*70)
        print("МЕТОД 2: Загрузка маркетов через CCXT")
        print("="*70)
        try:
            markets = self.exchange.load_markets()
            self.ccxt_symbols = {
                k: v for k, v in markets.items() 
                if v.get('quote') == 'USDT' 
                and v.get('type') == 'swap'
                and v.get('linear')
            }
            print(f"📊 Всего маркетов в CCXT: {len(markets)}")
            print(f"📊 USDT linear swap: {len(self.ccxt_symbols)}")

            sample = list(self.ccxt_symbols.keys())[:5]
            print(f"\nПримеры unified символов CCXT:")
            for s in sample:
                print(f"   {s} → active={self.ccxt_symbols[s].get('active')}")

            return self.ccxt_symbols
        except Exception as e:
            print(f"❌ Ошибка загрузки маркетов: {e}")
            traceback.print_exc()
            return {}

    async def fetch_native_contracts(self) -> Set[str]:
        print("\n" + "="*70)
        print("МЕТОД 3: Нативное API BingX (/openApi/swap/v2/quote/contracts)")
        print("="*70)
        url = "https://open-api.bingx.com/openApi/swap/v2/quote/contracts"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=10) as resp:
                    data = await resp.json()
                    if data.get('code') != 0:
                        print(f"❌ API ошибка: {data}")
                        return set()

                    contracts = data.get('data', [])
                    self.native_symbols = set()

                    for c in contracts:
                        symbol = c.get('symbol', '')
                        if symbol.endswith('-USDT'):
                            ccxt_like = symbol.replace('-USDT', '/USDT')
                            self.native_symbols.add(ccxt_like)

                    print(f"📊 Контрактов в нативном API: {len(contracts)}")
                    print(f"📊 Уникальных символов (приведено к /USDT): {len(self.native_symbols)}")

                    sample = list(self.native_symbols)[:5]
                    print(f"\nПримеры нативных символов:")
                    for s in sample:
                        print(f"   Нативный: {s.replace('/USDT', '-USDT')} → Приведенный: {s}")

                    return self.native_symbols

            except Exception as e:
                print(f"❌ Ошибка нативного API: {e}")
                traceback.print_exc()
                return set()

    def compare_symbol_lists(self):
        print("\n" + "="*70)
        print("МЕТОД 4: Сравнение CCXT vs Нативное API")
        print("="*70)

        ccxt_set = set()
        for sym, info in self.ccxt_symbols.items():
            clean = sym.replace(':USDT', '')
            ccxt_set.add(clean)

        only_in_ccxt = ccxt_set - self.native_symbols
        only_in_native = self.native_symbols - ccxt_set
        common = ccxt_set & self.native_symbols

        print(f"✅ Совпадают: {len(common)}")
        print(f"⚠️  Только в CCXT (возможно делист/ошибка): {len(only_in_ccxt)}")
        print(f"ℹ️  Только в нативном API: {len(only_in_native)}")

        if only_in_ccxt:
            print(f"\n🔴 Символы из CCXT, которых НЕТ в нативном API (первые 20):")
            for s in sorted(only_in_ccxt)[:20]:
                print(f"   - {s}")

        self.problematic_symbols = sorted(only_in_ccxt)

    def test_ohlcv_formats(self, symbol_base: str) -> List[Tuple[str, str, bool, str]]:
        formats = [
            (f"{symbol_base}:USDT", "unified (:USDT)"),
            (symbol_base, "clean (/USDT)"),
            (symbol_base.replace('/', '-'), "native (-USDT)")
        ]

        results = []
        for fmt, name in formats:
            try:
                since = self.exchange.milliseconds() - 24 * 60 * 60 * 1000
                ohlcv = self.exchange.fetch_ohlcv(fmt, '1h', since, 2)
                success = len(ohlcv) > 0
                results.append((name, fmt, success, f"{len(ohlcv)} свечей"))
            except Exception as e:
                results.append((name, fmt, False, str(e)[:60]))

        return results

    def test_ticker_formats(self, symbol_base: str) -> List[Tuple[str, str, bool, str]]:
        formats = [
            (f"{symbol_base}:USDT", "unified (:USDT)"),
            (symbol_base, "clean (/USDT)"),
            (symbol_base.replace('/', '-'), "native (-USDT)")
        ]

        results = []
        for fmt, name in formats:
            try:
                ticker = self.exchange.fetch_ticker(fmt)
                success = ticker is not None and ticker.get('last') is not None
                results.append((name, fmt, success, f"price={ticker.get('last')}"))
            except Exception as e:
                results.append((name, fmt, False, str(e)[:60]))

        return results

    async def run_symbol_tests(self):
        print("\n" + "="*70)
        print("МЕТОД 5-7: Тестирование загрузки данных для конкретных пар")
        print("="*70)

        test_pairs = self.test_symbols + self.problematic_symbols[:10]

        for sym in test_pairs:
            print(f"\n{'─'*60}")
            print(f"Тестируем: {sym}")
            print(f"{'─'*60}")

            base = sym.replace('/USDT', '')

            print("  📈 OHLCV fetch:")
            for name, fmt, ok, detail in self.test_ohlcv_formats(base):
                status = "✅" if ok else "❌"
                print(f"     {status} {name:20} | {fmt:25} | {detail}")

            print("  💰 Ticker fetch:")
            for name, fmt, ok, detail in self.test_ticker_formats(base):
                status = "✅" if ok else "❌"
                print(f"     {status} {name:20} | {fmt:25} | {detail}")

            unified = f"{sym}:USDT"
            if unified in self.ccxt_symbols:
                info = self.ccxt_symbols[unified]
                print(f"  ℹ️  CCXT active={info.get('active')}, type={info.get('type')}")

            time.sleep(0.5)

    async def test_native_klines(self):
        print("\n" + "="*70)
        print("МЕТОД 8: Нативный endpoint BingX для свечей")
        print("="*70)

        test_symbols_native = ["BTC-USDT", "MOVR-USDT", "ONG-USDT", "1000BONK-USDT"]
        url_base = "https://open-api.bingx.com/openApi/swap/v3/quote/klines"

        async with aiohttp.ClientSession() as session:
            for sym in test_symbols_native:
                params = {
                    "symbol": sym,
                    "interval": "1h",
                    "limit": 2
                }
                try:
                    async with session.get(url_base, params=params, timeout=10) as resp:
                        data = await resp.json()
                        if data.get('code') == 0:
                            klines = data.get('data', [])
                            print(f"✅ {sym:20} | {len(klines)} свечей")
                        else:
                            print(f"❌ {sym:20} | API: {data.get('msg')}")
                except Exception as e:
                    print(f"❌ {sym:20} | Error: {e}")
                time.sleep(0.3)

    def print_recommendations(self):
        print("\n" + "="*70)
        print("🔧 РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ")
        print("="*70)

        print("""
1. ПРОБЛЕМА:
   CCXT unified symbols для swap: "BTC/USDT:USDT"
   Твой код делает: symbol.replace(':USDT', '') → "BTC/USDT"
   Но CCXT fetch_ohlcv ожидает unified формат "BTC/USDT:USDT"!

2. РЕШЕНИЕ:

   ВАРИАНТ А (рекомендуется): Использовать unified symbols для CCXT методов
   ──────────────────────────────────────────────────────────────────────
   При вызове fetch_ohlcv, fetch_ticker и других CCXT методов 
   используй символ В ФОРМАТЕ "BTC/USDT:USDT".

   ИЗМЕНЕНИЕ В data_fetcher.py:
   - Убрать  .replace(':USDT', '')  при работе с CCXT
   - Или добавлять :USDT обратно перед вызовом fetch_ohlcv

   ВАРИАНТ Б: Фильтровать по нативному API
   ──────────────────────────────────────────────────────────────────────
   Перед сканированием получать список контрактов через:
   /openApi/swap/v2/quote/contracts
   и использовать ТОЛЬКО те символы, которые есть в этом списке.

3. КОНКРЕТНЫЙ ФИКС для data_fetcher.py:

   В методе get_all_usdt_contracts():
   ```python
   # Было (проблема):
   clean_symbol = symbol.replace(':USDT', '')

   # Стало (сохраняем unified для CCXT):
   clean_symbol = symbol  # Оставляем "BTC/USDT:USDT"
   ```

   Или, если тебе нужен формат без :USDT внутри бота:
   ```python
   # Сохраняем 2 версии:
   unified = symbol                    # "BTC/USDT:USDT" → для CCXT
   display = symbol.replace(':USDT', '')  # "BTC/USDT" → для логов/UI
   ```

4. ПРОВЕРКА АКТИВНОСТИ:
   Некоторые символы (MOVR, ONG, 1000BONK) могут быть делистнуты 
   или недоступны в твоем регионе. Всегда проверяй:
   - market.get('active') в CCXT
   - Наличие в нативном /quote/contracts
        """)

    async def run(self):
        print("🔍 BingX Symbol Diagnostic Tool")
        print(f"Время: {pd.Timestamp.now()}")

        if not self.init_ccxt():
            return

        self.load_ccxt_markets()
        await self.fetch_native_contracts()
        self.compare_symbol_lists()
        await self.run_symbol_tests()
        await self.test_native_klines()
        self.print_recommendations()
        self.save_report()

    def save_report(self):
        report = {
            "ccxt_markets_count": len(self.ccxt_symbols),
            "native_markets_count": len(self.native_symbols),
            "problematic_symbols": self.problematic_symbols,
            "timestamp": str(pd.Timestamp.now())
        }
        with open("bingx_diagnostic_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Отчет сохранен: bingx_diagnostic_report.json")


if __name__ == "__main__":
    diag = BingXDiagnostic(api_key="", api_secret="")
    asyncio.run(diag.run())
