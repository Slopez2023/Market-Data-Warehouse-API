# Market Data API - Professional Dashboard Implementation Plan

**Status:** Proposal  
**Target Delivery:** Week 5 (Post-Production Deployment)  
**Scope:** Production-grade monitoring dashboard for operational visibility  
**Effort Estimate:** 2-3 days (backend API + frontend)

---

## Executive Summary

A **web-based real-time dashboard** to monitor API health, data quality, and system resources. Designed for operations teams with zero external dependencies (no Grafana, Datadog, etc.).

**Key Features:**
- Real-time metrics refresh (auto-refresh every 5-30 seconds)
- Historical trend charts (last 7/30 days)
- Alert management with threshold notifications
- Data quality heatmap (validation rate per symbol)
- System resource monitoring (disk, memory, CPU)
- Production-ready with minimal overhead

---

## Architecture

### Tech Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Frontend** | HTML5 + CSS3 + Chart.js | Zero dependencies, runs locally |
| **Backend** | FastAPI `/metrics` endpoint | Integrates with existing API |
| **Data Storage** | SQLite (metrics DB) + API queries | No external services |
| **Refresh** | WebSocket or polling (AJAX) | Real-time without overhead |

### File Structure

```
market-data-api/
├── src/
│   ├── dashboard/
│   │   ├── __init__.py
│   │   ├── metrics_collector.py    (collects metrics hourly)
│   │   └── models.py                (metric schemas)
│   └── routes/
│       └── dashboard_routes.py      (API endpoints for dashboard)
├── web/
│   ├── dashboard.html               (main UI)
│   ├── css/
│   │   └── dashboard.css
│   └── js/
│       └── dashboard.js
├── metrics.db                        (SQLite - metrics history)
└── main.py                          (add dashboard routes)
```

---

## Phase 1: Backend Implementation (Day 1-2)

### 1.1 Metrics Collector Service

**File:** `src/dashboard/metrics_collector.py`

```python
from dataclasses import dataclass
from datetime import datetime
import asyncio
import sqlite3

@dataclass
class MetricSnapshot:
    timestamp: datetime
    api_health: bool
    response_time_ms: float
    symbols_count: int
    validation_rate: float
    total_records: int
    disk_usage_percent: float
    memory_usage_percent: float
    cpu_usage_percent: float
    latest_data_timestamp: datetime
    backfill_status: str  # "pending", "running", "success", "failed"

class MetricsCollector:
    """Collects and stores historical metrics."""
    
    async def collect_snapshot(self) -> MetricSnapshot:
        """Gather all metrics in single snapshot."""
        # Query API /health and /status endpoints
        # Check system resources (psutil)
        # Check database state
        # Return composite snapshot
    
    async def store_metric(self, metric: MetricSnapshot):
        """Store in SQLite for historical analysis."""
        # Insert into metrics table
    
    async def start_background_collection(self, interval_seconds: int = 300):
        """Run collector every N seconds."""
        # Background task that runs collection loop
```

**Metrics Table Schema:**
```sql
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    api_healthy BOOLEAN,
    response_time_ms FLOAT,
    symbols_count INTEGER,
    validation_rate FLOAT,
    total_records INTEGER,
    disk_usage_percent FLOAT,
    memory_usage_percent FLOAT,
    cpu_usage_percent FLOAT,
    latest_timestamp DATETIME,
    backfill_status TEXT
);

CREATE INDEX idx_metrics_timestamp ON metrics(timestamp DESC);
```

---

### 1.2 Dashboard API Endpoints

**File:** `src/routes/dashboard_routes.py`

