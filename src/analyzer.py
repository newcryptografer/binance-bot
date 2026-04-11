import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

import pandas_ta as ta


class TechnicalAnalyzer:
    def __init__(self):
        self._cache: Dict[str, pd.DataFrame] = {}
    
    @staticmethod
    def _prepare_dataframe(ohlcv_data: List[List[float]]) -> pd.DataFrame:
        df = pd.DataFrame(
            ohlcv_data,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.sort_values('timestamp')
        df = df.set_index('timestamp')
        return df

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        df = pd.DataFrame({'close': prices})
        rsi = df.ta.rsi(length=period)
        return float(rsi.iloc[-1]) if not rsi.empty else 50.0

    @staticmethod
    def calculate_vwap(ohlcv_data: List[List[float]]) -> float:
        if not ohlcv_data or len(ohlcv_data) < 2:
            return 0.0
        df = TechnicalAnalyzer._prepare_dataframe(ohlcv_data)
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()
        return float(df['vwap'].iloc[-1])

    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> float:
        if len(prices) < period:
            return prices[-1] if prices else 0.0
        df = pd.DataFrame({'close': prices})
        ema = df.ta.ema(length=period)
        return float(ema.iloc[-1]) if not ema.empty else prices[-1]

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
        return min(lows), max(highs)
    
    @staticmethod
    def calculate_atr(ohlcv_data: List[List[float]], period: int = 14) -> float:
        if len(ohlcv_data) < period + 1:
            return 0.0
        df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        atr = df.ta.atr(length=period)
        return float(atr.iloc[-1]) if not atr.empty else 0.0
    
    @staticmethod
    def calculate_pivot_sr(ohlcv_data: List[List[float]]) -> Dict[str, float]:
        if len(ohlcv_data) < 2:
            return {'pivot': 0, 's1': 0, 's2': 0, 'r1': 0, 'r2': 0}
        recent = ohlcv_data[-1]
        high, low, close = recent[1], recent[2], recent[4]
        pivot = (high + low + close) / 3
        s1 = pivot * 2 - high
        s2 = pivot - (high - low)
        r1 = pivot * 2 - low
        r2 = pivot + (high - low)
        return {'pivot': pivot, 's1': s1, 's2': s2, 'r1': r1, 'r2': r2}
    
    @staticmethod
    def calculate_market_structure(ohlcv_data: List[List[float]], lookback: int = 50) -> Dict[str, Any]:
        if len(ohlcv_data) < lookback:
            return {'structure': 'unknown', 'trend': 'neutral', 'swing': 0}
        
        recent = ohlcv_data[-lookback:]
        highs = [c[1] for c in recent]
        lows = [c[2] for c in recent]
        closes = [c[4] for c in recent]
        
        hh = max(highs[-10:])
        ll = min(lows[-10:])
        prev_hh = max(highs[-20:-10]) if len(highs) >= 20 else hh
        prev_ll = min(lows[-20:-10]) if len(lows) >= 20 else ll
        
        if hh > prev_hh and ll > prev_ll:
            structure = 'uptrend'
            trend = 'bullish'
        elif hh < prev_hh and ll < prev_ll:
            structure = 'downtrend'
            trend = 'bearish'
        else:
            structure = 'range'
            trend = 'neutral'
        
        swing = hh - ll
        range_pct = swing / closes[-1] * 100 if closes[-1] > 0 else 0
        
        return {
            'structure': structure,
            'trend': trend,
            'hh': hh,
            'll': ll,
            'swing': swing,
            'range_pct': range_pct
        }

    def analyze_multi_timeframe(
        self,
        entry_data: List[List[float]],
        trend_data: List[List[float]],
        main_data: List[List[float]]
    ) -> Dict[str, Any]:
        entry_df = self._prepare_dataframe(entry_data)
        trend_df = self._prepare_dataframe(trend_data)
        main_df = self._prepare_dataframe(main_data)
        
        entry_df.ta.sma(length=20, append=True)
        entry_df.ta.rsi(length=14, append=True)
        entry_df.ta.vwap(append=True)
        
        trend_df.ta.sma(length=50, append=True)
        trend_df.ta.sma(length=200, append=True)
        trend_df.ta.rsi(length=14, append=True)
        trend_df.ta.macd(fast=12, slow=26, signal=9, append=True)
        
        main_df.ta.sma(length=50, append=True)
        main_df.ta.sma(length=200, append=True)
        main_df.ta.rsi(length=14, append=True)
        
        return {
            'entry': self._analyze_tf(entry_df, 'entry'),
            'trend': self._analyze_tf(trend_df, 'trend'),
            'main': self._analyze_tf(main_df, 'main'),
        }
    
    def _analyze_tf(self, df: pd.DataFrame, prefix: str) -> Dict[str, Any]:
        closes = df['close'].values if 'close' in df.columns else []
        last_idx = len(df) - 1 if len(df) > 0 else 0
        
        rsi_col = f'RSI_14' if f'RSI_14' in df.columns else None
        sma20_col = f'SMA_20' if f'SMA_20' in df.columns else None
        sma50_col = f'SMA_50' if f'SMA_50' in df.columns else None
        sma200_col = f'SMA_200' if f'SMA_200' in df.columns else None
        
        rsi = float(df[rsi_col].iloc[-1]) if rsi_col and not df[rsi_col].empty else 50.0
        sma20 = float(df[sma20_col].iloc[-1]) if sma20_col and not df[sma20_col].empty else 0.0
        sma50 = float(df[sma50_col].iloc[-1]) if sma50_col and not df[sma50_col].empty else 0.0
        sma200 = float(df[sma200_col].iloc[-1]) if sma200_col and not df[sma200_col].empty else 0.0
        vwap = float(df['VWAP'].iloc[-1]) if 'VWAP' in df.columns and not df['VWAP'].empty else df['close'].iloc[-1] if len(df) > 0 else 0.0
        
        return {
            'rsi': rsi,
            'sma20': sma20,
            'sma50': sma50,
            'sma200': sma200,
            'vwap': vwap,
            'trend': 'bullish' if sma50 > sma200 else 'bearish' if sma50 < sma200 else 'neutral',
        }

    def analyze_symbol(self, ohlcv_data: List[List[float]], current_price: float,
                      volume: float, avg_volume: float) -> Dict[str, Any]:
        if not ohlcv_data:
            return {
                'rsi': 50.0, 'vwap': 0.0, 'ema_9': 0.0, 'ema_21': 0.0, 'ema_50': 0.0, 'ema_200': 0.0,
                'macd': 0.0, 'macd_signal': 0.0, 'macd_hist': 0.0,
                'stoch_k': 50.0, 'stoch_d': 50.0,
                'atr': 0.0,
                'pivot': 0, 's1': 0, 's2': 0, 'r1': 0, 'r2': 0,
                'adr': 0.0, 'momentum': 0.0, 'volume_ratio': 1.0,
                'support': 0.0, 'resistance': 0.0,
            }
        df = self._prepare_dataframe(ohlcv_data)
        df.ta.rsi(length=14, append=True)
        df.ta.adx(length=14, append=True)
        df.ta.ema(length=9, append=True)
        df.ta.ema(length=21, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.ema(length=200, append=True)
        df.ta.vwap(append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.stoch(length=14, append=True)
        df.ta.atr(length=14, append=True)
        
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        
        pivot = self.calculate_pivot_sr(ohlcv_data)
        structure = self.calculate_market_structure(ohlcv_data)
        
        return {
            'rsi': float(df['RSI_14'].iloc[-1]) if not df['RSI_14'].empty else 50.0,
            'adx': float(df['ADX_14'].iloc[-1]) if 'ADX_14' in df.columns and not df['ADX_14'].empty else 0.0,
            'vwap': float(df['VWAP'].iloc[-1]) if 'VWAP' in df.columns and not df['VWAP'].empty else closes[-1],
            'ema_9': float(df['EMA_9'].iloc[-1]) if 'EMA_9' in df.columns and not df['EMA_9'].empty else 0.0,
            'ema_21': float(df['EMA_21'].iloc[-1]) if 'EMA_21' in df.columns and not df['EMA_21'].empty else 0.0,
            'ema_50': float(df['EMA_50'].iloc[-1]) if 'EMA_50' in df.columns and not df['EMA_50'].empty else 0.0,
            'ema_200': float(df['EMA_200'].iloc[-1]) if 'EMA_200' in df.columns and not df['EMA_200'].empty else 0.0,
            'macd': float(df['MACD_12_26_9'].iloc[-1]) if 'MACD_12_26_9' in df.columns and not df['MACD_12_26_9'].empty else 0.0,
            'macd_signal': float(df['MACDs_12_26_9'].iloc[-1]) if 'MACDs_12_26_9' in df.columns and not df['MACDs_12_26_9'].empty else 0.0,
            'macd_hist': float(df['MACDh_12_26_9'].iloc[-1]) if 'MACDh_12_26_9' in df.columns and not df['MACDh_12_26_9'].empty else 0.0,
            'stoch_k': float(df['STOCHk_14'].iloc[-1]) if 'STOCHk_14' in df.columns and not df['STOCHk_14'].empty else 50.0,
            'stoch_d': float(df['STOCHd_14'].iloc[-1]) if 'STOCHd_14' in df.columns and not df['STOCHd_14'].empty else 50.0,
            'atr': float(df['ATR_14'].iloc[-1]) if 'ATR_14' in df.columns and not df['ATR_14'].empty else 0.0,
            'pivot': pivot['pivot'], 's1': pivot['s1'], 's2': pivot['s2'], 'r1': pivot['r1'], 'r2': pivot['r2'],
            'adr': self.calculate_adr(list(highs), list(lows), list(closes)),
            'momentum': self.calculate_momentum(list(closes)),
            'volume_ratio': self.calculate_volume_ratio(volume, avg_volume),
            'support': self.calculate_support_resistance(ohlcv_data)[0],
            'resistance': self.calculate_support_resistance(ohlcv_data)[1],
            'structure': structure['structure'],
            'trend': structure['trend'],
            'range_pct': structure['range_pct'],
        }


analyzer = TechnicalAnalyzer()