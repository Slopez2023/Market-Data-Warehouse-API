# Dashboard Enhancement: Quick Execution Guide

## Executive Command Summary

Run these in order to fully implement asset data tables:

```bash
# Phase 1: Backend APIs (verify working first)
pytest tests/ -k "asset" -v  # Run asset tests (after creation)

# Phase 2-4: Frontend (after HTML/JS/CSS updated)
# Just refresh the browser - no build required

# Phase 5: Full system test
pytest tests/ -v --cov
```

---

## Phase 1: Backend API Implementation (30-40 min)

### Step 1a: Create Backend Route File

**File: `src/routes/asset_data.py`**

This file will contain 3 new endpoints for:
1. Asset summary (GET /api/v1/assets/{symbol})
2. Candle data (GET /api/v1/assets/{symbol}/candles)
3. Enrichment metrics (GET /api/v1/assets/{symbol}/enrichment)

**Key Implementation Details:**

```python
from fastapi import APIRouter, Query, HTTPException
from src.services.database_service import DatabaseService

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])
db = DatabaseService()

@router.get("/{symbol}")
async def get_asset_summary(symbol: str):
    """Get asset overview with all timeframes"""
    # Query database for symbol data
    # Return: status, last_update, records by timeframe, enrichment status
    # Response: 200 OK with asset data OR 404 if symbol not found

@router.get("/{symbol}/candles")
async def get_asset_candles(
    symbol: str,
    timeframe: str = Query("1h"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get paginated candle data with enrichment status"""
    # Query candles from database
    # Join with enrichment features
    # Return paginated results with timestamps, OHLCV, features
    # Response: 200 OK with candles array + pagination info

@router.get("/{symbol}/enrichment")
async def get_asset_enrichment(
    symbol: str,
    timeframe: str = Query("1h")
):
    """Get enrichment metrics for symbol/timeframe"""
    # Query enrichment logs
    # Calculate metrics (fetch success, compute success, quality)
    # Return: fetch/compute/quality sections with percentages
    # Response: 200 OK with enrichment data
```

**Database Queries Needed:**

The DatabaseService will need these helper methods (if not exists):

1. `get_candles_by_symbol(symbol, timeframe, limit, offset)`
2. `get_enrichment_metrics(symbol, timeframe)`
3. `get_symbol_summary(symbol)`
4. `get_timeframe_counts(symbol)`

Most of these already exist in DatabaseService - just adapt them.

### Step 1b: Register Routes in main.py

```python
from src.routes.asset_data import router as asset_router

app.include_router(asset_router)
```

### Step 1c: Test Backend APIs

```bash
# Test asset summary
curl http://localhost:8000/api/v1/assets/AAPL | jq

# Test candle data
curl 'http://localhost:8000/api/v1/assets/AAPL/candles?timeframe=1h&limit=10' | jq

# Test enrichment metrics
curl 'http://localhost:8000/api/v1/assets/AAPL/enrichment?timeframe=1h' | jq
```

**Expected**: All three endpoints return valid JSON with data

---

## Phase 2: HTML Structure (30-40 min)

### Step 2a: Add Assets Section to index.html

Insert after "Symbol Quality & Status" section (around line 256):

```html
<!-- Assets Section -->
<section class="card">
    <div class="assets-section-header">
        <h2>Asset Data & Enrichment Details</h2>
        <div class="assets-controls">
            <select id="asset-timeframe-filter" class="timeframe-filter" onchange="filterAssetsByTimeframe(this.value)">
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
                onkeyup="searchAssets(this.value)"
            >
        </div>
    </div>

    <div class="assets-list" id="assets-container">
        <div style="text-align: center; padding: 20px; color: var(--text-secondary);">
            Loading assets...
        </div>
    </div>
</section>

<!-- Asset Detail Modal -->
<div id="asset-modal" class="modal" style="display: none;">
    <div class="modal-content">
        <div class="modal-header">
            <h3 id="modal-symbol">AAPL</h3>
            <span class="modal-close" onclick="closeAssetModal()">&times;</span>
        </div>
        <div id="modal-body" style="padding: 20px;"></div>
    </div>
</div>
```

