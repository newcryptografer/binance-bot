# Binance Futures Auto Trading Bot - SPEC

## Proje Özeti

**Proje Adı:** Binance Futures Scalper Bot  
**Dil:** Python 3.12  
**Kullanım:** Binance USDT-M Futures'te sürekli vadeli tüm koinleri tarayarak en karlı 5 koin için otomatik long/short işlem açar, TP ve trailing stoploss ile yönetir.

---

## Özellikler

### 1. Pazar Tarama
- Tüm USDT-M futures aktif koinleri çeker (`futures/exchangeInfo`)
- Her koin için: kapanış, yüksek, düşük, hacim, açık interest verilerini çeker
- Scanning periyodu: her 5 dakikada bir (configurable)

### 2. Karlılık Analizi (Scoring)
Her koin için scoring formülü:
```
RSI = 14 periyod RSI (oversold <30 / overbought >70)
ADR = (Yüksek - Düşük) / Kapanış * 100 (günlük hareket aralığı)
VolScore = Hacim / Ortalama Hacim oranı
Momentum = Son 5 mumun toplam yönü (+=long, -=short)
Trend = 50 EMA vs 200 EMA pozisyonu
OB_Imbalance = (Bid_Volume - Ask_Volume) / (Bid_Volume + Ask_Volume)

Score = (RSI_Uygunluk * 0.20) + (ADR * 0.15) + (VolScore * 0.15) + (Momentum * 0.15) + (Trend * 0.15) + (OB_Imbalance * 0.20)
```
- RSI oversold (<35) = +puan (long için)
- RSI overbought (>65) = +puan (short için)
- OB Imbalance > 0.2 (bid ağırlıklı) = +puan long
- OB Imbalance < -0.2 (ask ağırlıklı) = +puan short

### 3. Sinyal Üretimi
- En yüksek scoreları alan 5 koin seçilir
- Her koin için: LONG veya SHORT sinyali belirlenir
- Entry fiyatı: %1 market emir girişi (configurable)
- Pozisyon büyüklüğü: her koin için eşit (toplam sermaye / 5) * kaldıraç

### 4. Risk Yönetimi
- **Kaldıraç:** 10x (configurable)
- **Entry:** %1 sermaye her koin için
- **Stop Loss:** %2 (configurable)
- **Take Profit:** %3 (configurable)
- **Trailing Stop:** %1.5 (TP'ye ulaşınca %1.5'e çek, breakout protection)
- **Max Açık Pozisyon:** 5 koin (simultaneous)
- **Cooldown:** Her işlem sonrası 15 dakika bekleme

### 5. Emir Yönetimi (VWAP + Orderbook)
- **Entry:** LIMIT emir, orderbook derinliğine göre:
  - Orderbook'tan bid/ask fiyatları çekilir
  - VWAP hesaplanır (son 100 mumun hacim ağırlıklı ortalaması)
  - Destek (long için VWAP altı) / Direnç (short için VWAP üstü) seviyeleri belirlenir
  - Entry: Destek/direnç seviyesinden %0.2 offset ile limit emir
  - Fiyat 30 saniye içinde girmezse market emir ile gir
- **TP:** LIMIT emir, VWAP bazlı:
  - Long: TP = VWAP * 1.03, TP2 = VWAP * 1.05
  - Short: TP = VWAP * 0.97, TP2 = VWAP * 0.95
  - Kısmi: %50 TP1, %50 TP2
- **SL:** STOP-LIMIT emir:
  - Long: SL = Entry * 0.98
  - Short: SL = Entry * 1.02
- **Trailing:** Her mumda VWAP güncellenir, SL VWAP'a göre çekilir
- **Margin:** Cross margin + Hedge mod (her yön için ayrı pozisyon açılabilir)

### 6. Modlar
| Mod | Açıklama | Emir Gönderimi |
|-----|----------|----------------|
| `paper` | Sanal işlem | Sadece log, gerçek emir yok |
| `live` | Gerçek işlem | Gerçek Binance API emirleri |

---

## Konfigürasyon (config.yaml)

```yaml
binance:
  api_key: "API_KEY"      # Paper mod için de doldur (canlı veri için gerekli)
  api_secret: "API_SECRET"

trading:
  mode: paper             # paper = canlı veri + simüle, live = gerçek işlem
  leverage: 10
  entry_percent: 1.0      # %1 sermaye
  stop_loss_percent: 2.0 # %2
  take_profit_percent: 3.0 # %3
  trailing_stop_percent: 1.5
  max_positions: 5
  cooldown_minutes: 15

scanning:
  interval_seconds: 300  # 5 dakika
  min_volume_usdt: 100000 # min hacim filter
  
risk:
  max_daily_loss_percent: 5.0
  max_consecutive_losses: 3
```

---

## Teknik Mimari

```
src/
├── main.py              # Entry point
├── config.py            # Konfigürasyon yönetimi
├── binance_client.py    # Binance API wrapper
├── scanner.py           # Pazar tarama & analiz
├── analyzer.py          #Karlılık scoring
├── signal_generator.py # Trading sinyalleri
├── risk_manager.py     # Risk hesaplamaları
├── order_manager.py    # Emir yönetimi
├── trailing_stop.py    # Trailing stop engine
├── logger.py           # Logging
└── utils.py            # Yardımcı fonksiyonlar
```

---

## Kütüphaneler

- **ccxt** - Binance API (spot & futures)
- **pandas** - Veri analizi
- **numpy** - Sayısal hesaplamalar
- **pyyaml** - Konfigürasyon
- **python-dotenv** - API key yönetimi

---

## Güvenlik Kuralları

1. API key/secret `.env` dosyasında saklanır (gitignore)
2. Testnet modda başlatılır, onay sonrası live geçilir
3. Günlük max kayıp %5'te otomatik durdurma
4. 3 art arda kayıpta cooldown
5. Tüm işlemler loglanır (trades_log.csv)

---

## Çalıştırma

```bash
# Kurulum
pip install -r requirements.txt

# Paper mod (test)
python main.py --mode paper

# Live mod (gerçek)
python main.py --mode live
```

---

## Onay İstenenler

1. ✅ Konfigürasyon değerleri uygun mu? (kaldıraç, %, cooldown)
2. ✅ Scoring formülü mantıklı mı?
3. ✅ Emir türleri doğru mu? (market entry, limit TP, stop-loss)
4. ✅ Trailing stop mekanizması yeterli mi?
5. ✅ Risk kuralları yeterli mi?

---

## Notlar

- Stop-limit yerine stop-market kullanılır (daha güvenilir)
- Futures USDT-M kontratları hedeflenir
- Cross margin + Hedge mod (aynı koin için hem long hem short açılabilir)
- Saat dilimi: UTC (Binance UTC kullanır)