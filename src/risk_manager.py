from typing import Dict, Any, List, Optional
from datetime import datetime
from src.binance_client import binance_client
from src.logger import logger
from src.config import config


class RiskManager:
    def __init__(self):
        self.max_daily_loss_percent = config.risk.get('max_daily_loss_percent', 5.0)
        self.max_consecutive_losses = config.risk.get('max_consecutive_losses', 3)
        self._daily_pnl = 0.0
        self._consecutive_losses = 0
        self._last_reset_date: Optional[str] = None

    def check_daily_loss_limit(self) -> bool:
        today = datetime.now().strftime('%Y-%m-%d')
        
        if self._last_reset_date != today:
            self._daily_pnl = 0.0
            self._last_reset_date = today
            logger.info("Daily PnL reset")
        
        return self._daily_pnl > -self.max_daily_loss_percent

    def check_consecutive_losses(self) -> bool:
        return self._consecutive_losses < self.max_consecutive_losses

    def can_open_position(self) -> bool:
        if not self.check_daily_loss_limit():
            logger.warning("Daily loss limit reached. Stopping trading.")
            return False
        
        if not self.check_consecutive_losses():
            logger.warning(f"Consecutive loss limit reached ({self.max_consecutive_losses}). Waiting for cooldown.")
            return False
        
        return True

    def record_trade(self, pnl: float) -> None:
        self._daily_pnl += pnl
        
        if pnl < 0:
            self._consecutive_losses += 1
            logger.info(f"Loss recorded. Consecutive losses: {self._consecutive_losses}")
        else:
            self._consecutive_losses = 0
            logger.info(f"Profit recorded. Daily PnL: {self._daily_pnl:.2f}")

    def calculate_position_size(self, symbol: str, direction: str) -> float:
        balance = binance_client.get_wallet_balance()
        entry_percent = config.trading.get('entry_percent', 1.0)
        leverage = config.trading.get('leverage', 10)
        
        base_amount = balance * (entry_percent / 100)
        position_size = base_amount * leverage
        
        min_notional = 10.0
        if position_size < min_notional:
            position_size = min_notional
        
        return int(position_size)
        
        precision = self._get_quantity_precision(symbol)
        return round(position_size, precision)

    def _get_quantity_precision(self, symbol: str) -> int:
        try:
            markets = binance_client.fetch_markets()
            market = next((m for m in markets if m['symbol'] == symbol), None)
            if market:
                precision = market.get('precision', {}).get('amount', 2)
                return precision
        except Exception:
            pass
        return 2


risk_manager = RiskManager()