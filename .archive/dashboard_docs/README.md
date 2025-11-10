# Market Data API Dashboard

A **lightweight, modern, zero-dependency dashboard** for real-time monitoring of the Market Data API.

## Features

✨ **Real-time Metrics**
- API health status and response times
- Symbol availability and record counts
- Validation rate and data quality
- Latest data timestamp
- Scheduler status

📊 **System Overview**
- Database size estimation
- Data freshness (age calculation)
- Gap detection statistics
- Quick symbol quality view

🎯 **Quick Actions**
- Refresh dashboard (or use Ctrl+R)
- View API documentation
- Test health endpoint
- View historical data for any symbol

🚀 **Performance**
- Auto-refresh every 10 seconds
- <100ms API response times
- No external dependencies
- Works entirely client-side
- Mobile responsive

## Architecture

```
dashboard/
├── index.html      # Main UI structure
├── style.css       # Modern styling (CSS Grid, Flexbox)
├── script.js       # Data fetching & updates
└── README.md       # This file
```

### Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Frontend** | HTML5 + CSS3 + Vanilla JS | Zero dependencies, instant load |
| **Styling** | CSS Grid + Flexbox + Custom Properties | Modern, responsive, no frameworks |
| **Data** | Fetch API + JSON | Native, lightweight, no libraries |
| **Serving** | FastAPI StaticFiles | Built into existing API |

## Usage

### Automatic (Recommended)

The dashboard is automatically mounted at startup:

```bash
# Build and run with Docker
docker-compose up

# Access dashboard
http://localhost:8000/dashboard
```

### Manual Access

```bash
# If running locally
python main.py
# Visit: http://localhost:8000/dashboard

# API documentation
http://localhost:8000/docs

# Health check
curl http://localhost:8000/health
```

## What It Shows

### Key Metrics (Top Cards)
- **API Status**: Healthy/Unhealthy indicator with response time
- **Symbols Loaded**: Count of active symbols in database
- **Total Records**: Total OHLCV candles stored
- **Validation Rate**: Percentage of validated records
- **Latest Data**: Most recent date in database
- **Scheduler**: Status of auto-backfill scheduler

### Symbol Quality Section
- Quick grid showing major symbols (AAPL, MSFT, GOOGL, etc.)
- Hover to see quality status
- Click to view historical data

### System Resources
- **Database Size**: Estimated size in MB
- **Data Age**: How old the most recent data is
- **Gap Detection**: Records flagged with gaps

### Quick Actions
- 🔄 Refresh: Update dashboard immediately
- 📖 API Docs: Open Swagger/OpenAPI documentation
- 🏥 Health Check: Test API connectivity

## Dashboard Updates

The dashboard automatically refreshes every **10 seconds** from the API endpoints:

| Endpoint | Used For | Frequency |
|----------|----------|-----------|
| `/health` | API status & scheduler running | Every refresh |
| `/api/v1/status` | Database metrics & quality | Every refresh |

No database queries are made from the dashboard—all data flows through existing API endpoints.

## Alerts

The dashboard displays alerts for:

- ⚠️ **Validation Rate Low**: < 95% (warning)
- 🔴 **Data Stale**: > 24 hours old (critical)
- 🔴 **Scheduler Not Running**: Auto-backfill offline (critical)
- 🔴 **API Unreachable**: Connection failures (critical)

## Performance

| Metric | Target | Actual |
|--------|--------|--------|
| Page Load | <1s | ~500ms |
| API Call | <200ms | 10-50ms |
| Memory | <20MB | ~10MB |
| Network | Minimal | ~5KB per refresh |

## Customization

### Change Refresh Interval

Edit `script.js`:
```javascript
const CONFIG = {
    REFRESH_INTERVAL: 10000, // Change to 5000 (5s) or 30000 (30s)
};
```

### Add More Symbols to Grid

Edit `updateSymbolGrid()` in `script.js`:
```javascript
const defaultSymbols = ['AAPL', 'MSFT', 'GOOGL', ...]; // Add more
```

### Customize Colors

Edit CSS variables in `style.css`:
```css
:root {
    --primary: #10b981;        /* Green accent */
    --bg-dark: #0f172a;        /* Dark background */
    --success: #10b981;        /* Success color */
}
```

## Troubleshooting

### Dashboard Shows "Offline"

1. Check API is running: `curl http://localhost:8000/health`
2. Check network connectivity
3. Verify Docker ports: `docker ps | grep api`
4. Check API logs: `docker-compose logs api`

### Metrics Not Updating

1. Clear browser cache (Ctrl+Shift+Delete)
2. Refresh page (F5 or Ctrl+R)
3. Check browser console (F12) for errors
4. Verify API endpoints: `curl http://localhost:8000/api/v1/status | jq`

### Symbols Show as "Ready" But Data Is Stale

This is expected if backfill hasn't run recently. Check:
- Scheduler status on dashboard
- Logs: `docker-compose logs api | grep backfill`
- Manual backfill: `docker-compose exec api python backfill.py`

## Browser Support

- ✅ Chrome/Edge 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Mobile browsers (iOS Safari, Chrome Android)

## Development

To develop or modify the dashboard:

```bash
# Edit files directly (hot reload not available)
# Changes will appear after page refresh

# To test locally without Docker:
# 1. Start API: python main.py
# 2. Open: http://localhost:8000/dashboard

# To inspect network requests:
# Open browser DevTools (F12) → Network tab
```

## Future Enhancements

Possible additions (keep scope small):

- [ ] Chart.js for validation rate trends
- [ ] WebSocket for real-time updates (if needed)
- [ ] Dark/light theme toggle
- [ ] Export metrics as JSON
- [ ] Email alerts integration

## No External Dependencies

This dashboard intentionally uses **zero external libraries**:

- ❌ No jQuery
- ❌ No React/Vue/Angular
- ❌ No Bootstrap/Tailwind (pure CSS)
- ❌ No npm/webpack build step
- ❌ No API gateway required

Just HTML, CSS, and JavaScript—works immediately in any browser.

## File Sizes

- `index.html`: ~3 KB
- `style.css`: ~8 KB
- `script.js`: ~9 KB
- **Total**: ~20 KB (uncompressed)
- **Gzipped**: ~6 KB

Minimal bandwidth and instant loading.

---

**Last Updated:** November 2025  
**Maintained by:** Market Data API Team
