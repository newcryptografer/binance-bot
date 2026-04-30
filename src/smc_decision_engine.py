from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from collections import deque


class SMCStructure:
    """Piyasa Yapısı Analizi"""
    
    def __init__(self, lookback: int = 50):
        self.lookback = lookback
    
    def analyze(self, ohlcv_data: List[List[float]]) -> Dict[str, Any]:
        if not ohlcv_data or len(ohlcv_data) < self.lookback:
            return {
                'structure': 'unknown', 'trend': 'neutral', 'direction': 'none',
                'hh': 0, 'll': 0, 'structure_score': 0, 'current_price': 0
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
            structure, direction, trend = 'uptrend', 'LONG', 'bullish'
        elif hh < prev_hh and ll < prev_ll:
            structure, direction, trend = 'downtrend', 'SHORT', 'bearish'
        else:
            structure, direction, trend = 'range', 'none', 'neutral'
        
        swing = hh - ll
        range_pct = swing / current_price * 100 if current_price > 0 else 0
        
        bos = (structure == 'uptrend' and current_price > hh) or (structure == 'downtrend' and current_price < ll)
        chos = (structure == 'uptrend' and prev_hh > prev_ll) or (structure == 'downtrend' and prev_hh < prev_ll)
        
        structure_score = 50 if direction in ('LONG', 'SHORT') else 0
        
        return {
            'structure': structure, 'trend': trend, 'direction': direction,
            'hh': hh, 'll': ll, 'prev_hh': prev_hh, 'prev_ll': prev_ll,
            'swing': swing, 'range_pct': range_pct,
            'bos': bos, 'chos': chos,
            'structure_score': structure_score, 'current_price': current_price
        }


class SMCAdvancedFeatures:
    """Seçenek 1,2,3 için gelişmiş SMC özellikleri"""
    
    def __init__(self):
        self.liquidity_lookback = 20
        self.stop_hunt_threshold = 0.005
        self.order_block_min_size = 0.02
        self.fvg_min_size = 0.001
    
    def apply_option(self, ohlcv_data: List[List[float]], option: int) -> Dict[str, Any]:
        if not ohlcv_data or len(ohlcv_data) < 10:
            return {'option': option, 'strength': 0.0, 'signal': 'WAIT', 'description': 'Yetersiz veri'}
        
        if option == 1:
            return self._option1_liquidity_stop_hunt(ohlcv_data)
        elif option == 2:
            return self._option2_order_block_liquidity(ohlcv_data)
        elif option == 3:
            return self._option3_full_analysis(ohlcv_data)
        return {'option': option, 'strength': 0.0, 'signal': 'WAIT', 'description': 'Invalid option'}
    
    def _option1_liquidity_stop_hunt(self, ohlcv_data: List[List[float]]) -> Dict[str, Any]:
        recent = ohlcv_data[-self.liquidity_lookback:]
        highs = [c[1] for c in recent]
        lows = [c[2] for c in recent]
        closes = [c[4] for c in recent]
        
        swing_high = max(highs)
        swing_low = min(lows)
        
        threshold = 0.001
        high_touches = sum(1 for h in highs if abs(h - swing_high) / swing_high < threshold)
        low_touches = sum(1 for l in lows if abs(l - swing_low) / swing_low < threshold)
        liquidity_strength = min((high_touches + low_touches) / 10, 1.0)
        
        stop_hunt = False
        for i in range(len(closes)-1):
            if recent[i][1] > swing_high * (1 + self.stop_hunt_threshold) and closes[i+1] < swing_high:
                stop_hunt = True
                break
        
        strength = liquidity_strength * 0.7 + (0.3 if stop_hunt else 0)
        signal = 'LONG' if strength > 0.5 else 'SHORT' if strength > 0.3 else 'WAIT'
        
        return {
            'option': 1, 'strength': strength, 'signal': signal,
            'description': f'Liquidity={liquidity_strength:.2f}, StopHunt={stop_hunt}'
        }
    
    def _option2_order_block_liquidity(self, ohlcv_data: List[List[float]]) -> Dict[str, Any]:
        if len(ohlcv_data) < 10:
            return {'option': 2, 'strength': 0, 'signal': 'WAIT', 'description': 'Yetersiz veri'}
        
        recent = ohlcv_data[-20:]
        bullish_ob = bearish_ob = None
        
        for i in range(2, len(recent)):
            curr, prev = recent[i], recent[i-1]
            curr_body = abs(curr[3] - curr[0])
            prev_body = abs(prev[3] - prev[0])
            
            if prev[3] < prev[0] and curr[3] > curr[0]:  # prev bearish, curr bullish
                if curr_body > prev_body * 2 and i < len(recent)-1:
                    if recent[i+1][3] > curr[3]:
                        bullish_ob = (prev[0] + prev[3]) / 2
            
            if prev[3] > prev[0] and curr[3] < curr[0]:  # prev bullish, curr bearish
                if curr_body > prev_body * 2 and i < len(recent)-1:
                    if recent[i+1][3] < curr[3]:
                        bearish_ob = (prev[0] + prev[3]) / 2
        
        liquidity = self._calc_liquidity(ohlcv_data[-20:])
        strength = 0.0
        signal = 'WAIT'
        if bullish_ob is not None:
            strength = 0.8
            signal = 'LONG'
        elif bearish_ob is not None:
            strength = 0.8
            signal = 'SHORT'
        
        return {
            'option': 2, 'strength': strength, 'signal': signal,
            'description': f'BullOB={bullish_ob is not None}, BearOB={bearish_ob is not None}, Liq={liquidity:.2f}'
        }
    
    def _calc_liquidity(self, data: List[List[float]]) -> float:
        highs = [c[1] for c in data]
        lows = [c[2] for c in data]
        return (max(highs) - min(lows)) / data[-1][4] * 100 if data else 0
    
    def _option3_full_analysis(self, ohlcv_data: List[List[float]]) -> Dict[str, Any]:
        fvg = self._calc_fvg(ohlcv_data)
        ob = self._option2_order_block_liquidity(ohlcv_data)
        
        strength = fvg['strength'] * 0.4 + ob['strength'] * 0.6
        signal = 'WAIT'
        if strength > 0.7:
            signal = fvg['signal'] if fvg['signal'] != 'WAIT' else ob['signal']
        elif strength > 0.5:
            signal = ob['signal'] if ob['signal'] != 'WAIT' else 'WAIT'
        
        return {
            'option': 3, 'strength': strength, 'signal': signal,
            'description': f'FVG={fvg["description"]}, OB={ob["description"]}'
        }
    
    def _calc_fvg(self, ohlcv_data: List[List[float]]) -> Dict[str, Any]:
        if len(ohlcv_data) < 3:
            return {'strength': 0, 'signal': 'WAIT', 'description': 'FVG yok'}
        
        c1, c3 = ohlcv_data[-3], ohlcv_data[-1]
        bullish_fvg = c3[2] > c1[1]
        bearish_fvg = c3[1] < c1[2]
        
        avg_price = (ohlcv_data[-3][4] + ohlcv_data[-2][4] + ohlcv_data[-1][4]) / 3
        gap_size = 0
        signal = 'WAIT'
        if bullish_fvg:
            gap_size = (c3[2] - c1[1]) / avg_price if avg_price > 0 else 0
            signal = 'LONG'
        elif bearish_fvg:
            gap_size = (c1[2] - c3[1]) / avg_price if avg_price > 0 else 0
            signal = 'SHORT'
        
        strength = min(gap_size / self.fvg_min_size, 1.0) if avg_price > 0 else 0
        return {
            'strength': strength, 'signal': signal,
            'description': f'FVG_{signal}={gap_size:.2%}' if gap_size > 0 else 'FVG yok'
        }


class SMCDecisionEngine:
    """Tüm SMC özelliklerini birleştiren karar motoru"""
    
    def __init__(self):
        self.structure_1h = SMCStructure(lookback=50)
        self.structure_4h = SMCStructure(lookback=50)
        self.structure_1d = SMCStructure(lookback=30)
        self.advanced = SMCAdvancedFeatures()
        self.min_structure_score = 40
        self.cache = {}
        self.cache_ttl = 30
    
    def analyze_structure(
        self,
        data_1h: List[List[float]],
        data_4h: List[List[float]],
        data_1d: Optional[List[List[float]]] = None
    ) -> Dict[str, Any]:
        struct_1h = self.structure_1h.analyze(data_1h)
        struct_4h = self.structure_4h.analyze(data_4h)
        struct_1d = None
        if data_1d:
            struct_1d = self.structure_1d.analyze(data_1d)
        
        return {
            '1h': struct_1h, '4h': struct_4h, '1d': struct_1d,
            'main': struct_4h if not data_1d else (struct_1d if struct_1d else struct_4h),
            'trend': struct_4h
        }
    
    def make_decision(
        self,
        structure_data: Dict[str, Any],
        technical_data: Dict[str, Any],
        ohlcv_1h: List[List[float]],
        option: int = 1
    ) -> Dict[str, Any]:
        main_trend = structure_data.get('main', {}).get('direction', 'none')
        trend_1h = structure_data.get('1h', {}).get('direction', 'none')
        trend_4h = structure_data.get('4h', {}).get('direction', 'none')
        trend_1d = structure_data.get('1d', {}).get('direction') if structure_data.get('1d') else None
        
        main_structure = structure_data.get('main', {}).get('structure', 'unknown')
        
        if main_structure == 'range':
            return {'decision': 'WAIT', 'reason': 'Range piyasası', 'confidence': 0, 'entry_allowed': False}
        if main_trend == 'none':
            return {'decision': 'WAIT', 'reason': 'Trend yok', 'confidence': 0, 'entry_allowed': False}
        
        structure_score = 0
        entry_allowed = False
        confidence = 0
        
        if main_trend == trend_1h:
            structure_score += 30
            if main_trend == trend_4h:
                structure_score += 20
            if trend_1d and main_trend == trend_1d:
                structure_score += 25
        
        # Gelişmiş SMC analizi
        advanced = self.advanced.apply_option(ohlcv_1h, option)
        
        if structure_score >= self.min_structure_score:
            confidence = min(structure_score + 
                            technical_data.get('momentum_score', 0) + 
                            technical_data.get('technical_score', 0) +
                            (advanced['strength'] * 30), 100)
            
            # Seçenek bazlı eşik
            thresholds = {1: 40, 2: 50, 3: 60}
            if confidence >= thresholds.get(option, 50):
                entry_allowed = True
        
        if not entry_allowed:
            return {
                'decision': 'WAIT',
                'reason': f'Structure={structure_score}, Confidence={confidence:.1f}',
                'confidence': confidence,
                'structure_confirmed': structure_score >= self.min_structure_score,
                'main_trend': main_trend,
                'entry_allowed': False
            }
        
        return {
            'decision': main_trend,
            'reason': f'{main_trend} + Option{option}',
            'confidence': confidence,
            'structure_confirmed': True,
            'main_trend': main_trend,
            'entry_allowed': True,
            'advanced_smc': advanced,
            'structure_data': {
                '1h': structure_data.get('1h', {}).get('structure'),
                '4h': structure_data.get('4h', {}).get('structure'),
                '1d': structure_data.get('1d', {}).get('structure') if structure_data.get('1d') else None
            }
        }
    
    def get_entry_direction(
        self,
        data_1h: List[List[float]],
        data_4h: List[List[float]],
        data_1d: Optional[List[List[float]]] = None,
        technical_data: Optional[Dict[str, Any]] = None,
        option: int = 1
    ) -> Dict[str, Any]:
        if technical_data is None:
            technical_data = {}
        
        # Cache key
        cache_key = f"{hash(str(data_1h[-1][4]))}_{hash(str(data_4h[-1][4]))}_{option}"
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if (datetime.now() - entry['time']).total_seconds() < self.cache_ttl:
                return entry['result']
        
        structure_data = self.analyze_structure(data_1h, data_4h, data_1d)
        result = self.make_decision(structure_data, technical_data, data_1h, option)
        
        if len(self.cache) > 100:
            self.cache.clear()
        self.cache[cache_key] = {'result': result, 'time': datetime.now()}
        return result
    
    def validate_entry(
        self,
        decision: Dict[str, Any],
        entry_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not decision.get('entry_allowed', False):
            return {'valid': False, 'reason': decision.get('reason', 'Entry not allowed')}
        
        direction = decision.get('main_trend', 'none')
        rsi = entry_data.get('rsi', 50)
        
        if direction == 'LONG' and rsi > 75:
            return {'valid': False, 'reason': f'RSI overbought: {rsi}'}
        if direction == 'SHORT' and rsi < 25:
            return {'valid': False, 'reason': f'RSI oversold: {rsi}'}
        
        adx = entry_data.get('adx', 0)
        if adx < 20:
            return {'valid': False, 'reason': f'ADX too weak: {adx}'}
        
        if entry_data.get('structure') == 'range':
            return {'valid': False, 'reason': 'Entry timeframe in range'}
        
        return {'valid': True, 'reason': 'Entry validated'}


smc_engine = SMCDecisionEngine()