### Step 2b: Asset Card Template

Add a template function in script.js that generates this HTML (see Phase 3):

```html
<div class="asset-card" data-symbol="AAPL">
    <div class="asset-card-header" onclick="toggleAssetExpand(event, 'AAPL')">
        <div class="asset-header-left">
            <span class="asset-symbol">AAPL</span>
            <span class="asset-status-badge healthy">● Healthy</span>
        </div>
        <div class="asset-header-middle">
            <span class="quick-stat">10,524 records</span>
            <span class="quick-stat">99.8% quality</span>
            <span class="quick-stat">0 anomalies</span>
        </div>
        <div class="asset-header-right">
            <span class="expand-toggle">▼</span>
        </div>
    </div>

    <div class="asset-details" style="display: none;">
        <!-- Tab Navigation -->
        <div class="asset-tabs">
            <button class="asset-tab-btn active" onclick="switchAssetTab(event, 'AAPL', 'overview')">Overview</button>
            <button class="asset-tab-btn" onclick="switchAssetTab(event, 'AAPL', 'candles')">Candle Data</button>
            <button class="asset-tab-btn" onclick="switchAssetTab(event, 'AAPL', 'enrichment')">Enrichment</button>
        </div>

        <!-- Overview Tab -->
        <div id="tab-overview-AAPL" class="asset-tab-content active">
            <div class="overview-grid">
                <div class="stat-box">
                    <span class="stat-label">Status</span>
                    <span class="stat-value healthy">Healthy</span>
                </div>
                <div class="stat-box">
                    <span class="stat-label">Last Update</span>
                    <span class="stat-value">2024-11-13 15:30 UTC</span>
                </div>
                <div class="stat-box">
                    <span class="stat-label">Data Age</span>
                    <span class="stat-value">0 minutes</span>
                </div>
                <div class="stat-box">
                    <span class="stat-label">Quality Score</span>
                    <span class="stat-value">0.95 / 1.0</span>
                </div>
            </div>

            <div class="timeframes-section">
                <h4>Records by Timeframe</h4>
                <table class="timeframes-table">
                    <thead>
                        <tr>
                            <th>Timeframe</th>
                            <th>Records</th>
                            <th>Latest</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="tf-tbody-AAPL">
                        <tr><td colspan="4">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Candles Tab -->
        <div id="tab-candles-AAPL" class="asset-tab-content" style="display: none;">
            <div class="candles-controls">
                <span class="candle-count">100 candles loaded</span>
                <button class="btn btn-small" onclick="loadMoreCandles('AAPL')">Load 100 More</button>
            </div>
            <table class="candles-data-table">
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Open</th>
                        <th>High</th>
                        <th>Low</th>
                        <th>Close</th>
                        <th>Volume</th>
                        <th>VWAP</th>
                        <th>Enriched</th>
                    </tr>
                </thead>
                <tbody id="candles-tbody-AAPL">
                    <tr><td colspan="8" style="text-align: center;">Loading...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Enrichment Tab -->
        <div id="tab-enrichment-AAPL" class="asset-tab-content" style="display: none;">
            <div class="enrichment-metrics-grid">
                <div class="enrichment-card">
                    <h4>Fetch Pipeline</h4>
                    <div class="metric">
                        <span class="metric-label">Success Rate</span>
                        <span class="metric-value">99.2%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Avg Response Time</span>
                        <span class="metric-value">245 ms</span>
                    </div>
                </div>
                <div class="enrichment-card">
                    <h4>Compute Pipeline</h4>
                    <div class="metric">
                        <span class="metric-label">Success Rate</span>
                        <span class="metric-value">100%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Avg Time</span>
                        <span class="metric-value">12 ms</span>
                    </div>
                </div>
                <div class="enrichment-card">
                    <h4>Data Quality</h4>
                    <div class="metric">
                        <span class="metric-label">Validation Rate</span>
                        <span class="metric-value">99.8%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Quality Score</span>
                        <span class="metric-value">0.95</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
```

