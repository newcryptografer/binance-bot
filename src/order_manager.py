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
        ob_data = binance_client.get_liquidity_zones(symbol, current_price)
        
        def get_orderbook_zones(orders: list, total_vol: float, n: int = 3) -> list:
            if not orders or total_vol == 0:
                return []
            sorted_orders = sorted(orders, key=lambda x: x.get('volume', 0), reverse=True)
            return [{'price': o.get('price', 0), 'volume': o.get('volume', 0)} for o in sorted_orders[:n]]
        
        bid_zones = get_orderbook_zones(ob_data.get('bids', []), ob_data.get('total_bid_volume', 0), 3)
        ask_zones = get_orderbook_zones(ob_data.get('asks', []), ob_data.get('total_ask_volume', 0), 3)
        
        # Fetch different timeframe VWAPs
        try:
            ohlcv_15m = binance_client.fetch_ohlcv(symbol, '15m', 100)
            vwap_15m = calculate_vwap(ohlcv_15m) if ohlcv_15m else vwap
        except:
            vwap_15m = vwap
        
        try:
            ohlcv_4h = binance_client.fetch_ohlcv(symbol, '4h', 90)
            vwap_4h = calculate_vwap(ohlcv_4h) if ohlcv_4h else vwap
        except:
            vwap_4h = vwap
        
        try:
            ohlcv_1d = binance_client.fetch_ohlcv(symbol, '1d', 30)
            vwap_1d = calculate_vwap(ohlcv_1d) if ohlcv_1d else vwap
        except:
            vwap_1d = vwap
        
        if direction == 'LONG':
            # Entry: Fiyat 15m VWAP destek seviyesine gelince gir
            vwap_support = min(vwap_15m, ob_data.get('strong_bid', vwap_15m * 0.99))
            
            # Fiyat VWAP destek seviyesinde veya altında olmalı
            if current_price > vwap_support:
                logger.info(f"LONG waiting: price {current_price} above VWAP support {vwap_support}")
                return None
            
            entry_price = current_price  # Market fiyatından gir
            
            # SL: VWAP destek ALTINDA (LONG için SL aşağıda - kaybettiğimiz yer)
            sl = min(entry_price * (1 - self.sl_percent / 100), vwap_support)
            
            # TP1: Orderbook ASK ilk kalın bölge
            tp1 = ask_zones[0]['price'] if ask_zones and len(ask_zones) > 0 else current_price * 1.03
            
            # TP2: Orderbook ASK ikinci kalın bölge
            tp2 = ask_zones[1]['price'] if ask_zones and len(ask_zones) > 1 else current_price * 1.05
            
            # TP3: Orderbook ASK üçüncü kalın bölge veya 4h VWAP
            tp3 = ask_zones[2]['price'] if ask_zones and len(ask_zones) > 2 else vwap_4h * 1.05
            
            entry_reason = f"Entry: {entry_price:.4f} (VWAP support:{vwap_support:.4f})"
            tp1_reason = f"TP1: {tp1:.4f} (OB thick zone 1: {ask_zones[0].get('volume', 0):.0f} contracts)"
            tp2_reason = f"TP2: {tp2:.4f} (OB thick zone 2: {ask_zones[1].get('volume', 0):.0f} contracts)"
            tp3_reason = f"TP3: {tp3:.4f} (OB thick zone 3: {ask_zones[2].get('volume', 0):.0f} contracts)"
        else:
            # Entry: Fiyat 15m VWAP direnç seviyesine gelince gir
            vwap_resistance = max(vwap_15m, ob_data.get('strong_ask', vwap_15m * 1.01))
            
            # Fiyat VWAP direnç seviyesinde veya üstünde olmalı (direnci kırmış olmalı)
            if current_price < vwap_resistance:
                logger.info(f"SHORT waiting: price {current_price} below VWAP resistance {vwap_resistance}")
                return None
            
            entry_price = current_price  # Market fiyatından gir
            
            # SL: VWAP direnç ÜSTÜNDE (SHORT için SL yukarıda - kaybettiğimiz yer)
            sl = max(entry_price * (1 + self.sl_percent / 100), vwap_resistance)
            
            # TP1: Orderbook BID ilk kalın bölge
            tp1 = bid_zones[0]['price'] if bid_zones and len(bid_zones) > 0 else current_price * 0.97
            
            # TP2: Orderbook BID ikinci kalın bölge
            tp2 = bid_zones[1]['price'] if bid_zones and len(bid_zones) > 1 else current_price * 0.95
            
            # TP3: Orderbook BID üçüncü kalın bölge veya 4h VWAP
            tp3 = bid_zones[2]['price'] if bid_zones and len(bid_zones) > 2 else vwap_4h * 0.95
            
            entry_reason = f"Entry: {entry_price:.4f} (VWAP resistance:{vwap_resistance:.4f})"
            tp1_reason = f"TP1: {tp1:.4f} (OB thick zone 1: {bid_zones[0].get('volume', 0):.0f} contracts)"
            tp2_reason = f"TP2: {tp2:.4f} (OB thick zone 2: {bid_zones[1].get('volume', 0):.0f} contracts)"
            tp3_reason = f"TP3: {tp3:.4f} (OB thick zone 3: {bid_zones[2].get('volume', 0):.0f} contracts)"

        precision = self._get_price_precision(symbol)
        
        return {
            'entry_price': round(entry_price, precision),
            'tp1_price': round(tp1, precision),
            'tp2_price': round(tp2, precision),
            'tp3_price': round(tp3, precision),
            'sl_price': round(sl, precision),
            'ob_imbalance': ob_data.get('imbalance', 0),
            'bid_volume': ob_data.get('bid_volume', 0),
            'ask_volume': ob_data.get('ask_volume', 0),
            'entry_reason': entry_reason,
            'tp1_reason': tp1_reason,
            'tp2_reason': tp2_reason,
            'tp3_reason': tp3_reason,
            'vwap': vwap_15m,
            'vwap_4h': vwap_4h,
            'vwap_1d': vwap_1d,
            'ob_zones': {'bids': bid_zones, 'asks': ask_zones},
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