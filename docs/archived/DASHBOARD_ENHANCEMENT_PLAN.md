# Dashboard Enhancement Plan: Asset Data Tables

## Executive Summary

Add comprehensive asset-specific data visualization to the dashboard with expandable rows, data tables, enrichment metrics, and quality scores for each symbol.

---

## PHASE 1: Backend API Enhancements (30-40 min)

### 1.1 New Endpoints for Asset-Specific Data

Create new route file: `src/routes/asset_data.py`

**Endpoint 1: Get Asset Candle Data**
```
GET /api/v1/assets/{symbol}/candles?timeframe=1h&limit=100&offset=0
Response:
{
  "symbol": "AAPL",
  "timeframe": "1h",
  "total_records": 5420,
  "candles": [
    {
      "id": "uuid",
      "timestamp": "2024-11-13T15:30:00Z",
      "open": 234.50,
      "high": 235.20,
      "low": 233.80,
      "close": 234.95,
      "volume": 2150000,
      "vwap": 234.89,
      "count": 8500,
      "enrichment_status": "complete",  // new field
      "features": {  // enrichment features
        "sma_20": 234.12,
        "rsi": 65.5,
        "macd": 1.23,
        "trend": "bullish"
      }
    }
  ],
  "pagination": {
    "limit": 100,
    "offset": 0,
    "total": 5420
  }
}
```

**Endpoint 2: Get Asset Enrichment Data**
```
GET /api/v1/assets/{symbol}/enrichment?timeframe=1h
Response:
{
  "symbol": "AAPL",
  "timeframe": "1h",
  "enrichment_status": "complete",
  "last_enrichment": "2024-11-13T01:30:00Z",
  "fetch_metrics": {
    "total_fetches": 250,
    "successful": 248,
    "failed": 2,
    "success_rate": 99.2%,
    "avg_response_time": 245
  },
  "compute_metrics": {
    "total_computations": 248,
    "successful": 248,
    "failed": 0,
    "success_rate": 100%,
    "avg_compute_time": 12
  },
  "quality_metrics": {
    "validation_rate": 99.8%,
    "quality_score": 0.95,
    "missing_features": 2,
    "anomalies": 0,
    "gaps": 0
  }
}
```

**Endpoint 3: Get Asset Summary**
```
GET /api/v1/assets/{symbol}
Response:
{
  "symbol": "AAPL",
  "asset_type": "equity",
  "status": "healthy",
  "last_update": "2024-11-13T15:30:00Z",
  "data_age_hours": 0,
  "total_records": 54200,
  "timeframes": {
    "1m": { "records": 5420, "latest": "2024-11-13T15:30:00Z", "status": "healthy" },
    "5m": { "records": 1084, "latest": "2024-11-13T15:30:00Z", "status": "healthy" },
    "15m": { "records": 361, "latest": "2024-11-13T15:30:00Z", "status": "healthy" },
    "1h": { "records": 5420, "latest": "2024-11-13T15:30:00Z", "status": "healthy" },
    "1d": { "records": 50, "latest": "2024-11-13T00:00:00Z", "status": "healthy" }
  },
  "enrichment": {
    "status": "complete",
    "success_rate": 99.2%,
    "last_run": "2024-11-13T01:30:00Z"
  },
  "quality": {
    "validation_rate": 99.8%,
    "quality_score": 0.95,
    "health": "excellent"
  }
}
```

### 1.2 Backend Implementation

**File: `src/routes/asset_data.py`**
- 3 new async route handlers
- Database queries for candle/enrichment data
- Pagination support (limit, offset)
- Filtering by timeframe
- 40-50 lines total per handler = ~150 lines

**Database Queries**
- Query candles with enrichment features (LEFT JOIN)
- Aggregate enrichment metrics per symbol/timeframe
- Get latest timestamp per timeframe
- Calculate quality scores

---

## PHASE 2: Frontend Dashboard Structure (40-50 min)

### 2.1 Dashboard HTML Layout

**New Structure in `dashboard/index.html`:**

