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

// Backfill tracking state
let activeBackfillJobs = new Map(); // job_id -> job data

/**
 * Restore selected symbols from localStorage
 */
function restoreSelectedSymbols() {
  try {
    const saved = localStorage.getItem("selected-symbols");
    if (saved && saved.trim() !== "") {
      const symbols = JSON.parse(saved);
      if (Array.isArray(symbols)) {
        selectedSymbols = new Set(symbols);
        console.log(`Restored ${symbols.length} selected symbols from localStorage`);
      } else {
        console.warn("Invalid selected symbols format in localStorage");
        selectedSymbols = new Set();
      }
    } else {
      selectedSymbols = new Set();
    }
  } catch (e) {
    console.warn("Could not restore selected symbols:", e);
    selectedSymbols = new Set();
  }
}

/**
 * Persist selected symbols to localStorage
 */
function persistSelectedSymbols() {
  try {
    const symbolsArray = Array.from(selectedSymbols);
    localStorage.setItem("selected-symbols", JSON.stringify(symbolsArray));
    console.log(`Persisted ${symbolsArray.length} symbols to localStorage`);
  } catch (e) {
    console.error("Failed to persist selected symbols:", e);
    // Silently fail - localStorage might be full or unavailable
  }
}

/**
 * Initialize dashboard on page load
 */
document.addEventListener("DOMContentLoaded", () => {
  console.log("Dashboard initializing...");
  restoreSelectedSymbols();
  setupSymbolSearch();
  setupCollapsibleSections();
  setupSymbolTableClickHandlers();
  setupKeyboardShortcuts();
  restoreSectionStates();
  refreshDashboard();
  setInterval(refreshDashboard, CONFIG.REFRESH_INTERVAL);
});

/**
 * Setup keyboard shortcuts
 */
function setupKeyboardShortcuts() {
  document.addEventListener("keydown", (e) => {
    // Ignore if user is typing in input
    if (
      ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)
    ) {
      return;
    }

    const ctrlOrCmd = e.ctrlKey || e.metaKey;

    // Ctrl/Cmd + R = Refresh dashboard
    if (ctrlOrCmd && e.key.toLowerCase() === "r") {
      e.preventDefault();
      refreshDashboard();
      return;
    }

    // ? = Show help modal
    if (e.key === "?") {
      e.preventDefault();
      showKeyboardHelp();
      return;
    }

    // S = Focus search box
    if (e.key.toLowerCase() === "s") {
      e.preventDefault();
      const searchBox = document.getElementById("symbol-search");
      if (searchBox) searchBox.focus();
      return;
    }

    // ESC = Close modals
    if (e.key === "Escape") {
      closeAssetModal();
      closeBackfillModal();
      closeEnrichModal();
      closeHelpModal();
      return;
    }

    // B = Open backfill modal (if symbols selected)
    if (e.key.toLowerCase() === "b" && selectedSymbols.size > 0) {
      e.preventDefault();
      openBackfillModal();
      return;
    }

    // E = Open enrich modal (if symbols selected)
    if (e.key.toLowerCase() === "e" && selectedSymbols.size > 0) {
      e.preventDefault();
      openEnrichModal();
      return;
    }
  });
}

/**
 * Show keyboard shortcuts help modal
 */
