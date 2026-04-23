"""
Модуль сканирования рынка для поиска торговых сигналов
С поддержкой мультитаймфреймного анализа
"""
import asyncio
from typing import List, Dict, Optional
import pandas as pd

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
        Сканирует все доступные пары и возвращает список сигналов.
        Использует мультитаймфрейм если включен в настройках.
        """
        symbols = await self.get_active_symbols()
        if not symbols:
            self.logger.warning("Нет доступных символов для сканирования")
            return []

        max_scan = getattr(self.settings, 'max_scan_symbols', 50)
        symbols_to_scan = symbols[:max_scan]

        # Определяем использовать ли мультитаймфрейм
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
        """
        Мультитаймфреймный анализ символа.
        Агрегирует сигналы с нескольких таймфреймов с весами.
        """
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

            # Проверяем согласие направлений
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
                return None  # Нет согласия

            # Берём цену и объём из основного таймфрейма (обычно 1h)
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
        """Оценка сигналов на основе индикаторов."""
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last

        score = 0
        direction = None

        # 1. RSI
        rsi = last.get('rsi', 50)
        if rsi < 30:
            score += 2
            direction = 'LONG'
        elif rsi > 70:
            score += -2
            direction = 'SHORT'

        # 2. MACD пересечение
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

        # 3. Цена относительно Bollinger Bands
        close = last['close']
        bb_upper = last.get('bb_upper', float('inf'))
        bb_lower = last.get('bb_lower', 0)
        if close < bb_lower:
            score += 1
            if direction is None:
                direction = 'LONG'
        elif close > bb_upper:
            score += -1
            if direction is None:
                direction = 'SHORT'

        # 4. SMA 20/50 пересечение
        sma20 = last.get('sma_20')
        sma50 = last.get('sma_50')
        prev_sma20 = prev.get('sma_20')
        prev_sma50 = prev.get('sma_50')
        if sma20 and sma50 and prev_sma20 and prev_sma50:
            if prev_sma20 <= prev_sma50 and sma20 > sma50:
                score += 2
                if direction is None:
                    direction = 'LONG'
            elif prev_sma20 >= prev_sma50 and sma20 < sma50:
                score += -2
                if direction is None:
                    direction = 'SHORT'

        # Фильтр по минимальному объёму
        min_volume = getattr(self.settings, 'min_volume_24h_usdt', 0)
        if ticker.get('volume_24h', 0) < min_volume:
            return None

        # Проверяем минимальный счёт — ИСПРАВЛЕНО: используем min_signal_score
        min_score = getattr(self.settings, 'min_signal_score', 4)
        if abs(score) >= min_score and direction is not None:
            confidence = min(abs(score) / 10.0, 1.0)
            return {
                "symbol": symbol,
                "direction": direction,
                "score": score,
                "confidence": confidence,
                "price": ticker['last_price'],
                "volume_24h": ticker['volume_24h'],
                "signal": True,
                "indicators": {
                    "rsi": rsi,
                    "macd": macd,
                    "macd_signal": macd_signal,
                    "sma20": sma20,
                    "sma50": sma50,
                }
            }
        return None
