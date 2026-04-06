import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime


class TechnicalAnalyzer:
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def calculate_vwap(ohlcv_data: List[List[float]]) -> float:
        if not ohlcv_data or len(ohlcv_data) < 2:
            return 0.0
        
        df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()
        
        return float(df['vwap'].iloc[-1])

    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> float:
        if len(prices) < period:
            return prices[-1] if prices else 0.0
        
        df = pd.DataFrame({'price': prices})
        ema = df['price'].ewm(span=period, adjust=False).mean()
        return float(ema.iloc[-1])

    @staticmethod
    def calculate_adr(highs: List[float], lows: List[float], closes: List[float]) -> float:
        if not highs or not lows:
            return 0.0
        
        ranges = [(h - l) / c * 100 for h, l, c in zip(highs, lows, closes)]
        return np.mean(ranges) if ranges else 0.0

    @staticmethod
    def calculate_momentum(closes: List[float]) -> float:
        if len(closes) < 5:
            return 0.0
        
        momentum = 0
        for i in range(1, min(6, len(closes))):
            if closes[-i] > closes[-i-1]:
                momentum += 1
            elif closes[-i] < closes[-i-1]:
                momentum -= 1
        
        return momentum

    @staticmethod
    def calculate_volume_ratio(volume: float, avg_volume: float) -> float:
        if avg_volume == 0:
            return 1.0
        return volume / avg_volume

    @staticmethod
    def calculate_support_resistance(ohlcv_data: List[List[float]], lookback: int = 20) -> Tuple[float, float]:
        if len(ohlcv_data) < lookback:
            return 0.0, 0.0
        
        recent = ohlcv_data[-lookback:]
        lows = [candle[2] for candle in recent]
        highs = [candle[1] for candle in recent]
        
        support = min(lows)
        resistance = max(highs)
        
        return support, resistance

    @staticmethod
    def analyze_symbol(ohlcv_data: List[List[float]], current_price: float, 
                       volume: float, avg_volume: float) -> Dict[str, Any]:
        if not ohlcv_data:
            return {
                'rsi': 50.0,
                'vwap': 0.0,
                'ema_50': 0.0,
                'ema_200': 0.0,
                'adr': 0.0,
                'momentum': 0.0,
                'volume_ratio': 1.0,
                'support': 0.0,
                'resistance': 0.0,
            }
        
        closes = [candle[4] for candle in ohlcv_data]
        highs = [candle[1] for candle in ohlcv_data]
        lows = [candle[2] for candle in ohlcv_data]
        
        return {
            'rsi': TechnicalAnalyzer.calculate_rsi(closes),
            'vwap': TechnicalAnalyzer.calculate_vwap(ohlcv_data),
            'ema_50': TechnicalAnalyzer.calculate_ema(closes, 50),
            'ema_200': TechnicalAnalyzer.calculate_ema(closes, 200),
            'adr': TechnicalAnalyzer.calculate_adr(highs, lows, closes),
            'momentum': TechnicalAnalyzer.calculate_momentum(closes),
            'volume_ratio': TechnicalAnalyzer.calculate_volume_ratio(volume, avg_volume),
            'support': TechnicalAnalyzer.calculate_support_resistance(ohlcv_data)[0],
            'resistance': TechnicalAnalyzer.calculate_support_resistance(ohlcv_data)[1],
        }


analyzer = TechnicalAnalyzer()