function showKeyboardHelp() {
  const helpHTML = `
    <div id="help-modal" class="modal" style="display: flex;" role="dialog" aria-labelledby="help-modal-title" aria-modal="true">
      <div class="modal-overlay" onclick="closeHelpModal()"></div>
      <div class="modal-content">
        <div class="modal-header">
          <h2 id="help-modal-title">Keyboard Shortcuts</h2>
          <button class="modal-close" onclick="closeHelpModal()" aria-label="Close keyboard shortcuts dialog">×</button>
        </div>
        <div class="shortcuts-list">
          <div class="shortcut-item">
            <span class="shortcut-key">Ctrl/Cmd + R</span>
            <span class="shortcut-desc">Refresh dashboard</span>
          </div>
          <div class="shortcut-item">
            <span class="shortcut-key">S</span>
            <span class="shortcut-desc">Focus symbol search</span>
          </div>
          <div class="shortcut-item">
            <span class="shortcut-key">B</span>
            <span class="shortcut-desc">Open backfill modal (with symbols selected)</span>
          </div>
          <div class="shortcut-item">
            <span class="shortcut-key">E</span>
            <span class="shortcut-desc">Open enrichment modal (with symbols selected)</span>
          </div>
          <div class="shortcut-item">
            <span class="shortcut-key">ESC</span>
            <span class="shortcut-desc">Close any modal</span>
          </div>
          <div class="shortcut-item">
            <span class="shortcut-key">?</span>
            <span class="shortcut-desc">Show this help</span>
          </div>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", helpHTML);
  // Focus on close button for keyboard accessibility
  document.querySelector("#help-modal .modal-close").focus();
}

/**
 * Close help modal
 */
function closeHelpModal() {
  const modal = document.getElementById("help-modal");
  if (modal) modal.remove();
}

/**
 * Toggle collapsible section
 */
function toggleSection(sectionName) {
  const section = document.querySelector(`[data-section="${sectionName}"]`);
  if (section) {
    section.classList.toggle("collapsed");
    // Persist preference in localStorage
    const collapsed = section.classList.contains("collapsed");
    localStorage.setItem(
      `section-${sectionName}`,
      collapsed ? "collapsed" : "expanded"
    );
  }
}

/**
 * Restore section states from localStorage
 */
function restoreSectionStates() {
  const sections = document.querySelectorAll(".collapsible-section");
  sections.forEach((section) => {
    const sectionName = section.getAttribute("data-section");
    const state = localStorage.getItem(`section-${sectionName}`);
    if (state === "collapsed") {
      section.classList.add("collapsed");
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
  const overallStatus = document.getElementById("overall-status");
  const responseTime = document.getElementById("response-time");

  statusBadge.className = `status-badge ${isHealthy ? "healthy" : "critical"}`;
  statusBadge.textContent = `● ${isHealthy ? "Healthy" : "Unhealthy"}`;

  if (overallStatus) {
    overallStatus.textContent = isHealthy ? "🟢 Healthy" : "🔴 Offline";
    overallStatus.style.color = isHealthy ? "var(--success)" : "var(--danger)";
  }

  responseTime.textContent = `${duration.toFixed(0)} ms`;
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
      container.innerHTML = `
        <tr>
          <td colspan="8" style="text-align: center; padding: 60px 20px;">
            <div style="color: var(--text-secondary);">
              <div style="font-size: 56px; margin-bottom: 24px;">📊</div>
              <h3 style="font-size: 24px; font-weight: 700; margin-bottom: 12px; color: var(--text-primary);">No Market Data Available</h3>
              <p style="font-size: 15px; margin-bottom: 8px; line-height: 1.6;">
                The database is currently empty. To get started, you need to load historical market data.
              </p>
              <p style="font-size: 14px; margin-bottom: 24px; color: var(--text-secondary); line-height: 1.6;">
                Use the Backfill feature to import data for one or more symbols across your desired timeframes and date ranges.
              </p>
              
              <div style="background: rgba(15, 147, 112, 0.05); border: 1px solid rgba(15, 147, 112, 0.2); border-radius: 8px; padding: 20px; margin: 24px 0; text-align: left; font-size: 13px;">
                <h4 style="color: var(--text-primary); margin-bottom: 12px; font-size: 14px; font-weight: 600;">Getting Started Steps:</h4>
                <ol style="margin: 0; padding-left: 20px; color: var(--text-secondary);">
                  <li style="margin-bottom: 8px;">Click <strong>"Manual Backfill..."</strong> button above</li>
                  <li style="margin-bottom: 8px;">Select symbols and date range (minimum 30 days recommended)</li>
                  <li style="margin-bottom: 8px;">Choose timeframes: 5m, 15m, 1h, 1d (at least one required)</li>
                  <li>Click "Start Backfill" to begin data import</li>
                </ol>
              </div>
              
              <div style="display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; margin-bottom: 16px;">
                <button class="btn btn-primary" onclick="triggerManualBackfill()" style="padding: 10px 24px; font-size: 14px;">Start Backfill Now</button>
                <button class="btn btn-secondary" onclick="viewDocs()" style="padding: 10px 24px; font-size: 14px;">View API Documentation</button>
              </div>
              
              <p style="font-size: 12px; margin-top: 20px; color: var(--text-secondary); border-top: 1px solid rgba(15, 147, 112, 0.2); padding-top: 16px;">
                Once data is loaded, you'll see symbols listed here with quality metrics, validation rates, and data age information.
              </p>
            </div>
          </td>
        </tr>
      `;
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
    .map((symbol) => {
      const isSelected = selectedSymbols.has(symbol.symbol);
      return `
    <tr class="${isSelected ? "selected" : ""}">
      <td style="width: 40px;">
        <input type="checkbox" class="symbol-checkbox" data-symbol="${escapeHtml(
          symbol.symbol
        )}" 
               ${
                 isSelected ? "checked" : ""
               } onchange="toggleSymbolSelection(this)">
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
    })
    .join("");

  if (!html) {
    container.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; padding: 40px 20px;">
          <div style="color: var(--text-secondary);">
            <div style="font-size: 32px; margin-bottom: 12px;">🔍</div>
            <p style="font-size: 16px; font-weight: 600; margin-bottom: 8px; color: var(--text-primary);">No matching symbols</p>
            <p style="font-size: 13px;">Try adjusting your search term or status filter</p>
            <button class="btn btn-secondary" onclick="document.getElementById('symbol-search').value = ''; document.getElementById('status-filter').value = ''; setupSymbolSearch();" style="margin-top: 16px;">Clear Filters</button>
          </div>
        </td>
      </tr>
    `;
  } else {
    container.innerHTML = html;
  }
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
  document.addEventListener("click", (e) => {
    const row = e.target.closest("#symbol-tbody tr");
    if (row && !row.querySelector('input[type="checkbox"]')) {
      // Get symbol from first column after checkbox column
      const symbolCell = row.querySelector("td:nth-child(2) .symbol-name");
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
  const symbol = checkbox.getAttribute("data-symbol");
  const row = checkbox.closest("tr");

  if (checkbox.checked) {
    selectedSymbols.add(symbol);
    row.classList.add("selected");
  } else {
    selectedSymbols.delete(symbol);
    row.classList.remove("selected");
  }

  persistSelectedSymbols();
  updateSelectionToolbar();
  updateSelectAllCheckbox();
}

/**
 * Toggle select all checkboxes
 */
function toggleSelectAll(checkbox) {
  const checkboxes = document.querySelectorAll(".symbol-checkbox");
  checkboxes.forEach((cb) => {
    cb.checked = checkbox.checked;
    toggleSymbolSelection(cb);
  });
}

/**
 * Update the "select all" checkbox state based on current selections
 */
function updateSelectAllCheckbox() {
  const selectAll = document.getElementById("select-all-symbols");
  const checkboxes = document.querySelectorAll(".symbol-checkbox");
  const checked = document.querySelectorAll(".symbol-checkbox:checked");

  if (selectAll) {
    selectAll.checked =
      checkboxes.length > 0 && checkboxes.length === checked.length;
    selectAll.indeterminate =
      checked.length > 0 && checkboxes.length !== checked.length;
  }
}

/**
 * Update toolbar visibility and count
 */
function updateSelectionToolbar() {
  const toolbar = document.getElementById("selection-toolbar");
  const count = document.getElementById("selection-count");

  if (selectedSymbols.size > 0) {
    toolbar.style.display = "flex";
    count.textContent = `${selectedSymbols.size} symbol${
      selectedSymbols.size !== 1 ? "s" : ""
    } selected`;
  } else {
    toolbar.style.display = "none";
  }
}

/**
 * Clear all selections
 */
function clearSelection() {
  selectedSymbols.clear();
  persistSelectedSymbols();
  document
    .querySelectorAll(".symbol-checkbox")
    .forEach((cb) => (cb.checked = false));
  document
    .querySelectorAll(".symbol-table tbody tr")
    .forEach((row) => row.classList.remove("selected"));
  document.getElementById("select-all-symbols").checked = false;
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
  // Open FastAPI Swagger UI docs at root /docs endpoint
  window.open("/docs", "_blank");
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
    // Get status data which contains basic metrics
    const statusResponse = await fetch(`${CONFIG.API_BASE}/api/v1/status`);
    const status = statusResponse.ok ? await statusResponse.json() : null;
    
    // Try to fetch enrichment endpoints but don't fail if they don't exist
    const [overview, metrics, health, history] = await Promise.all([
      fetch(`${CONFIG.API_BASE}/api/v1/enrichment/dashboard/overview`)
        .then((r) => r.ok ? r.json() : null)
        .catch(() => null),
      fetch(`${CONFIG.API_BASE}/api/v1/enrichment/dashboard/metrics`)
        .then((r) => r.ok ? r.json() : null)
        .catch(() => null),
      fetch(`${CONFIG.API_BASE}/api/v1/enrichment/dashboard/health`)
        .then((r) => r.ok ? r.json() : null)
        .catch(() => null),
      fetch(`${CONFIG.API_BASE}/api/v1/enrichment/history?limit=10`)
        .then((r) => r.ok ? r.json() : null)
        .catch(() => null),
    ]);

    // Update with available data
    if (overview) updateEnrichmentStatus(overview);
    if (metrics) updatePipelineMetrics(metrics);
    if (health) updateHealthStatus(health);
    if (history) updateJobQueue(history);
    
    // If enrichment endpoints don't exist, generate synthetic data from status
    if (!overview && status?.database) {
      updateEnrichmentStatusFromStatus(status);
    }
    if (!metrics && status?.database) {
      updatePipelineMetricsFromStatus(status);
    }
    if (!health && status) {
      updateHealthStatusFromStatus(status);
    }
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
    formatNumber(fetchPipeline.total_jobs || fetchPipeline.total_fetches || 0)
  );
  updateMetricValue(
    "fetch-success-rate",
    (fetchPipeline.success_rate || 0).toFixed(1)
  );
  updateMetricValue(
    "fetch-avg-time",
    (fetchPipeline.avg_job_duration_seconds * 1000 || fetchPipeline.avg_response_time_ms || 0).toFixed(0)
  );
  updateMetricValue(
    "fetch-records",
    formatNumber(fetchPipeline.total_records_fetched || data.last_24h?.records_fetched || 0)
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
    (computePipeline.avg_computation_time_ms || computePipeline.avg_time_ms || 0).toFixed(0)
  );
  updateMetricValue(
    "compute-features",
    formatNumber(computePipeline.total_features_computed || data.last_24h?.features_computed || 0)
  );

  // Data Quality
  const dataQuality = data.data_quality || {};
  updateMetricValue(
    "quality-validation",
    (dataQuality.avg_validation_rate || 0).toFixed(1)
  );
  updateMetricValue(
    "quality-score",
    (dataQuality.avg_quality_score || 0).toFixed(2)
  );
  updateMetricValue(
    "quality-complete",
    (dataQuality.avg_data_completeness || 0).toFixed(1)
  );
  
  // Calculate healthy symbols from health status
  const healthyCount = data.symbol_health?.healthy || 0;
  updateMetricValue(
    "quality-healthy",
    formatNumber(healthyCount)
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
 * Update job queue display with enrichment job data
 */
function updateJobQueue(data) {
  const jobs = data.jobs || [];
  const tbody = document.getElementById("job-tbody");

  if (jobs.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="6" style="text-align: center; color: var(--text-secondary);">No recent jobs</td></tr>';
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
      <td>
        <span class="job-status ${job.success ? "success" : "failed"}">
          ${job.success ? "✓ Success" : "✗ Failed"}
        </span>
      </td>
      <td>${formatNumber(job.records_fetched || 0)}</td>
      <td>${formatNumber(job.records_inserted || 0)}</td>
      <td>${(job.response_time_ms || 0).toFixed(0)} ms</td>
      <td>${formatDate(job.created_at) || "--"}</td>
    </tr>
  `
    )
    .join("");

  tbody.innerHTML = html;
  updateMetricValue("job-count", `Showing ${jobs.length} recent jobs`);
}

