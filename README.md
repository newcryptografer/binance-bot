# Binance Futures Auto Trading Bot

## Kurulum

```bash
pip install -r requirements.txt
```

## Konfigürasyon

`config.yaml` dosyasını düzenleyin:

```yaml
binance:
  api_key: "API_KEY"        # Canlı veri için gerekli
  api_secret: "API_SECRET"

trading:
  mode: paper               # paper veya live
  leverage: 20             # 20x kaldıraç
  entry_percent: 0.5        # %10 pozisyon (0.5% × 20x)
  stop_loss_percent: 1.5    # %1.5
  max_positions: 5         # Max 5 koin
  cooldown_minutes: 15

scanning:
  interval_seconds: 300     # 5 dakika
  min_volume_usdt: 100000   # Min hacim
  timeframe: 1h

risk:
  max_daily_loss_percent: 5.0
  max_consecutive_losses: 3
```

## Çalıştırma

```bash
python main.py --mode paper  # ÖNERİLEN
python main.py --mode live   # Gerçek işlem
```

## Kontroller

- **S** - Manuel tarama
- **P** - Durdur/Devam
- **C** - Tüm pozisyonları kapat
- **Q** - Çıkış

## Emir Stratejisi

### Orderbook Yöntemi

| LONG | Kural |
|------|------|
| **Entry** | En kalın BID +0.3% |
| **SL** | En kalın BID -1.5% |
| **TP1** | En ince ASK (%30 kapat) |
| **TP2** | Orta ASK -0.5% (%30 kapat) |
| **TP3** | En kalın ASK -1.5% (%100 kapat) |

| SHORT | Kural |
|-------|-------|
| **Entry** | En kalın ASK -1.5% |
| **SL** | En kalın ASK +1.5% |
| **TP1** | En ince BID (%30 kapat) |
| **TP2** | Orta BID -0.5% (%30 kapat) |
| **TP3** | En kalın BID -1.5% (%100 kapat) |

### Pozisyon Dağılımı

| Seviye | Kapatan % |
|--------|-----------|
| TP1 | %30 |
| TP2 | %30 |
| TP3 | %100 |

### Kasa Kontrol

- **Kaldıraç:** 20x
- **Her koin:** %10 (0.5% × 20)
- **Max pozisyon:** 5 koin (%50 toplam)

## Güvenlik

1. İlk olarak `mode: paper` ile test edin
2. API key gerekli (canlı veri için)
3. Risk limitlerini ayarlayın
4. `mode: live` öncesi paper modda test yapın