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