/**
 * Fallback: Update enrichment status from status endpoint
 */
function updateEnrichmentStatusFromStatus(status) {
  const db = status.database || {};
  const isRunning = status.data_quality?.scheduler_status === "running";
  
  updateMetricValue("enrichment-scheduler-status", isRunning ? "🟢 Running" : "⚫ Stopped");
  updateMetricValue("enrichment-last-run", formatDate(db.latest_data) || "Never");
  updateMetricValue("enrichment-next-run", "Check scheduler");
  updateMetricValue("enrichment-success-rate", "N/A");
  updateMetricValue("enrichment-symbols-count", `${db.symbols_available || 0}/60`);
  updateMetricValue("enrichment-avg-time", "N/A");
}

/**
 * Fallback: Update pipeline metrics from status endpoint
 */
function updatePipelineMetricsFromStatus(status) {
  const db = status.database || {};
  const dq = status.data_quality || {};
  
  // Fetch pipeline
  updateMetricValue("fetch-total", formatNumber(db.total_records || 0));
  updateMetricValue("fetch-success-rate", (db.validation_rate_pct || 0).toFixed(1));
  updateMetricValue("fetch-avg-time", "N/A");
  updateMetricValue("fetch-records", formatNumber(db.total_records || 0));
  
  // Compute pipeline
  updateMetricValue("compute-total", "N/A");
  updateMetricValue("compute-success-rate", "N/A");
  updateMetricValue("compute-avg-time", "N/A");
  updateMetricValue("compute-features", "N/A");
  
  // Data quality
  updateMetricValue("quality-validation", (db.validation_rate_pct || 0).toFixed(1));
  updateMetricValue("quality-score", "N/A");
  updateMetricValue("quality-complete", "N/A");
  updateMetricValue("quality-healthy", formatNumber(db.symbols_available || 0));
}

/**
 * Fallback: Update health status from status endpoint
 */
function updateHealthStatusFromStatus(status) {
  const isRunning = status.data_quality?.scheduler_status === "running";
  
  updateMetricValue("health-scheduler", isRunning ? "🟢 Healthy" : "⚫ Stopped");
  updateMetricValue("health-database", "🟢 Healthy");
  updateMetricValue("health-api", "🟢 Healthy");
  updateMetricValue("health-failures", "N/A");
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
  const modal = document.getElementById("asset-modal");
  modal.style.display = "flex";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-labelledby", "modal-symbol");
  modal.setAttribute("aria-modal", "true");

  document.getElementById("modal-symbol").textContent = symbol;

  // Load overview by default
  await loadAssetOverview(symbol);

  // Focus close button for accessibility
  modal.querySelector(".modal-close").focus();
}

function closeAssetModal() {
  document.getElementById("asset-modal").style.display = "none";
  currentSymbol = null;
}

function switchAssetTab(tabName) {
  // Ensure current symbol is set
  if (!currentSymbol) {
    console.warn("No current symbol set for tab switch");
    return;
  }

  // Hide all tabs
  const tabs = ["overview", "candles", "enrichment"];
  tabs.forEach((tab) => {
    const element = document.getElementById(`tab-${tab}`);
    if (element) element.style.display = "none";
  });

  // Update button states and ARIA attributes
  document.querySelectorAll(".asset-tab-btn").forEach((btn) => {
    btn.classList.remove("active");
    btn.setAttribute("aria-selected", "false");
  });

  // Show selected tab
  const tabElement = document.getElementById(`tab-${tabName}`);
  if (tabElement) {
    tabElement.style.display = "block";
  }
  
  // Set active button and update ARIA using event target or find button
  const buttons = document.querySelectorAll(".asset-tab-btn");
  let activeBtn = null;
  
  if (event && event.target) {
    activeBtn = event.target.closest(".asset-tab-btn");
  } else {
    // Find button by matching tab name in onclick handler
    for (const btn of buttons) {
      if (btn.getAttribute("onclick")?.includes(tabName)) {
        activeBtn = btn;
        break;
      }
    }
  }
  
  if (activeBtn) {
    activeBtn.classList.add("active");
    activeBtn.setAttribute("aria-selected", "true");
  }

  // Load data for specific tabs only if modal is visible
  const modal = document.getElementById("asset-modal");
  if (modal && modal.style.display === "flex") {
    if (tabName === "candles") {
      // Get selected timeframe if available, default to 1h
      const timeframeSelect = document.getElementById("candle-timeframe");
      const timeframe = timeframeSelect ? timeframeSelect.value : "1h";
      loadCandleData(currentSymbol, timeframe);
    } else if (tabName === "enrichment") {
      // Always use 1h for enrichment view
      loadEnrichmentData(currentSymbol, "1h");
    }
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
    if (!response.ok) throw new Error("Failed to load asset data");
    const asset = await response.json();

    assetCache.set(cacheKey, { data: asset, timestamp: Date.now() });
    renderOverview(asset);
  } catch (error) {
    console.error("Error loading asset overview:", error);
    document.getElementById(
      "overview-grid"
    ).innerHTML = `<p style="color: red;">Error loading asset data: ${error.message}</p>`;
  }
}

function renderOverview(asset) {
  const grid = document.getElementById("overview-grid");
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
      <span class="stat-value">${asset.data_age_hours || "--"} hours</span>
    </div>
    <div class="stat-box">
      <span class="stat-label">Quality Score</span>
      <span class="stat-value">${
        (asset.quality?.quality_score * 100).toFixed(1) || "--"
      }%</span>
    </div>
  `;

  // Populate timeframes table
  const tbody = document.getElementById("timeframes-tbody");
  tbody.innerHTML = "";

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

async function loadCandleData(symbol, timeframe = "1h") {
  try {
    // Ensure modal is open
    const modal = document.getElementById("asset-modal");
    if (modal.style.display !== "flex") {
      return;
    }

    const cacheKey = `candles-${symbol}-${timeframe}`;
    const cached = assetCache.get(cacheKey);

    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      renderCandles(cached.data);
      return;
    }

    const response = await fetch(
      `${CONFIG.API_BASE}/api/v1/assets/${symbol}/candles?timeframe=${timeframe}&limit=100`
    );
    if (!response.ok) throw new Error("Failed to load candles");
    const data = await response.json();

    assetCache.set(cacheKey, { data: data, timestamp: Date.now() });
    renderCandles(data);
  } catch (error) {
    console.error("Error loading candles:", error);
    const tbody = document.getElementById("candles-tbody");
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align: center; padding: 20px; color: var(--danger);">
            Error loading candles: ${escapeHtml(error.message)}
          </td>
        </tr>
      `;
    }
  }
}

