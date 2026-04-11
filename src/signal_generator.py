from typing import Dict, Any, List, Optional
from datetime import datetime
from src.scanner import scanner
from src.binance_client import binance_client
from src.logger import logger
from src.config import config
from src.smc_decision_engine import smc_engine


class ConfluenceSystem:
    """
    KESİŞİM (CONFLOENCE) SİSTEMİ
    Sinyal = Gösterge1 + Gösterge2 + Gösterge3 + Yapı
    
    Göstergeler:
    1. RSI - Momentum (Aşırı alım/satım)
    2. MACD - Trend (Crossover)
    3. Stochastic - Momentum
    4. EMA Cross - Trend yönü
    5. VWAP - Değer alanı
    6. Volume - Hacim onayı
    7. Order Flow - Likidite
    
    Yapı (SMC):
    - Market Structure (1h + 4h)
    """
    
    def __init__(self):
        self.min_confluence = 3  # Minimum gösterge onayı
    
    def check_rsi(self, data: Dict[str, Any], direction: str) -> Dict[str, Any]:
        """Gösterge 1: RSI - Momentum"""
        rsi = data.get('rsi', 50)
        
        if direction == 'LONG':
            if rsi < 30:
                return {'confirm': True, 'strength': 3, 'reason': 'RSI oversold'}
            elif rsi < 40:
                return {'confirm': True, 'strength': 2, 'reason': 'RSI < 40'}
            elif rsi < 50:
                return {'confirm': True, 'strength': 1, 'reason': 'RSI < 50'}
            else:
                return {'confirm': False, 'strength': 0, 'reason': f'RSI {rsi:.1f}'}
        else:
            if rsi > 70:
                return {'confirm': True, 'strength': 3, 'reason': 'RSI overbought'}
            elif rsi > 60:
                return {'confirm': True, 'strength': 2, 'reason': 'RSI > 60'}
            elif rsi > 50:
                return {'confirm': True, 'strength': 1, 'reason': 'RSI > 50'}
            else:
                return {'confirm': False, 'strength': 0, 'reason': f'RSI {rsi:.1f}'}
    
    def check_macd(self, data: Dict[str, Any], direction: str) -> Dict[str, Any]:
        """Gösterge 2: MACD - Trend"""
        macd = data.get('macd', 0)
        macd_hist = data.get('macd_hist', 0)
        macd_signal = data.get('macd_signal', 0)
        
        if direction == 'LONG':
            if macd > 0 and macd_hist > 0:
                return {'confirm': True, 'strength': 3, 'reason': 'MACD bullish cross'}
            elif macd > macd_signal:
                return {'confirm': True, 'strength': 2, 'reason': 'MACD > signal'}
            elif macd_hist > 0:
                return {'confirm': True, 'strength': 1, 'reason': 'MACD hist positive'}
            else:
                return {'confirm': False, 'strength': 0, 'reason': 'MACD bearish'}
        else:
            if macd < 0 and macd_hist < 0:
                return {'confirm': True, 'strength': 3, 'reason': 'MACD bearish cross'}
            elif macd < macd_signal:
                return {'confirm': True, 'strength': 2, 'reason': 'MACD < signal'}
            elif macd_hist < 0:
                return {'confirm': True, 'strength': 1, 'reason': 'MACD hist negative'}
            else:
                return {'confirm': False, 'strength': 0, 'reason': 'MACD bullish'}
    
    def check_stochastic(self, data: Dict[str, Any], direction: str) -> Dict[str, Any]:
        """Gösterge 3: Stochastic - Momentum"""
        stoch_k = data.get('stoch_k', 50)
        stoch_d = data.get('stoch_d', 50)
        
        if direction == 'LONG':
            if stoch_k < 20:
                return {'confirm': True, 'strength': 3, 'reason': 'Stoch oversold'}
            elif stoch_k < 30:
                return {'confirm': True, 'strength': 2, 'reason': 'Stoch < 30'}
            elif stoch_k < stoch_d:
                return {'confirm': True, 'strength': 1, 'reason': 'Stoch K < D'}
            else:
                return {'confirm': False, 'strength': 0, 'reason': f'Stoch {stoch_k:.1f}'}
        else:
            if stoch_k > 80:
                return {'confirm': True, 'strength': 3, 'reason': 'Stoch overbought'}
            elif stoch_k > 70:
                return {'confirm': True, 'strength': 2, 'reason': 'Stoch > 70'}
            elif stoch_k > stoch_d:
                return {'confirm': True, 'strength': 1, 'reason': 'Stoch K > D'}
            else:
                return {'confirm': False, 'strength': 0, 'reason': f'Stoch {stoch_k:.1f}'}
    
    def check_ema_cross(self, data: Dict[str, Any], direction: str) -> Dict[str, Any]:
        """Gösterge 4: EMA Cross - Trend"""
        ema_9 = data.get('ema_9', 0)
        ema_21 = data.get('ema_21', 0)
        ema_50 = data.get('ema_50', 0)
        
        if direction == 'LONG':
            if ema_9 > ema_21 > ema_50:
                return {'confirm': True, 'strength': 3, 'reason': 'EMA bullish align'}
            elif ema_9 > ema_21:
                return {'confirm': True, 'strength': 2, 'reason': 'EMA 9 > 21'}
            elif ema_9 > ema_50:
                return {'confirm': True, 'strength': 1, 'reason': 'EMA 9 > 50'}
            else:
                return {'confirm': False, 'strength': 0, 'reason': 'EMA bearish'}
        else:
            if ema_9 < ema_21 < ema_50:
                return {'confirm': True, 'strength': 3, 'reason': 'EMA bearish align'}
            elif ema_9 < ema_21:
                return {'confirm': True, 'strength': 2, 'reason': 'EMA 9 < 21'}
            elif ema_9 < ema_50:
                return {'confirm': True, 'strength': 1, 'reason': 'EMA 9 < 50'}
            else:
                return {'confirm': False, 'strength': 0, 'reason': 'EMA bullish'}
    
    def check_vwap(self, data: Dict[str, Any], direction: str) -> Dict[str, Any]:
        """Gösterge 5: VWAP - Değer Alanı"""
        vwap = data.get('vwap', 0)
        current_price = data.get('current_price', 0)
        
        if vwap == 0 or current_price == 0:
            return {'confirm': False, 'strength': 0, 'reason': 'No VWAP'}
        
        if direction == 'LONG':
            if current_price > vwap:
                return {'confirm': True, 'strength': 2, 'reason': 'Price above VWAP'}
            else:
                return {'confirm': False, 'strength': 0, 'reason': 'Price below VWAP'}
        else:
            if current_price < vwap:
                return {'confirm': True, 'strength': 2, 'reason': 'Price below VWAP'}
            else:
                return {'confirm': False, 'strength': 0, 'reason': 'Price above VWAP'}
    
    def check_volume(self, data: Dict[str, Any], direction: str) -> Dict[str, Any]:
        """Gösterge 6: Volume - Hacim Onayı"""
        vol_ratio = data.get('volume_ratio', 1)
        
        if vol_ratio >= 1.5:
            return {'confirm': True, 'strength': 3, 'reason': f'High volume {vol_ratio:.1f}x'}
        elif vol_ratio >= 1.2:
            return {'confirm': True, 'strength': 2, 'reason': f'Elevated volume {vol_ratio:.1f}x'}
        elif vol_ratio >= 1.0:
            return {'confirm': True, 'strength': 1, 'reason': f'Normal volume {vol_ratio:.1f}x'}
        else:
            return {'confirm': False, 'strength': 0, 'reason': f'Low volume {vol_ratio:.1f}x'}
    
    def check_order_flow(self, data: Dict[str, Any], direction: str) -> Dict[str, Any]:
        """Gösterge 7: Order Flow - Likidite"""
        ob_imbalance = data.get('ob_imbalance', 0)
        
        if direction == 'LONG':
            if ob_imbalance > 0.25:
                return {'confirm': True, 'strength': 3, 'reason': 'Strong buy imbalance'}
            elif ob_imbalance > 0.15:
                return {'confirm': True, 'strength': 2, 'reason': 'Moderate buy imbalance'}
            elif ob_imbalance > 0:
                return {'confirm': True, 'strength': 1, 'reason': 'Slight buy imbalance'}
            else:
                return {'confirm': False, 'strength': 0, 'reason': 'Sell pressure'}
        else:
            if ob_imbalance < -0.25:
                return {'confirm': True, 'strength': 3, 'reason': 'Strong sell imbalance'}
            elif ob_imbalance < -0.15:
                return {'confirm': True, 'strength': 2, 'reason': 'Moderate sell imbalance'}
            elif ob_imbalance < 0:
                return {'confirm': True, 'strength': 1, 'reason': 'Slight sell imbalance'}
            else:
                return {'confirm': False, 'strength': 0, 'reason': 'Buy pressure'}
    
    def calculate_confluence(self, data: Dict[str, Any], direction: str) -> Dict[str, Any]:
        """
        Ana Confluence Hesaplama
        Signal = Gösterge1 + Gösterge2 + Gösterge3 + + Yapı
        """
        indicators = [
            ('RSI', self.check_rsi(data, direction)),
            ('MACD', self.check_macd(data, direction)),
            ('Stochastic', self.check_stochastic(data, direction)),
            ('EMA', self.check_ema_cross(data, direction)),
            ('VWAP', self.check_vwap(data, direction)),
            ('Volume', self.check_volume(data, direction)),
            ('OrderFlow', self.check_order_flow(data, direction)),
        ]
        
        total_confirmations = 0
        total_strength = 0
        confirmed_indicators = []
        
        for name, result in indicators:
            if result['confirm']:
                total_confirmations += 1
                total_strength += result['strength']
                confirmed_indicators.append(f"{name}:{result['strength']}")
        
        confluence_score = (total_confirmations / len(indicators)) * 100
        normalized_strength = min(total_strength / (len(indicators) * 3) * 100, 100)
        
        structure = data.get('structure', 'unknown')
        if structure in ['uptrend', 'downtrend']:
            total_strength += 2
            normalized_strength = min(total_strength / (len(indicators) * 3) * 100, 100)
            confirmed_indicators.append('Structure:2')
        
        return {
            'confluence_score': confluence_score,
            'strength_score': normalized_strength,
            'confirmations': total_confirmations,
            'total_indicators': len(indicators),
            'confirmed_list': ','.join(confirmed_indicators),
            'meets_minimum': total_confirmations >= self.min_confluence,
        }