```html
<!-- Assets Section (after Symbol Quality & Status) -->
<section class="card">
    <div class="assets-section-header">
        <h2>Asset Data & Enrichment</h2>
        <div class="assets-controls">
            <select id="asset-timeframe-filter" class="timeframe-filter">
                <option value="1m">1 Minute</option>
                <option value="5m">5 Minutes</option>
                <option value="15m">15 Minutes</option>
                <option value="1h" selected>1 Hour</option>
                <option value="1d">Daily</option>
            </select>
            <input 
                type="text" 
                id="asset-search" 
                class="asset-search" 
                placeholder="Search assets..."
            >
        </div>
    </div>

    <!-- Assets List with Expandable Rows -->
    <div class="assets-list">
        <div id="assets-container">
            <!-- Dynamic content loaded here -->
        </div>
    </div>
</section>

<!-- Modal for detailed asset view -->
<div id="asset-detail-modal" class="modal" style="display: none;">
    <div class="modal-content">
        <span class="close" onclick="closeAssetModal()">&times;</span>
        <div id="modal-body"></div>
    </div>
</div>
```

### 2.2 Asset Card Component

Each asset will have:
```html
<div class="asset-card">
    <div class="asset-card-header" onclick="toggleAssetDetails(symbol)">
        <div class="asset-info">
            <span class="asset-symbol">AAPL</span>
            <span class="asset-status healthy">● Healthy</span>
        </div>
        <div class="asset-quick-stats">
            <span>5,420 records</span>
            <span>99.8% quality</span>
            <span>0 anomalies</span>
        </div>
        <span class="expand-icon">▼</span>
    </div>

    <div class="asset-card-details" style="display: none;">
        <!-- Three tabs: Overview, Candles, Enrichment -->
        <div class="asset-tabs">
            <button class="tab-btn active" onclick="switchTab(symbol, 'overview')">
                Overview
            </button>
            <button class="tab-btn" onclick="switchTab(symbol, 'candles')">
                Candle Data (100 recent)
            </button>
            <button class="tab-btn" onclick="switchTab(symbol, 'enrichment')">
                Enrichment Metrics
            </button>
        </div>

        <!-- Tab 1: Overview -->
        <div id="tab-overview-{symbol}" class="tab-content active">
            <div class="overview-grid">
                <div class="overview-item">
                    <label>Status</label>
                    <span id="overview-status-{symbol}">--</span>
                </div>
                <div class="overview-item">
                    <label>Last Update</label>
                    <span id="overview-lastupdate-{symbol}">--</span>
                </div>
                <div class="overview-item">
                    <label>Data Age</label>
                    <span id="overview-dataage-{symbol}">--</span>
                </div>
                <div class="overview-item">
                    <label>Quality Score</label>
                    <span id="overview-quality-{symbol}">--</span>
                </div>
            </div>
            <div class="timeframes-overview">
                <h4>Records by Timeframe</h4>
                <table id="timeframes-table-{symbol}" class="timeframes-table">
                    <thead>
                        <tr>
                            <th>Timeframe</th>
                            <th>Records</th>
                            <th>Latest</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="timeframes-tbody-{symbol}"></tbody>
                </table>
            </div>
        </div>

        <!-- Tab 2: Candle Data -->
        <div id="tab-candles-{symbol}" class="tab-content">
            <div class="candles-controls">
                <button onclick="loadMoreCandles(symbol)" class="btn btn-small">Load More</button>
                <span id="candles-count-{symbol}" class="record-count">Loading...</span>
            </div>
            <table id="candles-table-{symbol}" class="data-table">
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Open</th>
                        <th>High</th>
                        <th>Low</th>
                        <th>Close</th>
                        <th>Volume</th>
                        <th>VWAP</th>
                        <th>Enrichment</th>
                    </tr>
                </thead>
                <tbody id="candles-tbody-{symbol}">
                    <tr><td colspan="8" style="text-align: center;">Loading...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Tab 3: Enrichment Metrics -->
        <div id="tab-enrichment-{symbol}" class="tab-content">
            <div class="enrichment-detail-grid">
                <div class="enrichment-section">
                    <h4>Fetch Pipeline</h4>
                    <div class="metric-pair">
                        <span>Success Rate</span>
                        <span id="enrichment-fetch-success-{symbol}">--%</span>
                    </div>
                    <div class="metric-pair">
                        <span>Avg Response</span>
                        <span id="enrichment-fetch-time-{symbol}">-- ms</span>
                    </div>
                </div>
                <div class="enrichment-section">
                    <h4>Compute Pipeline</h4>
                    <div class="metric-pair">
                        <span>Success Rate</span>
                        <span id="enrichment-compute-success-{symbol}">--%</span>
                    </div>
                    <div class="metric-pair">
                        <span>Avg Time</span>
                        <span id="enrichment-compute-time-{symbol}">-- ms</span>
                    </div>
                </div>
                <div class="enrichment-section">
                    <h4>Data Quality</h4>
                    <div class="metric-pair">
                        <span>Validation Rate</span>
                        <span id="enrichment-quality-validation-{symbol}">--%</span>
                    </div>
                    <div class="metric-pair">
                        <span>Quality Score</span>
                        <span id="enrichment-quality-score-{symbol}">--</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
```

