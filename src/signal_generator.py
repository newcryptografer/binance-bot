from typing import Dict, Any, List, Optional
from datetime import datetime
from src.scanner import scanner
from src.binance_client import binance_client
from src.logger import logger
from src.config import config


class SignalGenerator:
    def __init__(self):
        self.max_positions = config.trading.get('max_positions', 5)
        self.cooldown_minutes = config.trading.get('cooldown_minutes', 15)

    def calculate_long_score(self, data: Dict[str, Any]) -> float:
        score = 0.0
        current_price = data.get('current_price', 0)
        
        # === MOMENTUM (%20) ===
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
        
        # === TREND (%25) ===
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
        
        # === SUPPORT/RESISTANCE (%20) ===
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
        
        # === VOLUME (%15) ===
        vol_ratio = data.get('volume_ratio', 1)
        score += min((vol_ratio - 1) * 8, 15)
        
        adr = data.get('adr', 0)
        score += min(adr * 1.5, 10)
        
        # === ORDER FLOW (%20) ===
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
        
        # === MOMENTUM ===
        momentum = data.get('momentum', 0)
        score += momentum * 3
        
        return score

    def calculate_short_score(self, data: Dict[str, Any]) -> float:
        score = 0.0
        current_price = data.get('current_price', 0)
        
        # === MOMENTUM (%20) ===
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
        
        # === TREND (%25) ===
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
        
        # === SUPPORT/RESISTANCE (%20) ===
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
        
        # === VOLUME (%15) ===
        vol_ratio = data.get('volume_ratio', 1)
        score += min((vol_ratio - 1) * 8, 15)
        
        adr = data.get('adr', 0)
        score += min(adr * 1.5, 10)
        
        # === ORDER FLOW (%20) ===
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
        
        # === MOMENTUM ===
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

    def generate_signals(self, scanned_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        signals = []
        
        for data in scanned_data:
            data = self.enrich_with_orderbook(data['symbol'], data)
            
            long_score = self.calculate_long_score(data)
            short_score = self.calculate_short_score(data)
            
            entry_price = data.get('current_price', 0)
            direction = None
            score = 0
            
            if long_score > short_score:
                direction = 'LONG'
                score = long_score
            elif short_score > long_score:
                direction = 'SHORT'
                score = short_score
            
            structure = data.get('structure', 'unknown')
            if structure == 'range':
                continue  # Range'de işlem yok
            
            if direction:
                tp1 = 0.01
                tp2 = 0.02
                tp3 = 0.03
                sl = 0.02
                rr1 = tp1 / sl  # 0.5
                rr2 = tp2 / sl  # 1.0
                rr3 = tp3 / sl  # 1.5
                
                signals.append({
                    'symbol': data['symbol'],
                    'direction': direction,
                    'score': score,
                    'rr': rr3,  # Use TP3 for best RR
                    'entry_price': data.get('current_price', 0),
                    'vwap': data.get('vwap', 0),
                    'support': data.get('support', 0),
                    'resistance': data.get('resistance', 0),
                    'rsi': data.get('rsi', 50),
                    'ob_imbalance': data.get('ob_imbalance', 0),
                    'ob_bid_volume': data.get('ob_bid_volume', 0),
                    'ob_ask_volume': data.get('ob_ask_volume', 0),
                    'strong_bid': data.get('strong_bid'),
                    'strong_ask': data.get('strong_ask'),
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