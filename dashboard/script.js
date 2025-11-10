/**
 * Market Data API Dashboard
 * Real-time monitoring and system health
 */

// Configuration
const CONFIG = {
    API_BASE: window.location.origin,
    REFRESH_INTERVAL: 10000, // 10 seconds
    RETRY_DELAY: 5000, // 5 seconds
    MAX_RETRIES: 3
};

// State
let state = {
    retries: 0,
    lastUpdate: null,
    symbols: [],
    isLoading: true
};

/**
 * Initialize dashboard on page load
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard initializing...');
    refreshDashboard();
    setInterval(refreshDashboard, CONFIG.REFRESH_INTERVAL);
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'r') {
            e.preventDefault();
            refreshDashboard();
        }
    });
});

/**
 * Main refresh function - fetches all dashboard data
 */
async function refreshDashboard() {
    try {
        state.isLoading = true;
        const startTime = performance.now();

        // Fetch all data in parallel
        const [health, status] = await Promise.all([
            fetchAPI('/health'),
            fetchAPI('/api/v1/status')
        ]).catch(err => {
            console.error('API fetch failed:', err);
            throw err;
        });

        const duration = performance.now() - startTime;

        // Update UI with fresh data
        updateHealth(health, duration);
        updateStatus(status);
        updateDashboard(status);
        updateAlerts(status);

        // Reset retry counter on success
        state.retries = 0;
        state.lastUpdate = new Date();
        updateTimestamp();

        console.log(`Dashboard refreshed in ${duration.toFixed(0)}ms`);
    } catch (error) {
        console.error('Dashboard refresh error:', error);
        handleError(error);
    } finally {
        state.isLoading = false;
    }
}

/**
 * Fetch from API with retry logic
 */
async function fetchAPI(endpoint, retries = 0) {
    try {
        const response = await fetch(`${CONFIG.API_BASE}${endpoint}`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' },
            timeout: 5000
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    } catch (error) {
        if (retries < CONFIG.MAX_RETRIES) {
            await sleep(CONFIG.RETRY_DELAY);
            return fetchAPI(endpoint, retries + 1);
        }
        throw error;
    }
}

/**
 * Update health check display
 */
function updateHealth(health, duration) {
    const isHealthy = health.status === 'healthy';
    const statusBadge = document.getElementById('status-badge');
    const apiStatus = document.getElementById('api-status');
    const responseTime = document.getElementById('response-time');

    // Update status badge
    statusBadge.className = `status-badge ${isHealthy ? 'healthy' : 'critical'}`;
    statusBadge.textContent = `● ${isHealthy ? 'Healthy' : 'Unhealthy'}`;

    // Update API status
    apiStatus.textContent = isHealthy ? '✓ Online' : '✗ Offline';
    apiStatus.style.color = isHealthy ? 'var(--success)' : 'var(--danger)';

    // Update response time
    responseTime.textContent = `Response: ${duration.toFixed(0)} ms`;
}

/**
 * Update status metrics from API
 */
function updateStatus(status) {
    const db = status.database || {};

    // Update metrics
    updateMetric('symbols-count', db.symbols_available || 0, 'symbols');
    updateMetric('total-records', formatNumber(db.total_records || 0), '');
    updateMetric('validation-rate', `${(db.validation_rate_pct || 0).toFixed(1)}`, '%');
    updateMetric('latest-data', formatDate(db.latest_data) || '---', '');
    updateMetric('scheduler-status', status.data_quality?.scheduler_status === 'running' ? '🟢 Running' : '⚫ Stopped', '');

    // Store for symbol grid
    if (db.symbols_available) {
        state.symbols = db.symbols_available;
    }
}

/**
 * Update dashboard with quality metrics
 */
function updateDashboard(status) {
    const db = status.database || {};

    // Update system resources
    updateMetric('db-size', `${Math.round((db.total_records || 0) / 10000)} MB`, '');
    updateMetric('data-age', calculateAge(db.latest_data), '');
    updateMetric('gap-count', formatNumber(status.data_quality?.records_with_gaps_flagged || 0), '');

    // Generate symbol quality grid
    updateSymbolGrid(status);
}

/**
 * Update alerts section based on system state
 */
function updateAlerts(status) {
    const alertsContainer = document.getElementById('alerts');
    const alerts = [];
    const db = status.database || {};

    // Check validation rate
    if (db.validation_rate_pct < 95) {
        alerts.push({
            level: 'warning',
            message: `Validation rate low: ${db.validation_rate_pct.toFixed(1)}%`
        });
    }

    // Check data freshness
    const lastUpdate = new Date(db.latest_data);
    const hoursOld = (Date.now() - lastUpdate) / (1000 * 60 * 60);
    if (hoursOld > 24) {
        alerts.push({
            level: 'critical',
            message: `Data is stale: ${hoursOld.toFixed(1)} hours old`
        });
    }

    // Check scheduler
    if (status.data_quality?.scheduler_status !== 'running') {
        alerts.push({
            level: 'critical',
            message: 'Auto-backfill scheduler is not running'
        });
    }

    // Render alerts
    alertsContainer.innerHTML = alerts.length > 0 
        ? alerts.map(a => `
            <div class="alert ${a.level}">
                <span>${a.message}</span>
            </div>
          `).join('')
        : '';
}

/**
 * Generate symbol quality grid
 */
function updateSymbolGrid(status) {
    const container = document.getElementById('symbol-grid');
    const defaultSymbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX'];

    const html = defaultSymbols.map(symbol => `
        <div class="symbol-item" title="Click to view ${symbol} data">
            <div class="symbol">${symbol}</div>
            <div class="quality">✓ Ready</div>
            <div class="records">View Data</div>
        </div>
    `).join('');

    container.innerHTML = html || '<p style="grid-column: 1/-1; color: var(--text-secondary);">No symbol data available</p>';

    // Add click handlers
    document.querySelectorAll('.symbol-item').forEach(item => {
        item.addEventListener('click', () => {
            const symbol = item.querySelector('.symbol').textContent;
            viewSymbolData(symbol);
        });
    });
}

/**
 * Utility: Update metric display
 */
function updateMetric(elementId, value, suffix = '') {
    const el = document.getElementById(elementId);
    if (el) {
        el.textContent = `${value}${suffix}`;
    }
}

/**
 * Utility: Format number with commas
 */
function formatNumber(num) {
    return num.toLocaleString('en-US');
}

/**
 * Utility: Format date to readable format
 */
function formatDate(dateStr) {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

/**
 * Utility: Calculate how old data is
 */
function calculateAge(dateStr) {
    if (!dateStr) return '---';
    const date = new Date(dateStr);
    const hours = Math.round((Date.now() - date) / (1000 * 60 * 60));
    
    if (hours < 1) return '<1h';
    if (hours < 24) return `${hours}h`;
    return `${Math.floor(hours / 24)}d`;
}

/**
 * Utility: Update last refresh timestamp
 */
function updateTimestamp() {
    const time = new Date();
    const timeStr = time.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    });
    document.getElementById('last-update').textContent = `Last updated: ${timeStr} UTC`;
}