function renderCandles(data) {
  const count = document.getElementById("candle-count");
  count.textContent = `${
    data.pagination?.total?.toLocaleString() || "--"
  } total candles`;

  const tbody = document.getElementById("candles-tbody");
  tbody.innerHTML = "";

  if (!data.candles || data.candles.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="8" style="text-align: center; color: var(--text-secondary);">No candles available</td></tr>';
    return;
  }

  for (const candle of data.candles) {
    const enrichmentClass =
      candle.enrichment_status === "complete" ? "complete" : "pending";
    tbody.innerHTML += `
      <tr>
        <td>${formatDateTime(candle.timestamp)}</td>
        <td>$${(candle.open || 0).toFixed(2)}</td>
        <td>$${(candle.high || 0).toFixed(2)}</td>
        <td>$${(candle.low || 0).toFixed(2)}</td>
        <td>$${(candle.close || 0).toFixed(2)}</td>
        <td>${(candle.volume || 0).toLocaleString()}</td>
        <td>$${(candle.vwap || 0).toFixed(2)}</td>
        <td><span class="badge ${enrichmentClass}">${
      candle.enrichment_status || "pending"
    }</span></td>
      </tr>
    `;
  }
}

async function loadEnrichmentData(symbol, timeframe = "1h") {
  try {
    // Ensure modal is open
    const modal = document.getElementById("asset-modal");
    if (modal.style.display !== "flex") {
      return;
    }

    const cacheKey = `enrichment-${symbol}-${timeframe}`;
    const cached = assetCache.get(cacheKey);

    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      renderEnrichment(cached.data);
      return;
    }

    const response = await fetch(
      `${CONFIG.API_BASE}/api/v1/assets/${symbol}/enrichment?timeframe=${timeframe}`
    );
    if (!response.ok) throw new Error("Failed to load enrichment data");
    const enrichment = await response.json();

    assetCache.set(cacheKey, { data: enrichment, timestamp: Date.now() });
    renderEnrichment(enrichment);
  } catch (error) {
    console.error("Error loading enrichment:", error);
    const grid = document.getElementById("enrichment-grid");
    if (grid) {
      grid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 20px; color: var(--danger);">
          Error loading enrichment data: ${escapeHtml(error.message)}
        </div>
      `;
    }
  }
}

function renderEnrichment(enrichment) {
  const grid = document.getElementById("enrichment-grid");

  grid.innerHTML = `
    <div class="enrichment-card">
      <h4>Fetch Pipeline</h4>
      <div class="metric">
        <span class="metric-label">Success Rate</span>
        <span class="metric-value">${(
          enrichment.fetch_metrics?.success_rate || 0
        ).toFixed(1)}%</span>
      </div>
      <div class="metric">
        <span class="metric-label">Avg Response</span>
        <span class="metric-value">${
          enrichment.fetch_metrics?.avg_response_time || "--"
        } ms</span>
      </div>
      <div class="metric">
        <span class="metric-label">Total Fetches</span>
        <span class="metric-value">${
          enrichment.fetch_metrics?.total_fetches || "--"
        }</span>
      </div>
    </div>

    <div class="enrichment-card">
      <h4>Compute Pipeline</h4>
      <div class="metric">
        <span class="metric-label">Success Rate</span>
        <span class="metric-value">${(
          enrichment.compute_metrics?.success_rate || 0
        ).toFixed(1)}%</span>
      </div>
      <div class="metric">
        <span class="metric-label">Avg Time</span>
        <span class="metric-value">${
          enrichment.compute_metrics?.avg_compute_time || "--"
        } ms</span>
      </div>
      <div class="metric">
        <span class="metric-label">Total Computations</span>
        <span class="metric-value">${
          enrichment.compute_metrics?.total_computations || "--"
        }</span>
      </div>
    </div>

    <div class="enrichment-card">
      <h4>Data Quality</h4>
      <div class="metric">
        <span class="metric-label">Validation Rate</span>
        <span class="metric-value">${(
          enrichment.quality_metrics?.validation_rate || 0
        ).toFixed(1)}%</span>
      </div>
      <div class="metric">
        <span class="metric-label">Quality Score</span>
        <span class="metric-value">${(
          enrichment.quality_metrics?.quality_score || 0
        ).toFixed(2)}</span>
      </div>
      <div class="metric">
        <span class="metric-label">Missing Features</span>
        <span class="metric-value">${
          enrichment.quality_metrics?.missing_features || 0
        }</span>
      </div>
    </div>
  `;
}

function loadMoreCandles(symbol) {
  // This would require pagination tracking
  // For now, just reload with limit
  loadCandleData(symbol, document.getElementById("candle-timeframe").value);
}

function getStatusClass(status) {
  const s = (status || "").toLowerCase();
  if (s.includes("healthy") || s.includes("complete")) return "healthy";
  if (s.includes("warning") || s.includes("partial")) return "warning";
  if (s.includes("stale") || s.includes("failed")) return "stale";
  return "neutral";
}

function formatDateTime(date) {
  if (!date) return "--";
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
  // Open backfill modal directly - users can enter symbols manually
  openBackfillModalDirect();
}

/**
 * Quick Actions - View Admin Panel (placeholder)
 */
function viewAdminPanel() {
  // Scroll to admin section
  const adminSection = document.querySelector('.admin-section');
  if (adminSection) {
    adminSection.scrollIntoView({ behavior: 'smooth' });
    // Open the section if collapsed
    const sectionContent = adminSection.querySelector('.section-content');
    if (sectionContent && sectionContent.style.display === 'none') {
      toggleSection('admin');
    }
  }
}

/**
 * Open backfill modal directly (for Manual Backfill button)
 * Allows users to enter symbols manually via a text input
 */
function openBackfillModalDirect() {
  const modal = document.getElementById("backfill-modal");
  const displayDiv = document.getElementById("backfill-symbols");

  // If no symbols selected, show an input field instead
  if (selectedSymbols.size === 0) {
    displayDiv.innerHTML = `
      <div style="width: 100%; display: flex; gap: 8px; margin-bottom: 12px;">
        <input 
          type="text" 
          id="manual-symbol-input" 
          placeholder="Enter symbols separated by commas (e.g., AAPL,GOOGL,MSFT)" 
          style="flex: 1; padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 4px; font-size: 13px;"
        >
        <button 
          class="btn btn-sm btn-primary" 
          onclick="addManualSymbols()"
          style="white-space: nowrap;"
        >Add Symbols</button>
      </div>
      <div id="manual-symbols-list"></div>
    `;
  } else {
    // Populate selected symbols
    const symbolsHTML = Array.from(selectedSymbols)
      .map((s) => `<span class="symbol-tag">${escapeHtml(s)}</span>`)
      .join("");
    
    displayDiv.innerHTML = symbolsHTML;
  }

  // Set default dates (last 30 days)
  const today = new Date();
  const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

  document.getElementById("backfill-end-date").value = today
    .toISOString()
    .split("T")[0];
  document.getElementById("backfill-start-date").value = thirtyDaysAgo
    .toISOString()
    .split("T")[0];

  // Check at least one timeframe is selected by default
  ensureDefaultTimeframe();

  modal.style.display = "flex";
  
  // Set focus trap for accessibility
  setupModalFocusTrap(modal);

  // Focus symbol input or first form input
  setTimeout(() => {
    const manualInput = document.getElementById("manual-symbol-input");
    if (manualInput) {
      manualInput.focus();
    } else {
      const firstInput = modal.querySelector(".form-input");
      if (firstInput) firstInput.focus();
    }
  }, 100);
}

/**
 * Add manually entered symbols to the selected set
 */
function addManualSymbols() {
  const input = document.getElementById("manual-symbol-input");
  if (!input) return;

  const symbols = input.value
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter((s) => s.length > 0);

  if (symbols.length === 0) {
    showValidationError("Please enter at least one symbol");
    return;
  }

  symbols.forEach((s) => selectedSymbols.add(s));
  persistSelectedSymbols();

  // Refresh the display to show selected symbols
  const displayDiv = document.getElementById("backfill-symbols");
  const symbolsHTML = Array.from(selectedSymbols)
    .map((s) => `<span class="symbol-tag">${escapeHtml(s)}</span>`)
    .join("");
  displayDiv.innerHTML = `
    <div style="margin-bottom: 12px;">${symbolsHTML}</div>
    <div style="width: 100%; display: flex; gap: 8px;">
      <input 
        type="text" 
        id="manual-symbol-input" 
        placeholder="Add more symbols..." 
        style="flex: 1; padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 4px; font-size: 13px;"
      >
      <button 
        class="btn btn-sm btn-secondary" 
        onclick="addManualSymbols()"
        style="white-space: nowrap;"
      >Add More</button>
      <button 
        class="btn btn-sm btn-secondary" 
        onclick="clearManualSymbols()"
        style="white-space: nowrap;"
      >Clear</button>
    </div>
  `;

  // Focus the input for potential additional symbols
  setTimeout(() => {
    const nextInput = document.getElementById("manual-symbol-input");
    if (nextInput) nextInput.focus();
  }, 50);
}

/**
 * Clear all manually entered symbols
 */
function clearManualSymbols() {
  selectedSymbols.clear();
  persistSelectedSymbols();
  openBackfillModalDirect();
}

/**
 * Open backfill modal
 */
function openBackfillModal() {
  if (selectedSymbols.size === 0) {
    showValidationError("Please select at least one symbol");
    return;
  }

  const modal = document.getElementById("backfill-modal");
  const displayDiv = document.getElementById("backfill-symbols");

  // Populate selected symbols
  const symbolsHTML = Array.from(selectedSymbols)
    .map((s) => `<span class="symbol-tag">${escapeHtml(s)}</span>`)
    .join("");
  
  displayDiv.innerHTML = symbolsHTML || '<span style="color: var(--text-secondary);">No symbols selected</span>';

  // Set default dates (last 30 days)
  const today = new Date();
  const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

  document.getElementById("backfill-end-date").value = today
    .toISOString()
    .split("T")[0];
  document.getElementById("backfill-start-date").value = thirtyDaysAgo
    .toISOString()
    .split("T")[0];

  // Check at least one timeframe is selected by default
  ensureDefaultTimeframe();

  modal.style.display = "flex";
  
  // Set focus trap for accessibility
  setupModalFocusTrap(modal);

  // Focus first input for accessibility
  const firstInput = modal.querySelector(".form-input");
  if (firstInput) {
    setTimeout(() => firstInput.focus(), 100);
  }
}

/**
 * Close backfill modal
 */
function closeBackfillModal() {
  document.getElementById("backfill-modal").style.display = "none";
}

/**
 * Ensure at least one timeframe is checked by default
 */
function ensureDefaultTimeframe() {
  const checkboxes = document.querySelectorAll("#backfill-timeframes input");
  const anyChecked = Array.from(checkboxes).some(cb => cb.checked);
  
  if (!anyChecked && checkboxes.length > 0) {
    checkboxes[2].checked = true; // Default to 1h
    console.log("Default timeframe (1h) selected");
  }
}

/**
 * Setup keyboard focus trap for modal
 * Ensures tab focus stays within modal when open
 */
function setupModalFocusTrap(modal) {
  const focusableElements = modal.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  
  if (focusableElements.length === 0) return;
  
  const firstElement = focusableElements[0];
  const lastElement = focusableElements[focusableElements.length - 1];
  
  modal.addEventListener("keydown", (e) => {
    if (e.key !== "Tab") return;
    
    if (e.shiftKey) {
      // Shift + Tab: move focus backward
      if (document.activeElement === firstElement) {
        e.preventDefault();
        lastElement.focus();
      }
    } else {
      // Tab: move focus forward
      if (document.activeElement === lastElement) {
        e.preventDefault();
        firstElement.focus();
      }
    }
  });
}

/**
 * Validate timeframe selection and add visual feedback
 */
function validateTimeframeSelection(containerSelector) {
  const checkboxes = document.querySelectorAll(containerSelector + " input[type='checkbox']");
  const anyChecked = Array.from(checkboxes).some(cb => cb.checked);
  
  if (!anyChecked) {
    // Add visual indicator to the fieldset
    const fieldset = document.querySelector(containerSelector).closest("fieldset");
    if (fieldset) {
      fieldset.style.borderLeft = "3px solid var(--danger)";
    }
    return false;
  }
  
  // Remove error styling if valid
  const fieldset = document.querySelector(containerSelector).closest("fieldset");
  if (fieldset) {
    fieldset.style.borderLeft = "";
  }
  
  return true;
}

/**
 * Show validation error in a user-friendly way
 */
function showValidationError(message) {
  const alertsContainer = document.getElementById("alerts");
  const errorHTML = `
    <div class="alert critical" style="margin-bottom: 16px;">
      <span>⚠️ ${escapeHtml(message)}</span>
    </div>
  `;
  alertsContainer.insertAdjacentHTML("afterbegin", errorHTML);
  
  // Auto-dismiss after 5 seconds
  setTimeout(() => {
    const alert = alertsContainer.querySelector(".alert.critical");
    if (alert) alert.remove();
  }, 5000);
}

/**
 * Submit backfill operation
 */
async function submitBackfill() {
  const symbols = getSelectedSymbols();
  const startDate = document.getElementById("backfill-start-date").value;
  const endDate = document.getElementById("backfill-end-date").value;
  const timeframes = Array.from(
    document.querySelectorAll("#backfill-timeframes input:checked")
  ).map((el) => el.value);

  // Validation
  const errors = [];

  if (!symbols || symbols.length === 0) {
    errors.push("No symbols selected");
  }
  if (!startDate) {
    errors.push("Start date is required");
  }
  if (!endDate) {
    errors.push("End date is required");
  }
  if (startDate && endDate && new Date(startDate) >= new Date(endDate)) {
    errors.push("Start date must be before end date");
  }
  
  // Validate timeframe selection
  if (!validateTimeframeSelection("#backfill-timeframes")) {
    errors.push("Please select at least one timeframe");
  }

  if (errors.length > 0) {
    showValidationError(errors.join(", "));
    return;
  }

  try {
    console.log("Submitting backfill:", {
      symbols,
      startDate,
      endDate,
      timeframes,
    });

    // Build request body (preferred over query params due to URL length limits)
    const requestBody = {
      symbols: symbols,
      start_date: startDate,
      end_date: endDate,
      timeframes: timeframes
    };

    const response = await fetch(
      `${CONFIG.API_BASE}/api/v1/backfill`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody)
      }
    );

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();

    // Track this job
    activeBackfillJobs.set(result.job_id, {
      symbols: symbols,
      timeframes: timeframes,
      startTime: Date.now(),
      lastUpdate: Date.now()
    });

    closeBackfillModal();
    clearSelection();
    
    // Show progress modal immediately
    showBackfillProgressModal(result.job_id);
    
    // Start polling for status
    pollBackfillStatus(result.job_id);
    
  } catch (error) {
    console.error("Backfill error:", error);
    showValidationError(`Error starting backfill: ${error.message}`);
  }
}

/**
 * Show progress modal for backfill job
 */
function showBackfillProgressModal(jobId) {
  const modalHTML = `
    <div id="backfill-progress-modal" class="modal" style="display: flex;" role="dialog" aria-labelledby="backfill-progress-title" aria-modal="true">
      <div class="modal-overlay"></div>
      <div class="modal-content modal-form" style="width: 600px;">
        <div class="modal-header">
          <h2 id="backfill-progress-title">Backfill in Progress</h2>
          <button class="modal-close" onclick="closeBackfillProgressModal()" aria-label="Close progress dialog">×</button>
        </div>

        <div style="margin-bottom: 24px;">
          <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span style="font-weight: 600;">Overall Progress</span>
            <span id="progress-percentage" style="font-weight: 600;">0%</span>
          </div>
          <div style="width: 100%; height: 24px; background: var(--bg-secondary); border-radius: 12px; overflow: hidden;">
            <div id="progress-bar" style="width: 0%; height: 100%; background: linear-gradient(90deg, #0f9370, #11b981); transition: width 0.3s ease; display: flex; align-items: center; justify-content: flex-end; padding-right: 8px;">
              <span id="bar-text" style="color: white; font-size: 11px; font-weight: 600;"></span>
            </div>
          </div>
        </div>

        <div style="background: var(--bg-secondary); border-radius: 8px; padding: 16px; margin-bottom: 16px;">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 13px;">
            <div>
              <span style="color: var(--text-secondary); display: block; margin-bottom: 4px;">Symbols Completed</span>
              <span id="symbols-completed" style="font-weight: 600; font-size: 16px;">0 / 0</span>
            </div>
            <div>
              <span style="color: var(--text-secondary); display: block; margin-bottom: 4px;">Total Records Inserted</span>
              <span id="records-inserted" style="font-weight: 600; font-size: 16px;">0</span>
            </div>
            <div>
              <span style="color: var(--text-secondary); display: block; margin-bottom: 4px;">Current Symbol</span>
              <span id="current-symbol" style="font-weight: 600; font-size: 14px; font-family: monospace;">--</span>
            </div>
            <div>
              <span style="color: var(--text-secondary); display: block; margin-bottom: 4px;">Elapsed Time</span>
              <span id="elapsed-time" style="font-weight: 600; font-size: 14px;">0s</span>
            </div>
          </div>
        </div>

        <div style="background: var(--bg-secondary); border-radius: 8px; padding: 12px; max-height: 200px; overflow-y: auto; margin-bottom: 16px;">
          <div style="font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px;">PROCESSING LOG</div>
          <div id="backfill-log" style="font-family: monospace; font-size: 11px; line-height: 1.6; color: var(--text-secondary);"></div>
        </div>

        <div class="form-actions">
          <button class="btn btn-secondary" onclick="closeBackfillProgressModal()" aria-label="Close progress dialog">Close</button>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHTML);
}