---

## Phase 3: JavaScript Logic (50-60 min)

### Step 3a: Add to script.js

Add these functions to dashboard/script.js:

```javascript
// ============================================================
// ASSET DATA FUNCTIONS
// ============================================================

const assetCache = new Map();

async function loadAssetsList() {
    try {
        // Get symbol list (already have from symbol table)
        const symbolsResponse = await fetch('/api/v1/health');
        const health = await symbolsResponse.json();
        const symbols = health.symbols_in_database || [];

        const container = document.getElementById('assets-container');
        container.innerHTML = '';

        for (const symbol of symbols) {
            const card = await createAssetCard(symbol);
            container.appendChild(card);
        }

        if (symbols.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: var(--text-secondary);">No assets available</p>';
        }
    } catch (error) {
        console.error('Error loading assets:', error);
        document.getElementById('assets-container').innerHTML = 
            '<p style="color: red;">Error loading assets</p>';
    }
}

async function createAssetCard(symbol) {
    const card = document.createElement('div');
    card.className = 'asset-card';
    card.setAttribute('data-symbol', symbol);
    
    try {
        const response = await fetch(`/api/v1/assets/${symbol}`);
        const asset = await response.json();
        
        const status = asset.status || 'unknown';
        const statusClass = getStatusClass(status);
        
        card.innerHTML = `
            <div class="asset-card-header" onclick="toggleAssetExpand(event, '${symbol}')">
                <div class="asset-header-left">
                    <span class="asset-symbol">${symbol}</span>
                    <span class="asset-status-badge ${statusClass}">● ${status}</span>
                </div>
                <div class="asset-header-middle">
                    <span class="quick-stat">${asset.total_records?.toLocaleString() || '--'} records</span>
                    <span class="quick-stat">${asset.quality?.validation_rate?.toFixed(1) || '--'}% quality</span>
                </div>
                <div class="asset-header-right">
                    <span class="expand-toggle">▼</span>
                </div>
            </div>
            <div class="asset-details" style="display: none;" id="details-${symbol}">
                <div class="asset-tabs">
                    <button class="asset-tab-btn active" onclick="switchAssetTab(event, '${symbol}', 'overview')">Overview</button>
                    <button class="asset-tab-btn" onclick="switchAssetTab(event, '${symbol}', 'candles')">Candles</button>
                    <button class="asset-tab-btn" onclick="switchAssetTab(event, '${symbol}', 'enrichment')">Enrichment</button>
                </div>

                <div id="tab-overview-${symbol}" class="asset-tab-content active"></div>
                <div id="tab-candles-${symbol}" class="asset-tab-content" style="display: none;"></div>
                <div id="tab-enrichment-${symbol}" class="asset-tab-content" style="display: none;"></div>
            </div>
        `;
        
        return card;
    } catch (error) {
        console.error(`Error creating card for ${symbol}:`, error);
        card.innerHTML = `<div class="asset-card-header">${symbol} <span style="color: red;">Error loading</span></div>`;
        return card;
    }
}

function toggleAssetExpand(event, symbol) {
    event.stopPropagation();
    const details = document.getElementById(`details-${symbol}`);
    const isVisible = details.style.display !== 'none';
    details.style.display = isVisible ? 'none' : 'block';
    
    if (!isVisible) {
        loadAssetOverview(symbol);
    }
}

async function loadAssetOverview(symbol) {
    try {
        const response = await fetch(`/api/v1/assets/${symbol}`);
        const asset = await response.json();
        
        const overviewTab = document.getElementById(`tab-overview-${symbol}`);
        const statusClass = getStatusClass(asset.status);
        
        overviewTab.innerHTML = `
            <div class="overview-grid">
                <div class="stat-box">
                    <span class="stat-label">Status</span>
                    <span class="stat-value ${statusClass}">${asset.status}</span>
                </div>
                <div class="stat-box">
                    <span class="stat-label">Last Update</span>
                    <span class="stat-value">${formatDateTime(asset.last_update)}</span>
                </div>
                <div class="stat-box">
                    <span class="stat-label">Data Age</span>
                    <span class="stat-value">${asset.data_age_hours} hours</span>
                </div>
                <div class="stat-box">
                    <span class="stat-label">Quality Score</span>
                    <span class="stat-value">${asset.quality?.quality_score?.toFixed(2)}/1.0</span>
                </div>
            </div>

            <div class="timeframes-section">
                <h4>Records by Timeframe</h4>
                <table class="timeframes-table">
                    <thead>
                        <tr>
                            <th>Timeframe</th>
                            <th>Records</th>
                            <th>Latest</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${Object.entries(asset.timeframes || {}).map(([tf, data]) => `
                            <tr>
                                <td>${tf}</td>
                                <td>${data.records?.toLocaleString() || '--'}</td>
                                <td>${formatDateTime(data.latest)}</td>
                                <td><span class="status-badge ${getStatusClass(data.status)}">${data.status}</span></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (error) {
        console.error(`Error loading overview for ${symbol}:`, error);
        document.getElementById(`tab-overview-${symbol}`).innerHTML = 
            '<p style="color: red;">Error loading data</p>';
    }
}

async function loadCandleData(symbol, timeframe = '1h') {
    try {
        const response = await fetch(
            `/api/v1/assets/${symbol}/candles?timeframe=${timeframe}&limit=100`
        );
        const data = await response.json();
        
        const candlesTab = document.getElementById(`tab-candles-${symbol}`);
        candlesTab.innerHTML = `
            <div class="candles-controls">
                <span class="candle-count">${data.pagination?.total?.toLocaleString() || '--'} total candles</span>
                <button class="btn btn-small" onclick="loadMoreCandles('${symbol}')">Load More</button>
            </div>
            <table class="candles-data-table">
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Open</th>
                        <th>High</th>
                        <th>Low</th>
                        <th>Close</th>
                        <th>Volume</th>
                        <th>VWAP</th>
                        <th>Enriched</th>
                    </tr>
                </thead>
                <tbody>
                    ${(data.candles || []).map(candle => `
                        <tr>
                            <td>${formatDateTime(candle.timestamp)}</td>
                            <td>$${candle.open?.toFixed(2)}</td>
                            <td>$${candle.high?.toFixed(2)}</td>
                            <td>$${candle.low?.toFixed(2)}</td>
                            <td>$${candle.close?.toFixed(2)}</td>
                            <td>${candle.volume?.toLocaleString()}</td>
                            <td>$${candle.vwap?.toFixed(2)}</td>
                            <td><span class="badge ${candle.enrichment_status === 'complete' ? 'success' : 'warning'}">${candle.enrichment_status}</span></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error(`Error loading candles for ${symbol}:`, error);
        document.getElementById(`tab-candles-${symbol}`).innerHTML = 
            '<p style="color: red;">Error loading candle data</p>';
    }
}

async function loadEnrichmentMetrics(symbol, timeframe = '1h') {
    try {
        const response = await fetch(
            `/api/v1/assets/${symbol}/enrichment?timeframe=${timeframe}`
        );
        const enrichment = await response.json();
        
        const enrichmentTab = document.getElementById(`tab-enrichment-${symbol}`);
        enrichmentTab.innerHTML = `
            <div class="enrichment-metrics-grid">
                <div class="enrichment-card">
                    <h4>Fetch Pipeline</h4>
                    <div class="metric">
                        <span class="metric-label">Success Rate</span>
                        <span class="metric-value">${enrichment.fetch_metrics?.success_rate?.toFixed(1) || '--'}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Avg Response Time</span>
                        <span class="metric-value">${enrichment.fetch_metrics?.avg_response_time || '--'} ms</span>
                    </div>
                </div>
                <div class="enrichment-card">
                    <h4>Compute Pipeline</h4>
                    <div class="metric">
                        <span class="metric-label">Success Rate</span>
                        <span class="metric-value">${enrichment.compute_metrics?.success_rate?.toFixed(1) || '--'}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Avg Time</span>
                        <span class="metric-value">${enrichment.compute_metrics?.avg_compute_time || '--'} ms</span>
                    </div>
                </div>
                <div class="enrichment-card">
                    <h4>Data Quality</h4>
                    <div class="metric">
                        <span class="metric-label">Validation Rate</span>
                        <span class="metric-value">${enrichment.quality_metrics?.validation_rate?.toFixed(1) || '--'}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Quality Score</span>
                        <span class="metric-value">${enrichment.quality_metrics?.quality_score?.toFixed(2) || '--'}</span>
                    </div>
                </div>
            </div>
        `;
    } catch (error) {
        console.error(`Error loading enrichment for ${symbol}:`, error);
        document.getElementById(`tab-enrichment-${symbol}`).innerHTML = 
            '<p style="color: red;">Error loading enrichment data</p>';
    }
}

function switchAssetTab(event, symbol, tabName) {
    event.stopPropagation();
    
    // Hide all tabs
    document.getElementById(`tab-overview-${symbol}`).style.display = 'none';
    document.getElementById(`tab-candles-${symbol}`).style.display = 'none';
    document.getElementById(`tab-enrichment-${symbol}`).style.display = 'none';
    
    // Remove active class from buttons
    const buttons = document.querySelectorAll(`#details-${symbol} .asset-tab-btn`);
    buttons.forEach(btn => btn.classList.remove('active'));
    
    // Show selected tab
    document.getElementById(`tab-${tabName}-${symbol}`).style.display = 'block';
    event.target.classList.add('active');
    
    // Load data if needed
    if (tabName === 'candles' && !document.getElementById(`tab-candles-${symbol}`).innerHTML.includes('table')) {
        loadCandleData(symbol);
    } else if (tabName === 'enrichment' && !document.getElementById(`tab-enrichment-${symbol}`).innerHTML.includes('card')) {
        loadEnrichmentMetrics(symbol);
    }
}

function searchAssets(query) {
    const cards = document.querySelectorAll('.asset-card');
    cards.forEach(card => {
        const symbol = card.getAttribute('data-symbol');
        const matches = symbol.toUpperCase().includes(query.toUpperCase());
        card.style.display = matches ? 'block' : 'none';
    });
}

function filterAssetsByTimeframe(timeframe) {
    // Re-load candles with selected timeframe when user changes filter
    // This would require tracking which tab is open
    console.log('Filter by timeframe:', timeframe);
}

async function loadMoreCandles(symbol) {
    // Implement pagination
    console.log('Load more candles for:', symbol);
}

// Helper functions
function getStatusClass(status) {
    const statusLower = (status || '').toLowerCase();
    if (statusLower.includes('healthy') || statusLower.includes('complete')) return 'healthy';
    if (statusLower.includes('warning') || statusLower.includes('partial')) return 'warning';
    if (statusLower.includes('stale') || statusLower.includes('failed')) return 'stale';
    return 'neutral';
}

function formatDateTime(timestamp) {
    if (!timestamp) return '--';
    try {
        return new Date(timestamp).toLocaleString();
    } catch {
        return timestamp;
    }
}

function closeAssetModal() {
    document.getElementById('asset-modal').style.display = 'none';
}

// Add to main dashboard load function
async function loadDashboard() {
    // ... existing code ...
    await loadAssetsList();  // Add this line
}
```

### Step 3b: Update Main Dashboard Refresh

In the existing `loadDashboard()` function, add:

```javascript
async function loadDashboard() {
    // ... existing calls ...
    await loadSymbolsTable();
    await loadEnrichmentStatus();
    await loadPipelineMetrics();
    
    // ADD THIS:
    await loadAssetsList();
}
```

---

## Phase 4: CSS Styling (20-30 min)

### Step 4a: Add to dashboard/style.css

Add at the end of the file:

```css
/* ============================================================
   ASSET CARDS STYLING
   ============================================================ */

.assets-section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.assets-section-header h2 {
    margin: 0;
}

.assets-controls {
    display: flex;
    gap: 15px;
    align-items: center;
}

.asset-search {
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 14px;
    background: var(--bg-secondary);
    color: var(--text-primary);
    width: 250px;
}

.asset-search:focus {
    outline: none;
    border-color: var(--primary-color);
}

.timeframe-filter {
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 14px;
    background: var(--bg-secondary);
    color: var(--text-primary);
    cursor: pointer;
}

.timeframe-filter:focus {
    outline: none;
    border-color: var(--primary-color);
}

.assets-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.asset-card {
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
    background: var(--bg-secondary);
    transition: all 0.3s ease;
}

.asset-card:hover {
    border-color: var(--primary-color);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.asset-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    cursor: pointer;
    background: var(--bg-tertiary);
    transition: background 0.2s ease;
}

.asset-card-header:hover {
    background: var(--bg-hover);
}

.asset-header-left {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 150px;
}

.asset-symbol {
    font-weight: 600;
    font-size: 16px;
    color: var(--text-primary);
    min-width: 60px;
}

.asset-status-badge {
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
}

.asset-status-badge.healthy {
    background: rgba(76, 175, 80, 0.2);
    color: #4caf50;
}

.asset-status-badge.warning {
    background: rgba(255, 193, 7, 0.2);
    color: #ffc107;
}

.asset-status-badge.stale {
    background: rgba(244, 67, 54, 0.2);
    color: #f44336;
}

.asset-header-middle {
    display: flex;
    gap: 20px;
    flex: 1;
    justify-content: center;
}

.quick-stat {
    font-size: 13px;
    color: var(--text-secondary);
}

.asset-header-right {
    display: flex;
    justify-content: flex-end;
    min-width: 30px;
}

.expand-toggle {
    font-size: 12px;
    color: var(--text-secondary);
    transition: transform 0.3s ease;
}

.asset-details.expanded .expand-toggle {
    transform: rotate(180deg);
}

.asset-details {
    padding: 16px;
    border-top: 1px solid var(--border-color);
    background: var(--bg-primary);
}

/* Asset Tabs */

.asset-tabs {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 16px;
}

.asset-tab-btn {
    padding: 8px 16px;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.2s ease;
}

.asset-tab-btn:hover {
    color: var(--text-primary);
}

.asset-tab-btn.active {
    color: var(--primary-color);
    border-bottom-color: var(--primary-color);
}

.asset-tab-content {
    display: none;
}

.asset-tab-content.active {
    display: block;
}

/* Overview Tab */

.overview-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
    margin-bottom: 24px;
}

.stat-box {
    padding: 12px;
    background: var(--bg-tertiary);
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.stat-label {
    font-size: 12px;
    color: var(--text-secondary);
    font-weight: 500;
}

.stat-value {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
}

.stat-value.healthy {
    color: #4caf50;
}

.stat-value.warning {
    color: #ffc107;
}

.stat-value.stale {
    color: #f44336;
}

.timeframes-section h4 {
    margin: 0 0 12px 0;
    font-size: 14px;
    color: var(--text-primary);
}

.timeframes-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

.timeframes-table thead {
    background: var(--bg-tertiary);
}

.timeframes-table th,
.timeframes-table td {
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
}

.timeframes-table th {
    font-weight: 600;
    color: var(--text-secondary);
}

.timeframes-table tbody tr:hover {
    background: var(--bg-tertiary);
}

/* Candles Tab */

.candles-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding: 8px 0;
}

.candle-count {
    font-size: 13px;
    color: var(--text-secondary);
}

.candles-data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
}

.candles-data-table thead {
    background: var(--bg-tertiary);
}

.candles-data-table th,
.candles-data-table td {
    padding: 8px 10px;
    text-align: right;
    border-bottom: 1px solid var(--border-color);
}

.candles-data-table th:first-child,
.candles-data-table td:first-child {
    text-align: left;
}

.candles-data-table th {
    font-weight: 600;
    color: var(--text-secondary);
}

.candles-data-table tbody tr:hover {
    background: var(--bg-tertiary);
}

.badge {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 500;
}

.badge.success {
    background: rgba(76, 175, 80, 0.2);
    color: #4caf50;
}

.badge.warning {
    background: rgba(255, 193, 7, 0.2);
    color: #ffc107;
}

/* Enrichment Tab */

.enrichment-metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 16px;
}

