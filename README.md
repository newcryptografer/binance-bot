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

## Sinyal Analizi Nasıl Yapılır?

### 1. Tarama (Scanner)
- 665+ perpetual koin tarar
- Her koin için 200 mum çeker (1h timeframe)
- Tüm göstergeleri hesaplar

### 2. Göstergeler

| Göstergesi | Kullanım Amacı | Hesaplama |
|------------|-----------------|-----------|
| **RSI (14)** | Aşırı alım/satım | Klasik RSI formülü |
| **EMA 50/200** | Trend yönü | EMA golden/death cross |
| **VWAP** | Ortalama fiyat | (Fiyat × Hacim) / Hacim |
| **ADR** | Günlük hareket | High - Low |
| **Momentum** | Güç | Fiyat değişimi |
| **Volume Ratio** | Hacim yoğunluğu | Şimdi / Ortalama |
| **OB Imbalance** | Al sat dengesi | (BID - ASK) / Toplam |

### 3. Skor Hesaplama

**LONG Skoru (+ yönde):**
| Göstergesi | Koşul | Puan |
|-----------|-------|------|
| RSI | > 55 | +15 |
| | > 50 | +10 |
| | < 30 | -20 |
| EMA | 50>200 & fiyat>50 | +15 |
| | fiyat>200 | -10 |
| VWAP | fiyat < VWAP | +10 |
| OB Imp | > 0.2 (BID ağırlıklı) | +15 |
| ADR | Yüksek | +max 20 |
| Volume | Yüksek | +max 20 |

**SHORT Skoru (- yönde):**
| Göstergesi | Koşul | Puan |
|-----------|-------|------|
| RSI | > 65 | +25 |
| | > 55 | +15 |
| | < 30 | +20 |
| EMA | 50<200 & fiyat<50 | +15 |
| | fiyat<200 | -10 |
| VWAP | fiyat > VWAP | +10 |
| OB Imp | < -0.2 (ASK ağırlıklı) | +15 |

### 4. Sinyal Üretimi

```python
# Skor > 20 = Geçerli sinyal
if LONG > SHORT and LONG > 20:
    Sinyal = LONG
elif SHORT > LONG and SHORT > 20:
    Sinyal = SHORT
```

### 5. Sinyal Verileri

Her sinyal şunları içerir:
- Symbol (örn: BTC/USDT:USDT)
- Direction (LONG/SHORT)
- Score (toplam puan)
- Entry price (giriş fiyatı)
- VWAP seviyesi
- Support/Resistance
- RSI değeri
- Orderbook verileri

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