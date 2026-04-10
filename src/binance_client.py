import os
import json
import time
import threading
import logging
import websocket
from typing import Dict, Any, List, Optional

try:
    from binance.futures import Futures
except (ImportError, NameError):
    try:
        from binance.um_futures import UMFutures as Futures
    except (ImportError, NameError):
        print("Warning: binance-futures-connector not installed")
        Futures = None

from src.config import config


logger = logging.getLogger(__name__)


class BinanceClient:
    def __init__(self):
        self._client: Optional[Futures] = None
        self._ws: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._price_cache: Dict[str, Dict] = {}
        self._running = False
        self._init_client()
    
    def _init_client(self):
        api_key = config.binance.get('api_key', '')
        api_secret = config.binance.get('api_secret', '')
        
        if not api_key or not api_secret:
            logger.warning("No API credentials - using public endpoints")
            self._client = Futures(base_url="https://fapi.binance.com")
        else:
            self._client = Futures(
                key=api_key,
                secret=api_secret,
                base_url="https://fapi.binance.com"
            )
            logger.info("Binance client initialized")
    
    @property
    def client(self) -> Futures:
        if self._client is None:
            self._init_client()
        return self._client
    
    @property
    def is_paper(self) -> bool:
        return config.trading.get('mode', 'paper') == 'paper'
    
    def get_markets(self) -> List[Dict[str, Any]]:
        try:
            resp = self.client.exchange_info()
            markets = [m for m in resp.get('symbols', []) 
                      if m.get('quoteAsset') == 'USDT' 
                      and m.get('contractType') == 'PERPETUAL'
                      and m.get('status') == 'TRADING']
            return markets
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []
    
    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 200) -> List[List[float]]:
        try:
            resp = self.client.klines(symbol=symbol, interval=interval, limit=limit)
            return [[float(x) for x in r[:6]] for r in resp]
        except Exception as e:
            logger.error(f"Error fetching klines for {symbol}: {e}")
            return []
    
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        try:
            if hasattr(self.client, 'ticker_price'):
                resp = self.client.ticker_price(symbol=symbol)
                return {'last': float(resp.get('price', 0)), 'high': 0, 'low': 0, 'volume': 100000, 'quoteVolume': 100000}
            elif hasattr(self.client, 'ticker_24h'):
                resp = self.client.ticker_24h(symbol=symbol)
                return {'last': float(resp.get('lastPrice', 0)), 'high': float(resp.get('highPrice', 0)), 'low': float(resp.get('lowPrice', 0)), 'volume': float(resp.get('volume', 0)), 'quoteVolume': float(resp.get('quoteVolume', 0))}
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
        return {}
    
    def fetch_markets(self) -> List[Dict[str, Any]]:
        return self.get_markets()
    
    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        return self.get_ticker(symbol)
    
    def fetch_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 200) -> List[List[float]]:
        return self.get_klines(symbol, interval, limit)
    
    def get_orderbook_levels(self, symbol: str, levels: int = 20) -> Dict[str, Any]:
        try:
            depth = self.client.depth(symbol=symbol, limit=levels)
            bids = [[float(b[0]), float(b[1])] for b in depth.get('bids', [])]
            asks = [[float(a[0]), float(a[1])] for a in depth.get('asks', [])]
            
            bid_prices = [b[0] for b in bids]
            ask_prices = [a[0] for a in asks]
            bid_vols = [b[1] for b in bids]
            ask_vols = [a[1] for a in asks]
            
            total_bid = sum(bid_vols)
            total_ask = sum(ask_vols)
            
            bids_by_vol = sorted(bids, key=lambda x: x[1], reverse=True)
            asks_by_vol = sorted(asks, key=lambda x: x[1], reverse=True)
            
            best_bid = bid_prices[0] if bid_prices else 0
            best_ask = ask_prices[0] if ask_prices else 0
            
            return {
                'best_bid': best_bid,
                'best_ask': best_ask,
                'mid_price': (best_bid + best_ask) / 2,
                'total_bid_volume': total_bid,
                'total_ask_volume': total_ask,
                'bid_ask_ratio': total_bid / total_ask if total_ask > 0 else 1,
                'bids': [{'price': b[0], 'volume': b[1]} for b in bids],
                'asks': [{'price': a[0], 'volume': a[1]} for a in asks],
                'bids_by_vol': [{'price': b[0], 'volume': b[1]} for b in bids_by_vol[:5]],
                'asks_by_vol': [{'price': a[0], 'volume': a[1]} for a in asks_by_vol[:5]],
                'imbalance': (total_bid - total_ask) / (total_bid + total_ask) if (total_bid + total_ask) > 0 else 0,
            }
        except Exception as e:
            logger.error(f"Error fetching orderbook for {symbol}: {e}")
            return {'bids': [], 'asks': [], 'bids_by_vol': [], 'asks_by_vol': []}
    
    def get_liquidity_zones(self, symbol: str, current_price: float) -> Dict[str, Any]:
        ob = self.get_orderbook_levels(symbol, 20)
        
        bids = ob.get('bids', [])
        asks = ob.get('asks', [])
        total_bid = ob.get('total_bid_volume', 0)
        total_ask = ob.get('total_ask_volume', 0)
        
        strong_bid = None
        for b in bids[:5]:
            if b['volume'] > total_bid * 0.3:
                strong_bid = b['price']
                break
        
        strong_ask = None
        for a in asks[:5]:
            if a['volume'] > total_ask * 0.3:
                strong_ask = a['price']
                break
        
        return {
            'strong_bid': strong_bid,
            'strong_ask': strong_ask,
            'imbalance': ob.get('imbalance', 0),
            'bid_volume': total_bid,
            'ask_volume': total_ask,
            'bids': ob.get('bids', []),
            'asks': ob.get('asks', []),
        }
    
    def get_balance(self) -> float:
        if not self._client or self.is_paper:
            return 10000  # paper mode default balance
        try:
            account = self.client.balance()
            return float(account.get('availableBalance', 0))
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
        return 10000
    
    def get_wallet_balance(self) -> float:
        return self.get_balance()
    
    @property
    def has_credentials(self) -> bool:
        api_key = config.binance.get('api_key', '')
        api_secret = config.binance.get('api_secret', '')
        return bool(api_key and api_secret)
    
    @property
    def exchange(self):
        return self._client
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        if self.is_paper:
            logger.info(f"[PAPER] Set leverage {leverage}x for {symbol}")
            return True
        try:
            self.client.position_side_dual(True)
            self.client.leverage(symbol=symbol, leverage=leverage)
            return True
        except Exception as e:
            logger.warning(f"Could not set leverage: {e}")
            return True
    
    def place_order(self, symbol: str, side: str, order_type: str, 
                   quantity: float, price: Optional[float] = None,
                   position_side: str = "BOTH") -> Optional[Dict[str, Any]]:
        if self.is_paper:
            order_id = f"paper_{int(time.time()*1000)}"
            logger.info(f"[PAPER] {side} {order_type} {symbol} qty={quantity} @ {price or 'market'}")
            return {
                'orderId': order_id,
                'symbol': symbol,
                'side': side,
                'type': order_type,
                'price': price,
                'origQty': quantity,
                'status': 'NEW'
            }
        
        try:
            params = {
                'symbol': symbol,
                'side': side,
                'positionSide': position_side,
            }
            
            if order_type == 'MARKET':
                params['orderType'] = 'MARKET'
                params['quantity'] = quantity
            else:
                params['orderType'] = 'LIMIT'
                params['price'] = price
                params['quantity'] = quantity
                params['timeInForce'] = 'GTC'
            
            resp = self.client.new_order(**params)
            return resp
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    def get_positions(self) -> List[Dict[str, Any]]:
        try:
            return self.client.positionRisk()
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    def fetch_positions(self) -> List[Dict[str, Any]]:
        return self.get_positions()
    
    def cancel_order(self, symbol: str, order_id: str) -> bool:
        if self.is_paper:
            return True
        try:
            self.client.cancel(symbol=symbol, orderId=order_id)
            return True
        except Exception as e:
            logger.error(f"Error canceling order: {e}")
            return False
    
    def start_websocket(self):
        self._running = True
        self._ws_thread = threading.Thread(target=self._ws_loop, daemon=True)
        self._ws_thread.start()
    
    def _ws_loop(self):
        while self._running:
            try:
                ws_url = "wss://fstream.binance.com/ws"
                self._ws = websocket.WebSocketApp(
                    ws_url,
                    on_message=self._on_message,
                    on_error=lambda ws, e: logger.error(f"WS error: {e}"),
                    on_close=lambda ws, code, msg: logger.warning(f"WS closed: {code}"),
                    on_open=self._on_open
                )
                self._ws.run_forever(ping_interval=30)
            except Exception as e:
                logger.error(f"WS loop error: {e}")
            time.sleep(5)
    
    def _on_open(self, ws):
        ws.send(json.dumps({"method": "SUBSCRIBE", "params": ["!ticker@arr"], "id": 1}))
        logger.info("WebSocket connected")
    
    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if isinstance(data, list):
                for ticker in data:
                    symbol = ticker.get('s')
                    if symbol and symbol.endswith('USDT'):
                        self._price_cache[symbol] = {
                            'price': float(ticker.get('c', 0)),
                            'volume': float(ticker.get('v', 0)),
                        }
        except:
            pass
    
    def stop_websocket(self):
        self._running = False
        if self._ws:
            self._ws.close()


