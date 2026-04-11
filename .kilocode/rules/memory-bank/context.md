# Active Context: Binance Futures Trading Bot

## Current State

**Bot Status**: ⚡ In Development

SMC karar motoru ana karar mekanizması olarak entegre edildi.

## Recently Completed

- [x] Create SMC Decision Engine module (smc_decision_engine.py)
  - Piyasa yapısı analizi: Higher Highs/Higher Lows = Uptrend, Lower Highs/Lower Lows = Downtrend, Range = Sideways
  - 1h ve 4h/1D timeframe'lerde yapı analizi
  - BOS/CHoCH detection
  - Karar = Ana Yapı + Orta Yapı + Teknik Onay
- [x] Update signal_generator.py to use SMC decisions as primary decision mechanism
- [x] Update scanner.py to fetch multi-timeframe data (1h, 4h, 1d)
- [x] System supports Live/Paper mode via --mode argument

## Current Structure

| File/Directory | Purpose | Status |
|----------------|---------|--------|
| `src/smc_decision_engine.py` | SMC Karar Motoru | ✅ NEW |
| `src/signal_generator.py` | Signal generation + SMC entegrasyonu | ✅ Updated |
| `src/scanner.py` | Market scanner + multi-TF | ✅ Updated |
| `requirements.txt` | Dependencies | ✅ Updated |
| `src/binance_client.py` | Binance API client | ✅ Updated |
| `src/analyzer.py` | Technical analysis | ✅ Updated with pandas-ta |
| `src/order_manager.py` | Order management | ✅ Existing |
| `main.py` | Main trading loop + Live/Paper | ✅ Existing |

## Current Focus

The bot is functional with:
- binance-futures-connector for API
- pandas-ta for technical analysis
- Orderbook-based entry/exit with liquidity zones
- SMC karar motoru as primary decision mechanism
- Live/Paper mode support

## Pending Improvements

- [ ] Test in paper mode
- [ ] Add more SMC features (Liquidity Pools, Stop Hunt, Order Blocks, FVG)

## Session History

| Date | Changes |
|------|---------|
| 2026-04-11 | Add SMC Decision Engine with market structure analysis |
| 2026-04-11 | Integrate SMC to signal_generator as primary decision |
| 2026-04-11 | Add multi-timeframe (1h, 4h, 1d) to scanner |
| 2026-04-10 | Migrate from ccxt to binance-futures-connector |
| 2026-04-10 | Add pandas-ta for technical analysis |