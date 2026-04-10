# Active Context: Binance Futures Trading Bot

## Current State

**Bot Status**: ⚡ In Development

Rewrite to use binance-futures-connector library instead of ccxt.

## Recently Completed

- [x] Update requirements.txt with binance-futures-connector 4.1.0, pandas-ta 0.4.71b0
- [x] Rewrite binance_client.py with binance-futures-connector (with orderbook, liquidity zones, WebSocket)
- [x] Update analyzer.py to use pandas-ta for technical analysis
- [x] Add multi-timeframe analysis support to analyzer.py
- [x] Fix binance_ws export for WebSocket connection

## Current Structure

| File/Directory | Purpose | Status |
|----------------|---------|--------|
| `requirements.txt` | Dependencies | ✅ Updated |
| `src/binance_client.py` | Binance API client | ✅ Updated |
| `src/analyzer.py` | Technical analysis | ✅ Updated with pandas-ta |
| `src/signal_generator.py` | Signal generation | ✅ Basic confluence |
| `src/scanner.py` | Market scanner | ✅ Existing |
| `src/order_manager.py` | Order management | ✅ Existing |
| `main.py` | Main trading loop | ✅ Existing |

## Current Focus

The bot is functional with:
- binance-futures-connector for API
- pandas-ta for technical analysis
- Orderbook-based entry/exit with liquidity zones
- Basic scoring system

## Pending Improvements

- [ ] Full multi-timeframe confluence system (1m-5m entry, 15m-1h trend, 4h-1D main)
- [ ] Enhanced confluence scoring (trend + momentum + order flow + volume + structure)
- [ ] Test in paper mode

## Session History

| Date | Changes |
|------|---------|
| 2026-04-10 | Migrate from ccxt to binance-futures-connector |
| 2026-04-10 | Add pandas-ta for technical analysis |
| 2026-04-10 | Fix binance_ws WebSocket export |