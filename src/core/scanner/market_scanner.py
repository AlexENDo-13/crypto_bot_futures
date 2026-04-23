"""
Модуль сканирования рынка для поиска торговых сигналов
С поддержкой мультитаймфреймного анализа.
Теперь сканирует наиболее ликвидные пары (по объёму за 24ч).
"""
import asyncio
from typing import List, Dict, Optional
import pandas as pd
import numpy as np
from src.core.market.data_fetcher import MarketDataFetcher
from src.utils.api_client import AsyncBingXClient
from src.config.settings import Settings
from src.core.logger import BotLogger


class MarketScanner:
    """Сканер рынка: ищет сигналы на основе технического анализа"""

    def __init__(self, client: AsyncBingXClient, settings: Settings, logger: BotLogger):
        self.client = client
        self.settings = settings
        self.logger = logger
        self.data_fetcher = MarketDataFetcher(client, settings, logger)
        self.active_symbols: List[str] = []
        self._symbols_last_update = 0
        self._symbols_cache_ttl = 3600  # 1 час

    async def get_active_symbols(self) -> List[str]:
        """Получить список активных USDT-фьючерсов."""
        now = asyncio.get_event_loop().time()
        if not self.active_symbols or (now - self._symbols_last_update) > self._symbols_cache_ttl:
            self.active_symbols = await self.data_fetcher.get_all_usdt_contracts()
            self._symbols_last_update = now
        return self.active_symbols

    async def scan_all(self) -> List[Dict]:
        """
        Сканирует все доступные пары, отбирая наиболее ликвидные по объёму,
        и возвращает список сигналов.
        """
        symbols = await self.get_active_symbols()
        if not symbols:
            self.logger.warning("Нет доступных символов для сканирования")
            return []

        max_scan = getattr(self.settings, 'max_scan_symbols', 50)

        # Предварительно загружаем тикеры, чтобы отсортировать по объёму
        try:
            all_tickers = await self.client.get_all_tickers()
            # Сортируем символы по убыванию объёма (quoteVolume), у кого нет – в конец
            def get_volume(sym):
                t = all_tickers.get(sym, {})
                return float(t.get('quoteVolume', 0)) if t else 0
            symbols_sorted = sorted(symbols, key=get_volume, reverse=True)
            symbols_to_scan = symbols_sorted[:max_scan]
        except Exception as e:
            self.logger.warning(f"Не удалось отсортировать по объёму, используем первые {max_scan} символов: {e}")
            symbols_to_scan = symbols[:max_scan]

        use_mtf = getattr(self.settings, 'use_multi_timeframe', False)
        if use_mtf:
            tasks = [self.analyze_symbol_multi_tf(sym) for sym in symbols_to_scan]
        else:
            tasks = [self.analyze_symbol(sym) for sym in symbols_to_scan]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        signals = []
        for res in results:
            if isinstance(res, dict) and res.get("signal"):
                signals.append(res)
            elif isinstance(res, Exception):
                self.logger.error(f"Ошибка при анализе: {res}")

        signals.sort(key=lambda x: x.get("score", 0), reverse=True)
        return signals

    async def analyze_symbol(self, symbol: str, timeframe: str = None) -> Optional[Dict]:
        """Анализирует один символ на наличие сигнала (один таймфрейм)."""
        try:
            if timeframe is None:
                timeframe = getattr(self.settings, 'default_timeframe', '1h')
            df = await self.data_fetcher.fetch_klines(symbol, timeframe, limit=100)
            if df is None or df.empty:
                return None

            if 'rsi' not in df.columns:
                df = await self.data_fetcher.calculate_indicators(df)

            ticker = await self.data_fetcher.fetch_ticker(symbol)
            if not ticker:
                return None

            signal = self._evaluate_signals(symbol, df, ticker)
            return signal
        except Exception as e:
            self.logger.error(f"Ошибка анализа {symbol}: {e}")
            return None

    async def analyze_symbol_multi_tf(self, symbol: str) -> Optional[Dict]:
        """Мультитаймфреймный анализ символа."""
        try:
            timeframes = getattr(self.settings, 'timeframes', ['15m', '1h', '4h'])
            weights = getattr(self.settings, 'timeframe_weights', {
                '15m': 0.2, '1h': 0.5, '4h': 0.3
            })
            min_agreement = getattr(self.settings, 'min_timeframe_agreement', 2)

            signals = []
            for tf in timeframes:
                signal = await self.analyze_symbol(symbol, timeframe=tf)
                if signal and signal.get("signal"):
                    signals.append({
                        'timeframe': tf,
                        'direction': signal['direction'],
                        'score': signal['score'] * weights.get(tf, 0.33),
                        'confidence': signal['confidence'],
                        'price': signal['price'],
                        'volume_24h': signal['volume_24h'],
                    })

            if len(signals) < min_agreement:
                return None

            long_signals = [s for s in signals if s['direction'] == 'LONG']
            short_signals = [s for s in signals if s['direction'] == 'SHORT']

            if len(long_signals) >= min_agreement:
                direction = 'LONG'
                total_score = sum(s['score'] for s in long_signals)
                avg_confidence = sum(s['confidence'] for s in long_signals) / len(long_signals)
                agreeing_tfs = [s['timeframe'] for s in long_signals]
            elif len(short_signals) >= min_agreement:
                direction = 'SHORT'
                total_score = sum(s['score'] for s in short_signals)
                avg_confidence = sum(s['confidence'] for s in short_signals) / len(short_signals)
                agreeing_tfs = [s['timeframe'] for s in short_signals]
            else:
                return None

            primary = signals[0]
            return {
                "symbol": symbol,
                "direction": direction,
                "score": round(total_score, 2),
                "confidence": round(avg_confidence, 2),
                "price": primary['price'],
                "volume_24h": primary['volume_24h'],
                "signal": True,
                "timeframes": agreeing_tfs,
                "multi_timeframe": True,
            }
        except Exception as e:
            self.logger.error(f"Ошибка мультитаймфреймного анализа {symbol}: {e}")
            return None

    def _evaluate_signals(self, symbol: str, df: pd.DataFrame, ticker: Dict) -> Optional[Dict]:
        """
        Оценка сигналов на основе индикаторов.
        ИСПРАВЛЕНО: RSI < 30 → LONG требует подтверждения (цена выше EMA).
        """
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        score = 0
        direction = None

        # RSI с подтверждением разворота
        rsi = last.get('rsi', 50)
        ema_12 = last.get('ema_12', last.get('close', 0))
        close = last.get('close', 0)

        if rsi < 30:
            if close > ema_12 or (last.get('close', 0) > last.get('open', 0)):
                score += 2
                direction = 'LONG'
            else:
                score += 1
        elif rsi > 70:
            if close < ema_12 or (last.get('close', 0) < last.get('open', 0)):
                score += -2
                direction = 'SHORT'
            else:
                score += -1

        # MACD пересечение
        macd = last.get('macd', 0)
        macd_signal = last.get('macd_signal', 0)
        prev_macd = prev.get('macd', 0)
        prev_macd_signal = prev.get('macd_signal', 0)
        if prev_macd <= prev_macd_signal and macd > macd_signal:
            score += 3
            direction = 'LONG'
        elif prev_macd >= prev_macd_signal and macd < macd_signal:
            score += -3
            direction = 'SHORT'

        # Bollinger Bands
        bb_upper = last.get('bb_upper', 0)
        bb_lower = last.get('bb_lower', 0)
        if close <= bb_lower:
            score += 2
            if direction is None:
                direction = 'LONG'
        elif close >= bb_upper:
            score += -2
            if direction is None:
                direction = 'SHORT'

        # Тренд по EMA
        ema_26 = last.get('ema_26', 0)
        if ema_12 > ema_26:
            score += 1
            if direction is None:
                direction = 'LONG'
        else:
            score += -1
            if direction is None:
                direction = 'SHORT'

        # Объём
        volume_ratio = last.get('volume', 0) / (df['volume'].rolling(20).mean().iloc[-1] or 1)
        atr_percent = last.get('atr_percent', 0)
        if volume_ratio > 1.5 and atr_percent > 0.5:
            score += 1 if direction == 'LONG' else -1

        if direction is None:
            return None

        min_score = getattr(self.settings, 'min_signal_score', 4)
        if abs(score) < min_score:
            return None

        # Фильтр ликвидности
        volume_24h = ticker.get('volume_24h', 0)
        min_volume = getattr(self.settings, 'min_volume_24h_usdt', 50000)
        if volume_24h < min_volume:
            return None

        confidence = min(abs(score) / 10.0, 1.0)
        return {
            "symbol": symbol,
            "direction": direction,
            "score": score,
            "confidence": confidence,
            "price": ticker.get('last_price', close),
            "volume_24h": volume_24h,
            "signal": True,
            "rsi": rsi,
            "atr_percent": atr_percent,
            "multi_timeframe": False,
        }
