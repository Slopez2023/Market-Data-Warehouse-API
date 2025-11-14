/**
 * Market Data API Dashboard
 * Real-time monitoring and system health
 */

// Configuration - Dynamic API URL
// If served via reverse proxy, API might be on different host/port
// Support query param ?api_base=http://host:port to override
const CONFIG = {
  API_BASE: getAPIBase(),
  REFRESH_INTERVAL: 10000,
  RETRY_DELAY: 5000,
  MAX_RETRIES: 3,
};

/**
 * Determine API base URL with fallback logic
 */
function getAPIBase() {
  // Check URL parameter first (for reverse proxy scenarios)
  const params = new URLSearchParams(window.location.search);
  const customBase = params.get("api_base");
  if (customBase) return customBase;

  // Use current origin if on same host
  return window.location.origin;
}

// State
let state = {
  retries: 0,
  lastUpdate: null,
  symbols: [],
  isLoading: true,
};

// Asset modal state
let currentSymbol = null;
let assetCache = new Map();
const CACHE_TTL = 60000; // 1 minute

// Selection state for bulk operations
let selectedSymbols = new Set();

/**
 * Initialize dashboard on page load
 */
document.addEventListener("DOMContentLoaded", () => {
  console.log("Dashboard initializing...");
  setupSymbolSearch();
  setupCollapsibleSections();
  setupSymbolTableClickHandlers();
  restoreSectionStates();
  refreshDashboard();
  setInterval(refreshDashboard, CONFIG.REFRESH_INTERVAL);

  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.key === "r") {
      e.preventDefault();
      refreshDashboard();
    }
  });
});

/**
 * Toggle collapsible section
 */
function toggleSection(sectionName) {
  const section = document.querySelector(`[data-section="${sectionName}"]`);
  if (section) {
    section.classList.toggle('collapsed');
    // Persist preference in localStorage
    const collapsed = section.classList.contains('collapsed');
    localStorage.setItem(`section-${sectionName}`, collapsed ? 'collapsed' : 'expanded');
  }
}

/**
 * Restore section states from localStorage
 */
function restoreSectionStates() {
  const sections = document.querySelectorAll('.collapsible-section');
  sections.forEach(section => {
    const sectionName = section.getAttribute('data-section');
    const state = localStorage.getItem(`section-${sectionName}`);
    if (state === 'collapsed') {
      section.classList.add('collapsed');
    }
  });
}

/**
 * Main refresh function
 */
async function refreshDashboard() {
  try {
    state.isLoading = true;
    const startTime = performance.now();

    const healthResponse = await fetch(`${CONFIG.API_BASE}/health`);
    if (!healthResponse.ok)
      throw new Error(`Health endpoint returned ${healthResponse.status}`);
    const health = await healthResponse.json();

    const statusResponse = await fetch(`${CONFIG.API_BASE}/api/v1/status`);
    if (!statusResponse.ok)
      throw new Error(`Status endpoint returned ${statusResponse.status}`);
    const status = await statusResponse.json();

    const duration = performance.now() - startTime;

    updateHealth(health, duration);
    updateStatus(status);
    updateDashboard(status);
    updateAlerts(status);
    await updateSymbolGrid(status);

    // Load enrichment data
    await updateEnrichmentData();

    state.retries = 0;
    state.lastUpdate = new Date();
    updateTimestamp();

    console.log(`Dashboard refreshed in ${duration.toFixed(0)}ms`);
  } catch (error) {
    console.error("Dashboard refresh error:", error);
    handleError(error);
  } finally {
    state.isLoading = false;
  }
}

/**
 * Update health display
 */
function updateHealth(health, duration) {
  const isHealthy = health.status === "healthy";
  const statusBadge = document.getElementById("status-badge");
  const apiStatus = document.getElementById("api-status");
  const responseTime = document.getElementById("response-time");

  statusBadge.className = `status-badge ${isHealthy ? "healthy" : "critical"}`;
  statusBadge.textContent = `● ${isHealthy ? "Healthy" : "Unhealthy"}`;

  apiStatus.textContent = isHealthy ? "✓ Online" : "✗ Offline";
  apiStatus.style.color = isHealthy ? "var(--success)" : "var(--danger)";

  responseTime.textContent = `Response: ${duration.toFixed(0)} ms`;
}

/**
 * Update status metrics
 */
function updateStatus(status) {
  const db = status.database || {};

  updateMetric("symbols-count", db.symbols_available || 0, "");
  updateMetric("total-records", formatNumber(db.total_records || 0), "");
  updateMetric(
    "validation-rate",
    `${(db.validation_rate_pct || 0).toFixed(1)}`,
    "%"
  );
  updateMetric("latest-data", formatDate(db.latest_data) || "---", "");
  updateMetric(
    "scheduler-status",
    status.data_quality?.scheduler_status === "running"
      ? "🟢 Running"
      : "⚫ Stopped",
    ""
  );

  if (db.symbols_available) {
    state.symbols = db.symbols_available;
  }
}

