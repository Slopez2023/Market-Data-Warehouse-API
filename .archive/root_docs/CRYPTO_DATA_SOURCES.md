# Crypto Data Sources - Complete Matrix

## 1. OHLCV Data (Intraday + Historical)

### ✅ FREE / FREEMIUM TIER

| Source | Coverage | Free Tier Limits | Historical Depth | Intraday | Notes |
|--------|----------|------------------|------------------|----------|-------|
| **CoinGecko API** | 10,000+ coins | 10-50 calls/min | 4+ years | Daily only | Best value; no auth needed |
| **Binance API** | All spot pairs | 1200 requests/min | 4+ years | 1m/5m/15m/1h+ | Direct exchange data; most liquid |
| **CryptoCompare** | 5000+ coins | 10 calls/min | 7 days history; 1yr w/ paid | 1m candles | Enterprise-grade tick data |
| **Finnhub** | Major coins | Free (limited) | Limited | Daily (premium) | Mixed coverage |
| **Token Metrics API** | 5000+ coins | 100k calls/month | Historical OHLCV | Real-time | AI-enhanced signals included |

### 💰 PAID TIER (Better for Serious Work)

| Source | Cost | Intraday Depth | Historical | Best For |
|--------|------|-----------------|------------|----------|
| **EODHD** | $19.99/mo | All timeframes | 30 years | Backtesting + multi-asset |
| **CryptoCompare PRO** | $99-999/mo | 1min tick data | 12 months | Professional trading |
| **Kaiko** | $500+ /mo | Real-time | Full history | Institutional traders |

---

## 2. NEWS & SENTIMENT (This is where crypto APIs differ from Polygon)

### ✅ FREE / FREEMIUM

| Source | Coverage | Free Limits | Sentiment Score | Notes |
|--------|----------|------------|-----------------|-------|
| **Crypto News API** | 50+ news sources | Limited calls | ✅ Yes | Curated crypto news only |
| **CoinTelegraph RSS** | CoinTelegraph articles | Unlimited | ❌ No | Need text analysis separately |
| **Twitter/X API** | Real-time tweets | v2 free tier | ❌ No | Custom sentiment analysis needed |
| **Reddit API** | r/cryptocurrency, etc | Free | ❌ No | Community sentiment (DIY) |
| **LunarCrush** | 500+ coins | Free tier (limited) | ✅ Yes | Social sentiment + buzz |
| **Santiment** | 1000+ coins | Free tier | ✅ Yes | On-chain + sentiment combo |
| **Glassnode** | Bitcoin/Ethereum | Free endpoints | ⚠️ Limited | On-chain metrics only |

### 💰 PAID TIER

| Source | Cost | Coverage | Sentiment | Best For |
|--------|------|----------|-----------|----------|
| **LunarCrush PRO** | $99/mo | 500+ coins | ✅ Real-time | Social signals + trending |
| **Santiment PRO** | $999/mo | 1000+ coins | ✅ + on-chain | Advanced institutional analysis |
| **Glassnode** | $500+/mo | All major coins | Limited | On-chain intelligence |
| **IntoTheBlock** | $250+/mo | All chains | ✅ + on-chain | Whale tracking + sentiment |

---

## 3. IV (IMPLIED VOLATILITY) FOR CRYPTO

### ❌ Limited/No Official Sources

**Problem:** Crypto options market is immature. Historical IV data is sparse.

### Workarounds:

| Option | Cost | Data Quality | Implementation |
|--------|------|--------------|-----------------|
| **Deribit API** | Free | ✅ Best (crypto options exchange) | Real-time IV from Deribit options |
| **Calculate from Prices** | Free | ⚠️ Historical only | Use GARCH/Garman-Klass on OHLCV |
| **LedgerX** | Premium | ✅ High | If available for your symbols |
| **Bybit/OKX Options** | Free (real-time only) | ⚠️ Current, not historical | Exchange-specific IV indices |

---

## 4. EARNINGS (Crypto Equivalent)

### ❌ Not Applicable

Cryptocurrencies don't have earnings reports. However, use these proxies:

| Metric | Source | Use Case |
|--------|--------|----------|
| **On-chain activity spikes** | Glassnode/Santiment | Event detection (like earnings surprises) |
| **Exchange inflows/outflows** | Glassnode/Santiment | Whale movement (institutional behavior) |
| **Protocol upgrades/milestones** | CoinGecko/Twitter | Hard fork announcements, updates |
| **News sentiment + volume spike** | Crypto News API + Deribit | Catalyst detection |

---

## RECOMMENDED STACK FOR YOUR CRYPTO TRADING

### Tier 1: Baseline (Get Started Now - FREE)
```
1. CoinGecko API
   ✅ OHLCV: Daily data for all 20 crypto assets
   ✅ Market cap, supply, fundamentals
   ❌ Intraday candles (free tier only daily)
   
2. Binance API
   ✅ OHLCV: 1m/5m/15m/1h candles in real-time
   ✅ 4+ years historical depth
   ✅ Exchange volume data
   
3. Crypto News API
   ✅ News + sentiment scores (-1 to +1)
   ✅ 5000+ monthly articles from 50+ sources
   ✅ Historical data back to Dec 2020
   
4. LunarCrush (Free Tier)
   ✅ Social sentiment (Twitter, Discord, Reddit)
   ✅ Top mentions and trending coins
   ⚠️ Limited coins on free tier (upgrade as needed)
```

### Tier 2: Production (LOW-COST UPGRADE)
```
Add ($50-150/month):
- CoinGecko PRO or EODHD ($19/mo)
  → Unlimited API calls, faster updates
  
- LunarCrush PRO ($99/mo)
  → Full coverage, historical sentiment, influencer tracking
  
- Deribit API (Free for real-time options IV)
  → Volatility regime identification
```