/**
 * Close backfill progress modal
 */
function closeBackfillProgressModal() {
  const modal = document.getElementById("backfill-progress-modal");
  if (modal) modal.remove();
}

/**
 * Poll backfill job status
 */
async function pollBackfillStatus(jobId) {
  const maxAttempts = 3600; // 1 hour if polling every second
  let attempts = 0;

  const poll = async () => {
    if (attempts > maxAttempts) {
      console.warn(`Backfill job ${jobId} polling timeout`);
      return;
    }

    try {
      const response = await fetch(
        `${CONFIG.API_BASE}/api/v1/backfill/status/${jobId}`
      );

      if (!response.ok) {
        if (response.status === 404) {
          console.warn(`Job ${jobId} not found`);
          return;
        }
        throw new Error(`HTTP ${response.status}`);
      }

      const status = await response.json();
      updateBackfillProgressDisplay(jobId, status);

      // Continue polling if not completed
      if (status.status !== "completed" && status.status !== "failed") {
        attempts++;
        setTimeout(poll, 1000); // Poll every second
      } else {
        console.info(`Backfill job ${jobId} finished with status: ${status.status}`);
        activeBackfillJobs.delete(jobId);
        
        // Show completion message
        const message = status.status === "completed" 
          ? `✓ Backfill completed! ${status.total_records_inserted} records inserted.`
          : `✗ Backfill failed: ${status.error}`;
        
        showValidationError(message);
        
        // Refresh dashboard after 2 seconds
        setTimeout(() => refreshDashboard(), 2000);
      }

    } catch (error) {
      console.error(`Error polling backfill status: ${error}`);
      attempts++;
      setTimeout(poll, 5000); // Retry after 5 seconds on error
    }
  };

  poll();
}