/**
 * Update dashboard metrics
 */
function updateDashboard(status) {
  const db = status.database || {};

  const estimatedMB = Math.round(((db.total_records || 0) * 500) / 1024 / 1024);
  updateMetric("db-size", `${estimatedMB} MB`, "");

  updateMetric("data-age", calculateAge(db.latest_data), "");
  updateMetric(
    "gap-count",
    formatNumber(status.data_quality?.records_with_gaps_flagged || 0),
    ""
  );
}

/**
 * Update alerts
 */
function updateAlerts(status) {
  const alertsContainer = document.getElementById("alerts");
  const alerts = [];
  const db = status.database || {};

  if (db.validation_rate_pct !== undefined && db.validation_rate_pct < 95) {
    alerts.push({
      level: "warning",
      message: `Validation rate low: ${db.validation_rate_pct.toFixed(1)}%`,
    });
  }

  if (db.latest_data) {
    const lastUpdate = new Date(db.latest_data);
    if (!isNaN(lastUpdate.getTime())) {
      const hoursOld = (Date.now() - lastUpdate) / (1000 * 60 * 60);
      if (hoursOld > 24) {
        alerts.push({
          level: "critical",
          message: `Data is stale: ${hoursOld.toFixed(1)} hours old`,
        });
      }
    }
  } else {
    alerts.push({
      level: "warning",
      message: "No data timestamp available",
    });
  }

  if (status.data_quality?.scheduler_status !== "running") {
    alerts.push({
      level: "critical",
      message: "Auto-backfill scheduler is not running",
    });
  }

  if (db.total_records === 0) {
    alerts.push({
      level: "critical",
      message: "No records in database",
    });
  }

  alertsContainer.innerHTML =
    alerts.length > 0
      ? alerts
          .map(
            (a) => `
            <div class="alert ${a.level}">
                <span>${a.message}</span>
            </div>
          `
          )
          .join("")
      : "";
}

/**
 * Track table state for sorting
 */
let symbolTableState = {
  allSymbols: [],
  currentSort: { column: "symbol", direction: "asc" },
  currentFilter: { search: "", status: "" },
};

/**
 * Update sort indicator display on headers
 */
function updateSortIndicators() {
  const headers = document.querySelectorAll(".symbol-table th");
  headers.forEach((header) => {
    const column = header
      .getAttribute("onclick")
      ?.match(/sortTable\('([^']+)'\)/)?.[1];
    if (column === symbolTableState.currentSort.column) {
      header.classList.remove("sort-asc", "sort-desc");
      header.classList.add(
        "data-sort",
        `sort-${symbolTableState.currentSort.direction}`
      );
    } else {
      header.classList.remove("sort-asc", "sort-desc", "data-sort");
    }
  });
}

/**
 * Update symbol table with real data
 */
async function updateSymbolGrid(status) {
  const container = document.getElementById("symbol-tbody");

  try {
    const response = await fetch(`${CONFIG.API_BASE}/api/v1/symbols/detailed`);
    if (!response.ok)
      throw new Error(`Failed to fetch symbols (${response.status})`);

    const data = await response.json();
    symbolTableState.allSymbols = data.symbols || [];

    if (symbolTableState.allSymbols.length === 0) {
      container.innerHTML =
        '<tr><td colspan="7" style="text-align: center; color: var(--text-secondary);">No symbols in database</td></tr>';
      updateSymbolCount(0, 0);
      return;
    }

    renderSymbolTable();
  } catch (error) {
    console.warn("Could not load symbols:", error);
    container.innerHTML =
      '<tr><td colspan="7" style="text-align: center; color: var(--text-secondary);">Symbol data unavailable</td></tr>';
  }
}

/**
 * Render filtered and sorted symbol table
 */