class BinanceWebSocket:
    def __init__(self, client: BinanceClient):
        self._client = client
        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._price_cache: Dict[str, Dict] = {}
    
    def connect(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("WebSocket connected")
    
    def _run_loop(self):
        while self._running:
            try:
                ws_url = "wss://fstream.binance.com/stream?streams=!ticker@arr"
                self._ws = websocket.WebSocketApp(
                    ws_url,
                    on_message=self._on_message,
                    on_error=lambda ws, e: logger.error(f"WS error: {e}"),
                    on_close=lambda ws, code, msg: logger.warning(f"WS closed: {code}"),
                    on_open=lambda ws: ws.send(json.dumps({"method": "SUBSCRIBE", "params": ["!ticker@arr"], "id": 1}))
                )
                self._ws.run_forever(ping_interval=30)
            except Exception as e:
                logger.error(f"WS loop error: {e}")
            time.sleep(5)
    
    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if isinstance(data, list):
                for ticker in data:
                    symbol = ticker.get('s')
                    if symbol and symbol.endswith('USDT'):
                        self._price_cache[symbol] = {
                            'price': float(ticker.get('c', 0)),
                            'volume': float(ticker.get('v', 0)),
                        }
        except:
            pass
    
    def close(self):
        self._running = False
        if self._ws:
            self._ws.close()
    
    @property
    def prices(self) -> Dict[str, Dict]:
        return self._price_cache
    
    def get_ticker_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        return self._price_cache.get(symbol)
    
    def subscribe_markets(self, symbols: List[str], callback):
        pass


binance_client = BinanceClient()
binance_ws = BinanceWebSocket(binance_client)