from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np


class SMCStructure:
    """
    Piyasa Yapısı Analizi
    - Higher Highs/Higher Lows = Uptrend
    - Lower Highs/Lower Lows = Downtrend  
    - Range = Sideways (Konsolidasyon)
    """
    
    def __init__(self, lookback: int = 50):
        self.lookback = lookback
    
    def analyze(self, ohlcv_data: List[List[float]]) -> Dict[str, Any]:
        if not ohlcv_data or len(ohlcv_data) < self.lookback:
            return {
                'structure': 'unknown',
                'trend': 'neutral',
                'direction': 'none',
                'hh': 0, 'll': 0, 'prev_hh': 0, 'prev_ll': 0,
                'swing': 0, 'range_pct': 0,
                'bos': False, 'chos': False,
                'structure_score': 0
            }
        
        recent = ohlcv_data[-self.lookback:]
        highs = [c[1] for c in recent]
        lows = [c[2] for c in recent]
        closes = [c[4] for c in recent]
        
        current_price = closes[-1]
        hh = max(highs[-10:])
        ll = min(lows[-10:])
        prev_hh = max(highs[-20:-10]) if len(highs) >= 20 else hh
        prev_ll = min(lows[-20:-10]) if len(lows) >= 20 else ll
        
        if hh > prev_hh and ll > prev_ll:
            structure = 'uptrend'
            direction = 'LONG'
            trend = 'bullish'
        elif hh < prev_hh and ll < prev_ll:
            structure = 'downtrend'
            direction = 'SHORT'
            trend = 'bearish'
        else:
            structure = 'range'
            direction = 'none'
            trend = 'neutral'
        
        swing = hh - ll
        range_pct = swing / current_price * 100 if current_price > 0 else 0
        
        bos = False
        chos = False
        if structure == 'uptrend' and current_price > hh:
            bos = True
        elif structure == 'downtrend' and current_price < ll:
            bos = True
        
        if (structure == 'uptrend' and prev_hh > prev_ll) or (structure == 'downtrend' and prev_hh < prev_ll):
            if direction != 'none':
                chos = True
        
        structure_score = 0
        if direction == 'LONG':
            structure_score = 50
        elif direction == 'SHORT':
            structure_score = 50
        else:
            structure_score = 0
        
        return {
            'structure': structure,
            'trend': trend,
            'direction': direction,
            'hh': hh,
            'll': ll,
            'prev_hh': prev_hh,
            'prev_ll': prev_ll,
            'swing': swing,
            'range_pct': range_pct,
            'bos': bos,
            'chos': chos,
            'structure_score': structure_score,
            'current_price': current_price
        }