function renderSymbolTable() {
  const container = document.getElementById("symbol-tbody");

  // Apply filters
  let filtered = symbolTableState.allSymbols.filter((symbol) => {
    const matchesSearch = symbol.symbol
      .toLowerCase()
      .includes(symbolTableState.currentFilter.search.toLowerCase());
    const matchesStatus =
      !symbolTableState.currentFilter.status ||
      symbol.status === symbolTableState.currentFilter.status;
    return matchesSearch && matchesStatus;
  });

  // Apply sort
  const sortCol = symbolTableState.currentSort.column;
  const sortDir = symbolTableState.currentSort.direction === "asc" ? 1 : -1;

  filtered.sort((a, b) => {
    let aVal = a[sortCol];
    let bVal = b[sortCol];

    // Handle numeric vs string
    if (typeof aVal === "string") {
      return aVal.localeCompare(bVal) * sortDir;
    }
    return (aVal - bVal) * sortDir;
  });

  // Render rows
  const html = filtered
    .map(
      (symbol) => {
        const isSelected = selectedSymbols.has(symbol.symbol);
        return `
    <tr class="${isSelected ? 'selected' : ''}">
      <td style="width: 40px;">
        <input type="checkbox" class="symbol-checkbox" data-symbol="${escapeHtml(symbol.symbol)}" 
               ${isSelected ? 'checked' : ''} onchange="toggleSymbolSelection(this)">
      </td>
      <td><span class="symbol-name">${escapeHtml(symbol.symbol)}</span></td>
      <td>${formatNumber(symbol.records)}</td>
      <td>${symbol.validation_rate.toFixed(1)}%</td>
      <td>${formatDate(symbol.latest_data)}</td>
      <td>${formatAge(symbol.data_age_hours)}</td>
      <td>${formatTimeframes(symbol.timeframes || [])}</td>
      <td>
        <span class="status-badge status-${symbol.status}">
          ${getStatusIcon(symbol.status)} ${capitalizeFirst(symbol.status)}
        </span>
      </td>
    </tr>
  `;
      }
    )
    .join("");

  container.innerHTML =
    html ||
    '<tr><td colspan="8" style="text-align: center; color: var(--text-secondary);">No matching symbols</td></tr>';
  updateSymbolCount(filtered.length, symbolTableState.allSymbols.length);
  updateSortIndicators();
}

/**
 * Sort table by column
 */
function sortTable(column) {
  if (symbolTableState.currentSort.column === column) {
    // Toggle direction if clicking same column
    symbolTableState.currentSort.direction =
      symbolTableState.currentSort.direction === "asc" ? "desc" : "asc";
  } else {
    // New column, default to ascending
    symbolTableState.currentSort.column = column;
    symbolTableState.currentSort.direction = "asc";
  }
  renderSymbolTable();
}

/**
 * Handle search input
 */
function setupSymbolSearch() {
  const searchInput = document.getElementById("symbol-search");
  const statusFilter = document.getElementById("status-filter");

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      symbolTableState.currentFilter.search = e.target.value;
      renderSymbolTable();
    });
  }

  if (statusFilter) {
    statusFilter.addEventListener("change", (e) => {
      symbolTableState.currentFilter.status = e.target.value;
      renderSymbolTable();
    });
  }
}

/**
 * Setup symbol table row click handlers
 */
function setupSymbolTableClickHandlers() {
  document.addEventListener('click', (e) => {
    const row = e.target.closest('#symbol-tbody tr');
    if (row && !row.querySelector('input[type="checkbox"]')) {
      // Get symbol from first column after checkbox column
      const symbolCell = row.querySelector('td:nth-child(2) .symbol-name');
      if (symbolCell) {
        const symbol = symbolCell.textContent;
        openAssetModal(symbol);
      }
    }
  });
}

/**
 * Toggle individual symbol selection
 */
function toggleSymbolSelection(checkbox) {
  const symbol = checkbox.getAttribute('data-symbol');
  const row = checkbox.closest('tr');
  
  if (checkbox.checked) {
    selectedSymbols.add(symbol);
    row.classList.add('selected');
  } else {
    selectedSymbols.delete(symbol);
    row.classList.remove('selected');
  }
  
  updateSelectionToolbar();
  updateSelectAllCheckbox();
}

/**
 * Toggle select all checkboxes
 */
function toggleSelectAll(checkbox) {
  const checkboxes = document.querySelectorAll('.symbol-checkbox');
  checkboxes.forEach(cb => {
    cb.checked = checkbox.checked;
    toggleSymbolSelection(cb);
  });
}

/**
 * Update the "select all" checkbox state based on current selections
 */
function updateSelectAllCheckbox() {
  const selectAll = document.getElementById('select-all-symbols');
  const checkboxes = document.querySelectorAll('.symbol-checkbox');
  const checked = document.querySelectorAll('.symbol-checkbox:checked');
  
  if (selectAll) {
    selectAll.checked = checkboxes.length > 0 && checkboxes.length === checked.length;
    selectAll.indeterminate = checked.length > 0 && checkboxes.length !== checked.length;
  }
}

/**
 * Update toolbar visibility and count
 */
function updateSelectionToolbar() {
  const toolbar = document.getElementById('selection-toolbar');
  const count = document.getElementById('selection-count');
  
  if (selectedSymbols.size > 0) {
    toolbar.style.display = 'flex';
    count.textContent = `${selectedSymbols.size} symbol${selectedSymbols.size !== 1 ? 's' : ''} selected`;
  } else {
    toolbar.style.display = 'none';
  }
}

/**
 * Clear all selections
 */
function clearSelection() {
  selectedSymbols.clear();
  document.querySelectorAll('.symbol-checkbox').forEach(cb => cb.checked = false);
  document.querySelectorAll('.symbol-table tbody tr').forEach(row => row.classList.remove('selected'));
  document.getElementById('select-all-symbols').checked = false;
  updateSelectionToolbar();
}

/**
 * Get selected symbols as array
 */
function getSelectedSymbols() {
  return Array.from(selectedSymbols);
}

/**
 * Update symbol count display
 */
