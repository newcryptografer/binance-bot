from typing import Dict, Any, List, Optional
from datetime import datetime
from src.binance_client import binance_client, binance_ws
from src.analyzer import analyzer
from src.config import config
from src.logger import logger


class Scanner:
    def __init__(self):
        self.min_volume = config.scanning.get('min_volume_usdt', 100000)
        self.ohlcv_limit = config.scanning.get('ohlcv_limit', 200)
        self.timeframe = config.scanning.get('timeframe', '1h')
        self._cached_markets: Optional[List[Dict[str, Any]]] = None
        self._last_cache_time: Optional[datetime] = None

    def get_usdt_futures_symbols(self) -> List[str]:
        cache_age = None
        if self._last_cache_time:
            cache_age = (datetime.now() - self._last_cache_time).total_seconds()
        
        if self._cached_markets is None or cache_age is None or cache_age > 300:
            markets = binance_client.fetch_markets()
            self._cached_markets = markets
            self._last_cache_time = datetime.now()
            logger.info(f"Loaded {len(markets)} USDT futures markets")
        
        return [m['symbol'] for m in self._cached_markets]

    def scan_symbol(self, symbol: str, fetch_multi_tf: bool = True) -> Optional[Dict[str, Any]]:
        try:
            ws_ticker = binance_ws.get_ticker_data(symbol)
            
            if ws_ticker:
                current_price = ws_ticker.get('price', 0)
                volume = ws_ticker.get('volume', 0)
            else:
                ticker = binance_client.fetch_ticker(symbol)
                current_price = float(ticker['last'])
                volume = float(ticker['quoteVolume'])
            
            if volume < self.min_volume:
                return None
            
            ohlcv = binance_client.fetch_ohlcv(symbol, self.timeframe, self.ohlcv_limit)
            
            if not ohlcv or len(ohlcv) < 50:
                return None
            
            avg_volume = sum([c[5] for c in ohlcv[-24:]]) / 24
            
            analysis = analyzer.analyze_symbol(ohlcv, current_price, volume, avg_volume)
            analysis['symbol'] = symbol
            analysis['current_price'] = current_price
            analysis['volume'] = volume
            analysis['avg_volume'] = avg_volume
            
            if fetch_multi_tf:
                try:
                    ohlcv_1h = binance_client.fetch_ohlcv(symbol, '1h', 50)
                    ohlcv_4h = binance_client.fetch_ohlcv(symbol, '4h', 50)
                    ohlcv_1d = binance_client.fetch_ohlcv(symbol, '1d', 30)
                    
                    analysis['ohlcv_1h'] = ohlcv_1h
                    analysis['ohlcv_4h'] = ohlcv_4h
                    analysis['ohlcv_1d'] = ohlcv_1d
                except Exception as e:
                    logger.debug(f"Multi-TF error for {symbol}: {e}")
            
            return analysis
            
        except Exception as e:
            logger.debug(f"Error scanning {symbol}: {e}")
            return None

    def scan_all_symbols(self, limit: int = 50) -> List[str]:
        symbols = self.get_usdt_futures_symbols()
        
        if not symbols:
            logger.warning("No symbols found")
            return []
        
        symbols_to_subscribe = symbols[:50]
        binance_ws.subscribe_markets(symbols_to_subscribe, lambda s, d: None)
        
        return symbols_to_subscribe

    def scan_all_with_data(self, limit: int = 50) -> List[Dict[str, Any]]:
        symbols = self.scan_all_symbols(limit)
        results = []
        
        logger.info(f"Scanning {len(symbols)} symbols...")
        
        for i, symbol in enumerate(symbols):
            if i % 20 == 0:
                logger.info(f"Progress: {i}/{len(symbols)}")
            
            result = self.scan_symbol(symbol)
            if result:
                results.append(result)
        
        logger.info(f"Found {len(results)} viable symbols")
        return results


scanner = Scanner()