```python
from fastapi import APIRouter
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

@router.get("/metrics/current")
async def get_current_metrics():
    """Latest snapshot."""
    return {
        "timestamp": datetime.utcnow(),
        "api": {"healthy": True, "response_time_ms": 12.5},
        "data": {"symbols": 15, "records": 18373, "validation_rate": 0.997},
        "system": {"disk_usage": 42, "memory_usage": 35, "cpu_usage": 8},
        "backfill": {"status": "success", "last_run": "2025-11-10T02:00:00Z"}
    }

@router.get("/metrics/history")
async def get_metrics_history(hours: int = 24):
    """Historical metrics for charts."""
    # Query last N hours from SQLite
    # Return time-series data
    return {
        "timestamps": [...],
        "api_response_times": [...],
        "validation_rates": [...],
        "disk_usage": [...],
        "memory_usage": [...]
    }

@router.get("/symbol-quality")
async def get_symbol_quality():
    """Quality metrics per symbol."""
    return {
        "symbols": [
            {"symbol": "AAPL", "records": 1200, "validation_rate": 0.996, "gaps": 2},
            {"symbol": "MSFT", "records": 1185, "validation_rate": 0.995, "gaps": 1},
            ...
        ]
    }

@router.get("/alerts")
async def get_alerts():
    """Current and recent alerts."""
    return {
        "active": [
            {"level": "warning", "message": "Disk usage at 75%", "time": "..."},
        ],
        "recent": [...]
    }
```

---

## Phase 2: Frontend Implementation (Day 2-3)

### 2.1 Dashboard HTML Structure

**File:** `web/dashboard.html`

```html
<!DOCTYPE html>
<html>
<head>
    <title>Market Data API - Operations Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="css/dashboard.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3/dist/chart.min.js"></script>
</head>
<body>
    <div class="dashboard">
        <!-- Header -->
        <header>
            <h1>Market Data API - Operations Dashboard</h1>
            <div class="header-controls">
                <span id="last-updated">Last updated: --:-- UTC</span>
                <button id="refresh-btn">Refresh Now</button>
                <span id="status-indicator" class="status-healthy">●</span>
            </div>
        </header>

        <!-- Alerts -->
        <section class="alerts-panel" id="alerts-panel">
            <!-- Alert items injected here -->
        </section>

        <!-- Key Metrics Grid -->
        <section class="metrics-grid">
            <!-- API Health -->
            <div class="metric-card">
                <h3>API Status</h3>
                <div class="metric-value" id="api-health">Checking...</div>
                <div class="metric-detail">Response: <span id="response-time">-- ms</span></div>
            </div>

            <!-- Data Quality -->
            <div class="metric-card">
                <h3>Data Quality</h3>
                <div class="metric-value" id="validation-rate">-- %</div>
                <div class="metric-detail"><span id="symbols-count">--</span> symbols loaded</div>
            </div>

            <!-- Database Size -->
            <div class="metric-card">
                <h3>Database</h3>
                <div class="metric-value" id="total-records">-- K</div>
                <div class="metric-detail">records in <span id="db-size">-- MB</span></div>
            </div>

            <!-- Disk Usage -->
            <div class="metric-card">
                <h3>Disk Usage</h3>
                <div class="metric-value" id="disk-usage">-- %</div>
                <progress id="disk-progress" value="0" max="100"></progress>
            </div>

            <!-- Memory Usage -->
            <div class="metric-card">
                <h3>Memory Usage</h3>
                <div class="metric-value" id="memory-usage">-- %</div>
                <progress id="memory-progress" value="0" max="100"></progress>
            </div>

            <!-- Last Backfill -->
            <div class="metric-card">
                <h3>Latest Data</h3>
                <div class="metric-value" id="latest-timestamp">--</div>
                <div class="metric-detail" id="backfill-status">Status: --</div>
            </div>
        </section>

        <!-- Charts Section -->
        <section class="charts-section">
            <!-- API Response Times -->
            <div class="chart-container">
                <h3>API Response Times (24h)</h3>
                <canvas id="response-time-chart"></canvas>
            </div>

            <!-- Validation Rate Trend -->
            <div class="chart-container">
                <h3>Validation Rate Trend (7d)</h3>
                <canvas id="validation-rate-chart"></canvas>
            </div>

            <!-- Symbol Quality Heatmap -->
            <div class="chart-container full-width">
                <h3>Symbol Data Quality</h3>
                <div id="symbol-quality-table"></div>
            </div>

            <!-- System Resources -->
            <div class="chart-container">
                <h3>System Resources (24h)</h3>
                <canvas id="system-resources-chart"></canvas>
            </div>
        </section>

        <!-- Activity Log -->
        <section class="activity-section">
            <h3>Recent Activity</h3>
            <div id="activity-log" class="activity-log">
                <!-- Populated from API -->
            </div>
        </section>
    </div>

    <script src="js/dashboard.js"></script>
</body>
</html>
```