### 2.3 HTML Changes Summary

- Add assets section after symbol quality table: ~80 lines
- Add modal for detailed view: ~15 lines
- Add tab structure and tables: ~120 lines
- **Total HTML additions: ~215 lines**

---

## PHASE 3: Frontend JavaScript Logic (50-60 min)

### 3.1 Core Functions in `dashboard/script.js`

**1. Load Assets List**
```javascript
async function loadAssetsList() {
  // Fetch list of all symbols
  // Render asset cards with quick stats
  // Group by status (healthy/warning/stale)
  // Implement search and filtering
}
```

**2. Toggle Asset Details**
```javascript
function toggleAssetDetails(symbol) {
  // Toggle visibility of asset card details
  // Load detailed data on first toggle
  // Cache data to avoid repeated API calls
}
```

**3. Load Candle Data**
```javascript
async function loadCandleData(symbol, timeframe = '1h', limit = 100, offset = 0) {
  // Fetch candles from /api/v1/assets/{symbol}/candles
  // Format timestamps and prices
  // Highlight enrichment status
  // Populate table
  // Handle pagination
}
```

**4. Load Enrichment Metrics**
```javascript
async function loadEnrichmentMetrics(symbol, timeframe = '1h') {
  // Fetch enrichment data from /api/v1/assets/{symbol}/enrichment
  // Populate fetch/compute/quality sections
  // Show success rates and averages
}
```

**5. Tab Switching**
```javascript
function switchTab(symbol, tabName) {
  // Show selected tab content
  // Hide other tabs
  // Load data if not already loaded
  // Add active state styling
}
```

**6. Search & Filter**
```javascript
function filterAssets(searchTerm, timeframe) {
  // Filter displayed assets by search
  // Re-filter on selection change
  // Update visible cards
}
```

**7. Pagination**
```javascript
async function loadMoreCandles(symbol) {
  // Increment offset
  // Fetch next batch
  // Append to existing table
  // Update count display
}
```

### 3.2 JavaScript Changes Summary

- Asset list loader: ~60 lines
- Toggle/expand logic: ~30 lines
- Candle data loader: ~50 lines
- Enrichment loader: ~40 lines
- Tab switching: ~25 lines
- Search/filter: ~35 lines
- Pagination: ~30 lines
- Utility functions: ~40 lines
- **Total JavaScript additions: ~310 lines**

---

## PHASE 4: CSS Styling (20-30 min)

### 4.1 New CSS Classes in `dashboard/style.css`

```css
/* Assets Section */
.assets-section-header { }
.assets-controls { }
.asset-search { }
.timeframe-filter { }

/* Asset Cards */
.assets-list { }
.asset-card { }
.asset-card-header { }
.asset-card-header:hover { }
.asset-info { }
.asset-symbol { }
.asset-status { }
.asset-quick-stats { }
.expand-icon { }
.asset-card-details { }

/* Tabs */
.asset-tabs { }
.tab-btn { }
.tab-btn.active { }
.tab-content { }
.tab-content.active { }

/* Tables */
.data-table { }
.data-table thead { }
.data-table tbody tr { }
.data-table tbody tr:hover { }
.data-table td { }
.timeframes-table { }

/* Overview Grid */
.overview-grid { }
.overview-item { }
.timeframes-overview { }

/* Enrichment Detail */
.enrichment-detail-grid { }
.enrichment-section { }
.metric-pair { }

/* Controls */
.candles-controls { }
.record-count { }

/* Modal */
.modal { }
.modal-content { }
.close { }

/* Responsive */
@media (max-width: 768px) { }
```

### 4.2 CSS Changes Summary

- Asset card styling: ~100 lines
- Tab styling: ~50 lines
- Table styling: ~50 lines
- Modal styling: ~40 lines
- Responsive design: ~40 lines
- **Total CSS additions: ~280 lines**

---

## PHASE 5: Integration & Refinement (20-30 min)

### 5.1 Update Main Dashboard Load

Modify `loadDashboard()` in `script.js`:
```javascript
async function loadDashboard() {
  // Existing calls...
  await loadSymbolsTable();
  await loadEnrichmentStatus();
  
  // New calls
  await loadAssetsList();  // NEW
  
  // Existing...
}
```