function updateSymbolCount(displayed, total) {
  const el = document.getElementById("symbol-count");
  if (el) {
    el.textContent =
      displayed === total
        ? `Showing ${displayed} symbol${displayed !== 1 ? "s" : ""}`
        : `Showing ${displayed} of ${total} symbols`;
  }
}

/**
 * Get status icon
 */
function getStatusIcon(status) {
  const icons = {
    healthy: "✓",
    warning: "⚠",
    stale: "✗",
  };
  return icons[status] || "?";
}

/**
 * Format age in hours to readable format
 */
function formatAge(hours) {
  if (hours < 1) return "<1h";
  if (hours < 24) return `${Math.round(hours)}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

/**
 * Format timeframes array to readable string
 */
function formatTimeframes(timeframes) {
  if (!timeframes || timeframes.length === 0) {
    return '<span style="color: var(--text-secondary);">--</span>';
  }
  const sorted = ["5m", "15m", "30m", "1h", "4h", "1d", "1w"].filter((tf) =>
    timeframes.includes(tf)
  );
  return sorted.join(", ") || "--";
}

/**
 * HTML escape utility
 */
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Capitalize first letter
 */
function capitalizeFirst(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/**
 * Update metric display
 */
function updateMetric(elementId, value, suffix = "") {
  const el = document.getElementById(elementId);
  if (el) {
    el.textContent = `${value}${suffix}`;
  }
}

/**
 * Format number with commas
 */
function formatNumber(num) {
  return num.toLocaleString("en-US");
}

/**
 * Format date
 */
function formatDate(dateStr) {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return null;
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * Calculate data age
 */
function calculateAge(dateStr) {
  if (!dateStr) return "---";
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return "---";
  const hours = Math.round((Date.now() - date) / (1000 * 60 * 60));

  if (hours < 1) return "<1h";
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

/**
 * Update timestamp
 */
function updateTimestamp() {
  const time = new Date();
  const timeStr = time.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
  document.getElementById(
    "last-update"
  ).textContent = `Last updated: ${timeStr} UTC`;
}

/**
 * Error handler
 */
function handleError(error) {
  const alertsContainer = document.getElementById("alerts");
  const errorMsg = error.message || "Unknown error";

  const willRetry = state.retries < CONFIG.MAX_RETRIES;
  const retryMsg = willRetry
    ? ` (Retrying... ${state.retries + 1}/${CONFIG.MAX_RETRIES})`
    : " (Max retries exceeded)";

  alertsContainer.innerHTML = `
        <div class="alert critical">
            <span>⚠️ API Connection Error: ${errorMsg}${retryMsg}</span>
        </div>
    `;

  if (state.retries >= CONFIG.MAX_RETRIES) {
    document.querySelectorAll(".metric-value").forEach((el) => {
      if (el.id !== "api-status" && el.textContent === "--") {
        el.textContent = "N/A";
      }
    });
  }

  const statusBadge = document.getElementById("status-badge");
  statusBadge.className = "status-badge critical";
  statusBadge.textContent = "● Offline";

  state.retries++;

  if (willRetry) {
    console.log(`Retrying in ${CONFIG.RETRY_DELAY}ms...`);
    setTimeout(refreshDashboard, CONFIG.RETRY_DELAY);
  }
}

/**
 * Open API docs
 */
function viewDocs() {
  window.open(`${CONFIG.API_BASE}/docs`, "_blank");
}

/**
 * View symbol data
 */
function viewSymbolData(symbol) {
  const today = new Date();
  const oneYearAgo = new Date(
    today.getFullYear() - 1,
    today.getMonth(),
    today.getDate()
  );

  const startDate = oneYearAgo.toISOString().split("T")[0];
  const endDate = today.toISOString().split("T")[0];

  const url = `${CONFIG.API_BASE}/api/v1/historical/${symbol}?start=${startDate}&end=${endDate}`;
  window.open(url, "_blank");
}

/**
 * Test health endpoint
 */
async function testHealth() {
  try {
    const response = await fetch(`${CONFIG.API_BASE}/health`);
    if (!response.ok)
      throw new Error(`Health endpoint returned ${response.status}`);
    const data = await response.json();
    alert(
      `✓ Health Check Passed\n\nStatus: ${data.status}\nScheduler: ${
        data.scheduler_running ? "Running" : "Stopped"
      }`
    );
  } catch (error) {
    alert(`✗ Health Check Failed\n\nError: ${error.message}`);
  }
}

/**
 * Update enrichment data from API
 */
async function updateEnrichmentData() {
  try {
    // Fetch all enrichment endpoints in parallel
    const [overview, metrics, health, history] = await Promise.all([
      fetch(`${CONFIG.API_BASE}/api/v1/enrichment/dashboard/overview`)
        .then((r) => r.json())
        .catch(() => null),
      fetch(`${CONFIG.API_BASE}/api/v1/enrichment/dashboard/metrics`)
        .then((r) => r.json())
        .catch(() => null),
      fetch(`${CONFIG.API_BASE}/api/v1/enrichment/dashboard/health`)
        .then((r) => r.json())
        .catch(() => null),
      fetch(`${CONFIG.API_BASE}/api/v1/enrichment/history?limit=10`)
        .then((r) => r.json())
        .catch(() => null),
    ]);

    if (overview) updateEnrichmentStatus(overview);
    if (metrics) updatePipelineMetrics(metrics);
    if (health) updateHealthStatus(health);
    if (history) updateJobQueue(history);
  } catch (error) {
    console.warn("Error loading enrichment data:", error);
  }
}

/**
 * Update enrichment status display
 */
function updateEnrichmentStatus(data) {
  const status =
    data.scheduler_status === "running" ? "🟢 Running" : "⚫ Stopped";
  updateMetricValue("enrichment-scheduler-status", status);
  updateMetricValue("enrichment-last-run", formatDate(data.last_run) || "--");
  updateMetricValue("enrichment-next-run", formatDate(data.next_run) || "--");
  updateMetricValue(
    "enrichment-success-rate",
    (data.success_rate || 0).toFixed(1)
  );
  updateMetricValue(
    "enrichment-symbols-count",
    `${data.symbols_enriched || 0}/${data.total_symbols || 0}`
  );
  updateMetricValue(
    "enrichment-avg-time",
    (data.avg_enrichment_time_seconds || 0).toFixed(1)
  );
}

/**
 * Update pipeline metrics display
 */
function updatePipelineMetrics(data) {
  // Fetch Pipeline
  const fetchPipeline = data.fetch_pipeline || {};
  updateMetricValue(
    "fetch-total",
    formatNumber(fetchPipeline.total_fetches || 0)
  );
  updateMetricValue(
    "fetch-success-rate",
    (fetchPipeline.success_rate || 0).toFixed(1)
  );
  updateMetricValue(
    "fetch-avg-time",
    (fetchPipeline.avg_response_time_ms || 0).toFixed(0)
  );
  updateMetricValue(
    "fetch-records",
    formatNumber(data.last_24h?.records_fetched || 0)
  );

  // Compute Pipeline
  const computePipeline = data.compute_pipeline || {};
  updateMetricValue(
    "compute-total",
    formatNumber(computePipeline.total_computations || 0)
  );
  updateMetricValue(
    "compute-success-rate",
    (computePipeline.success_rate || 0).toFixed(1)
  );
  updateMetricValue(
    "compute-avg-time",
    (computePipeline.avg_time_ms || 0).toFixed(0)
  );
  updateMetricValue(
    "compute-features",
    formatNumber(data.last_24h?.features_computed || 0)
  );

  // Data Quality
  const dataQuality = data.data_quality || {};
  updateMetricValue(
    "quality-validation",
    (dataQuality.validation_rate || 0).toFixed(1)
  );
  updateMetricValue(
    "quality-score",
    (dataQuality.avg_quality_score || 0).toFixed(2)
  );
  updateMetricValue(
    "quality-complete",
    (dataQuality.completeness_rate || 0).toFixed(1)
  );
  updateMetricValue(
    "quality-healthy",
    formatNumber(dataQuality.symbols_healthy || 0)
  );
}

/**
 * Update health status display
 */
function updateHealthStatus(data) {
  const schedulerHealth = getHealthBadge(data.scheduler);
  const databaseHealth = getHealthBadge(data.database);
  const apiHealth = getHealthBadge(data.api_connectivity);

  updateMetricValue("health-scheduler", schedulerHealth);
  updateMetricValue("health-database", databaseHealth);
  updateMetricValue("health-api", apiHealth);
  updateMetricValue(
    "health-failures",
    formatNumber(data.recent_failures_24h || 0)
  );
}

/**
 * Get health status badge
 */
function getHealthBadge(status) {
  const badges = {
    healthy: "🟢 Healthy",
    degraded: "🟡 Degraded",
    critical: "🔴 Critical",
  };
  return badges[status] || "⚪ Unknown";
}

/**
 * Update job queue display
 */
function updateJobQueue(data) {
  const jobs = data.jobs || [];
  const tbody = document.getElementById("job-tbody");

  if (jobs.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">No recent jobs</td></tr>';
    updateMetricValue("job-count", "No jobs recorded");
    return;
  }

  const html = jobs
    .map(
      (job) => `
    <tr>
      <td><span class="job-symbol">${escapeHtml(
        job.symbol || "N/A"
      )}</span></td>
      <td>${job.status || "unknown"}</td>
      <td>${formatDate(job.completion_time) || "--"}</td>
      <td>${formatNumber(job.records_processed || 0)}</td>
      <td>
        <span class="job-success ${job.success ? "success" : "failed"}">
          ${job.success ? "✓" : "✗"}
        </span>
      </td>
    </tr>
  `
    )
    .join("");

  tbody.innerHTML = html;
  updateMetricValue("job-count", `Showing ${jobs.length} recent jobs`);
}

/**
 * Update metric value by ID
 */
function updateMetricValue(elementId, value) {
  const el = document.getElementById(elementId);
  if (el) {
    el.textContent = value;
  }
}

/**
 * Run all tests and display results
 */
async function runAllTests() {
  const container = document.getElementById("test-container");
  const statusEl = document.getElementById("test-status");
  const summaryEl = document.getElementById("test-summary");
  const outputEl = document.getElementById("test-output");

  try {
    // Show container and loading state
    container.style.display = "block";
    statusEl.className = "test-status running";
    statusEl.textContent = "Running tests...";
    summaryEl.textContent = "";
    outputEl.textContent = "Executing tests...";

    // Call test endpoint
    const response = await fetch(`${CONFIG.API_BASE}/api/v1/tests/run`, {
      method: "GET",
      timeout: 130000, // 2+ minutes to allow tests to run
    });

    if (!response.ok) {
      throw new Error(`Test endpoint returned ${response.status}`);
    }

    const data = await response.json();

    // Update status
    statusEl.className = data.success
      ? "test-status success"
      : "test-status error";
    statusEl.textContent = data.success ? "✓ Tests Passed" : "✗ Tests Failed";

    // Update summary
    summaryEl.textContent = data.summary;

    // Update output
    const output = data.output || data.errors || "No output available";
    outputEl.textContent = output;
  } catch (error) {
    container.style.display = "block";
    statusEl.className = "test-status error";
    statusEl.textContent = "✗ Test Execution Error";
    summaryEl.textContent = `Error: ${error.message}`;
    outputEl.textContent = "Failed to run tests. Check API logs for details.";
    }
}

// ============================================================
// ASSET DETAIL MODAL FUNCTIONS
// ============================================================

async function openAssetModal(symbol) {
  currentSymbol = symbol;
  document.getElementById('asset-modal').style.display = 'flex';
  document.getElementById('modal-symbol').textContent = symbol;
  
  // Load overview by default
  await loadAssetOverview(symbol);
}

function closeAssetModal() {
  document.getElementById('asset-modal').style.display = 'none';
  currentSymbol = null;
}

function switchAssetTab(tabName) {
  // Hide all tabs
  document.getElementById('tab-overview').style.display = 'none';
  document.getElementById('tab-candles').style.display = 'none';
  document.getElementById('tab-enrichment').style.display = 'none';
  
  // Remove active class from buttons
  document.querySelectorAll('.asset-tab-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  
  // Show selected tab
  document.getElementById(`tab-${tabName}`).style.display = 'block';
  event.target.classList.add('active');
  
  // Load data if needed
  if (tabName === 'candles') {
    loadCandleData(currentSymbol, '1h');
  } else if (tabName === 'enrichment') {
    loadEnrichmentData(currentSymbol, '1h');
  }
}

async function loadAssetOverview(symbol) {
  try {
    const cacheKey = `asset-${symbol}`;
    const cached = assetCache.get(cacheKey);
    
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      renderOverview(cached.data);
      return;
    }
    
    const response = await fetch(`${CONFIG.API_BASE}/api/v1/assets/${symbol}`);
    if (!response.ok) throw new Error('Failed to load asset data');
    const asset = await response.json();
    
    assetCache.set(cacheKey, { data: asset, timestamp: Date.now() });
    renderOverview(asset);
  } catch (error) {
    console.error('Error loading asset overview:', error);
    document.getElementById('overview-grid').innerHTML = 
      `<p style="color: red;">Error loading asset data: ${error.message}</p>`;
  }
}

function renderOverview(asset) {
  const grid = document.getElementById('overview-grid');
  const statusClass = getStatusClass(asset.status);
  
  grid.innerHTML = `
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
      <span class="stat-value">${asset.data_age_hours || '--'} hours</span>
    </div>
    <div class="stat-box">
      <span class="stat-label">Quality Score</span>
      <span class="stat-value">${(asset.quality?.quality_score * 100).toFixed(1) || '--'}%</span>
    </div>
  `;
  
  // Populate timeframes table
  const tbody = document.getElementById('timeframes-tbody');
  tbody.innerHTML = '';
  
  for (const [tf, data] of Object.entries(asset.timeframes || {})) {
    const statusClass = getStatusClass(data.status);
    tbody.innerHTML += `
      <tr>
        <td><strong>${tf}</strong></td>
        <td>${(data.records || 0).toLocaleString()}</td>
        <td>${formatDateTime(data.latest)}</td>
        <td><span class="status-badge ${statusClass}">${data.status}</span></td>
      </tr>
    `;
  }
}

async function loadCandleData(symbol, timeframe = '1h') {
  try {
    const cacheKey = `candles-${symbol}-${timeframe}`;
    const cached = assetCache.get(cacheKey);
    
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      renderCandles(cached.data);
      return;
    }
    
    const response = await fetch(
      `${CONFIG.API_BASE}/api/v1/assets/${symbol}/candles?timeframe=${timeframe}&limit=100`
    );
    if (!response.ok) throw new Error('Failed to load candles');
    const data = await response.json();
    
    assetCache.set(cacheKey, { data: data, timestamp: Date.now() });
    renderCandles(data);
  } catch (error) {
    console.error('Error loading candles:', error);
    document.getElementById('candles-tbody').innerHTML = 
      `<tr><td colspan="8" style="color: red;">Error loading candles: ${error.message}</td></tr>`;
  }
}

function renderCandles(data) {
  const count = document.getElementById('candle-count');
  count.textContent = `${data.pagination?.total?.toLocaleString() || '--'} total candles`;
  
  const tbody = document.getElementById('candles-tbody');
  tbody.innerHTML = '';
  
  if (!data.candles || data.candles.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-secondary);">No candles available</td></tr>';
    return;
  }
  
  for (const candle of data.candles) {
    const enrichmentClass = candle.enrichment_status === 'complete' ? 'complete' : 'pending';
    tbody.innerHTML += `
      <tr>
        <td>${formatDateTime(candle.timestamp)}</td>
        <td>$${(candle.open || 0).toFixed(2)}</td>
        <td>$${(candle.high || 0).toFixed(2)}</td>
        <td>$${(candle.low || 0).toFixed(2)}</td>
        <td>$${(candle.close || 0).toFixed(2)}</td>
        <td>${(candle.volume || 0).toLocaleString()}</td>
        <td>$${(candle.vwap || 0).toFixed(2)}</td>
        <td><span class="badge ${enrichmentClass}">${candle.enrichment_status || 'pending'}</span></td>
      </tr>
    `;
  }
}

async function loadEnrichmentData(symbol, timeframe = '1h') {
  try {
    const cacheKey = `enrichment-${symbol}-${timeframe}`;
    const cached = assetCache.get(cacheKey);
    
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      renderEnrichment(cached.data);
      return;
    }
    
    const response = await fetch(
      `${CONFIG.API_BASE}/api/v1/assets/${symbol}/enrichment?timeframe=${timeframe}`
    );
    if (!response.ok) throw new Error('Failed to load enrichment data');
    const enrichment = await response.json();
    
    assetCache.set(cacheKey, { data: enrichment, timestamp: Date.now() });
    renderEnrichment(enrichment);
  } catch (error) {
    console.error('Error loading enrichment:', error);
    document.getElementById('enrichment-grid').innerHTML = 
      `<p style="color: red;">Error loading enrichment data: ${error.message}</p>`;
  }
}

function renderEnrichment(enrichment) {
  const grid = document.getElementById('enrichment-grid');
  
  grid.innerHTML = `
    <div class="enrichment-card">
      <h4>Fetch Pipeline</h4>
      <div class="metric">
        <span class="metric-label">Success Rate</span>
        <span class="metric-value">${(enrichment.fetch_metrics?.success_rate || 0).toFixed(1)}%</span>
      </div>
      <div class="metric">
        <span class="metric-label">Avg Response</span>
        <span class="metric-value">${enrichment.fetch_metrics?.avg_response_time || '--'} ms</span>
      </div>
      <div class="metric">
        <span class="metric-label">Total Fetches</span>
        <span class="metric-value">${enrichment.fetch_metrics?.total_fetches || '--'}</span>
      </div>
    </div>

    <div class="enrichment-card">
      <h4>Compute Pipeline</h4>
      <div class="metric">
        <span class="metric-label">Success Rate</span>
        <span class="metric-value">${(enrichment.compute_metrics?.success_rate || 0).toFixed(1)}%</span>
      </div>
      <div class="metric">
        <span class="metric-label">Avg Time</span>
        <span class="metric-value">${enrichment.compute_metrics?.avg_compute_time || '--'} ms</span>
      </div>
      <div class="metric">
        <span class="metric-label">Total Computations</span>
        <span class="metric-value">${enrichment.compute_metrics?.total_computations || '--'}</span>
      </div>
    </div>

    <div class="enrichment-card">
      <h4>Data Quality</h4>
      <div class="metric">
        <span class="metric-label">Validation Rate</span>
        <span class="metric-value">${(enrichment.quality_metrics?.validation_rate || 0).toFixed(1)}%</span>
      </div>
      <div class="metric">
        <span class="metric-label">Quality Score</span>
        <span class="metric-value">${(enrichment.quality_metrics?.quality_score || 0).toFixed(2)}</span>
      </div>
      <div class="metric">
        <span class="metric-label">Missing Features</span>
        <span class="metric-value">${enrichment.quality_metrics?.missing_features || 0}</span>
      </div>
    </div>
  `;
}

function loadMoreCandles(symbol) {
  // This would require pagination tracking
  // For now, just reload with limit
  loadCandleData(symbol, document.getElementById('candle-timeframe').value);
}

function getStatusClass(status) {
  const s = (status || '').toLowerCase();
  if (s.includes('healthy') || s.includes('complete')) return 'healthy';
  if (s.includes('warning') || s.includes('partial')) return 'warning';
  if (s.includes('stale') || s.includes('failed')) return 'stale';
  return 'neutral';
}

function formatDateTime(date) {
  if (!date) return '--';
  try {
    return new Date(date).toLocaleString();
  } catch {
    return date;
  }
}

/**
 * Quick Actions - Manual Backfill
 */
function triggerManualBackfill() {
  // Select all symbols for backfill
  selectedSymbols.clear();
  state.symbols.forEach(s => selectedSymbols.add(s.symbol));
  renderSymbolTable();
  updateSelectionToolbar();
  openBackfillModal();
}

/**
 * Quick Actions - View Admin Panel (placeholder)
 */
function viewAdminPanel() {
  alert('✓ Admin panel controls coming in Phase 2');
}

/**
 * Open backfill modal
 */
function openBackfillModal() {
  if (selectedSymbols.size === 0) {
    alert('Please select at least one symbol');
    return;
  }
  
  const modal = document.getElementById('backfill-modal');
  const displayDiv = document.getElementById('backfill-symbols');
  
  // Populate selected symbols
  displayDiv.innerHTML = Array.from(selectedSymbols)
    .map(s => `<span class="symbol-tag">${escapeHtml(s)}</span>`)
    .join('');
  
  // Set default dates (last 30 days)
  const today = new Date();
  const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
  
  document.getElementById('backfill-end-date').value = today.toISOString().split('T')[0];
  document.getElementById('backfill-start-date').value = thirtyDaysAgo.toISOString().split('T')[0];
  
  modal.style.display = 'flex';
}

/**
 * Close backfill modal
 */
function closeBackfillModal() {
  document.getElementById('backfill-modal').style.display = 'none';
}

/**
 * Submit backfill operation
 */
async function submitBackfill() {
  const symbols = getSelectedSymbols();
  const startDate = document.getElementById('backfill-start-date').value;
  const endDate = document.getElementById('backfill-end-date').value;
  const timeframes = Array.from(document.querySelectorAll('#backfill-timeframes input:checked'))
    .map(el => el.value);
  
  if (!startDate || !endDate || timeframes.length === 0) {
    alert('Please fill in all required fields');
    return;
  }
  
  try {
    console.log('Submitting backfill:', { symbols, startDate, endDate, timeframes });
    
    // Build query string
    const params = new URLSearchParams();
    symbols.forEach(s => params.append('symbols', s));
    params.append('start_date', startDate);
    params.append('end_date', endDate);
    timeframes.forEach(t => params.append('timeframes', t));
    
    const response = await fetch(`${CONFIG.API_BASE}/api/v1/backfill?${params.toString()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    
    alert(`✓ Backfill started for ${symbols.length} symbols\nJob ID: ${result.job_id}`);
    closeBackfillModal();
    clearSelection();
    refreshDashboard();
  } catch (error) {
    console.error('Backfill error:', error);
    alert(`Error starting backfill: ${error.message}`);
  }
}

