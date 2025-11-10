# Dashboard Quick Start

## Access

```
http://localhost:8000/dashboard
```

That's it. Dashboard auto-refreshes every 10 seconds.

---

## What You See

**Top 6 Cards:**
- API Status → Green = good, Red = offline
- Symbols Loaded → Count of active symbols
- Total Records → OHLCV candles in database
- Validation Rate → Should be >95%
- Latest Data → Most recent date
- Scheduler → Running = good, Stopped = needs check

**Red Alerts** = Issues that need attention

---

## Customize

### Refresh Speed

Edit `script.js`:
```javascript
REFRESH_INTERVAL: 10000, // Change to 5000 or 30000
```

### Colors

Edit `style.css`:
```css
--primary: #10b981; /* Change to different color */
```

### More Symbols

Edit `script.js`:
```javascript
const defaultSymbols = ['AAPL', 'MSFT', ...]; // Add more
```

---

## If It Shows "Offline"

```bash
# Check if API is running
curl http://localhost:8000/health

# Check containers
docker-compose ps

# Restart API if needed
docker-compose restart api
```

---

## Files

```
dashboard/
├── index.html   ← UI structure
├── style.css    ← Colors & layout
├── script.js    ← Data fetching
└── README.md    ← Full docs
```

---

## That's All

Dashboard runs automatically. No setup needed.