class SMCDecisionEngine:
    """
    SMC Karar Motoru - Ana Karar Mekanizması
    
    Piyasa yapısı hem 1h hem de 4h-1D (ana trend) için analiz edilir.
    Karar = Ana Yapı + Orta Yapı + Teknik Onay
    """
    
    def __init__(self):
        self.structure_1h = SMCStructure(lookback=50)
        self.structure_4h = SMCStructure(lookback=50)
        self.structure_1d = SMCStructure(lookback=30)
        
        self.min_structure_score = 40
        self.require_bos = True
        
        # SMC feature thresholds
        self.liquidity_lookback = 20
        self.stop_hunt_threshold = 0.005  # 0.5%
        self.order_block_min_size = 0.02  # 2% body size
        self.fvg_min_size = 0.001  # 0.1% gap size

    def detect_liquidity_pools(self, ohlcv_data: List[List[float]]) -> Dict[str, Any]:
        """
        Detect liquidity pools (swing highs/lows where stops are likely clustered)
        Returns:
            {
                'liquidity_high': price level or None,
                'liquidity_low': price level or None,
                'strength': float (0-1),
                'description': str
            }
        """
        if len(ohlcv_data) < self.liquidity_lookback:
            return {
                'liquidity_high': None,
                'liquidity_low': None,
                'strength': 0.0,
                'description': 'Insufficient data'
            }
        
        recent = ohlcv_data[-self.liquidity_lookback:]
        highs = [c[1] for c in recent]
        lows = [c[2] for c in recent]
        
        # Find swing highs and lows (local maxima/minima)
        # Simple approach: look for highest high and lowest low in the lookback period
        swing_high = max(highs)
        swing_low = min(lows)
        
        # Count how many times the price touched these levels (within a small threshold)
        threshold = 0.001  # 0.1% tolerance
        high_touches = sum(1 for h in highs if abs(h - swing_high) / swing_high < threshold)
        low_touches = sum(1 for l in lows if abs(l - swing_low) / swing_low < threshold)
        
        # Strength based on number of touches (more touches = stronger liquidity pool)
        strength = min((high_touches + low_touches) / 10, 1.0)  # Normalize to max 1.0
        
        return {
            'liquidity_high': swing_high,
            'liquidity_low': swing_low,
            'strength': strength,
            'description': f'Liquidity pool: High={swing_high:.4f} ({high_touches} touches), Low={swing_low:.4f} ({low_touches} touches)'
        }

    def detect_stop_hunt(self, ohlcv_data: List[List[float]]) -> Dict[str, Any]:
        """
        Detect stop hunt patterns (price briefly breaks swing high/low then reverses)
        Returns:
            {
                'stop_hunt_high': bool (price hunted stops above swing high),
                'stop_hunt_low': bool (price hunted stops below swing low),
                'strength': float (0-1),
                'description': str
            }
        """
        if len(ohlcv_data) < self.liquidity_lookback + 5:  # Need extra for confirmation
            return {
                'stop_hunt_high': False,
                'stop_hunt_low': False,
                'strength': 0.0,
                'description': 'Insufficient data'
            }
        
        # Get liquidity levels first
        liquidity = self.detect_liquidity_pools(ohlcv_data)
        swing_high = liquidity['liquidity_high']
        swing_low = liquidity['liquidity_low']
        
        if swing_high is None or swing_low is None:
            return {
                'stop_hunt_high': False,
                'stop_hunt_low': False,
                'strength': 0.0,
                'description': 'Could not determine liquidity levels'
            }
        
        # Check recent candles for stop hunt patterns
        recent = ohlcv_data[-5:]  # Last 5 candles
        highs = [c[1] for c in recent]
        lows = [c[2] for c in recent]
        closes = [c[4] for c in recent]
        
        # Stop hunt above: price goes above swing high but closes below it (bearish trap)
        stop_hunt_high = False
        for i, (high, close) in enumerate(zip(highs, closes)):
            if high > swing_high * (1 + self.stop_hunt_threshold) and close < swing_high:
                stop_hunt_high = True
                break
        
        # Stop hunt below: price goes below swing low but closes above it (bullish trap)
        stop_hunt_low = False
        for i, (low, close) in enumerate(zip(lows, closes)):
            if low < swing_low * (1 - self.stop_hunt_threshold) and close > swing_low:
                stop_hunt_low = True
                break
        
        # Strength based on how aggressive the hunt was
        max_excursion_high = max((h - swing_high) / swing_high for h in highs) if highs else 0
        max_excursion_low = max((swing_low - l) / swing_low for l in lows) if lows else 0
        strength = min(max(max_excursion_high, max_excursion_low) / self.stop_hunt_threshold, 1.0)
        
        description_parts = []
        if stop_hunt_high:
            description_parts.append(f"Stop hunt above {swing_high:.4f}")
        if stop_hunt_low:
            description_parts.append(f"Stop hunt below {swing_low:.4f}")
        
        return {
            'stop_hunt_high': stop_hunt_high,
            'stop_hunt_low': stop_hunt_low,
            'strength': strength,
            'description': ', '.join(description_parts) if description_parts else 'No stop hunt detected'
        }

    def detect_order_blocks(self, ohlcv_data: List[List[float]]) -> Dict[str, Any]:
        """
        Detect order blocks (areas where large institutions likely placed orders)
        Returns:
            {
                'bullish_ob': price level or None (recent bearish candle before bullish move),
                'bearish_ob': price level or None (recent bullish candle before bearish move),
                'strength': float (0-1),
                'description': str
            }
        """
        if len(ohlcv_data) < 10:
            return {
                'bullish_ob': None,
                'bearish_ob': None,
                'strength': 0.0,
                'description': 'Insufficient data'
            }
        
        recent = ohlcv_data[-20:]  # Look at last 20 candles
        bullish_ob = None
        bearish_ob = None
        
        # Look for order blocks: strong candle followed by opposite color candle
        for i in range(2, len(recent)):
            curr = recent[i]
            prev = recent[i-1]
            before_prev = recent[i-2]
            
            curr_open, curr_close = curr[0], curr[3]
            prev_open, prev_close = prev[0], prev[3]
            before_prev_open, before_prev_close = before_prev[0], before_prev[3]
            
            curr_body_size = abs(curr_close - curr_open)
            prev_body_size = abs(prev_close - prev_open)
            
            # Bullish OB: Bearish candle followed by strong bullish candle
            if prev_close < prev_open and curr_close > curr_open:  # Prev bearish, curr bullish
                if curr_body_size > prev_body_size * self.order_block_min_size:
                    # Check if this is followed by continued bullish momentum
                    if i < len(recent) - 1:
                        next_candle = recent[i+1]
                        next_close = next_candle[3]
                        if next_close > curr_close:  # Continued bullish
                            bullish_ob = (prev_open + prev_close) / 2  # Midpoint of the bearish candle
            
            # Bearish OB: Bullish candle followed by strong bearish candle
            if prev_close > prev_open and curr_close < curr_open:  # Prev bullish, curr bearish
                if curr_body_size > prev_body_size * self.order_block_min_size:
                    # Check if this is followed by continued bearish momentum
                    if i < len(recent) - 1:
                        next_candle = recent[i+1]
                        next_close = next_candle[3]
                        if next_close < curr_close:  # Continued bearish
                            bearish_ob = (prev_open + prev_close) / 2  # Midpoint of the bullish candle
        
        # Strength based on how recent and significant the OB is
        strength = 0.0
        if bullish_ob is not None or bearish_ob is not None:
            strength = 0.7  # Base strength
            # Increase strength if multiple OBs found or if they're very recent
            if bullish_ob is not None and bearish_ob is not None:
                strength = 0.9
        
        description_parts = []
        if bullish_ob is not None:
            description_parts.append(f"Bullish OB at {bullish_ob:.4f}")
        if bearish_ob is not None:
            description_parts.append(f"Bearish OB at {bearish_ob:.4f}")
        
        return {
            'bullish_ob': bullish_ob,
            'bearish_ob': bearish_ob,
            'strength': strength,
            'description': ', '.join(description_parts) if description_parts else 'No order blocks detected'
        }

    def detect_fair_value_gaps(self, ohlcv_data: List[List[float]]) -> Dict[str, Any]:
        """
        Detect Fair Value Gaps (FVG) - imbalances in price action where price moves quickly leaving a gap
        Returns:
            {
                'bullish_fvg': price level or None (gap between low of candle 1 and high of candle 3),
                'bearish_fvg': price level or None (gap between high of candle 1 and low of candle 3),
                'strength': float (0-1),
                'description': str
            }
        """
        if len(ohlcv_data) < 3:
            return {
                'bullish_fvg': None,
                'bearish_fvg': None,
                'strength': 0.0,
                'description': 'Insufficient data (need at least 3 candles)'
            }
        
        # Look at the last 3 candles for FVG pattern
        candle1 = ohlcv_data[-3]  # First candle
        candle2 = ohlcv_data[-2]  # Middle candle
        candle3 = ohlcv_data[-1]  # Last candle
        
        # Bullish FVG: Gap between low of candle 1 and high of candle 3 (when price moves up sharply)
        # This happens when candle3.low > candle1.high (gap up)
        bullish_fvg = None
        if candle3[2] > candle1[1]:  # candle3 low > candle1 high
            bullish_fvg = (candle1[1] + candle3[2]) / 2  # Midpoint of the gap
        
        # Bearish FVG: Gap between high of candle 1 and low of candle 3 (when price moves down sharply)
        # This happens when candle3.high < candle1.low (gap down)
        bearish_fvg = None
        if candle3[1] < candle1[2]:  # candle3 high < candle1 low
            bearish_fvg = (candle1[2] + candle3[1]) / 2  # Midpoint of the gap
        
        # Calculate gap size as percentage of price
        avg_price = (candle1[4] + candle2[4] + candle3[4]) / 3  # Average of closing prices
        bullish_gap_size = (candle3[2] - candle1[1]) / avg_price if candle3[2] > candle1[1] else 0
        bearish_gap_size = (candle1[2] - candle3[1]) / avg_price if candle1[2] > candle3[1] else 0
        
        # Strength based on gap size (normalized)
        strength = min(max(bullish_gap_size, bearish_gap_size) / self.fvg_min_size, 1.0) if avg_price > 0 else 0
        
        description_parts = []
        if bullish_fvg is not None:
            description_parts.append(f"Bullish FVG at {bullish_fvg:.4f} (gap: {bullish_gap_size:.2%})")
        if bearish_fvg is not None:
            description_parts.append(f"Bearish FVG at {bearish_fvg:.4f} (gap: {bearish_gap_size:.2%})")
        
        return {
            'bullish_fvg': bullish_fvg,
            'bearish_fvg': bearish_fvg,
            'strength': strength,
            'description': ', '.join(description_parts) if description_parts else 'No fair value gaps detected'
        }
    
    def analyze_structure(
        self,
        data_1h: List[List[float]],
        data_4h: List[List[float]],
        data_1d: Optional[List[List[float]]] = None
    ) -> Dict[str, Any]:
        """Tüm timeframe'lerde piyasa yapısını analiz et"""
        
        struct_1h = self.structure_1h.analyze(data_1h)
        struct_4h = self.structure_4h.analyze(data_4h)
        
        struct_1d = None
        if data_1d:
            struct_1d = self.structure_1d.analyze(data_1d)
        
        return {
            '1h': struct_1h,
            '4h': struct_4h,
            '1d': struct_1d,
            'main': struct_4h if not data_1d else (struct_1d if struct_1d else struct_4h),
            'trend': struct_4h
        }
    
    def make_decision(
        self,
        structure_data: Dict[str, Any],
        technical_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        SMC Karar Motoru - Ana Karar Fonksiyonu
        
        Returns:
            {
                'decision': 'LONG' | 'SHORT' | 'WAIT',
                'reason': str,
                'confidence': float (0-100),
                'structure_confirmed': bool,
                'main_trend': 'LONG' | 'SHORT' | 'none',
                'entry_allowed': bool
            }
        """
        
        main_trend = structure_data.get('main', {}).get('direction', 'none')
        trend_1h = structure_data.get('1h', {}).get('direction', 'none')
        trend_4h = structure_data.get('4h', {}).get('direction', 'none')
        
        main_structure = structure_data.get('main', {}).get('structure', 'unknown')
        main_trend_val = structure_data.get('main', {}).get('trend', 'neutral')
        
        if main_structure == 'range':
            return {
                'decision': 'WAIT',
                'reason': 'Market in range (sideways) - no clear trend',
                'confidence': 0,
                'structure_confirmed': False,
                'main_trend': 'none',
                'entry_allowed': False
            }
        
        if main_trend == 'none':
            return {
                'decision': 'WAIT',
                'reason': 'No clear market structure',
                'confidence': 0,
                'structure_confirmed': False,
                'main_trend': 'none',
                'entry_allowed': False
            }
        
        structure_score = 0
        entry_allowed = False
        confidence = 0
        
        if main_trend == trend_1h:
            structure_score += 30
            if main_trend == trend_4h:
                structure_score += 20
        
        structure_confirmed = structure_score >= self.min_structure_score
        
        if structure_confirmed:
            confidence = structure_score + technical_data.get('momentum_score', 0) + technical_data.get('technical_score', 0)
            confidence = min(confidence, 100)
            
            if confidence >= 50:
                entry_allowed = True
        
        if not entry_allowed:
            return {
                'decision': 'WAIT',
                'reason': f'Structure not confirmed (score: {structure_score})',
                'confidence': confidence,
                'structure_confirmed': structure_confirmed,
                'main_trend': main_trend,
                'entry_allowed': False
            }
        
        return {
            'decision': main_trend,
            'reason': f'Main trend confirmed: {main_trend_val}',
            'confidence': confidence,
            'structure_confirmed': structure_confirmed,
            'main_trend': main_trend,
            'entry_allowed': entry_allowed,
            'structure_data': {
                '1h': structure_data.get('1h', {}).get('structure'),
                '4h': structure_data.get('4h', {}).get('structure'),
            }
        }
    
    def get_entry_direction(
        self,
        data_1h: List[List[float]],
        data_4h: List[List[float]],
        data_1d: Optional[List[List[float]]] = None,
        technical_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ana giriş kararı - SMC'ye göre yön belirleme
        """
        
        if technical_data is None:
            technical_data = {}
        
        structure_data = self.analyze_structure(data_1h, data_4h, data_1d)
        
        return self.make_decision(structure_data, technical_data)
    
    def validate_entry(
        self,
        decision: Dict[str, Any],
        entry_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Giriş için ek doğrulama
        """
        
        if not decision.get('entry_allowed', False):
            return {
                'valid': False,
                'reason': decision.get('reason', 'Entry not allowed')
            }
        
        direction = decision.get('main_trend', 'none')
        
        rsi = entry_data.get('rsi', 50)
        if direction == 'LONG' and rsi > 75:
            return {
                'valid': False,
                'reason': f'RSI overbought: {rsi}'
            }
        if direction == 'SHORT' and rsi < 25:
            return {
                'valid': False,
                'reason': f'RSI oversold: {rsi}'
            }
        
        adx = entry_data.get('adx', 0)
        if adx < 20:
            return {
                'valid': False,
                'reason': f'ADX too weak: {adx}'
            }
        
        structure_1h = entry_data.get('structure')
        if structure_1h == 'range':
            return {
                'valid': False,
                'reason': 'Entry timeframe in range'
            }
        
        return {
            'valid': True,
            'reason': 'Entry validated'
        }


smc_engine = SMCDecisionEngine()