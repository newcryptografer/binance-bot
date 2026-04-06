import ccxt
import json
import threading
import time
import websocket
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime
from src.config import config
from src.logger import logger


class BinanceClient:
    def __init__(self):
        self._exchange: Optional[ccxt.binance] = None
    
    def _ensure_exchange(self) -> None:
        if self._exchange is not None:
            return
        
        api_key = config.binance.get('api_key', '')
        api_secret = config.binance.get('api_secret', '')
        
        print(f"[DEBUG] _ensure_exchange: api_key='{api_key}', api_secret='{api_secret}'")
        
        exchange_opts = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
                'hedged': True,
            }
        }
        
        if not api_key or not api_secret:
            logger.warning("API key/secret not provided - falling back to testnet")
            self._exchange = ccxt.binance({
                'urls': {
                    'api': {
                        'public': 'https://testnet.binancefuture.com',
                        'private': 'https://testnet.binancefuture.com',
                    }
                },
                **exchange_opts
            })
            logger.info("Binance Testnet mode initialized (Hedge Mode)")
        else:
            self._exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True,
                    'hedged': True,
                }
            })
            logger.info("Binance Live exchange initialized for market data")

    @property
    def is_testnet(self) -> bool:
        self._ensure_exchange()
        return self._exchange is not None and 'testnet' in str(self._exchange.urls.get('api', {}).get('private', ''))
    
    @property
    def has_credentials(self) -> bool:
        api_key = config.binance.get('api_key', '')
        api_secret = config.binance.get('api_secret', '')
        return bool(api_key and api_secret)

    @property
    def exchange(self) -> ccxt.binance:
        self._ensure_exchange()
        return self._exchange

    def fetch_markets(self) -> List[Dict[str, Any]]:
        markets = self.exchange.load_markets()
        usdt_futures = []
        for m in markets.values():
            symbol = m.get('symbol', '')
            if (m.get('quote') == 'USDT' or m.get('quote') == 'USD') and m.get('type') == 'future':
                # Filter: perpetual contracts only (no date like 260626)
                if ':' in symbol:
                    base = symbol.split(':')[-1]
                else:
                    base = symbol.split('/')[-1] if '/' in symbol else symbol
                # Skip if ends with year/month (like 260626)
                if len(base) >= 4 and base[:4].isdigit():
                    continue
                usdt_futures.append(m)
        
        logger.info(f"[DEBUG] Total markets: {len(markets)}, USDT futures: {len(usdt_futures)}")
        print(f"[DEBUG] Sample symbols: {[m.get('symbol') for m in usdt_futures[:5]]}")
        return usdt_futures

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        return self.exchange.fetch_ticker(symbol)

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> List[List[float]]:
        return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

    def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        return self.exchange.fetch_order_book(symbol, limit)

    def fetch_l2_order_book(self, symbol: str, depth: int = 50) -> Dict[str, Any]:
        ob = self.exchange.fetch_order_book(symbol, depth)
        
        bid_volume = sum([float(b[1]) for b in ob.get('bids', [])[:10]])
        ask_volume = sum([float(a[1]) for a in ob.get('asks', [])[:10]])
        
        ob['bid_volume'] = bid_volume
        ob['ask_volume'] = ask_volume
        ob['imbalance'] = (bid_volume - ask_volume) / (bid_volume + ask_volume) if (bid_volume + ask_volume) > 0 else 0
        
        return ob

    def get_orderbook_levels(self, symbol: str, levels: int = 10) -> Dict[str, Any]:
        ob = self.fetch_order_book(symbol, levels)
        
        bids = ob.get('bids', [])
        asks = ob.get('asks', [])
        
        bid_prices = [float(b[0]) for b in bids]
        ask_prices = [float(a[0]) for a in asks]
        
        bid_volumes = [float(b[1]) for b in bids]
        ask_volumes = [float(a[1]) for a in asks]
        
        max_bid_volume_idx = bid_volumes.index(max(bid_volumes)) if bid_volumes else 0
        max_ask_volume_idx = ask_volumes.index(max(ask_volumes)) if ask_volumes else 0
        
        best_bid = bid_prices[0] if bid_prices else 0
        best_ask = ask_prices[0] if ask_prices else 0
        mid_price = (best_bid + best_ask) / 2
        
        return {
            'best_bid': best_bid,
            'best_ask': best_ask,
            'mid_price': mid_price,
            'spread': best_ask - best_bid if best_ask and best_bid else 0,
            'spread_percent': ((best_ask - best_bid) / mid_price * 100) if mid_price > 0 else 0,
            'max_bid_level_price': bid_prices[max_bid_volume_idx] if bid_prices else 0,
            'max_ask_level_price': ask_prices[max_ask_volume_idx] if ask_prices else 0,
            'total_bid_volume': sum(bid_volumes),
            'total_ask_volume': sum(ask_volumes),
            'bid_ask_ratio': sum(bid_volumes) / sum(ask_volumes) if sum(ask_volumes) > 0 else 1,
            'bids': [{'price': p, 'volume': v} for p, v in bids],
            'asks': [{'price': p, 'volume': v} for p, v in asks],
        }

    def get_liquidity_zones(self, symbol: str, current_price: float) -> Dict[str, Any]:
        ob_levels = self.get_orderbook_levels(symbol, 20)
        
        bid_prices = [b['price'] for b in ob_levels['bids']]
        ask_prices = [a['price'] for a in ob_levels['asks']]
        
        strong_bid_zone = None
        strong_ask_zone = None
        
        for i, b in enumerate(ob_levels['bids'][:5]):
            if b['volume'] > ob_levels['total_bid_volume'] * 0.3:
                strong_bid_zone = b['price']
                break
        
        for i, a in enumerate(ob_levels['asks'][:5]):
            if a['volume'] > ob_levels['total_ask_volume'] * 0.3:
                strong_ask_zone = a['price']
                break
        
        return {
            'strong_bid': strong_bid_zone,
            'strong_ask': strong_ask_zone,
            'bid_volume': ob_levels['total_bid_volume'],
            'ask_volume': ob_levels['total_ask_volume'],
            'imbalance': ob_levels['imbalance'],
            'entry_bid': strong_bid_zone if strong_bid_zone else current_price * 0.998,
            'entry_ask': strong_ask_zone if strong_ask_zone else current_price * 1.002,
        }

    def fetch_balance(self) -> Dict[str, Any]:
        return self.exchange.fetch_balance({'type': 'future'})

    def fetch_positions(self) -> List[Dict[str, Any]]:
        positions = self.exchange.fetch_positions()
        return [p for p in positions if float(p.get('contracts', 0)) > 0]

    def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.exchange.fetch_open_orders(symbol, params={'type': 'future'})

    def create_order(self, symbol: str, side: str, order_type: str, 
                     amount: float, price: Optional[float] = None,
                     params: Optional[Dict] = None) -> Dict[str, Any]:
        order_params = {'type': 'future', 'marginMode': 'cross'}
        if params:
            order_params.update(params)
        
        return self.exchange.create_order(
            symbol, order_type, side, amount, price, order_params
        )

    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        try:
            self._ensure_exchange()
            if self.is_testnet:
                logger.info(f"[TESTNET] Leverage {leverage}x for {symbol}")
                return {'leverage': leverage, 'symbol': symbol}
            return self.exchange.set_leverage(symbol, leverage)
        except Exception as e:
            logger.warning(f"Leverage skipped: {e}")
            return {'leverage': leverage, 'symbol': symbol}

    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        return self.exchange.cancel_order(order_id, symbol)

    def cancel_all_orders(self, symbol: str) -> List[Dict[str, Any]]:
        return self.exchange.cancel_all_orders(symbol, params={'type': 'future'})

    def get_wallet_balance(self) -> float:
        balance = self.fetch_balance()
        return float(balance.get('USDT', {}).get('free', 0))

    def get_total_balance(self) -> float:
        balance = self.fetch_balance()
        return float(balance.get('USDT', {}).get('total', 0))

    def fetch_funding_rate(self, symbol: str) -> Optional[float]:
        try:
            funding = self.exchange.fetch_funding_rate(symbol)
            return funding.get('fundingRate')
        except Exception:
            return None

    def fetch_open_interest(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            oi = self.exchange.fetch_open_interest(symbol)
            return oi
        except Exception:
            return None


class BinanceWebSocket:
    def __init__(self):
        self._ws: Optional[websocket.WebSocketApp] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._subscribers: Dict[str, List[Callable]] = {}
        self._price_cache: Dict[str, Dict] = {}
        
        self._base_url = "wss://stream.binancefuture.com/ws"
        
    def connect(self):
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_ws, daemon=True)
        self._thread.start()
        logger.info("WebSocket connected")
    
    def _run_ws(self):
        while self._running:
            try:
                self._ws = websocket.WebSocketApp(
                    self._base_url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_open=self._on_open
                )
                self._ws.run_forever(ping_interval=30)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            if self._running:
                time.sleep(5)
    
    def _on_open(self, ws):
        logger.info("WebSocket connection opened")
        subscribe_msg = {"method": "SUBSCRIBE", "params": ["!ticker@arr"], "id": 1}
        ws.send(json.dumps(subscribe_msg))
    
    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            
            if 'e' in data and data['e'] == '24hrTicker':
                symbol = data['s']
                self._price_cache[symbol] = {
                    'price': float(data['c']),
                    'high': float(data['h']),
                    'low': float(data['l']),
                    'volume': float(data['v']),
                    'change': float(data['p']),
                    'change_percent': float(data['P']),
                }
            elif isinstance(data, list):
                for item in data:
                    if 's' in item:
                        symbol = item['s']
                        self._price_cache[symbol] = {
                            'price': float(item.get('c', 0)),
                            'high': float(item.get('h', 0)),
                            'low': float(item.get('l', 0)),
                            'volume': float(item.get('v', 0)),
                        }
        except Exception as e:
            logger.debug(f"WebSocket message error: {e}")
    
    def _on_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"WebSocket closed: {close_status_code}")
    
    def subscribe_markets(self, symbols: List[str], callback: Callable):
        self._subscribers.setdefault("all_tickers", []).append(callback)
        
        if self._ws and self._running and symbols:
            params = [f"{s.lower()}@ticker" for s in symbols[:50]]
            msg = {"method": "SUBSCRIBE", "params": params, "id": int(time.time())}
            self._ws.send(json.dumps(msg))
    
    def get_ticker_data(self, symbol: str) -> Optional[Dict]:
        return self._price_cache.get(symbol)
    
    def get_all_prices(self) -> Dict[str, float]:
        return {s: d.get('price', 0) for s, d in self._price_cache.items()}
    
    def disconnect(self):
        self._running = False
        if self._ws:
            self._ws.close()
        if self._thread:
            self._thread.join(timeout=5)


binance_client = BinanceClient()
binance_ws = BinanceWebSocket()