.enrichment-card {
    padding: 16px;
    background: var(--bg-tertiary);
    border-radius: 6px;
    border-left: 4px solid var(--primary-color);
}

.enrichment-card h4 {
    margin: 0 0 12px 0;
    font-size: 14px;
    color: var(--text-primary);
}

.metric {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
    border-bottom: 1px solid var(--border-color);
}

.metric:last-child {
    border-bottom: none;
}

.metric-label {
    font-size: 13px;
    color: var(--text-secondary);
}

.metric-value {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}

/* Modal */

.modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.modal-content {
    background: var(--bg-primary);
    border-radius: 8px;
    max-width: 90%;
    max-height: 90%;
    overflow-y: auto;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px;
    border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
    margin: 0;
    color: var(--text-primary);
}

.modal-close {
    font-size: 24px;
    cursor: pointer;
    color: var(--text-secondary);
}

.modal-close:hover {
    color: var(--text-primary);
}

/* Responsive */

@media (max-width: 1024px) {
    .asset-header-middle {
        gap: 10px;
        font-size: 12px;
    }

    .assets-controls {
        flex-direction: column;
        gap: 10px;
    }

    .asset-search,
    .timeframe-filter {
        width: 100%;
    }

    .overview-grid {
        grid-template-columns: repeat(2, 1fr);
    }

    .enrichment-metrics-grid {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 768px) {
    .asset-card-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 8px;
    }

    .asset-header-middle {
        width: 100%;
        justify-content: flex-start;
        font-size: 11px;
        gap: 10px;
    }

    .overview-grid {
        grid-template-columns: 1fr;
    }

    .candles-data-table {
        font-size: 11px;
    }

    .candles-data-table th,
    .candles-data-table td {
        padding: 6px 4px;
    }
}
```

---

## Phase 5: Integration & Testing (20-30 min)

### Step 5a: Test All Endpoints

```bash
# Terminal 1: Start API
python main.py