/**
 * Utility: Sleep helper
 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Error handler
 */
function handleError(error) {
    const alertsContainer = document.getElementById('alerts');
    const errorMsg = error.message || 'Unknown error';
    
    // Show error alert
    alertsContainer.innerHTML = `
        <div class="alert critical">
            <span>⚠️ API Connection Error: ${errorMsg}</span>
        </div>
    `;

    // Set all metrics to loading state
    document.querySelectorAll('.metric-value').forEach(el => {
        if (el.id !== 'api-status') {
            el.textContent = '--';
        }
    });

    // Update status badge
    const statusBadge = document.getElementById('status-badge');
    statusBadge.className = 'status-badge critical';
    statusBadge.textContent = '● Offline';

    // Retry indicator
    state.retries++;
    if (state.retries < CONFIG.MAX_RETRIES) {
        console.log(`Retrying in ${CONFIG.RETRY_DELAY / 1000}s... (${state.retries}/${CONFIG.MAX_RETRIES})`);
    }
}

/**
 * Quick action: Open API documentation
 */
function viewDocs() {
    window.open(`${CONFIG.API_BASE}/docs`, '_blank');
}

/**
 * Quick action: View symbol data
 */
function viewSymbolData(symbol) {
    const today = new Date();
    const oneYearAgo = new Date(today.getFullYear() - 1, today.getMonth(), today.getDate());
    
    const startDate = oneYearAgo.toISOString().split('T')[0];
    const endDate = today.toISOString().split('T')[0];
    
    const url = `${CONFIG.API_BASE}/api/v1/historical/${symbol}?start=${startDate}&end=${endDate}`;
    window.open(url, '_blank');
}

/**
 * Quick action: Test health endpoint
 */
async function testHealth() {
    try {
        const response = await fetch(`${CONFIG.API_BASE}/health`);
        const data = await response.json();
        alert(`✓ Health Check Passed\n\nStatus: ${data.status}\nScheduler: ${data.scheduler_running ? 'Running' : 'Stopped'}`);
    } catch (error) {
        alert(`✗ Health Check Failed\n\nError: ${error.message}`);
    }
}
