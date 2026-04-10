from typing import Dict, Any, List, Optional
from datetime import datetime
from src.binance_client import binance_client
from src.logger import logger
from src.config import config
import time


def calculate_vwap(ohlcv_data: List[List[float]]) -> float:
    if not ohlcv_data or len(ohlcv_data) < 2:
        return 0.0
    volume_sum = 0.0
    price_vol_sum = 0.0
    for candle in ohlcv_data:
        typical_price = (candle[2] + candle[1] + candle[4]) / 3
        vol = candle[5]
        price_vol_sum += typical_price * vol
        volume_sum += vol
    return price_vol_sum / volume_sum if volume_sum > 0 else 0.0


class OrderManager:
    def __init__(self):
        self.leverage = int(config.trading.get('leverage', 10))
        self.tp1_percent = config.trading.get('tp1_percent', 3.0)
        self.tp2_percent = config.trading.get('tp2_percent', 5.0)
        self.sl_percent = config.trading.get('stop_loss_percent', 2.0)
        self.trailing_percent = config.trading.get('trailing_stop_percent', 1.5)
        self.entry_timeout_seconds = config.trading.get('entry_timeout_seconds', 30)

    def set_leverage_for_symbol(self, symbol: str) -> bool:
        try:
            binance_client.set_leverage(symbol, self.leverage)
            logger.info(f"Leverage set to {self.leverage}x for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Failed to set leverage for {symbol}: {e}")
            return False

    def calculate_prices_with_orderbook(self, symbol: str, direction: str, 
                                         vwap: float, current_price: float) -> Optional[Dict[str, Any]]:
        ob_data = binance_client.get_orderbook_levels(symbol, 20)
        
        bids = ob_data.get('bids', [])
        asks = ob_data.get('asks', [])
        
        bids_thin_to_thick = sorted(bids, key=lambda x: x.get('volume', 0))
        asks_thin_to_thick = sorted(asks, key=lambda x: x.get('volume', 0))
        
        bids_thick_to_thin = list(reversed(bids_thin_to_thick))
        asks_thick_to_thin = list(reversed(asks_thin_to_thick))
        
        if direction == 'LONG':
            # Entry: En kalın BID + 0.3%
            thick_bid = bids_thick_to_thin[0].get('price', current_price) if bids_thick_to_thin else current_price
            entry_price = thick_bid * 1.003
            entry_vol = bids_thick_to_thin[0].get('volume', 0) if bids_thick_to_thin else 0
            
            # SL: En kalın BID - 1.5%
            sl = thick_bid * 0.985
            
            # TP1: En ince ASK
            thin_ask = asks_thin_to_thick[0].get('price', current_price * 1.02) if asks_thin_to_thick else current_price * 1.02
            tp1 = thin_ask
            
            # TP2: Orta ASK - 0.5%
            mid_idx = len(asks_thin_to_thick) // 2
            mid_ask = asks_thin_to_thick[mid_idx].get('price', current_price * 1.03) if mid_idx < len(asks_thin_to_thick) else current_price * 1.03
            tp2 = mid_ask * 0.995
            
            # TP3: En kalın ASK - 1.5%
            thick_ask = asks_thick_to_thin[0].get('price', current_price * 1.05) if asks_thick_to_thin else current_price * 1.05
            tp3 = thick_ask * 0.985
            
            entry_reason = f"LONG: entry={entry_price:.4f} (thick bid+0.3%), vol={entry_vol:.0f})"
            tp1_reason = f"TP1: {tp1:.4f} (ince ask)"
            tp2_reason = f"TP2: {tp2:.4f} (orta ask-0.5%)"
            tp3_reason = f"TP3: {tp3:.4f} (thick ask-1.5%)"
        else:
            # SHORT: Entry: En kalın ASK - 1.5%
            thick_ask = asks_thick_to_thin[0].get('price', current_price) if asks_thick_to_thin else current_price
            entry_price = thick_ask * 0.985
            entry_vol = asks_thick_to_thin[0].get('volume', 0) if asks_thick_to_thin else 0
            
            # SL: En kalın ASK + 1.5%
            sl = thick_ask * 1.015
            
            # TP1: En ince BID
            thin_bid = bids_thin_to_thick[0].get('price', current_price * 0.98) if bids_thin_to_thick else current_price * 0.98
            tp1 = thin_bid
            
            # TP2: Orta BID - 0.5%
            mid_idx = len(bids_thin_to_thick) // 2
            mid_bid = bids_thin_to_thick[mid_idx].get('price', current_price * 0.97) if mid_idx < len(bids_thin_to_thick) else current_price * 0.97
            tp2 = mid_bid * 0.995
            
            # TP3: En kalın BID - 1.5%
            thick_bid = bids_thick_to_thin[0].get('price', current_price * 0.95) if bids_thick_to_thin else current_price * 0.95
            tp3 = thick_bid * 0.985
            
            entry_reason = f"SHORT: entry={entry_price:.4f} (thick ask-1.5%), vol={entry_vol:.0f})"
            tp1_reason = f"TP1: {tp1:.4f} (ince bid)"
            tp2_reason = f"TP2: {tp2:.4f} (orta bid-0.5%)"
            tp3_reason = f"TP3: {tp3:.4f} (thick bid-1.5%)"

        precision = self._get_price_precision(symbol)
        
        return {
            'entry_price': round(entry_price, precision),
            'tp1_price': round(tp1, precision),
            'tp2_price': round(tp2, precision),
            'tp3_price': round(tp3, precision),
            'sl_price': round(sl, precision),
            'tp1_percent': 30,   # %30 of position
            'tp2_percent': 30,   # %30 of position
            'tp3_percent': 100,  # %100 of position (remaining)
            'ob_imbalance': ob_data.get('imbalance', 0),
            'bid_volume': ob_data.get('total_bid_volume', 0),
            'ask_volume': ob_data.get('total_ask_volume', 0),
            'entry_reason': entry_reason,
            'tp1_reason': tp1_reason,
            'tp2_reason': tp2_reason,
            'tp3_reason': tp3_reason,
            'valid': True,
        }

    def calculate_tp_prices(self, entry_price: float, direction: str) -> tuple:
        if direction == 'LONG':
            tp1 = entry_price * (1 + self.tp1_percent / 100)
            tp2 = entry_price * (1 + self.tp2_percent / 100)
        else:
            tp1 = entry_price * (1 - self.tp1_percent / 100)
            tp2 = entry_price * (1 - self.tp2_percent / 100)
        
        return round(tp1, 2), round(tp2, 2)

    def calculate_sl_price(self, entry_price: float, direction: str) -> float:
        if direction == 'LONG':
            sl = entry_price * (1 - self.sl_percent / 100)
        else:
            sl = entry_price * (1 + self.sl_percent / 100)
        
        return round(sl, 2)

    def _get_price_precision(self, symbol: str) -> int:
        try:
            markets = binance_client.fetch_markets()
            market = next((m for m in markets if m['symbol'] == symbol), None)
            if market:
                return market.get('precision', {}).get('price', 2)
        except Exception:
            pass
        return 2

    def place_entry_order(self, symbol: str, direction: str, amount: float,
                           vwap: float, current_price: float) -> Optional[Dict[str, Any]]:
        if not self.set_leverage_for_symbol(symbol):
            return None

        price_data = self.calculate_prices_with_orderbook(
            symbol, direction, vwap, current_price
        )
        
        entry_price = price_data['entry_price']
        
        logger.info(f"Entry calculation: {entry_price} (OB imbalance: {price_data['ob_imbalance']:.2%})")
        logger.info(f"  Entry reason: {price_data['entry_reason']}")
        
        side = 'buy' if direction == 'LONG' else 'sell'
        
        if config.is_paper_mode:
            logger.info(f"[PAPER] {direction} Entry: {symbol} @ {entry_price}, Amount: {amount}")
            logger.info(f"[PAPER] TP1: {price_data['tp1_price']}, TP2: {price_data['tp2_price']}, SL: {price_data['sl_price']}")
            return {
                'id': f"paper_{datetime.now().timestamp()}",
                'symbol': symbol,
                'side': side,
                'type': 'limit',
                'price': entry_price,
                'amount': amount,
                'entry_price': entry_price,
                'tp1_price': price_data['tp1_price'],
                'tp2_price': price_data['tp2_price'],
                'sl_price': price_data['sl_price'],
                'ob_data': {
                    'imbalance': price_data['ob_imbalance'],
                    'bid_volume': price_data['bid_volume'],
                    'ask_volume': price_data['ask_volume'],
                },
                'status': 'open',
                'created_at': datetime.now().isoformat(),
            }
        
        try:
            order = binance_client.create_order(
                symbol=symbol,
                side=side,
                order_type='market',
                amount=amount,
                params={'positionSide': 'LONG' if direction == 'LONG' else 'SHORT'}
)
            logger.info(f"Market entry order filled: {order['id']}")
            return order
        
        except Exception as e:
            logger.error(f"Failed to place entry order: {e}")
            return None

    def place_tp_orders(self, symbol: str, direction: str, amount: float,
                        entry_price: float) -> List[Optional[Dict[str, Any]]]:
        tp1_amount = amount * 0.5
        tp2_amount = amount * 0.5
        
        tp1_price, tp2_price = self.calculate_tp_prices(entry_price, direction)
        
        side = 'sell' if direction == 'LONG' else 'buy'
        
        if config.is_paper_mode:
            logger.info(f"[PAPER] TP1: {symbol} @ {tp1_price}, Amount: {tp1_amount}")
            logger.info(f"[PAPER] TP2: {symbol} @ {tp2_price}, Amount: {tp2_amount}")
            return [
                {'id': f"paper_tp1_{datetime.now().timestamp()}", 'price': tp1_price},
                {'id': f"paper_tp2_{datetime.now().timestamp()}", 'price': tp2_price},
            ]
        
        try:
            tp1 = binance_client.create_order(
                symbol=symbol,
                side=side,
                order_type='limit',
                amount=tp1_amount,
                price=tp1_price,
                params={'positionSide': 'LONG' if direction == 'LONG' else 'SHORT'}
            )
            
            tp2 = binance_client.create_order(
                symbol=symbol,
                side=side,
                order_type='limit',
                amount=tp2_amount,
                price=tp2_price,
                params={'positionSide': 'LONG' if direction == 'LONG' else 'SHORT'}
            )
            
            logger.info(f"TP orders placed: TP1 @ {tp1_price}, TP2 @ {tp2_price}")
            return [tp1, tp2]
            
        except Exception as e:
            logger.error(f"Failed to place TP orders: {e}")
            return [None, None]

    def place_sl_order(self, symbol: str, direction: str, amount: float,
                       entry_price: float) -> Optional[Dict[str, Any]]:
        sl_price = self.calculate_sl_price(entry_price, direction)
        
        side = 'sell' if direction == 'LONG' else 'buy'
        
        if config.is_paper_mode:
            logger.info(f"[PAPER] SL: {symbol} @ {sl_price}")
            return {'id': f"paper_sl_{datetime.now().timestamp()}", 'price': sl_price}
        
        try:
            sl_order = binance_client.create_order(
                symbol=symbol,
                side=side,
                order_type='stop_limit',
                amount=amount,
                price=sl_price,
                params={
                    'stopPrice': sl_price,
                    'positionSide': 'LONG' if direction == 'LONG' else 'SHORT',
                    'timeInForce': 'GTC'
                }
            )
            logger.info(f"SL order placed: {sl_order['id']} @ {sl_price}")
            return sl_order
            
        except Exception as e:
            logger.error(f"Failed to place SL order: {e}")
            return None

    def update_trailing_sl(self, symbol: str, direction: str, current_price: float,
                           entry_price: float, initial_sl: float) -> Optional[float]:
        if direction == 'LONG':
            profit_percent = (current_price - entry_price) / entry_price * 100
            if profit_percent >= self.tp1_percent:
                new_sl = current_price * (1 - self.trailing_percent / 100)
                if new_sl > initial_sl:
                    logger.info(f"Trailing SL updated for {symbol}: {new_sl}")
                    return new_sl
        else:
            profit_percent = (entry_price - current_price) / entry_price * 100
            if profit_percent >= self.tp1_percent:
                new_sl = current_price * (1 + self.trailing_percent / 100)
                if new_sl < initial_sl:
                    logger.info(f"Trailing SL updated for {symbol}: {new_sl}")
                    return new_sl
        
        return None

    def close_position(self, symbol: str, direction: str, amount: float) -> bool:
        side = 'sell' if direction == 'LONG' else 'buy'
        
        if config.is_paper_mode:
            logger.info(f"[PAPER] Close: {symbol} {direction} {amount}")
            return True
        
        try:
            binance_client.create_order(
                symbol=symbol,
                side=side,
                order_type='market',
                amount=amount,
                params={'positionSide': 'LONG' if direction == 'LONG' else 'SHORT'}
            )
            logger.info(f"Position closed: {symbol}")
            return True
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return False


order_manager = OrderManager()