from typing import Dict, Any, List, Optional
from datetime import datetime
from src.order_manager import order_manager
from src.risk_manager import risk_manager
from src.logger import logger
from src.config import config


class TrailingStopEngine:
    def __init__(self):
        self._active_positions: Dict[str, Dict[str, Any]] = {}
        self.check_interval_seconds = 60

    def add_position(self, symbol: str, direction: str, entry_price: float,
                     amount: float, sl_price: float) -> None:
        self._active_positions[symbol] = {
            'direction': direction,
            'entry_price': entry_price,
            'amount': amount,
            'initial_sl': sl_price,
            'current_sl': sl_price,
            'created_at': datetime.now(),
        }
        logger.info(f"Position tracked: {symbol} {direction} @ {entry_price}")

    def remove_position(self, symbol: str) -> None:
        if symbol in self._active_positions:
            del self._active_positions[symbol]
            logger.info(f"Position removed from tracking: {symbol}")

    def get_active_positions(self) -> Dict[str, Dict[str, Any]]:
        return self._active_positions.copy()

    def check_and_update(self, symbol: str, current_price: float) -> Optional[float]:
        if symbol not in self._active_positions:
            return None
        
        pos = self._active_positions[symbol]
        direction = pos['direction']
        entry_price = pos['entry_price']
        current_sl = pos['current_sl']
        
        new_sl = order_manager.update_trailing_sl(
            symbol, direction, current_price, entry_price, current_sl
        )
        
        if new_sl is not None:
            self._active_positions[symbol]['current_sl'] = new_sl
            return new_sl
        
        return None

    def is_position_active(self, symbol: str) -> bool:
        return symbol in self._active_positions


trailing_engine = TrailingStopEngine()