class SignalGenerator:
    def __init__(self):
        self.max_positions = config.trading.get('max_positions', 5)
        self.cooldown_minutes = config.trading.get('cooldown_minutes', 15)
        self.confluence = ConfluenceSystem()

    def calculate_long_score(self, data: Dict[str, Any]) -> float:
        score = 0.0
        current_price = data.get('current_price', 0)
        
        rsi = data.get('rsi', 50)
        if rsi < 30:
            score += 15
        elif rsi < 40:
            score += 10
        elif rsi < 45:
            score += 5
        elif rsi > 65:
            score -= 15
        elif rsi > 55:
            score -= 5
        
        stoch_k = data.get('stoch_k', 50)
        if stoch_k < 20:
            score += 8
        elif stoch_k < 30:
            score += 5
        
        macd = data.get('macd', 0)
        macd_hist = data.get('macd_hist', 0)
        if macd > 0 and macd_hist > 0:
            score += 7
        elif macd < 0 and macd_hist < 0:
            score -= 5
        
        adx = data.get('adx', 0)
        if adx >= 25:
            score += 10
        elif adx >= 20:
            score += 5
        
        ema_9 = data.get('ema_9', 0)
        ema_21 = data.get('ema_21', 0)
        ema_50 = data.get('ema_50', 0)
        ema_200 = data.get('ema_200', 0)
        
        if ema_9 > ema_21 > ema_50:
            score += 12
        if ema_50 > ema_200:
            score += 13
        elif current_price < ema_200:
            score -= 10
        
        vwap = data.get('vwap', 0)
        support = data.get('support', 0)
        if current_price > vwap and vwap > 0:
            score += 10
        if current_price > support and support > 0:
            score += 5
        
        pivot = data.get('pivot', 0)
        s1 = data.get('s1', 0)
        if current_price > s1 > 0:
            score += 5
        if current_price > vwap > s1:
            score += 5
        
        vol_ratio = data.get('volume_ratio', 1)
        score += min((vol_ratio - 1) * 8, 15)
        
        adr = data.get('adr', 0)
        score += min(adr * 1.5, 10)
        
        ob_imbalance = data.get('ob_imbalance', 0)
        if ob_imbalance > 0.25:
            score += 12
        elif ob_imbalance > 0.15:
            score += 8
        elif ob_imbalance > 0.05:
            score += 4
        elif ob_imbalance < -0.15:
            score -= 8
        
        ob_bid_vol = data.get('ob_bid_volume', 0)
        ob_ask_vol = data.get('ob_ask_volume', 0)
        if ob_bid_vol > ob_ask_vol * 1.5:
            score += 8
        
        momentum = data.get('momentum', 0)
        score += momentum * 3
        
        return score

    def calculate_short_score(self, data: Dict[str, Any]) -> float:
        score = 0.0
        current_price = data.get('current_price', 0)
        
        rsi = data.get('rsi', 50)
        if rsi > 70:
            score += 15
        elif rsi > 60:
            score += 10
        elif rsi > 55:
            score += 5
        elif rsi < 35:
            score -= 15
        elif rsi < 45:
            score -= 5
        
        stoch_k = data.get('stoch_k', 50)
        if stoch_k > 80:
            score += 8
        elif stoch_k > 70:
            score += 5
        
        macd = data.get('macd', 0)
        macd_hist = data.get('macd_hist', 0)
        if macd < 0 and macd_hist < 0:
            score += 7
        elif macd > 0 and macd_hist > 0:
            score -= 5
        
        ema_9 = data.get('ema_9', 0)
        ema_21 = data.get('ema_21', 0)
        ema_50 = data.get('ema_50', 0)
        ema_200 = data.get('ema_200', 0)
        
        if ema_9 < ema_21 < ema_50:
            score += 12
        if ema_50 < ema_200:
            score += 13
        elif current_price > ema_200:
            score -= 10
        
        vwap = data.get('vwap', 0)
        resistance = data.get('resistance', 0)
        if current_price < vwap and vwap > 0:
            score += 10
        if current_price < resistance and resistance > 0:
            score += 5
        
        pivot = data.get('pivot', 0)
        r1 = data.get('r1', 0)
        if current_price < r1 and r1 > 0:
            score += 5
        if current_price < vwap < r1:
            score += 5
        
        vol_ratio = data.get('volume_ratio', 1)
        score += min((vol_ratio - 1) * 8, 15)
        
        adr = data.get('adr', 0)
        score += min(adr * 1.5, 10)
        
        ob_imbalance = data.get('ob_imbalance', 0)
        if ob_imbalance < -0.25:
            score += 12
        elif ob_imbalance < -0.15:
            score += 8
        elif ob_imbalance < -0.05:
            score += 4
        elif ob_imbalance > 0.15:
            score -= 8
        
        ob_bid_vol = data.get('ob_bid_volume', 0)
        ob_ask_vol = data.get('ob_ask_volume', 0)
        if ob_ask_vol > ob_bid_vol * 1.5:
            score += 8
        
        momentum = data.get('momentum', 0)
        score -= momentum * 3
        
        return score

    def enrich_with_orderbook(self, symbol: str, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            ob_data = binance_client.get_liquidity_zones(symbol, data.get('current_price', 0))
            data['ob_imbalance'] = ob_data.get('imbalance', 0)
            data['ob_bid_volume'] = ob_data.get('bid_volume', 0)
            data['ob_ask_volume'] = ob_data.get('ask_volume', 0)
            data['strong_bid'] = ob_data.get('strong_bid')
            data['strong_ask'] = ob_data.get('strong_ask')
        except Exception as e:
            logger.debug(f"Could not fetch orderbook for {symbol}: {e}")
            data['ob_imbalance'] = 0
            data['ob_bid_volume'] = 0
            data['ob_ask_volume'] = 0
        return data
    
    def get_smc_decision(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        SMC Karar Motoru'ndan yön kararı al
        Piyasa yapısı hem 1h hem de 4h/1D için analiz edilir
        """
        try:
            data_1h = data.get('ohlcv_1h', [])
            data_4h = data.get('ohlcv_4h', [])
            data_1d = data.get('ohlcv_1d', [])
            
            technical_data = {
                'rsi': data.get('rsi', 50),
                'adx': data.get('adx', 0),
                'momentum': data.get('momentum', 0),
                'momentum_score': 0,
                'technical_score': 0
            }
            
            if technical_data.get('rsi', 50) < 40 or technical_data.get('rsi', 50) > 60:
                technical_data['momentum_score'] = 20
            
            if technical_data.get('adx', 0) >= 25:
                technical_data['technical_score'] = 20
            
            decision = smc_engine.get_entry_direction(data_1h, data_4h, data_1d if data_1d else None, technical_data)
            
            return decision
        except Exception as e:
            logger.debug(f"SMC decision error: {e}")
            return {
                'decision': 'WAIT',
                'reason': str(e),
                'confidence': 0,
                'structure_confirmed': False,
                'main_trend': 'none',
                'entry_allowed': False
            }

    def generate_signals(self, scanned_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        signals = []
        
        for data in scanned_data:
            data = self.enrich_with_orderbook(data['symbol'], data)
            
            smc_decision = self.get_smc_decision(data)
            
            if not smc_decision.get('entry_allowed', False):
                continue
            
            smc_direction = smc_decision.get('main_trend', 'none')
            confidence = smc_decision.get('confidence', 0)
            
            confluence = self.confluence.calculate_confluence(data, smc_direction)
            
            if not confluence.get('meets_minimum', False):
                continue
            
            long_score = self.calculate_long_score(data)
            short_score = self.calculate_short_score(data)
            
            direction = None
            score = 0
            
            if smc_direction == 'LONG':
                direction = 'LONG'
                score = long_score + confidence + confluence.get('strength_score', 0)
            elif smc_direction == 'SHORT':
                direction = 'SHORT'
                score = short_score + confidence + confluence.get('strength_score', 0)
            else:
                continue
            
            structure = data.get('structure', 'unknown')
            adx = data.get('adx', 0)
            
            if structure == 'range':
                continue
            if adx > 0 and adx < 20:
                continue
            
            min_score = 35
            temp_score = long_score if direction == 'LONG' else short_score
            if temp_score < min_score:
                continue
            
            tp1 = 0.01
            tp2 = 0.02
            tp3 = 0.03
            sl = 0.02
            rr1 = tp1 / sl
            rr2 = tp2 / sl
            rr3 = tp3 / sl
            
            grade = 'D'
            if score >= 80:
                grade = 'A'
            elif score >= 60:
                grade = 'B'
            elif score >= 40:
                grade = 'C'
            
            signals.append({
                'symbol': data['symbol'],
                'direction': direction,
                'score': score,
                'grade': grade,
                'rr': rr3,
                'entry_price': data.get('current_price', 0),
                'vwap': data.get('vwap', 0),
                'support': data.get('support', 0),
                'resistance': data.get('resistance', 0),
                'rsi': data.get('rsi', 50),
                'adx': data.get('adx', 0),
                'structure': data.get('structure', 'unknown'),
                'ob_imbalance': data.get('ob_imbalance', 0),
                'ob_bid_volume': data.get('ob_bid_volume', 0),
                'ob_ask_volume': data.get('ob_ask_volume', 0),
                'strong_bid': data.get('strong_bid'),
                'strong_ask': data.get('strong_ask'),
                'smc_confidence': confidence,
                'smc_reason': smc_decision.get('reason', ''),
                'confluence_score': confluence.get('confluence_score', 0),
                'confluence_confirmations': confluence.get('confirmations', 0),
                'confluence_list': confluence.get('confirmed_list', ''),
                'stop_loss_percent': config.trading.get('stop_loss_percent', 2.0),
                'take_profit_percent': config.trading.get('take_profit_percent', 3.0),
            })
        
        signals.sort(key=lambda x: (x['rr'], x['score']), reverse=True)
        return signals[:self.max_positions]

    def get_top_signals(self, limit: int = 5) -> List[Dict[str, Any]]:
        scanned = scanner.scan_all_with_data()
        if not scanned:
            logger.warning("No viable signals found")
            return []
        
        return self.generate_signals(scanned)[:limit]


signal_generator = SignalGenerator()