/**
 * Update progress display
 */
function updateBackfillProgressDisplay(jobId, status) {
  const progressPct = status.progress_pct || 0;
  const progressBar = document.getElementById("progress-bar");
  const progressPercentage = document.getElementById("progress-percentage");
  const symbolsCompleted = document.getElementById("symbols-completed");
  const recordsInserted = document.getElementById("records-inserted");
  const currentSymbol = document.getElementById("current-symbol");
  const elapsedTime = document.getElementById("elapsed-time");
  const log = document.getElementById("backfill-log");

  if (progressBar) {
    progressBar.style.width = `${progressPct}%`;
    const barText = document.getElementById("bar-text");
    if (progressPct > 10) {
      barText.textContent = `${progressPct}%`;
    }
  }

  if (progressPercentage) {
    progressPercentage.textContent = `${progressPct}%`;
  }

  if (symbolsCompleted) {
    symbolsCompleted.textContent = `${status.symbols_completed} / ${status.symbols_total}`;
  }

  if (recordsInserted) {
    recordsInserted.textContent = formatNumber(status.total_records_inserted);
  }

  if (currentSymbol) {
    currentSymbol.textContent = status.current_symbol || "--";
  }

  if (elapsedTime) {
    const jobData = activeBackfillJobs.get(jobId);
    if (jobData) {
      const elapsed = Math.floor((Date.now() - jobData.startTime) / 1000);
      elapsedTime.textContent = formatTime(elapsed);
    }
  }

  // Update log
  if (log && status.details) {
    const logLines = status.details
      .filter(d => d.status === "completed" || d.status === "failed")
      .map(d => {
        const icon = d.status === "completed" ? "✓" : "✗";
        const records = d.records_inserted || 0;
        return `${icon} ${d.symbol} ${d.timeframe}: ${records} records`;
      });
    
    log.innerHTML = logLines.map(line => `<div>${escapeHtml(line)}</div>`).join("");
    log.scrollTop = log.scrollHeight;
  }
}

/**
 * Format seconds to HH:MM:SS
 */
function formatTime(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  } else {
    return `${secs}s`;
  }
}

/**
 * Open enrichment modal
 */
function openEnrichModal() {
  if (selectedSymbols.size === 0) {
    showValidationError("Please select at least one symbol");
    return;
  }

  const modal = document.getElementById("enrich-modal");
  const displayDiv = document.getElementById("enrich-symbols");

  // Populate selected symbols
  const symbolsHTML = Array.from(selectedSymbols)
    .map((s) => `<span class="symbol-tag">${escapeHtml(s)}</span>`)
    .join("");
  
  displayDiv.innerHTML = symbolsHTML || '<span style="color: var(--text-secondary);">No symbols selected</span>';

  modal.style.display = "flex";
  
  // Set focus trap for accessibility
  setupModalFocusTrap(modal);

  // Focus dropdown for accessibility
  const dropdown = modal.querySelector("#enrich-timeframe");
  if (dropdown) {
    setTimeout(() => dropdown.focus(), 100);
  }
}

/**
 * Close enrichment modal
 */
function closeEnrichModal() {
  document.getElementById("enrich-modal").style.display = "none";
}

/**
 * Submit enrichment operation
 */