### 5.2 Auto-Refresh

Add assets to the auto-refresh cycle:
```javascript
setInterval(() => {
  refreshDashboard(); // Already refreshes all sections
}, 30000); // Every 30 seconds
```

### 5.3 Error Handling

- Add try-catch to all API calls
- Show user-friendly error messages
- Log to console for debugging
- Graceful fallback UI

### 5.4 Caching Strategy

```javascript
const assetCache = new Map();

async function getCachedAssetData(symbol, timeframe) {
  const key = `${symbol}-${timeframe}`;
  if (assetCache.has(key)) {
    const cached = assetCache.get(key);
    if (Date.now() - cached.timestamp < 60000) { // 1 min cache
      return cached.data;
    }
  }
  
  const data = await fetchAssetData(symbol, timeframe);
  assetCache.set(key, { data, timestamp: Date.now() });
  return data;
}
```

---

## Implementation Timeline

| Phase | Component | Time | Lines |
|-------|-----------|------|-------|
| 1 | Backend API (3 endpoints) | 30-40 min | ~450 |
| 2 | HTML Structure | 30-40 min | ~215 |
| 3 | JavaScript Logic | 50-60 min | ~310 |
| 4 | CSS Styling | 20-30 min | ~280 |
| 5 | Integration & Testing | 20-30 min | ~100 |
| **TOTAL** | | **2.5-3.5 hours** | **~1,355 lines** |

---

## File Changes Summary

### New Files
- `src/routes/asset_data.py` (450 lines)
- `DASHBOARD_ENHANCEMENT_PLAN.md` (this file)

### Modified Files
- `dashboard/index.html` (+215 lines)
- `dashboard/script.js` (+310 lines)
- `dashboard/style.css` (+280 lines)
- `main.py` (add route import, ~5 lines)

---

## Features Included

### For Each Asset:

✅ Quick Stats Card
- Symbol name & status badge
- Record count & quality score
- Anomaly count

✅ Overview Tab
- Current status & last update
- Data age
- Quality score
- Breakdown by timeframe (records, latest, status)

✅ Candle Data Tab
- 100 most recent candles
- Open, High, Low, Close, Volume, VWAP
- Count field (number of trades)
- Enrichment status badge
- Pagination (load more)

✅ Enrichment Metrics Tab
- Fetch pipeline: success rate, avg response time
- Compute pipeline: success rate, avg time
- Data quality: validation rate, quality score
- Anomaly detection: gaps, outliers, staleness

✅ Search & Filter
- Search by symbol
- Filter by timeframe
- Real-time updates

---

## API Integration Points

| Endpoint | Purpose | Implementation |
|----------|---------|-----------------|
| `GET /api/v1/assets/{symbol}` | Asset summary | Phase 1 |
| `GET /api/v1/assets/{symbol}/candles` | Candle data with pagination | Phase 1 |
| `GET /api/v1/assets/{symbol}/enrichment` | Enrichment metrics | Phase 1 |
| `GET /api/v1/enrichment/dashboard/overview` | Existing (already implemented) | Existing |
| `GET /api/v1/enrichment/dashboard/metrics` | Existing (already implemented) | Existing |

---

## Recommended Execution Order

1. **Backend First** (Phase 1) - Get APIs working, test with curl
2. **HTML Structure** (Phase 2) - Prepare layout
3. **JavaScript** (Phase 3) - Implement interactivity
4. **CSS** (Phase 4) - Polish styling
5. **Integration** (Phase 5) - Connect everything, test

---

## Testing Checklist

- [ ] Backend APIs return correct data
- [ ] Asset cards load without errors
- [ ] Tab switching works smoothly
- [ ] Candle pagination functions
- [ ] Search filters results
- [ ] Enrichment data displays correctly
- [ ] Responsive on mobile/tablet
- [ ] Auto-refresh updates all sections
- [ ] Error handling shows messages
- [ ] No console errors

---

## Performance Considerations

- **Pagination**: Load 100 candles per request (not all)
- **Caching**: Client-side cache for 1 minute
- **Lazy Loading**: Load enrichment details only when tab clicked
- **Debouncing**: Search has 300ms debounce
- **Auto-refresh**: 30-second interval (adjustable)

---

## Future Enhancements

1. Export candle data to CSV
2. Chart visualization (candlestick charts)
3. Anomaly detail modal
4. Feature impact analysis
5. Backfill history per symbol
6. Quality score trend chart
7. Alert subscriptions per asset
8. Custom timeframe selection
