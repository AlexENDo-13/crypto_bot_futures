#!/usr/bin/env python3
"""
Диагностический тестер для BingX Trading Bot.
Проверяет все этапы сканирования и принятия решений без открытия реальных ордеров.
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from src.config.settings import Settings
from src.core.logger import BotLogger
from src.utils.api_client import AsyncBingXClient
from src.core.market.data_fetcher import DataFetcher
from src.core.risk.risk_manager import RiskManager
from src.core.risk.risk_controller import RiskController
from src.core.signals.signal_evaluator import SignalEvaluator
from src.config.constants import TimeFrame
import pandas as pd

# Настройки
MAX_PAIRS_TO_ANALYZE = 30  # ограничим число пар для скорости
MIN_VOLUME_24H = 10000     # из конфига
MAX_SPREAD_PERCENT = 0.5
MAX_FUNDING_RATE = 0.005
IGNORE_SESSION = True

async def main():
    print("🔍 Запуск диагностического тестера...")
    settings = Settings()
    logger = BotLogger(level="INFO")

    # Инициализация клиента
    client = AsyncBingXClient(
        api_key=settings.get("api_key"),
        api_secret=settings.get("api_secret"),
        demo_mode=settings.get("demo_mode", True),
        settings=settings.data
    )
    await client._sync_server_time()
    logger.info("Клиент BingX инициализирован")

    data_fetcher = DataFetcher(client, logger, settings.data)
    risk_manager = RiskManager(client, settings.data)
    risk_controller = RiskController(logger, settings.data)
    signal_evaluator = SignalEvaluator(settings.data)

    # Получаем контракты
    contracts = await data_fetcher.get_all_usdt_contracts()
    print(f"📋 Загружено {len(contracts)} контрактов")

    # Получаем реальный баланс для расчетов
    account = await client.get_account_info()
    if account:
        balance = account['balance']
        print(f"💰 Реальный баланс: {balance:.2f} USDT")
    else:
        balance = settings.get("virtual_balance", 100.0)
        print(f"⚠️ Не удалось получить баланс, используется виртуальный: {balance:.2f} USDT")

    report = {
        "timestamp": datetime.now().isoformat(),
        "balance": balance,
        "total_contracts": len(contracts),
        "analyzed_pairs": [],
        "summary": {"passed_initial": 0, "passed_indicators": 0, "passed_position_size": 0}
    }

    # Фильтрация по первичным критериям (объём, спред, фандинг)
    filtered_symbols = []
    print("\n🔎 Первичная фильтрация...")
    for contract in contracts[:200]:  # Ограничим до 200 для скорости
        symbol = contract['symbol']
        # Пропускаем проблемные символы
        if symbol.startswith('NC') or symbol == "TRUMP/USDT":
            continue
        try:
            ticker = await client.get_ticker(symbol)
            volume = ticker.get('volume24h', 0)
            if volume < MIN_VOLUME_24H:
                continue

            # Проверка спреда
            ob = await client.get_order_book(symbol, limit=5)
            bids = ob.get('bids', [])
            asks = ob.get('asks', [])
            if bids and asks:
                spread = (float(asks[0][0]) - float(bids[0][0])) / float(bids[0][0]) * 100
                if spread > MAX_SPREAD_PERCENT:
                    continue

            # Проверка фандинга
            funding_data = await client.get_funding_rate(symbol)
            funding = funding_data.get('fundingRate', 0)
            if funding > MAX_FUNDING_RATE:
                continue

            filtered_symbols.append(symbol)
        except Exception as e:
            logger.debug(f"Ошибка при проверке {symbol}: {e}")

    print(f"✅ Первичный фильтр прошли: {len(filtered_symbols)} пар")
    report["summary"]["passed_initial"] = len(filtered_symbols)

    # Ограничиваем число пар для глубокого анализа
    symbols_to_analyze = filtered_symbols[:MAX_PAIRS_TO_ANALYZE]

    # Глубокий анализ
    print(f"\n🧠 Глубокий анализ {len(symbols_to_analyze)} пар...")
    for i, symbol in enumerate(symbols_to_analyze, 1):
        print(f"  [{i}/{len(symbols_to_analyze)}] {symbol}...", end=' ')
        result = {
            "symbol": symbol,
            "stage": "unknown",
            "verdict": "FAIL",
            "reason": "",
            "indicators": {}
        }

        try:
            # Загружаем свечи
            session = await client._get_session()
            df = await data_fetcher.fetch_klines_async(session, symbol, TimeFrame.H1.value, 100)
            if df is None or len(df) < 50:
                result["stage"] = "klines"
                result["reason"] = "Недостаточно свечей"
                report["analyzed_pairs"].append(result)
                print("❌ нет свечей")
                continue

            # Рассчитываем индикаторы
            indicators = data_fetcher.calculate_indicators(df)
            if not indicators:
                result["stage"] = "indicators"
                result["reason"] = "Ошибка расчёта индикаторов"
                report["analyzed_pairs"].append(result)
                print("❌ ошибка индикаторов")
                continue

            result["indicators"] = {
                "atr_percent": indicators.get("atr_percent", 0),
                "adx": indicators.get("adx", 0),
                "rsi": indicators.get("rsi", 50),
                "trend_score": indicators.get("trend_score", 0),
                "close_price": indicators.get("close_price", 0)
            }

            # Проверка минимальных порогов (из конфига)
            min_atr = settings.get("min_atr_percent", 0.5)
            min_adx = settings.get("min_adx", 10)
            atr = indicators.get("atr_percent", 0)
            adx = indicators.get("adx", 0)
            if atr < min_atr:
                result["stage"] = "thresholds"
                result["reason"] = f"ATR {atr:.2f}% < {min_atr}%"
                report["analyzed_pairs"].append(result)
                print(f"❌ ATR={atr:.2f}%")
                continue
            if adx < min_adx:
                result["stage"] = "thresholds"
                result["reason"] = f"ADX {adx:.1f} < {min_adx}"
                report["analyzed_pairs"].append(result)
                print(f"❌ ADX={adx:.1f}")
                continue

            # Оценка сигнала
            direction, strength, details = signal_evaluator.evaluate(indicators, multi_tf_data=None)
            if direction.value == "NEUTRAL" or strength < 0.6:
                result["stage"] = "signal"
                result["reason"] = f"Слабый сигнал ({direction.value}, сила {strength:.2f})"
                report["analyzed_pairs"].append(result)
                print(f"❌ сигнал {direction.value} ({strength:.2f})")
                continue

            result["indicators"]["signal_direction"] = direction.value
            result["indicators"]["signal_strength"] = strength

            # Расчёт размера позиции
            current_price = indicators.get("close_price", 0)
            stop_distance_pct = max(1.5, min(1.5 * atr, 8.0))  # как в TradeExecutor
            risk_percent = settings.get("max_risk_per_trade", 2.0)
            leverage = settings.get("max_leverage", 3)

            qty = risk_manager.calculate_position_size(
                symbol, balance, risk_percent, stop_distance_pct,
                leverage, atr, current_price
            )

            if qty == 0:
                result["stage"] = "position_size"
                result["reason"] = "qty = 0 (недостаточно маржи или нарушен мин. номинал)"
                report["analyzed_pairs"].append(result)
                print("❌ qty=0")
                continue

            notional = qty * current_price
            min_notional = risk_manager._get_min_notional(symbol) or risk_manager.MIN_NOTIONAL
            margin = notional / leverage

            result["position"] = {
                "qty": qty,
                "notional": notional,
                "min_notional": min_notional,
                "margin_required": margin,
                "available_balance": balance
            }

            if notional < min_notional:
                result["stage"] = "position_size"
                result["reason"] = f"Номинал {notional:.2f} < {min_notional:.2f}"
                report["analyzed_pairs"].append(result)
                print(f"❌ номинал {notional:.2f} < {min_notional:.2f}")
                continue

            if margin > balance:
                result["stage"] = "position_size"
                result["reason"] = f"Маржа {margin:.2f} > баланс {balance:.2f}"
                report["analyzed_pairs"].append(result)
                print(f"❌ маржа {margin:.2f} > баланс")
                continue

            # Все проверки пройдены!
            result["stage"] = "ready"
            result["verdict"] = "PASS"
            report["analyzed_pairs"].append(result)
            report["summary"]["passed_position_size"] += 1
            print("✅ ПРОШЛА ВСЕ ПРОВЕРКИ!")
            report["summary"]["passed_indicators"] += 1

        except Exception as e:
            result["stage"] = "error"
            result["reason"] = str(e)
            report["analyzed_pairs"].append(result)
            print(f"💥 ошибка: {e}")

    # Сохраняем отчёт
    report_path = Path("diagnostic_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n" + "="*50)
    print("📊 ИТОГИ ДИАГНОСТИКИ")
    print("="*50)
    print(f"Прошли первичный фильтр: {report['summary']['passed_initial']}")
    print(f"Прошли пороги (ATR/ADX) и сигнал: {report['summary']['passed_indicators']}")
    print(f"Прошли проверку размера позиции: {report['summary']['passed_position_size']}")
    print(f"\n📄 Подробный отчёт сохранён в: {report_path}")

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
