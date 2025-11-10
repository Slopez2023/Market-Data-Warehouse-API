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

/**
 * Initialize dashboard on page load
 */
document.addEventListener("DOMContentLoaded", () => {
  console.log("Dashboard initializing...");
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
 * Update symbol grid
 */
async function updateSymbolGrid(status) {
  const container = document.getElementById("symbol-grid");

  try {
    const symbolCount = status.database?.symbols_available || 0;

    if (symbolCount === 0) {
      container.innerHTML =
        '<p style="grid-column: 1/-1; color: var(--text-secondary);">No symbols in database</p>';
      return;
    }

    const displayCount = Math.min(symbolCount, 12);
    const symbols = [];

    for (let i = 1; i <= displayCount; i++) {
      symbols.push(`Symbol ${i}`);
    }

    const html = symbols
      .map(
        (symbol, idx) => `
        <div class="symbol-item" title="Click to view data">
            <div class="symbol">#${idx + 1}</div>
            <div class="quality">✓ Ready</div>
            <div class="records">${idx === 0 ? "1 of " + symbolCount : ""}</div>
        </div>
    `
      )
      .join("");

    container.innerHTML = html;

    document.querySelectorAll(".symbol-item").forEach((item, idx) => {
      item.addEventListener("click", () => {
        console.log(`Clicked symbol ${idx + 1}`);
      });
    });
  } catch (error) {
    console.warn("Could not load symbols:", error);
    container.innerHTML =
      '<p style="grid-column: 1/-1; color: var(--text-secondary);">Symbol data unavailable</p>';
  }
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