### Tier 3: Advanced (Institutional Grade)
```
Add ($500+/month):
- Santiment PRO ($999/mo)
  → Combine on-chain metrics + sentiment + technical
  
- Glassnode ($500+/mo)
  → Network health, whale wallets, exchange flows
```

---

## INTEGRATION STRATEGY FOR YOUR PROJECT

### What to Backfill (Priority Order)

1. **OHLCV (Already Done - Keep Going)**
   ```
   Source: Binance API or CoinGecko
   What: 1m/5m/15m/1h/1d/1w candles for all 20 crypto
   Depth: 2+ years historical
   Cost: FREE
   ```

2. **News + Sentiment (HIGH ROI)**
   ```
   Source: Crypto News API
   What: Daily news articles with sentiment scores
   Depth: Historical from Dec 2020 onwards
   Cost: ~$30-50/month
   Implementation: 1-2 days of work
   ```

3. **Social Sentiment (OPTIONAL BUT USEFUL)**
   ```
   Source: LunarCrush (free tier to test, then $99/mo)
   What: Twitter/social sentiment, trending coins
   Depth: Last 1-2 years (configurable)
   Cost: Free to start, $99/mo full coverage
   ```

4. **On-Chain Metrics (ADVANCED)**
   ```
   Source: Glassnode or Santiment
   What: Exchange flows, whale wallets, tx volume
   Depth: Full history
   Cost: $500+/month
   ROI: High for trend confirmation, but less important than sentiment
   ```

---

## Code Integration Example

### Using Binance for Intraday OHLCV (Better than CoinGecko for your use case)

```python
import ccxt

binance = ccxt.binance({'enableRateLimit': True})

# Get 1h candles for BTC/USDT
symbol = 'BTC/USDT'
timeframe = '1h'

ohlcv = binance.fetch_ohlcv(symbol, timeframe, limit=1000)
# Returns: [[timestamp, open, high, low, close, volume], ...]

# Store in your postgres like:
# INSERT INTO market_data (symbol, timeframe, open, high, low, close, volume, time)
# VALUES ('BTC-USD', '1h', ...)
```

### Using Crypto News API for Sentiment Backfill

```python
import requests

api_key = "YOUR_CRYPTO_NEWS_API_KEY"
url = "https://cryptonews-api.com/api/v1"

# Get BTC news with sentiment
params = {
    'tickers': 'BTC',
    'items': 50,
    'token': api_key
}

response = requests.get(url, params=params)
news = response.json()['data']

# Results include: title, description, sentiment (positive/negative/neutral), source
for article in news:
    print(f"{article['title']}: {article['sentiment']}")
```

### Using LunarCrush for Social Sentiment

```python
import requests

url = "https://api.lunarcrush.com/v2"

# Get sentiment for BTC/ETH
params = {
    'key': 'YOUR_KEY',
    'symbol': 'BTC,ETH',
    'data': 'social'
}

response = requests.get(f"{url}/sentiment", params=params)
sentiment = response.json()

# Results: sentiment_score, influence_score, alt_rank, etc.
```

---

## Cost Comparison Summary

### Baseline Setup (FREE)
- CoinGecko: $0/month (rate-limited)
- Binance: $0/month
- Crypto News API: $0/month (100 calls/month free tier, request more)
- LunarCrush: $0/month (limited coins)
- **Total: $0/month**

### Production Setup (RECOMMENDED)
- EODHD or CoinGecko PRO: $20/month
- Crypto News API: $50/month (better plans)
- LunarCrush: $99/month
- **Total: ~$170/month** ← Far cheaper than for stocks, get 3x the signals

### Institutional Setup (OVERKILL)
- Santiment: $999/month
- Glassnode: $500/month
- LunarCrush: $99/month
- **Total: $1,600+/month** ← Only if you're serious

---

## Action Plan

1. **THIS WEEK:**
   - Set up Binance API (free, 5 min setup)
   - Backfill 1h candles for your 20 crypto assets (1-2 hours of work)
   - Register for free tier: Crypto News API + LunarCrush

2. **NEXT WEEK:**
   - Backfill news + sentiment from Crypto News API (2-3 hours)
   - Build simple sentiment score aggregator
   - Test sentiment vs. price correlation on 2-3 symbols

3. **MONTH 2:**
   - Upgrade to LunarCrush PRO ($99/mo) if sentiment signals are strong
   - Add on-chain metrics (Glassnode or Santiment) if you find value

---

## Key Differences: Crypto vs Stocks (Your Polygon API)

| Data | Stocks (Polygon) | Crypto | Best Approach |
|------|-----------------|--------|---------------|
| **OHLCV** | ✅ Full intraday | ✅ Full intraday (Binance) | Use Binance for crypto |
| **Dividends/Splits** | ✅ Available | ❌ Not applicable | Skip for crypto |
| **News** | ✅ Benzinga | ❌ Polygon (no official source) | Use Crypto News API |
| **Sentiment** | Limited | ✅ Rich (social, on-chain) | Use LunarCrush/Santiment |
| **Earnings** | ✅ Yes | ❌ No equivalent | Use on-chain activity spikes |
| **IV** | ✅ Via options | ⚠️ Limited (Deribit only) | Calculate from OHLCV or Deribit |

---

## Notes

1. **Don't force Polygon for crypto** — It's not their strength. Switch to Binance + CoinGecko.
2. **Sentiment is your edge** — Crypto markets react faster to sentiment than stocks.
3. **On-chain is secondary** — Unless you're building sophisticated whale-tracking strategies.
4. **Test before paying** — Always backtest sentiment correlation on your assets before upgrading.

