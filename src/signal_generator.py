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
        
        rsi = data.get('rsi', 50)
        if rsi < 35:
            score += 25
        elif rsi < 45:
            score += 15
        elif rsi > 70:
            score -= 20
        
        adr = data.get('adr', 0)
        score += min(adr * 2, 20)
        
        vol_ratio = data.get('volume_ratio', 1)
        score += min((vol_ratio - 1) * 10, 20)
        
        momentum = data.get('momentum', 0)
        score += momentum * 4
        
        ema_50 = data.get('ema_50', 0)
        ema_200 = data.get('ema_200', 0)
        current_price = data.get('current_price', 0)
        if ema_50 > ema_200 and current_price > ema_50:
            score += 15
        elif current_price < ema_200:
            score -= 10
        
        vwap = data.get('vwap', 0)
        if current_price > vwap:
            score += 10
        
        ob_imbalance = data.get('ob_imbalance', 0)
        if ob_imbalance > 0.2:
            score += 15
        elif ob_imbalance > 0.1:
            score += 8
        
        return score

    def calculate_short_score(self, data: Dict[str, Any]) -> float:
        score = 0.0
        
        rsi = data.get('rsi', 50)
        if rsi > 65:
            score += 25
        elif rsi > 55:
            score += 15
        elif rsi < 30:
            score -= 20
        
        adr = data.get('adr', 0)
        score += min(adr * 2, 20)
        
        vol_ratio = data.get('volume_ratio', 1)
        score += min((vol_ratio - 1) * 10, 20)
        
        momentum = data.get('momentum', 0)
        score -= momentum * 4
        
        ema_50 = data.get('ema_50', 0)
        ema_200 = data.get('ema_200', 0)
        current_price = data.get('current_price', 0)
        if ema_50 < ema_200 and current_price < ema_50:
            score += 15
        elif current_price > ema_200:
            score -= 10
        
        vwap = data.get('vwap', 0)
        if current_price < vwap:
            score += 10
        
        ob_imbalance = data.get('ob_imbalance', 0)
        if ob_imbalance < -0.2:
            score += 15
        elif ob_imbalance < -0.1:
            score += 8
        
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
            
            if long_score > short_score and long_score > 20:
                direction = 'LONG'
                score = long_score
            elif short_score > long_score and short_score > 20:
                direction = 'SHORT'
                score = short_score
            
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