async function submitEnrich() {
  const symbols = getSelectedSymbols();
  const timeframe = document.getElementById("enrich-timeframe").value;

  // Validation
  const errors = [];

  if (!symbols || symbols.length === 0) {
    errors.push("No symbols selected");
  }
  if (!timeframe || timeframe === "") {
    errors.push("Please select a timeframe");
    // Add visual feedback to dropdown
    const dropdown = document.getElementById("enrich-timeframe");
    if (dropdown) {
      dropdown.style.borderColor = "var(--danger)";
      setTimeout(() => {
        dropdown.style.borderColor = "";
      }, 3000);
    }
  }

  if (errors.length > 0) {
    showValidationError(errors.join(", "));
    return;
  }

  try {
    console.log("Submitting enrichment:", { symbols, timeframe });

    // Build query string
    const params = new URLSearchParams();
    symbols.forEach((s) => params.append("symbols", s));
    params.append("timeframe", timeframe);

    const response = await fetch(
      `${CONFIG.API_BASE}/api/v1/enrich?${params.toString()}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }
    );

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();

    alert(
      `✓ Enrichment started for ${symbols.length} symbols\nJob ID: ${result.job_id}`
    );
    closeEnrichModal();
    clearSelection();
    refreshDashboard();
  } catch (error) {
    console.error("Enrichment error:", error);
    alert(`Error starting enrichment: ${error.message}`);
  }
}



/**
 * Setup collapsible sections (placeholder initialization)
 */
function setupCollapsibleSections() {
  // This is called from DOMContentLoaded
  // The actual toggle is handled by toggleSection()
}

/**
 * Helper: Escape HTML to prevent XSS
 */
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Helper: Get selected symbols array
 */
function getSelectedSymbols() {
  return Array.from(selectedSymbols);
}

/**
 * Helper: Format number with commas
 */
function formatNumber(num) {
  if (num === null || num === undefined) return "0";
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Helper: Format date/time
 */
function formatDate(dateString) {
  if (!dateString) return null;
  try {
    const date = new Date(dateString);
    if (isNaN(date)) return dateString;
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch {
    return dateString;
  }
}

/**
 * Helper: Calculate data age
 */
function calculateAge(dateString) {
  if (!dateString) return "Unknown";
  try {
    const date = new Date(dateString);
    const now = new Date();
    const hours = Math.round((now - date) / (1000 * 60 * 60));

    if (hours < 1) return "< 1 hour";
    if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'}`;
    const days = Math.round(hours / 24);
    return `${days} day${days === 1 ? '' : 's'}`;
  } catch {
    return "Unknown";
  }
}

/**
 * Helper: Update last update timestamp
 */
function updateTimestamp() {
  const element = document.getElementById("last-update");
  if (element && state.lastUpdate) {
    const time = state.lastUpdate.toLocaleTimeString('en-US');
    element.textContent = `Last updated: ${time} UTC`;
  }
}

/**
 * Helper: Handle API errors
 */
function handleError(error) {
  console.error(error.message);
  const statusBadge = document.getElementById("status-badge");
  if (statusBadge) {
    statusBadge.className = "status-badge critical";
    statusBadge.textContent = "● Error";
  }
}

/**
 * Update selection toolbar visibility
 */
function updateSelectionToolbar() {
  const toolbar = document.getElementById("selection-toolbar");
  const count = document.getElementById("selection-count");

  if (toolbar) {
    if (selectedSymbols.size > 0) {
      toolbar.style.display = "flex";
      if (count) count.textContent = `${selectedSymbols.size} symbol${selectedSymbols.size === 1 ? '' : 's'} selected`;
    } else {
      toolbar.style.display = "none";
    }
  }
}

/**
 * Clear all selections
 */
function clearSelection() {
  selectedSymbols.clear();
  persistSelectedSymbols();
  document.querySelectorAll(".symbol-table input[type='checkbox']").forEach(cb => {
    cb.checked = false;
  });
  updateSelectionToolbar();
}

/**
 * Setup symbol table click handlers for selection
 */
function setupSymbolTableClickHandlers() {
  document.addEventListener('change', (e) => {
    if (e.target.closest('.symbol-table tbody input[type="checkbox"]')) {
      const symbol = e.target.getAttribute('data-symbol');
      if (symbol) {
        if (e.target.checked) {
          selectedSymbols.add(symbol);
        } else {
          selectedSymbols.delete(symbol);
        }
        persistSelectedSymbols();
        updateSelectionToolbar();
      }
    }
  });
}

/**
 * Toggle select all checkboxes
 */
function toggleSelectAll(checkbox) {
  const allCheckboxes = document.querySelectorAll('.symbol-table tbody input[type="checkbox"]');
  allCheckboxes.forEach(cb => {
    cb.checked = checkbox.checked;
    const symbol = cb.getAttribute('data-symbol');
    if (symbol) {
      if (checkbox.checked) {
        selectedSymbols.add(symbol);
      } else {
        selectedSymbols.delete(symbol);
      }
    }
  });
  persistSelectedSymbols();
  updateSelectionToolbar();
}

/**
 * Setup search and filter for symbol table
 */
function setupSymbolSearch() {
  const searchBox = document.getElementById("symbol-search");
  const statusFilter = document.getElementById("status-filter");

  if (!searchBox || !statusFilter) return;

  const updateTable = () => {
    const searchTerm = searchBox.value.toLowerCase();
    const statusValue = statusFilter.value;

    const rows = document.querySelectorAll(".symbol-table tbody tr");
    let visibleCount = 0;

    rows.forEach(row => {
      const symbol = row.querySelector("td:nth-child(2)")?.textContent || "";
      const status = row.getAttribute("data-status") || "";

      const matchesSearch = symbol.toLowerCase().includes(searchTerm);
      const matchesStatus = !statusValue || status.toLowerCase() === statusValue.toLowerCase();

      if (matchesSearch && matchesStatus) {
        row.style.display = "";
        visibleCount++;
      } else {
        row.style.display = "none";
      }
    });
  };

  searchBox.addEventListener("input", updateTable);
  statusFilter.addEventListener("change", updateTable);
}

/**
 * Sort symbol table by column
 */
function sortTable(column) {
  const direction =
    symbolTableState.currentSort.column === column &&
    symbolTableState.currentSort.direction === "asc"
      ? "desc"
      : "asc";

  symbolTableState.currentSort = { column, direction };
  updateSortIndicators();
  renderSymbolTable();
}

/**
 * Render symbol table from cached data
 */
function renderSymbolTable() {
  const container = document.getElementById("symbol-tbody");
  let symbols = [...symbolTableState.allSymbols];

  // Apply filters
  const searchTerm = document.getElementById("symbol-search")?.value.toLowerCase() || "";
  const statusFilter = document.getElementById("status-filter")?.value || "";

  symbols = symbols.filter(sym => {
    const matchesSearch = sym.symbol.toLowerCase().includes(searchTerm);
    const matchesStatus = !statusFilter || sym.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Sort
  symbols.sort((a, b) => {
    let aVal = a[symbolTableState.currentSort.column];
    let bVal = b[symbolTableState.currentSort.column];

    if (typeof aVal === 'string') aVal = aVal.toLowerCase();
    if (typeof bVal === 'string') bVal = bVal.toLowerCase();

    const comparison = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    return symbolTableState.currentSort.direction === "asc" ? comparison : -comparison;
  });

  // Render rows
  if (symbols.length === 0) {
    container.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; padding: 40px; color: var(--text-secondary);">
          No symbols found
        </td>
      </tr>
    `;
  } else {
    container.innerHTML = symbols.map(sym => `
      <tr data-status="${sym.status}">
        <td>
          <input
            type="checkbox"
            data-symbol="${sym.symbol}"
            ${selectedSymbols.has(sym.symbol) ? 'checked' : ''}
          >
        </td>
        <td onclick="openAssetModal('${sym.symbol}')" style="cursor: pointer; color: var(--accent);">
          ${escapeHtml(sym.symbol)}
        </td>
        <td>${formatNumber(sym.records)}</td>
        <td>${(sym.validation_rate || 0).toFixed(1)}%</td>
        <td>${formatDate(sym.latest_data) || '---'}</td>
        <td>${calculateAge(sym.latest_data)}</td>
        <td>${(sym.timeframes || []).join(', ')}</td>
        <td>
          <span class="status-badge ${sym.status}">
            ${sym.status === 'healthy' ? '✓' : sym.status === 'warning' ? '⚠' : '✗'} ${sym.status}
          </span>
        </td>
      </tr>
    `).join("");
  }

  updateSymbolCount(symbols.length, symbolTableState.allSymbols.length);
}

/**
 * Update symbol count display
 */
function updateSymbolCount(displayed, total) {
  const element = document.getElementById("symbol-count");
  if (element) {
    if (displayed === total) {
      element.textContent = `${total} symbol${total === 1 ? '' : 's'}`;
    } else {
      element.textContent = `Showing ${displayed} of ${total} symbols`;
    }
  }
}

/**
 * Switch asset modal tab
 */
function switchAssetTab(tabName) {
  // Hide all tabs
  document.querySelectorAll(".asset-tab-content").forEach(tab => {
    tab.style.display = "none";
  });

  // Deactivate all buttons
  document.querySelectorAll(".asset-tab-btn").forEach(btn => {
    btn.classList.remove("active");
    btn.setAttribute("aria-selected", "false");
  });

  // Show selected tab
  const tab = document.getElementById(`tab-${tabName}`);
  if (tab) {
    tab.style.display = "block";
    const btn = document.querySelector(`[onclick="switchAssetTab('${tabName}')"]`);
    if (btn) {
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");
    }
  }
}

/**
 * Open asset modal
 */
function openAssetModal(symbol) {
  currentSymbol = symbol;
  const modal = document.getElementById("asset-modal");
  const titleEl = document.getElementById("modal-symbol");

  if (titleEl) titleEl.textContent = symbol;
  if (modal) modal.style.display = "flex";

  loadAssetDetails(symbol);
}

/**
 * Close asset modal
 */
function closeAssetModal() {
  const modal = document.getElementById("asset-modal");
  if (modal) modal.style.display = "none";
  currentSymbol = null;
}

/**
 * Load asset details
 */
async function loadAssetDetails(symbol) {
  try {
    // Check cache
    const now = Date.now();
    if (assetCache.has(symbol)) {
      const cached = assetCache.get(symbol);
      if (now - cached.timestamp < CACHE_TTL) {
        renderAssetDetails(cached.data);
        return;
      }
    }

    const response = await fetch(`${CONFIG.API_BASE}/api/v1/symbols/${symbol}/details`);
    if (!response.ok) throw new Error(`Failed to load details (${response.status})`);

    const data = await response.json();
    assetCache.set(symbol, { data, timestamp: now });
    renderAssetDetails(data);

  } catch (error) {
    console.error("Error loading asset details:", error);
    const gridEl = document.getElementById("overview-grid");
    if (gridEl) gridEl.innerHTML = `<p style="color: red;">Error loading details: ${error.message}</p>`;
  }
}

/**
 * Render asset overview
 */
function renderAssetDetails(data) {
  const gridEl = document.getElementById("overview-grid");
  if (!gridEl) return;

  const html = `
    <div class="overview-item">
      <span class="overview-label">Asset Class</span>
      <span class="overview-value">${escapeHtml(data.asset_class || '---')}</span>
    </div>
    <div class="overview-item">
      <span class="overview-label">Total Records</span>
      <span class="overview-value">${formatNumber(data.total_records || 0)}</span>
    </div>
    <div class="overview-item">
      <span class="overview-label">Latest Data</span>
      <span class="overview-value">${formatDate(data.latest_data) || '---'}</span>
    </div>
    <div class="overview-item">
      <span class="overview-label">Validation Rate</span>
      <span class="overview-value">${(data.validation_rate || 0).toFixed(1)}%</span>
    </div>
  `;

  gridEl.innerHTML = html;

  // Load timeframes
  loadTimeframeDetails(data.symbol);
}

/**
 * Load timeframe details for asset
 */
async function loadTimeframeDetails(symbol) {
  try {
    const response = await fetch(`${CONFIG.API_BASE}/api/v1/symbols/${symbol}/timeframes`);
    if (!response.ok) return;

    const data = await response.json();
    const tbody = document.getElementById("timeframes-tbody");
    if (!tbody) return;

    tbody.innerHTML = (data.timeframes || []).map(tf => `
      <tr>
        <td>${escapeHtml(tf.timeframe)}</td>
        <td>${formatNumber(tf.records)}</td>
        <td>${formatDate(tf.latest) || '---'}</td>
        <td><span class="status-badge ${tf.status}">${tf.status}</span></td>
      </tr>
    `).join("");

  } catch (error) {
    console.warn("Could not load timeframe details:", error);
  }
}

/**
 * Load and display candle data
 */
async function loadCandleData(symbol, timeframe) {
  try {
    const response = await fetch(`${CONFIG.API_BASE}/api/v1/symbols/${symbol}/candles/${timeframe}?limit=100`);
    if (!response.ok) throw new Error(`Failed to load candles (${response.status})`);

    const data = await response.json();
    const tbody = document.getElementById("candles-tbody");
    if (!tbody) return;

    const candles = data.candles || [];
    document.getElementById("candle-count").textContent = `${candles.length} candles`;

    tbody.innerHTML = candles.map(c => `
      <tr>
        <td>${formatDate(c.time)}</td>
        <td>${c.open?.toFixed(2) || '---'}</td>
        <td>${c.high?.toFixed(2) || '---'}</td>
        <td>${c.low?.toFixed(2) || '---'}</td>
        <td>${c.close?.toFixed(2) || '---'}</td>
        <td>${formatNumber(c.volume)}</td>
        <td>${c.vwap?.toFixed(2) || '---'}</td>
        <td><span class="status-badge ${c.quality_score >= 0.95 ? 'healthy' : 'warning'}">
          ${(c.quality_score * 100).toFixed(0)}%
        </span></td>
      </tr>
    `).join("");

  } catch (error) {
    console.error("Error loading candles:", error);
    const tbody = document.getElementById("candles-tbody");
    if (tbody) tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: red;">${escapeHtml(error.message)}</td></tr>`;
  }
}

/**
 * Load more candles
 */
async function loadMoreCandles(symbol) {
  const timeframe = document.getElementById("candle-timeframe")?.value || "1h";
  await loadCandleData(symbol, timeframe);
}

/**
 * View API docs
 */
function viewDocs() {
  window.open(`${CONFIG.API_BASE}/docs`, "_blank");
}

/**
 * Run tests
 */
async function runAllTests() {
  const container = document.getElementById("test-container");
  if (!container) return;

  container.style.display = "block";
  document.getElementById("test-status").textContent = "Running tests...";
  document.getElementById("test-summary").textContent = "";
  document.getElementById("test-output").textContent = "";

  try {
    const response = await fetch(`${CONFIG.API_BASE}/api/v1/admin/tests`, { method: "POST" });
    if (!response.ok) throw new Error(`Test endpoint returned ${response.status}`);

    const data = await response.json();
    document.getElementById("test-status").textContent = `Tests completed: ${data.passed} passed, ${data.failed} failed`;
    document.getElementById("test-summary").textContent = data.summary || "";
    document.getElementById("test-output").textContent = data.output?.join("\n") || "";

  } catch (error) {
    document.getElementById("test-status").textContent = `Error: ${escapeHtml(error.message)}`;
  }
}