/**
 * Open enrichment modal
 */
function openEnrichModal() {
  if (selectedSymbols.size === 0) {
    alert('Please select at least one symbol');
    return;
  }
  
  const modal = document.getElementById('enrich-modal');
  const displayDiv = document.getElementById('enrich-symbols');
  
  // Populate selected symbols
  displayDiv.innerHTML = Array.from(selectedSymbols)
    .map(s => `<span class="symbol-tag">${escapeHtml(s)}</span>`)
    .join('');
  
  modal.style.display = 'flex';
}

/**
 * Close enrichment modal
 */
function closeEnrichModal() {
  document.getElementById('enrich-modal').style.display = 'none';
}

/**
 * Submit enrichment operation
 */
async function submitEnrich() {
  const symbols = getSelectedSymbols();
  const timeframe = document.getElementById('enrich-timeframe').value;
  
  try {
    console.log('Submitting enrichment:', { symbols, timeframe });
    
    // Build query string
    const params = new URLSearchParams();
    symbols.forEach(s => params.append('symbols', s));
    params.append('timeframe', timeframe);
    
    const response = await fetch(`${CONFIG.API_BASE}/api/v1/enrich?${params.toString()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    
    alert(`✓ Enrichment started for ${symbols.length} symbols\nJob ID: ${result.job_id}`);
    closeEnrichModal();
    clearSelection();
    refreshDashboard();
  } catch (error) {
    console.error('Enrichment error:', error);
    alert(`Error starting enrichment: ${error.message}`);
  }
}

/**
 * Quick Actions - View API Docs
 */
function viewDocs() {
  window.open('/docs', '_blank');
}

/**
 * Setup collapsible sections (placeholder initialization)
 */
function setupCollapsibleSections() {
  // This is called from DOMContentLoaded
  // The actual toggle is handled by toggleSection()
}
