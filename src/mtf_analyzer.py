"""
ÇOKLU ZAMAN ANALİZİ - Multi-Timeframe Analysis Engine
=============================================
Profesyonel Sinyal Analiz Motoru

Three Timeframe Framework:
- Higher TF (4H/1D): Trend yönü belirler
- Trading TF (1H): Analiz için kullanılır  
- Entry TF (15m/5m): Precise giriş noktası

Sinyal = (TF1 + TF2 + TF3) + Confluence
Giriş için minimum 3 confluence factor gerekir
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class TimeframeRole(Enum):
    HIGHER_TREND = "higher"      # 4H/1D - Trend yönü
    TRADING_ANALYSIS = "trading"  # 1H - Analiz
    ENTRY Precision = "entry"    # 15m/5m - Giriş


@dataclass
class MTFCandle:
    """Multi-timeframe candle data"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class TrendData:
    """Trend bilgileri"""
    direction: str  # 'bullish', 'bearish', 'neutral'
    strength: float  # 0-100
    ema_9: float
    ema_21: float
    ema_50: float
    ema_200: float
    vwap: float
    structure: str  # 'uptrend', 'downtrend', 'range'


@dataclass
class MomentumData:
    """Momentum göstergeleri"""
    rsi: float
    macd: float
    macd_hist: float
    stoch_k: float
    adx: float


@dataclass
class ConfluenceCheck:
    """Tek bir timeframe confluence kontrolü"""
    trend_confirmed: bool
    momentum_confirmed: bool
    structure_confirmed: bool
    total_score: float
    details: str


@dataclass
class MTFAnalysisResult:
    """Multi-timeframe analiz sonucu"""
    higher_tf: TrendData
    trading_tf: TrendData
    entry_tf: TrendData
    
    higher_confluence: ConfluenceCheck
    trading_confluence: ConfluenceCheck
    entry_confluence: ConfluenceCheck
    
    total_score: float
    signal: str  # 'LONG', 'SHORT', 'WAIT'
    confidence: float  # 0-100
    
    meets_minimum: bool
    reason: str