### 2.2 Dashboard Styling

**File:** `web/css/dashboard.css`

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f1419;
    color: #e0e0e0;
    padding: 20px;
}

.dashboard {
    max-width: 1400px;
    margin: 0 auto;
}

header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 30px;
    padding: 20px;
    background: #1a1f28;
    border-radius: 8px;
    border-left: 4px solid #00d084;
}

header h1 {
    font-size: 24px;
    font-weight: 600;
}

.header-controls {
    display: flex;
    gap: 15px;
    align-items: center;
}

#status-indicator {
    font-size: 20px;
    animation: pulse 2s infinite;
}

.status-healthy { color: #00d084; }
.status-warning { color: #ffa500; }
.status-critical { color: #ff4444; }

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

button {
    padding: 8px 16px;
    background: #00d084;
    color: #0f1419;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 500;
}

button:hover {
    background: #00e896;
}

/* Alerts */
.alerts-panel {
    margin-bottom: 20px;
}

.alert {
    padding: 12px 16px;
    margin-bottom: 10px;
    border-left: 4px solid;
    background: #1a1f28;
    border-radius: 4px;
    display: flex;
    justify-content: space-between;
}

.alert.info { border-color: #00d084; }
.alert.warning { border-color: #ffa500; }
.alert.critical { border-color: #ff4444; }

/* Metrics Grid */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.metric-card {
    background: #1a1f28;
    padding: 20px;
    border-radius: 8px;
    border: 1px solid #2a3038;
}

.metric-card h3 {
    font-size: 12px;
    text-transform: uppercase;
    color: #888;
    margin-bottom: 12px;
    letter-spacing: 0.5px;
}

.metric-value {
    font-size: 32px;
    font-weight: 700;
    color: #00d084;
    margin-bottom: 8px;
}

.metric-detail {
    font-size: 13px;
    color: #888;
}

progress {
    width: 100%;
    height: 6px;
    border: none;
    border-radius: 3px;
    background: #2a3038;
    margin-top: 8px;
}

progress::-webkit-progress-bar {
    background: #2a3038;
}

progress::-webkit-progress-value {
    background: #00d084;
}

/* Charts */
.charts-section {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.chart-container {
    background: #1a1f28;
    padding: 20px;
    border-radius: 8px;
    border: 1px solid #2a3038;
}

.chart-container.full-width {
    grid-column: 1 / -1;
}

.chart-container h3 {
    margin-bottom: 20px;
    font-size: 14px;
    font-weight: 600;
}

/* Symbol Quality Table */
#symbol-quality-table {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
}

.symbol-quality-item {
    background: #0f1419;
    padding: 12px;
    border-radius: 4px;
    border: 1px solid #2a3038;
    text-align: center;
}

.symbol-quality-item .symbol { font-weight: 600; font-size: 14px; }
.symbol-quality-item .quality { color: #00d084; font-size: 12px; margin-top: 4px; }

/* Activity Log */
.activity-section {
    background: #1a1f28;
    padding: 20px;
    border-radius: 8px;
    border: 1px solid #2a3038;
}

.activity-log {
    max-height: 300px;
    overflow-y: auto;
    font-size: 13px;
}

.activity-item {
    padding: 8px 0;
    border-bottom: 1px solid #2a3038;
    color: #aaa;
}

.activity-item .timestamp {
    color: #666;
    font-size: 12px;
}

@media (max-width: 768px) {
    .charts-section {
        grid-template-columns: 1fr;
    }
    
    header {
        flex-direction: column;
        gap: 15px;
        text-align: center;
    }
}
```

### 2.3 Dashboard JavaScript

**File:** `web/js/dashboard.js`

```javascript
class Dashboard {
    constructor() {
        this.refreshInterval = 10000; // 10 seconds
        this.charts = {};
        this.init();
    }

    async init() {
        this.setupCharts();
        await this.refresh();
        this.startAutoRefresh();
    }

    setupCharts() {
        // Response Time Chart
        const rtCtx = document.getElementById('response-time-chart');
        this.charts.responseTime = new Chart(rtCtx, {
            type: 'line',
            data: { labels: [], datasets: [{ label: 'Response Time (ms)', data: [], borderColor: '#00d084' }] },
            options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
        });

        // Validation Rate Chart
        const vrCtx = document.getElementById('validation-rate-chart');
        this.charts.validationRate = new Chart(vrCtx, {
            type: 'line',
            data: { labels: [], datasets: [{ label: 'Validation Rate (%)', data: [], borderColor: '#00d084' }] },
            options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { min: 90, max: 100 } } }
        });
    }

    async refresh() {
        try {
            const [current, history, quality] = await Promise.all([
                fetch('/api/v1/dashboard/metrics/current').then(r => r.json()),
                fetch('/api/v1/dashboard/metrics/history?hours=24').then(r => r.json()),
                fetch('/api/v1/dashboard/symbol-quality').then(r => r.json())
            ]);

            this.updateCurrentMetrics(current);
            this.updateCharts(history);
            this.updateSymbolQuality(quality);
            this.updateLastRefresh();
        } catch (error) {
            console.error('Refresh failed:', error);
            this.setStatus('critical');
        }
    }

    updateCurrentMetrics(data) {
        document.getElementById('api-health').textContent = data.api.healthy ? 'Healthy' : 'Unhealthy';
        document.getElementById('response-time').textContent = data.api.response_time_ms.toFixed(1);
        document.getElementById('validation-rate').textContent = (data.data.validation_rate * 100).toFixed(1) + '%';
        document.getElementById('symbols-count').textContent = data.data.symbols;
        document.getElementById('total-records').textContent = (data.data.records / 1000).toFixed(1);
        document.getElementById('disk-usage').textContent = data.system.disk_usage + '%';
        document.getElementById('memory-usage').textContent = data.system.memory_usage + '%';
        document.getElementById('latest-timestamp').textContent = new Date(data.backfill.last_run).toLocaleDateString();
        
        // Update progress bars
        document.getElementById('disk-progress').value = data.system.disk_usage;
        document.getElementById('memory-progress').value = data.system.memory_usage;

        // Update status
        this.setStatus(this.determineStatus(data));
    }

    updateCharts(history) {
        // Update response time chart
        this.charts.responseTime.data.labels = history.timestamps.map(t => new Date(t).toLocaleTimeString());
        this.charts.responseTime.data.datasets[0].data = history.api_response_times;
        this.charts.responseTime.update('none');

        // Update validation rate chart
        this.charts.validationRate.data.labels = history.timestamps.map(t => new Date(t).toLocaleDateString());
        this.charts.validationRate.data.datasets[0].data = history.validation_rates.map(v => (v * 100).toFixed(1));
        this.charts.validationRate.update('none');
    }

    updateSymbolQuality(data) {
        const container = document.getElementById('symbol-quality-table');
        container.innerHTML = data.symbols.map(s => `
            <div class="symbol-quality-item">
                <div class="symbol">${s.symbol}</div>
                <div class="quality">${(s.validation_rate * 100).toFixed(1)}%</div>
                <div style="font-size: 11px; color: #888;">${s.records} records</div>
            </div>
        `).join('');
    }

    determineStatus(data) {
        if (!data.api.healthy) return 'critical';
        if (data.system.disk_usage > 90) return 'critical';
        if (data.system.memory_usage > 85) return 'warning';
        if (data.data.validation_rate < 0.95) return 'warning';
        return 'healthy';
    }

    setStatus(status) {
        const indicator = document.getElementById('status-indicator');
        indicator.className = `status-${status}`;
    }

    updateLastRefresh() {
        const now = new Date();
        document.getElementById('last-updated').textContent = 
            `Last updated: ${now.toLocaleTimeString()} UTC`;
    }

    startAutoRefresh() {
        document.getElementById('refresh-btn').addEventListener('click', () => this.refresh());
        setInterval(() => this.refresh(), this.refreshInterval);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => new Dashboard());
```

---

## Phase 3: Integration & Deployment (Day 3)

### 3.1 Add Routes to main.py

```python
from src.routes import dashboard_routes
from src.dashboard.metrics_collector import MetricsCollector

# In app lifespan:
async def lifespan(app: FastAPI):
    # Start metrics collector
    metrics_collector = MetricsCollector()
    asyncio.create_task(metrics_collector.start_background_collection(interval_seconds=300))
    
    app.include_router(dashboard_routes.router)
    yield
    
    # Cleanup
```

### 3.2 Serve Static Files

```python
from fastapi.staticfiles import StaticFiles

app.mount("/dashboard", StaticFiles(directory="web", html=True), name="dashboard")
```

### 3.3 Access Dashboard

```
http://localhost:8000/dashboard/dashboard.html
```

---

## Phase 4: Monitoring & Alerts (Optional Enhancement)

### 4.1 Alert Thresholds

```python
ALERT_THRESHOLDS = {
    "disk_usage_high": 80,          # Warn at 80%, critical at 90%
    "memory_usage_high": 75,
    "validation_rate_low": 0.95,
    "api_response_slow": 500,       # ms
    "data_stale": 86400,            # seconds (1 day)
    "backfill_failed": True,
}
```

### 4.2 Email/Webhook Notifications (Future)

```python
async def send_alert(level: str, message: str):
    # Integration points:
    # - Slack webhook
    # - Email via SMTP
    # - PagerDuty API
```

---

## Implementation Checklist

### Backend (Day 1-2)
- [ ] Create `src/dashboard/` module
- [ ] Implement `MetricsCollector` class
- [ ] Create SQLite metrics schema
- [ ] Implement dashboard API endpoints
- [ ] Add background collection task
- [ ] Test metric collection and queries

### Frontend (Day 2-3)
- [ ] Create `web/` directory structure
- [ ] Build HTML dashboard layout
- [ ] Style with professional CSS
- [ ] Implement JavaScript refresh logic
- [ ] Configure Chart.js visualizations
- [ ] Test responsive design

### Integration (Day 3)
- [ ] Add dashboard routes to FastAPI
- [ ] Mount static files
- [ ] Test full dashboard flow
- [ ] Verify data accuracy
- [ ] Performance test under load

### Documentation
- [ ] Update README with dashboard link
- [ ] Add dashboard access instructions
- [ ] Document metrics definitions
- [ ] Create troubleshooting guide

---

## Performance Considerations

| Aspect | Target | Implementation |
|--------|--------|-----------------|
| Page Load | <1s | Lazy-load charts, minify assets |
| Data Refresh | 10s | Lightweight JSON endpoints |
| Memory (Browser) | <50MB | Limit historical data points (1000 max) |
| Database Queries | <50ms | Index metrics table on timestamp |
| CPU (Collection) | <5% | Collect every 5 minutes, not continuously |

---

## Success Criteria

- ✅ Dashboard loads and displays current metrics
- ✅ Auto-refresh works reliably (10s interval)
- ✅ Charts render without lag
- ✅ Symbol quality heatmap shows all 15+ symbols
- ✅ Responsive design works on mobile
- ✅ Zero external dependencies
- ✅ <100ms API response times
- ✅ Memory-efficient with 7-day history

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1 | 1 day | Backend metrics collection API |
| Phase 2 | 1 day | Frontend dashboard UI |
| Phase 3 | 0.5 day | Integration testing |
| **Total** | **2.5 days** | **Production-ready dashboard** |

---

## Future Enhancements

1. **Advanced Analytics**
   - Data quality anomaly detection
   - Backfill performance trends
   - Validation rate predictions

2. **Alert System**
   - Slack integration
   - Email notifications
   - Custom threshold configuration

3. **Export Features**
   - PDF reports
   - CSV metrics export
   - Daily digest emails

4. **Security**
   - API key authentication
   - Role-based access (read-only, admin)
   - Audit logging

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Dashboard overhead slows API | Low | Medium | Run collector every 5min, not continuously |
| Storage bloat (metrics DB) | Low | Low | Auto-cleanup old metrics (>30 days) |
| Stale data displayed | Medium | Low | Show refresh timestamp, auto-refresh every 10s |
| Frontend errors | Medium | Low | Error boundaries, graceful degradation |

---

## Notes

- Dashboard is **optional** but highly recommended for operations visibility
- Can be deployed independently after API is production-stable
- No external services required (entirely self-hosted)
- Metrics retention: 30 days rolling window (auto-cleanup)
- Designed for single-user/team access (not multi-tenant)

---

## Questions for Stakeholders

1. Preferred refresh interval: 10s, 30s, or 1 minute?
2. Should we add email alerts? Slack integration?
3. Any additional metrics to track?
4. Access control needed (password-protected)?
