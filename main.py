import os
import sys
import time
import threading
import signal
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import argparse

sys.path.insert(0, str(Path(__file__).parent))

from src.config import config
from src.logger import logger, Logger
from src.binance_client import binance_client, binance_ws
from src.scanner import scanner
from src.signal_generator import signal_generator
from src.order_manager import order_manager
from src.risk_manager import risk_manager
from src.trailing_stop import trailing_engine
from src.dashboard import DashboardServer, update_dashboard_data

bot_instance = None


class TerminalUI:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @staticmethod
    def clear_screen():
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def print_header(title: str, width: int = 80):
        print(f"\n{TerminalUI.HEADER}{'='*width}{TerminalUI.ENDC}")
        print(f"{TerminalUI.HEADER}{title:^{width}}{TerminalUI.ENDC}")
        print(f"{TerminalUI.HEADER}{'='*width}{TerminalUI.ENDC}")

    @staticmethod
    def print_section(title: str):
        print(f"\n{TerminalUI.CYAN}{'-'*40}{TerminalUI.ENDC}")
        print(f"{TerminalUI.BOLD}{title}{TerminalUI.ENDC}")
        print(f"{TerminalUI.CYAN}{'-'*40}{TerminalUI.ENDC}")

    @staticmethod
    def print_signal(idx: int, sig: Dict[str, Any]):
        color = TerminalUI.GREEN if sig['direction'] == 'LONG' else TerminalUI.RED
        print(f"  {idx}. {color}{sig['direction']}{TerminalUI.ENDC} {sig['symbol']}")
        print(f"      Score: {sig['score']:.1f} | Price: {sig['entry_price']:.4f} | RSI: {sig['rsi']:.1f}")
        print(f"      OB Imbalance: {sig.get('ob_imbalance', 0):.2%}")
        if sig.get('strong_bid'):
            print(f"      Strong Bid: {sig['strong_bid']:.4f} | Strong Ask: {sig.get('strong_ask', 'N/A')}")

    @staticmethod
    def print_position(idx: int, pos: Dict[str, Any], current_price: float):
        direction = pos['direction']
        color = TerminalUI.GREEN if direction == 'LONG' else TerminalUI.RED
        
        entry = pos['entry_price']
        if direction == 'LONG':
            pnl_pct = (current_price - entry) / entry * 100
        else:
            pnl_pct = (entry - current_price) / entry * 100
        
        pnl_color = TerminalUI.GREEN if pnl_pct >= 0 else TerminalUI.RED
        
        print(f"  {idx}. {color}{direction}{TerminalUI.ENDC} {pos['symbol']}")
        print(f"      Entry: {entry:.4f} | Current: {current_price:.4f}")
        print(f"      PnL: {pnl_color}{pnl_pct:+.2f}%{TerminalUI.ENDC} | Amount: {pos['amount']}")
        print(f"      SL: {pos.get('sl_price', 'N/A')} | TP1: {pos.get('tp1_price', 'N/A')} | TP2: {pos.get('tp2_price', 'N/A')}")

    @staticmethod
    def print_balance(balance: float, daily_pnl: float, mode: str):
        pnl_color = TerminalUI.GREEN if daily_pnl >= 0 else TerminalUI.RED
        mode_color = TerminalUI.YELLOW if mode == 'paper' else TerminalUI.RED
        print(f"\n{TerminalUI.BOLD}Balance:{TerminalUI.ENDC} {balance:.2f} USDT")
        print(f"{TerminalUI.BOLD}Daily PnL:{TerminalUI.ENDC} {pnl_color}{daily_pnl:+.2f}%{TerminalUI.ENDC}")
        print(f"{TerminalUI.BOLD}Mode:{TerminalUI.ENDC} {mode_color}{mode.upper()}{TerminalUI.ENDC}")

    @staticmethod
    def print_controls():
        print(f"\n{TerminalUI.YELLOW}Controls:{TerminalUI.ENDC}")
        print(f"  [S] Scan Now  [P] Pause/Resume  [C] Close All  [Q] Quit")