class MultiTimeframeAnalyzer:
    """
    Çoklu Zaman Analiz Motoru
    
    Kullanım:
    1. Yüksek TF (4H/1D) trend yönünü belirle
    2. Trading TF (1H) analiz et
    3. Entry TF (15m) giriş zamanlamasını kontrol et
    4. Tüm timeframe'ler aynı yönde ise signal üret
    """
    
    def __init__(self):
        self.min_confluence = 3  # Minimum 3 factor
        self.min_score = 70      # Minimum toplam skor
    
    def analyze_trend(self, ohlcv: List[List[float]], period: int = 50) -> TrendData:
        """Tek TF için trend analizi"""
        if len(ohlcv) < period:
            return TrendData('neutral', 0, 0, 0, 0, 0, 0, 'unknown')
        
        closes = [c[4] for c in ohlcv[-period:]]
        highs = [c[1] for c in ohlcv[-period:]]
        lows = [c[2] for c in ohlcv[-period:]]
        
        current = closes[-1]
        
        # EMA hesapla (basit yaklaşım)
        ema_9 = sum(closes[-9:]) / 9 if len(closes) >= 9 else current
        ema_21 = sum(closes[-21:]) / 21 if len(closes) >= 21 else current
        ema_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else current
        ema_200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else current
        
        # VWAP
        typical = [(h + l + c) / 3 * v for c, h, l, v in zip(closes, highs, lows, [c[5] for c in ohlcv[-period:])]
        vwap = sum(typical) / period if typical else current
        
        # Market Structure
        hh = max(highs[-10:])
        ll = min(lows[-10:])
        prev_hh = max(highs[-20:-10]) if len(highs) >= 20 else hh
        prev_ll = min(lows[-20:-10]) if len(lows) >= 20 else ll
        
        if hh > prev_hh and ll > prev_ll:
            structure = 'uptrend'
            direction = 'bullish'
        elif hh < prev_hh and ll < prev_ll:
            structure = 'downtrend'
            direction = 'bearish'
        else:
            structure = 'range'
            direction = 'neutral'
        
        # Strength
        strength = 50
        if ema_9 > ema_21 > ema_50:
            strength += 25
        if ema_50 > ema_200:
            strength += 25
        
        return TrendData(
            direction=direction,
            strength=min(strength, 100),
            ema_9=ema_9,
            ema_21=ema_21,
            ema_50=ema_50,
            ema_200=ema_200,
            vwap=vwap,
            structure=structure
        )
    
    def analyze_momentum(self, ohlcv: List[List[float]]) -> MomentumData:
        """Momentum göstergeleri"""
        if len(ohlcv) < 50:
            return MomentumData(50, 0, 0, 50, 0)
        
        closes = [c[4] for c in ohlcv[-50:]]
        
        # RSI
        gains = [closes[i] - closes[i-1] for i in range(1, len(closes)) if closes[i] > closes[i-1]]
        losses = [closes[i-1] - closes[i] for i in range(1, len(closes)) if closes[i] < closes[i-1]]
        avg_gain = sum(gains) / 14 if gains else 1
        avg_loss = sum(losses) / 14 if losses else 1
        rs = avg_gain / avg_loss if avg_loss else 1
        rsi = 100 - (100 / (1 + rs))
        
        # MACD (basit)
        ema12 = sum(closes[-12:]) / 12
        ema26 = sum(closes[-26:]) / 26
        macd = ema12 - ema26
        signal = macd * 0.9
        macd_hist = macd - signal
        
        # Stochastic
        low14 = min(lows[-14:]) if len(closes) >= 14 else min(closes)
        high14 = max(highs[-14:]) if len(closes) >= 14 else max(closes)
        stoch_k = 100 * (closes[-1] - low14) / (high14 - low14) if high14 > low14 else 50
        
        # ADX (basit - trend strength)
        adx = abs(ema_21 - ema_50) / ema_50 * 100 if ema_50 else 0
        
        return MomentumData(
            rsi=rsi,
            macd=macd,
            macd_hist=macd_hist,
            stoch_k=stoch_k,
            adx=adx
        )
    
    def check_confluence(self, trend: TrendData, momentum: MomentumData, role: str) -> ConfluenceCheck:
        """Tek timeframe için confluence kontrolü"""
        trend_confirmed = False
        momentum_confirmed = False
        structure_confirmed = False
        details_parts = []
        
        # Trend kontrolü
        if role == "higher":
            if trend.direction == 'bullish':
                trend_confirmed = True
                details_parts.append("Trend:LL")
            elif trend.direction == 'bearish':
                trend_confirmed = True
                details_parts.append("Trend:HL")
        
        # Momentum kontrolü
        if momentum.rsi < 40 or momentum.rsi > 60:
            momentum_confirmed = True
            details_parts.append(f"RSI:{momentum.rsi:.0f}")
        
        if momentum.macd > 0 and momentum.macd_hist > 0:
            momentum_confirmed = True
            details_parts.append("MACD+")
        
        if momentum.stoch_k < 30 or momentum.stoch_k > 70:
            momentum_confirmed = True
            details_parts.append(f"Stoch:{momentum.stoch_k:.0f}")
        
        # Structure kontrolü
        if trend.structure in ['uptrend', 'downtrend']:
            structure_confirmed = True
            details_parts.append(trend.structure)
        
        total_score = sum([
            trend_confirmed * 30,
            momentum_confirmed * 40,
            structure_confirmed * 30
        ])
        
        return ConfluenceCheck(
            trend_confirmed=trend_confirmed,
            momentum_confirmed=momentum_confirmed,
            structure_confirmed=structure_confirmed,
            total_score=total_score,
            details=','.join(details_parts)
        )
    
    def analyze(
        self,
        higher_tf_data: List[List[float]],
        trading_tf_data: List[List[float]],
        entry_tf_data: Optional[List[List[float]]] = None
    ) -> MTFAnalysisResult:
        """
        Ana Multi-Timeframe Analiz Fonksiyonu
        
        Args:
            higher_tf_data: 4H veya 1D timeframe verisi (trend için)
            trading_tf_data: 1H timeframe verisi (analiz için)
            entry_tf_data: 15m/5m timeframe verisi (giriş için)
        
        Returns:
            MTFAnalysisResult: Tam analiz sonucu
        """
        if entry_tf_data is None:
            entry_tf_data = trading_tf_data
        
        # Her TF için trend analizi
        higher_trend = self.analyze_trend(higher_tf_data)
        trading_trend = self.analyze_trend(trading_tf_data)
        entry_trend = self.analyze_trend(entry_tf_data)
        
        # Her TF için momentum analizi
        higher_mom = self.analyze_momentum(higher_tf_data)
        trading_mom = self.analyze_momentum(trading_tf_data)
        entry_mom = self.analyze_momentum(entry_tf_data)
        
        # Confluence kontrolü
        higher_conf = self.check_confluence(higher_trend, higher_mom, "higher")
        trading_conf = self.check_confluence(trading_trend, trading_mom, "trading")
        entry_conf = self.check_confluence(entry_trend, entry_mom, "entry")
        
        # Toplam skor
        total_score = higher_conf.total_score + trading_conf.total_score + entry_conf.total_score
        
        # Signal kararı
        signal = "WAIT"
        reason = "No confluence"
        meets_minimum = False
        confidence = 0
        
        # Tüm timeframe'ler aynı yönde mi?
        if higher_trend.direction == trading_trend.direction == entry_trend.direction != "neutral":
            if higher_conf.trend_confirmed and trading_conf.trend_confirmed:
                signal = "LONG" if higher_trend.direction == "bullish" else "SHORT"
                meets_minimum = True
                confidence = min(total_score, 100)
                reason = f"MTF aligned: {higher_trend.direction}"
        
        return MTFAnalysisResult(
            higher_tf=higher_trend,
            trading_tf=trading_trend,
            entry_tf=entry_trend,
            higher_confluence=higher_conf,
            trading_confluence=trading_conf,
            entry_confluence=entry_conf,
            total_score=total_score,
            signal=signal,
            confidence=confidence,
            meets_minimum=meets_minimum,
            reason=reason
        )


class SignalGeneratorV2:
    """
    Profesyonel Sinyal Analiz Motoru v2
    MTF + Confluence tabanlı
    """
    
    def __init__(self):
        self.mtf = MultiTimeframeAnalyzer()
    
    def generate_signal(
        self,
        symbol: str,
        data_4h: List[List[float]],
        data_1h: List[List[float]],
        data_15m: Optional[List[List[float]]] = None
    ) -> Dict[str, Any]:
        """Signal üret"""
        result = self.mtf.analyze(data_4h, data_1h, data_15m)
        
        return {
            'symbol': symbol,
            'signal': result.signal,
            'confidence': result.confidence,
            'score': result.total_score,
            'reason': result.reason,
            'higher_trend': result.higher_tf.direction,
            'trading_trend': result.trading_tf.direction,
            'entry_trend': result.entry_tf.direction,
            'higher_structure': result.higher_tf.structure,
            'trading_structure': result.trading_tf.structure,
            'meets_minimum': result.meets_minimum,
            'higher_conf': result.higher_confluence.details,
            'trading_conf': result.trading_confluence.details,
            'entry_conf': result.entry_confluence.details,
        }


mtf_analyzer = MultiTimeframeAnalyzer()
signal_generator_v2 = SignalGeneratorV2()