# Terminal 2: Test APIs
curl http://localhost:8000/api/v1/assets/AAPL | jq
curl 'http://localhost:8000/api/v1/assets/AAPL/candles?timeframe=1h&limit=10' | jq
curl 'http://localhost:8000/api/v1/assets/AAPL/enrichment?timeframe=1h' | jq
```

### Step 5b: Test Frontend

1. Open browser to http://localhost:8000
2. Scroll to "Asset Data & Enrichment Details" section
3. Test:
   - Click on asset card to expand
   - Switch between tabs
   - Verify data loads
   - Search by symbol
   - Filter by timeframe

### Step 5c: Verify No Errors

Check browser console (F12):
- No red errors
- Network requests returning 200 OK
- All tables populated

### Step 5d: Performance Check

- Page load time < 3 seconds
- Asset expansion < 500ms
- Tab switching instant
- Search responds in < 200ms

---

## Summary of Changes

### Backend
- **1 new file**: `src/routes/asset_data.py` (3 endpoints)
- **2 files modified**: `main.py` (add import), database queries (if needed)

### Frontend  
- **3 files modified**:
  - `dashboard/index.html` (+215 lines)
  - `dashboard/script.js` (+310 lines)
  - `dashboard/style.css` (+280 lines)

### Total Implementation
- **~3 hours** of work
- **~1,355 lines** of code
- **Zero breaking changes**
- **Fully optional** - doesn't affect existing features

---

## Quick Commands Reference

```bash
# Backend test
pytest tests/ -v

# Frontend check (just refresh browser)
# No build needed - it's pure HTML/JS/CSS

# Full system test
pytest tests/ -v && python main.py

# Curl test individual endpoints
curl http://localhost:8000/api/v1/assets/AAPL | jq
```

---

## Next: Detailed Implementation

Want me to implement all phases now? Or prefer step-by-step?