class TradingBot:
    def __init__(self):
        self._running = False
        self._paused = False
        self._scan_interval = config.scanning.get('interval_seconds', 300)
        self._last_scan_time: Optional[datetime] = None
        self._active_trades: Dict[str, Dict[str, Any]] = {}
        self._trade_history: List[Dict[str, Any]] = []
        self._current_signals: List[Dict[str, Any]] = []
        self._last_balance: float = 0
        self._daily_start_balance: float = 0
        self._daily_pnl: float = 0
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logger.info("Shutdown signal received, stopping bot...")
        self._running = False

    def start(self):
        self._running = True
        
        self._last_balance = binance_client.get_wallet_balance()
        self._daily_start_balance = self._last_balance
        mode = "PAPER" if config.is_paper_mode else "LIVE"
        
        TerminalUI.print_header(f"Binance Futures Trading Bot - {mode} Mode")
        TerminalUI.print_balance(self._last_balance, 0, mode)
        
        if binance_client.has_credentials:
            try:
                binance_client.exchange.set_position_mode(True)
                logger.info("Hedge mode enabled")
            except Exception as e:
                logger.warning(f"Could not set hedge mode: {e}")
        else:
            logger.warning("No API credentials - running in testnet fallback mode")

        binance_ws.connect()
        logger.info("WebSocket stream connected")

        input_thread = threading.Thread(target=self._handle_input, daemon=True)
        input_thread.start()

        self._main_loop()

    def _handle_input(self):
        while self._running:
            try:
                user_input = input("\nCommand > ").strip().lower()
                if user_input == 's':
                    self._last_scan_time = None
                    print("Manual scan triggered...")
                elif user_input == 'p':
                    self._paused = not self._paused
                    print(f"{'Paused' if self._paused else 'Resumed'}")
                elif user_input == 'c':
                    self._close_all_positions()
                elif user_input == 'q':
                    print("Shutting down...")
                    self._running = False
            except:
                pass

    def _main_loop(self):
        while self._running:
            try:
                if not self._paused:
                    self._check_and_scan()
                    self._monitor_positions()
                    self._update_trailing_stops()
                    self._update_balance()
                    update_dashboard_data(self)
                
                time.sleep(30)
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                time.sleep(60)

    def _update_balance(self):
        current_balance = binance_client.get_wallet_balance()
        if self._daily_start_balance > 0:
            self._daily_pnl = (current_balance - self._daily_start_balance) / self._daily_start_balance * 100
        self._last_balance = current_balance

    def _render_ui(self):
        TerminalUI.clear_screen()
        mode = "PAPER" if config.is_paper_mode else "LIVE"
        mode_color = TerminalUI.YELLOW if mode == 'PAPER' else TerminalUI.RED
        
        TerminalUI.print_header(f"Binance Futures Bot - {mode_color}{mode}{TerminalUI.ENDC}")
        
        TerminalUI.print_balance(self._last_balance, self._daily_pnl, mode)
        
        TerminalUI.print_section(f"Active Signals ({len(self._current_signals)})")
        if self._current_signals:
            for i, sig in enumerate(self._current_signals[:5], 1):
                TerminalUI.print_signal(i, sig)
        else:
            print("  No signals currently")
        
        TerminalUI.print_section(f"Open Positions ({len(self._active_trades)})")
        if self._active_trades:
            for i, (symbol, pos) in enumerate(self._active_trades.items(), 1):
                try:
                    ticker = binance_client.fetch_ticker(symbol)
                    current_price = float(ticker['last'])
                    TerminalUI.print_position(i, pos, current_price)
                except:
                    TerminalUI.print_position(i, pos, pos['entry_price'])
        else:
            print("  No open positions")
        
        TerminalUI.print_section("Trade History")
        if self._trade_history:
            for trade in self._trade_history[-5:]:
                pnl_color = TerminalUI.GREEN if trade['pnl'] >= 0 else TerminalUI.RED
                print(f"  {trade['symbol']} {trade['direction']} | PnL: {pnl_color}{trade['pnl']:+.2f}{TerminalUI.ENDC}")
        else:
            print("  No trades yet")
        
        print(f"\nNext scan: {self._get_next_scan_time()}")
        TerminalUI.print_controls()

    def _get_next_scan_time(self) -> str:
        if self._last_scan_time:
            next_time = self._last_scan_time + timedelta(seconds=self._scan_interval)
            remaining = (next_time - datetime.now()).total_seconds()
            if remaining > 0:
                return f"in {int(remaining)}s"
        return "now"

    def _check_and_scan(self):
        if self._last_scan_time and (datetime.now() - self._last_scan_time).total_seconds() < self._scan_interval:
            return

        if not risk_manager.can_open_position():
            logger.warning("Risk limits reached, skipping scan")
            return

        if len(self._active_trades) >= config.trading.get('max_positions', 5):
            logger.info("Max positions reached, skipping scan")
            return

        logger.info(f"Scanning for signals...")
        
        signals = signal_generator.get_top_signals(limit=5)
        self._current_signals = signals
        
        if not signals:
            logger.info("No valid signals found")
            self._last_scan_time = datetime.now()
            return

        logger.info(f"Found {len(signals)} signals")

        for signal in signals:
            if len(self._active_trades) >= config.trading.get('max_positions', 5):
                break

            symbol = signal['symbol']
            if symbol in self._active_trades:
                continue

            self._execute_trade(signal)

        self._last_scan_time = datetime.now()

    def _execute_trade(self, signal: Dict[str, Any]):
        symbol = signal['symbol']
        direction = signal['direction']
        
        logger.info(f"Executing {direction} trade on {symbol}...")
        
        amount = risk_manager.calculate_position_size(symbol, direction)
        
        entry_result = order_manager.place_entry_order(
            symbol=symbol,
            direction=direction,
            amount=amount,
            vwap=signal['vwap'],
            current_price=signal['entry_price']
        )

        if not entry_result:
            logger.error(f"Failed to execute entry for {symbol}")
            return

        entry_price = entry_result.get('price', signal['entry_price'])
        
        price_data = order_manager.calculate_prices_with_orderbook(
            symbol, direction, signal['vwap'], signal['entry_price']
        )
        
        tp_orders = order_manager.place_tp_orders(
            symbol=symbol,
            direction=direction,
            amount=amount,
            entry_price=entry_price
        )

        sl_order = order_manager.place_sl_order(
            symbol=symbol,
            direction=direction,
            amount=amount,
            entry_price=entry_price
        )

        sl_price = price_data['sl_price']
        
        trailing_engine.add_position(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            amount=amount,
            sl_price=sl_price
        )

        self._active_trades[symbol] = {
            'direction': direction,
            'entry_price': entry_price,
            'amount': amount,
            'sl_price': sl_price,
            'tp1_price': price_data['tp1_price'],
            'tp2_price': price_data['tp2_price'],
            'tp1_filled': False,
            'tp2_filled': False,
            'created_at': datetime.now(),
            'entry_order_id': entry_result.get('id'),
            'tp_orders': tp_orders,
            'sl_order_id': sl_order.get('id') if sl_order else None,
        }

        logger.info(f"Trade opened: {symbol} {direction} @ {entry_price}, Amount: {amount}, SL: {sl_price}")

    def _monitor_positions(self):
        if config.is_paper_mode:
            self._monitor_paper_positions()
        else:
            self._monitor_live_positions()
    
    def _monitor_paper_positions(self):
        closed_symbols = []
        for symbol in list(self._active_trades.keys()):
            try:
                ticker = binance_client.fetch_ticker(symbol)
                current_price = float(ticker['last'])
            except:
                continue
            
            trade = self._active_trades[symbol]
            direction = trade['direction']
            entry_price = trade['entry_price']
            amount = trade['amount']
            
            tp1_hit = trade.get('tp1_filled', False)
            tp2_hit = trade.get('tp2_filled', False)
            
            if direction == 'LONG':
                pnl_pct = (current_price - entry_price) / entry_price * 100
                if not tp1_hit and current_price >= trade['tp1_price']:
                    trade['tp1_filled'] = True
                    logger.info(f"[PAPER] TP1 hit: {symbol} @ {current_price}")
                if not tp2_hit and current_price >= trade['tp2_price']:
                    trade['tp2_filled'] = True
                    logger.info(f"[PAPER] TP2 hit: {symbol} @ {current_price}")
                if current_price <= trade['sl_price']:
                    closed_symbols.append(symbol)
                    pnl = (trade['sl_price'] - entry_price) * amount
                elif trade['tp1_filled'] and trade['tp2_filled']:
                    closed_symbols.append(symbol)
                    pnl = (trade['tp2_price'] - entry_price) * amount
                else:
                    pnl = (current_price - entry_price) * amount
            else:
                pnl_pct = (entry_price - current_price) / entry_price * 100
                if not tp1_hit and current_price <= trade['tp1_price']:
                    trade['tp1_filled'] = True
                    logger.info(f"[PAPER] TP1 hit: {symbol} @ {current_price}")
                if not tp2_hit and current_price <= trade['tp2_price']:
                    trade['tp2_filled'] = True
                    logger.info(f"[PAPER] TP2 hit: {symbol} @ {current_price}")
                if current_price >= trade['sl_price']:
                    closed_symbols.append(symbol)
                    pnl = (entry_price - trade['sl_price']) * amount
                elif trade['tp1_filled'] and trade['tp2_filled']:
                    closed_symbols.append(symbol)
                    pnl = (entry_price - trade['tp2_price']) * amount
                else:
                    pnl = (entry_price - current_price) * amount
            
            if symbol in closed_symbols:
                risk_manager.record_trade(pnl)
                logger.info(f"[PAPER] Position closed: {symbol}, PnL: {pnl:.2f} USDT")
                self._trade_history.append({
                    'symbol': symbol,
                    'direction': trade['direction'],
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'amount': amount,
                    'pnl': pnl,
                    'closed_at': datetime.now().isoformat(),
                })
                trailing_engine.remove_position(symbol)
        
        for symbol in closed_symbols:
            del self._active_trades[symbol]
    
    def _monitor_live_positions(self):
        positions = binance_client.fetch_positions()
        
        closed_symbols = []
        for symbol in list(self._active_trades.keys()):
            pos = next((p for p in positions if p.get('symbol') == symbol), None)
            
            if not pos or float(pos.get('contracts', 0)) == 0:
                trade = self._active_trades[symbol]
                closed_symbols.append(symbol)
                
                current_price = binance_client.fetch_ticker(symbol)['last']
                
                if trade['direction'] == 'LONG':
                    pnl = (current_price - trade['entry_price']) * trade['amount']
                else:
                    pnl = (trade['entry_price'] - current_price) * trade['amount']
                
                risk_manager.record_trade(pnl)
                
                logger.info(f"Position closed: {symbol}, PnL: {pnl:.2f} USDT")
                
                self._trade_history.append({
                    'symbol': symbol,
                    'direction': trade['direction'],
                    'entry_price': trade['entry_price'],
                    'exit_price': current_price,
                    'amount': trade['amount'],
                    'pnl': pnl,
                    'closed_at': datetime.now().isoformat(),
                })
                
                trailing_engine.remove_position(symbol)
        
        for symbol in closed_symbols:
            del self._active_trades[symbol]

    def _update_trailing_stops(self):
        for symbol in list(self._active_trades.keys()):
            try:
                ticker = binance_client.fetch_ticker(symbol)
                current_price = float(ticker['last'])
                
                new_sl = trailing_engine.check_and_update(symbol, current_price)
                
                if new_sl:
                    self._active_trades[symbol]['sl_price'] = new_sl
                    
            except Exception as e:
                logger.error(f"Error updating trailing for {symbol}: {e}")

    def _close_all_positions(self):
        print("Closing all positions...")
        if config.is_paper_mode:
            for symbol, pos in list(self._active_trades.items()):
                try:
                    ticker = binance_client.fetch_ticker(symbol)
                    current_price = float(ticker['last'])
                except:
                    current_price = pos['entry_price']
                
                if pos['direction'] == 'LONG':
                    pnl = (current_price - pos['entry_price']) * pos['amount']
                else:
                    pnl = (pos['entry_price'] - current_price) * pos['amount']
                
                logger.info(f"[PAPER] Closed {symbol}, PnL: {pnl:.2f} USDT")
                self._trade_history.append({
                    'symbol': symbol,
                    'direction': pos['direction'],
                    'entry_price': pos['entry_price'],
                    'exit_price': current_price,
                    'amount': pos['amount'],
                    'pnl': pnl,
                    'closed_at': datetime.now().isoformat(),
                })
            
            self._active_trades.clear()
        else:
            for symbol, pos in list(self._active_trades.items()):
                order_manager.close_position(symbol, pos['direction'], pos['amount'])


def parse_args():
    parser = argparse.ArgumentParser(description='Binance Futures Trading Bot')
    parser.add_argument('--mode', choices=['paper', 'live'], default='paper',
                        help='Trading mode: paper (test) or live (real)')
    parser.add_argument('--config', default='config.yaml',
                        help='Path to config file')
    return parser.parse_args()


def main():
    global bot_instance
    
    args = parse_args()
    
    log_file = f"logs/bot_{datetime.now().strftime('%Y%m%d')}.log"
    logger.setup(log_file=log_file)
    
    config.load(args.config)
    if config._config is not None:
        config._config.setdefault('trading', {})['mode'] = args.mode
    
    logger.info(f"Starting bot in {args.mode.upper()} mode")
    
    bot = TradingBot()
    bot_instance = bot
    
    dashboard = DashboardServer(bot)
    dashboard.start()
    logger.info(f"Dashboard: http://localhost:5000")
    
    bot.start()


if __name__ == '__main__':
    main()