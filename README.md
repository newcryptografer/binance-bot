# Binance Futures Auto Trading Bot

## Kurulum

```bash
# Python 3.12 yükle (sisteminizde yoksa)

# Dependencies yükle
pip install -r requirements.txt

# veya
pip install ccxt pandas numpy pyyaml python-dotenv
```

## Konfigürasyon

`config.yaml` dosyasını düzenleyin:

```yaml
binance:
  api_key: "API_KEY"        # Paper mod için de doldur (canlı veri için gerekli)
  api_secret: "API_SECRET"  # Paper mod için de doldur

trading:
  mode: paper               # paper = canlı veri + simüle işlem, live = gerçek işlem
  leverage: 10
  entry_percent: 1.0
  stop_loss_percent: 2.0
  take_profit_percent: 3.0
  tp2_percent: 5.0
  trailing_stop_percent: 1.5
  max_positions: 5
  cooldown_minutes: 15

scanning:
  interval_seconds: 300
  min_volume_usdt: 100000
  timeframe: 1h

risk:
  max_daily_loss_percent: 5.0
  max_consecutive_losses: 3
```

## Çalıştırma

```bash
# Paper mod (canlı veri + risksiz işlem - ÖNERİLEN)
python main.py --mode paper

# Live mod (gerçek işlem)
python main.py --mode live
```

## Kontroller

- **S** - Manuel tarama başlat
- **P** - Durdur/Devam et
- **C** - Tüm pozisyonları kapat
- **Q** - Çıkış

## Özellikler

### Sinyal Analizi
- RSI (14 periyot)
- VWAP (Volume Weighted Average Price)
- EMA 50/200 crossover
- ADR (Average Daily Range)
- Hacim oranı
- Momentum
- Orderbook imbalance (bid/ask volume)

### Emir Stratejisi
- **Entry:** Orderbook liquidity zone + VWAP destek/direnç
- **TP1:** %3 (pozisyonun %50'si)
- **TP2:** %5 (pozisyonun %50'si)
- **SL:** %2
- **Trailing:** TP1'e ulaşınca %1.5 trailing stop

### Risk Yönetimi
- Günlük max kayıp: %5
- Art arda 3 kayıp = durdurma
- Cross margin + Hedge mod

## Güvenlik

1. İlk olarak `mode: paper` ile test edin (API key gerekli - canlı veri için)
2. API key'inizi `config.yaml` veya `.env` dosyasına girin
3. Risk limitlerini ihtiyacınıza göre ayarlayın
4. `mode: live` ile gerçek işleme geçmeden önce paper modda yeterli test yapın

## Not

- Bot her 5 dakikada bir tarama yapar
- En karlı 5 koin için sinyal üretir
- Her koin eşit sermaye kullanır (toplam / 5)
- Cross margin + Hedge mod açık (aynı koin için long+short açılabilir)