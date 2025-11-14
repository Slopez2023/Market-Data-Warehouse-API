# Dashboard UX Improvement Plan

**Status**: Approved ✓  
**Last Updated**: November 14, 2025  
**Owner**: Stephen Lopez  
**Duration**: 7 days (3 phases)  
**Priority**: High

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Strategic Decisions](#strategic-decisions)
4. [Phase 1: Foundation & Information Architecture](#phase-1-foundation--information-architecture)
5. [Phase 2: Bulk Actions & Controls](#phase-2-bulk-actions--controls)
6. [Phase 3: Polish & Admin Features](#phase-3-polish--admin-features)
7. [Best Practices & Standards](#best-practices--standards)
8. [Testing Strategy](#testing-strategy)
9. [Success Criteria](#success-criteria)
10. [Implementation Checklist](#implementation-checklist)

---

## Executive Summary

### The Problem
The current dashboard functions as a **passive monitoring tool** but lacks **operational controls**. Users can view status but cannot act on it. Information is disorganized, with redundant displays and missing features like bulk operations.

### The Solution
Three-phase UX redesign focusing on:
1. **Information reorganization** (sections by use case)
2. **Bulk action capabilities** (backfill, enrichment at scale)
3. **Admin controls & polish** (keyboard shortcuts, collapsible sections, empty states)

### Expected Outcome
- Reduce time to perform operations by 60%
- Eliminate user confusion about what to do next
- Create a true control center, not just a status page
- Maintain clean, professional design

---

## Current State Analysis

### Strengths
- ✓ Clean, modern dark theme
- ✓ Responsive metric cards and visual hierarchy
- ✓ Functional search + filter on symbol table
- ✓ Modal system for per-symbol details
- ✓ Proper error handling and retry logic
- ✓ Caching strategy (1-minute TTL)

### Critical Issues (UX-Blocking)

| Issue | Severity | Impact |
|-------|----------|--------|
| Empty "Action" column in symbol table | High | Confuses users, suggests missing functionality |
| No bulk operation capabilities | High | Can't backfill/enrich multiple symbols at once |
| Symbol table not clickable | High | Users must manually scroll to find data |
| Modal has no action buttons | High | View data but can't act on it |
| Redundant status displays (3 places) | Medium | Wastes space, confuses hierarchy |
| No admin controls visible | Medium | Manual operations require backend access |
| Collapsible sections missing | Medium | Too much information on one page |
| Inconsistent status icons | Low | Visual inconsistency (emoji vs symbols) |

### Information Architecture Problems

**Current Order** (not aligned with user workflow):
1. Alerts
2. Metrics (6 cards)
3. Enrichment Scheduler
4. Pipeline Metrics (3 cards)
5. Recent Jobs
6. System Health
7. Symbol Quality Table
8. System Resources
9. Test Suite
10. Quick Actions

**User Mental Model**:
1. "Is the system healthy?" → Status & Alerts
2. "What do I need to do?" → Quick Actions
3. "Which symbols need work?" → Symbol Table with Bulk Ops
4. "How is it performing?" → Monitoring (Pipeline, Health, Resources)
5. "How do I debug?" → Admin Panel (Tests, Manual Controls)

---

## Strategic Decisions

### Decision 1: Scope Approach ✓ APPROVED
**Chosen**: Option A - Evolutionary redesign
- Reorder sections, add features incrementally
- Medium effort, high immediate impact (80%)
- Maintains existing functionality while improving UX

---

### Decision 2: Information Hierarchy ✓ APPROVED

**New Section Order** (by user priority):
```
TIER 1 - At-a-Glance (always visible)
├─ System Status (simplified)
└─ Critical Alerts Only

TIER 2 - Control & Action (primary workflow)
├─ Quick Actions Toolbar
├─ Symbol Management Table (with bulk ops)
└─ Symbol Detail Modal

TIER 3 - Monitoring & Observability (collapsible)
├─ Enrichment Status
├─ Pipeline Metrics
├─ Recent Jobs
└─ System Health

TIER 4 - Admin & Advanced (collapsible)
├─ Admin Control Panel
├─ System Resources
└─ Test Suite
```

---

### Decision 3: Three-Phase Implementation ✓ APPROVED

| Phase | Duration | Focus | Deliverable |
|-------|----------|-------|-------------|
| **Phase 1** | Days 1-2 | Reorganize structure, fix core UX | Clean foundation, working table, simplified status |
| **Phase 2** | Days 3-4 | Bulk actions, control panel | Operational capabilities |
| **Phase 3** | Days 5-7 | Polish, admin features, accessibility | Production-ready dashboard |

---

### Decision 4: Feature Scope ✓ APPROVED

**What Users Can Do** (in priority order):
1. ✓ See system status at a glance
2. ✓ Find symbols quickly (search + filter)
3. ✓ Click symbol to see details
4. ✓ Select multiple symbols
5. ✓ Backfill selected symbols (with date range)
6. ✓ Trigger re-enrichment for selected symbols
7. ✓ Manually start/stop scheduler
8. ✓ View bulk operation progress
9. ✓ Use keyboard shortcuts (phase 3)

**Explicitly Out of Scope** (for now):
- ✗ Delete symbols
- ✗ Export data
- ✗ Modify configuration
- ✗ User authentication
- ✗ Real-time WebSocket updates

---

### Decision 5: Backend API Requirements ✓ APPROVED

**APIs to Verify/Create** (before Phase 2):

```
POST /api/v1/backfill
  body: { symbols: ["AAPL", "MSFT"], start_date: "2025-01-01", end_date: "2025-11-14" }
  returns: { job_id: "uuid", status: "queued", symbols_count: 2 }

POST /api/v1/enrich
  body: { symbols: ["AAPL", "MSFT"], timeframe: "1h" }
  returns: { job_id: "uuid", status: "queued", symbols_count: 2 }

GET /api/v1/jobs/{job_id}
  returns: { id: "uuid", status: "running|completed|failed", progress: 0-100, errors: [] }

POST /api/v1/scheduler/start
  returns: { status: "started" }

POST /api/v1/scheduler/stop
  returns: { status: "stopped" }
```

**If these don't exist**: Create mock implementations in Phase 2 that return success responses.

---

## Phase 1: Foundation & Information Architecture

**Duration**: Days 1-2  
**Deliverables**: Clean HTML/CSS structure, working symbol table, simplified status  
**No Backend Changes Needed**

### Phase 1.1: HTML Structure Reorganization

**File**: `/dashboard/index.html`

#### Step 1.1.1: Create New Section Order
Move sections in this order:

```html
<!-- TIER 1: STATUS & ALERTS -->
<header class="header"> ... </header>
<section id="alerts" class="alerts"></section>
<section class="status-summary"> ... </section>

<!-- TIER 2: ACTIONS & SYMBOL MANAGEMENT -->
<section class="quick-actions-bar"> ... (new) ... </section>
<section class="symbol-management">
  <h2>Symbol Quality & Status</h2>
  <div class="symbol-controls"> ... </div>
  <table id="symbol-table"> ... </table>
  <div id="asset-modal"> ... </div>
</section>

<!-- TIER 3: MONITORING (collapsible) -->
<section class="monitoring" data-collapsible="true">
  <h2>Enrichment Status</h2> ...
  <h2>Pipeline Metrics</h2> ...
  <h2>Recent Jobs</h2> ...
  <h2>System Health</h2> ...
</section>

<!-- TIER 4: ADMIN (collapsible) -->
<section class="admin-section" data-collapsible="true">
  <h2>Admin Control Panel</h2> ... (new)
  <h2>System Resources</h2> ...
  <h2>Test Suite</h2> ...
</section>

<footer class="footer"> ... </footer>
```

#### Step 1.1.2: Remove Redundant Elements
- Remove "Scheduler Status" metric card (move to Enrichment Status section)
- Remove "API Status" metric card (keep in status-summary only)
- Move "Latest Data" to enrichment section

#### Step 1.1.3: Simplify Status Summary
Replace the 6-card metrics-grid with a smaller status display:

```html
<section class="status-summary">
  <div class="status-header">
    <div class="status-badge-large" id="overall-status">🟢 Healthy</div>
    <div class="status-details">
      <p><strong>Response Time</strong>: <span id="response-time">-- ms</span></p>
      <p><strong>Records</strong>: <span id="total-records">--</span></p>
      <p><strong>Quality</strong>: <span id="validation-rate">--%</span></p>
    </div>
  </div>
</section>
```

#### Step 1.1.4: Create Quick Actions Bar
```html
<section class="quick-actions-bar">
  <h2>Quick Actions</h2>
  <div class="action-buttons">
    <button class="btn btn-primary" onclick="refreshDashboard()">Refresh Now</button>
    <button class="btn btn-secondary" onclick="triggerManualBackfill()">Manual Backfill...</button>
    <button class="btn btn-secondary" onclick="viewAdminPanel()">Admin Panel</button>
    <button class="btn btn-secondary" onclick="viewDocs()">API Docs</button>
  </div>
</section>
```

#### Step 1.1.5: Fix Symbol Table
- Remove empty "Action" column from HTML
- Add `data-symbol` attribute to each row
- Add row click handlers (CSS `:hover` + JS)
- Update column count in colspan statements

**Before**:
```html
<th onclick="sortTable('status')">Status</th>
<th>Action</th>
```

**After**:
```html
<th onclick="sortTable('status')">Status</th>
```

#### Step 1.1.6: Add Collapsible Container Structure
```html
<section class="monitoring collapsible-section" data-section="monitoring">
  <div class="section-header" onclick="toggleSection('monitoring')">
    <h2>Monitoring & Observability</h2>
    <span class="toggle-icon">▼</span>
  </div>
  <div class="section-content">
    <!-- all monitoring subsections inside -->
  </div>
</section>
```

---

### Phase 1.2: CSS Updates

**File**: `/dashboard/style.css`

#### Step 1.2.1: Add New Classes
```css
/* Status Summary - simplified version */
.status-summary {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 24px;
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  gap: 32px;
}

.status-badge-large {
  font-size: 28px;
  font-weight: 700;
  color: var(--primary);
}

.status-details {
  display: flex;
  gap: 24px;
}

.status-details p {
  font-size: 14px;
  color: var(--text-secondary);
}

.status-details strong {
  color: var(--text-primary);
  display: block;
  font-size: 12px;
  text-transform: uppercase;
  margin-bottom: 4px;
}

/* Quick Actions Bar */
.quick-actions-bar {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  border-top: 4px solid var(--primary);
  padding: 24px;
  margin-bottom: 24px;
}

.quick-actions-bar h2 {
  margin-bottom: 16px;
}

.action-buttons {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

/* Collapsible Sections */
.collapsible-section {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  margin-bottom: 24px;
  overflow: hidden;
  transition: all 0.3s ease;
}

.collapsible-section.collapsed .section-content {
  display: none;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px;
  cursor: pointer;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.3s ease;
  user-select: none;
}

.section-header:hover {
  background: rgba(15, 147, 112, 0.05);
}

.section-header h2 {
  margin: 0;
}

.toggle-icon {
  display: inline-block;
  transition: transform 0.3s ease;
  font-size: 12px;
  color: var(--text-secondary);
}

.collapsible-section.collapsed .toggle-icon {
  transform: rotate(-90deg);
}

.section-content {
  padding: 24px;
  display: block;
}

/* Symbol Management */
.symbol-management {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  border-top: 4px solid var(--primary);
  padding: 24px;
  margin-bottom: 24px;
}

/* Symbol Table Row Hover & Click */
.symbol-table tbody tr {
  cursor: pointer;
  transition: all 0.2s ease;
}

.symbol-table tbody tr:hover {
  background: rgba(15, 147, 112, 0.12);
  box-shadow: inset 0 0 0 1px rgba(15, 147, 112, 0.2);
}

/* Admin Section Styling */
.admin-section {
  background: var(--bg-card);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 10px;
  margin-bottom: 24px;
  overflow: hidden;
}

.admin-section .section-header {
  border-bottom: 1px solid rgba(239, 68, 68, 0.2);
  padding: 20px 24px;
}

.admin-section .section-header h2 {
  color: var(--danger);
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .status-details {
    flex-direction: column;
    gap: 12px;
  }

  .action-buttons {
    flex-direction: column;
  }

  .action-buttons .btn {
    width: 100%;
    text-align: center;
  }
}
```

#### Step 1.2.2: Update Responsive Behavior
- Ensure collapsible sections work on mobile
- Stack action buttons vertically on <600px
- Adjust status summary to single column on mobile

---

### Phase 1.3: JavaScript Updates

**File**: `/dashboard/script.js`

#### Step 1.3.1: Add Collapsible Section Toggle
```javascript
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
```

#### Step 1.3.2: Add Row Click Handler to Symbol Table
```javascript
/**
 * Setup symbol table row clicks
 */
function setupSymbolTableClickHandlers() {
  const tbody = document.getElementById('symbol-tbody');
  if (tbody) {
    tbody.addEventListener('click', (e) => {
      const row = e.target.closest('tr');
      if (row && !row.classList.contains('header')) {
        const symbolCell = row.querySelector('.symbol-name');
        if (symbolCell) {
          const symbol = symbolCell.textContent;
          openAssetModal(symbol);
        }
      }
    });
  }
}

// Call in renderSymbolTable() after HTML is updated
```

#### Step 1.3.3: Update Status Summary Display
```javascript
/**
 * Update simplified status summary
 */
function updateStatusSummary(health, status) {
  const isHealthy = health.status === 'healthy';
  const badge = document.getElementById('overall-status');
  
  if (badge) {
    badge.textContent = isHealthy ? '🟢 Healthy' : '🔴 Critical';
    badge.className = `status-badge-large ${isHealthy ? 'healthy' : 'critical'}`;
  }
  
  // Update inline metrics
  updateMetric('response-time', Math.round(health.response_time_ms || 0));
  updateMetric('total-records', formatNumber(status.database?.total_records || 0));
  updateMetric('validation-rate', (status.database?.validation_rate_pct || 0).toFixed(1));
}
```

#### Step 1.3.4: Initialize Phase 1 on Page Load
```javascript
// In DOMContentLoaded:
document.addEventListener("DOMContentLoaded", () => {
  console.log("Dashboard initializing...");
  restoreSectionStates();           // NEW
  setupSymbolTableClickHandlers();   // NEW
  setupSymbolSearch();
  refreshDashboard();
  setInterval(refreshDashboard, CONFIG.REFRESH_INTERVAL);
});
```

---

### Phase 1 Verification Checklist

- [ ] HTML sections reordered as per spec
- [ ] Redundant metric cards removed
- [ ] Status summary simplified (3 metrics only)
- [ ] Quick Actions bar visible
- [ ] "Action" column removed from symbol table
- [ ] Symbol table rows are clickable
- [ ] Collapsible sections toggle properly
- [ ] Section state persists (localStorage)
- [ ] CSS looks clean on desktop & tablet
- [ ] Mobile layout stacks properly
- [ ] All existing functionality still works
- [ ] No console errors

---

## Phase 2: Bulk Actions & Controls

**Duration**: Days 3-4  
**Deliverables**: Bulk operation UI, Admin Control Panel, Backend API integration  
**Requires**: Backend APIs verified (or mocked)

### Phase 2.1: Symbol Selection System

**File**: `/dashboard/style.css` + `/dashboard/script.js` + `/dashboard/index.html`

#### Step 2.1.1: Add Checkbox Column to Symbol Table
```html
<!-- In symbol-table thead -->
<th style="width: 40px;">
  <input type="checkbox" id="select-all-symbols" onchange="toggleSelectAll(this)">
</th>

<!-- In symbol-table tbody row template -->
<td style="width: 40px;">
  <input type="checkbox" class="symbol-checkbox" data-symbol="${symbol.symbol}">
</td>
```

#### Step 2.1.2: Add Selection Toolbar
```html
<!-- Insert before symbol table -->
<div class="symbol-selection-toolbar" id="selection-toolbar" style="display: none;">
  <div class="toolbar-left">
    <span id="selection-count">0 symbols selected</span>
  </div>
  <div class="toolbar-right">
    <button class="btn btn-sm btn-secondary" onclick="clearSelection()">Clear</button>
    <button class="btn btn-sm btn-primary" onclick="openBackfillModal()">Backfill Selected</button>
    <button class="btn btn-sm btn-primary" onclick="openEnrichModal()">Re-Enrich Selected</button>
  </div>
</div>
```

#### Step 2.1.3: Add CSS for Toolbar
```css
.symbol-selection-toolbar {
  background: rgba(15, 147, 112, 0.1);
  border: 1px solid var(--primary);
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toolbar-left {
  color: var(--text-secondary);
  font-size: 14px;
}

.toolbar-right {
  display: flex;
  gap: 8px;
}

.btn-sm {
  padding: 8px 12px;
  font-size: 13px;
}

/* Highlight selected rows */
.symbol-table tbody tr.selected {
  background: rgba(15, 147, 112, 0.15);
  box-shadow: inset 0 0 0 1px var(--primary);
}
```

#### Step 2.1.4: Add JavaScript for Selection Management
```javascript
/**
 * Track selected symbols
 */
let selectedSymbols = new Set();

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
}

/**
 * Toggle select all
 */
function toggleSelectAll(checkbox) {
  const checkboxes = document.querySelectorAll('.symbol-checkbox');
  checkboxes.forEach(cb => {
    cb.checked = checkbox.checked;
    toggleSymbolSelection(cb);
  });
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
```

---

### Phase 2.2: Modal Dialogs for Bulk Operations

**File**: `/dashboard/index.html` + `/dashboard/style.css`

#### Step 2.2.1: Create Backfill Modal
```html
<!-- Add after asset-modal -->
<div id="backfill-modal" class="modal" style="display: none;">
  <div class="modal-overlay" onclick="closeBackfillModal()"></div>
  <div class="modal-content modal-form">
    <div class="modal-header">
      <h2>Backfill Data</h2>
      <button class="modal-close" onclick="closeBackfillModal()">×</button>
    </div>

    <div class="form-group">
      <label for="backfill-symbols">Symbols</label>
      <div id="backfill-symbols" class="selected-symbols-display">
        <!-- Will be populated by JS -->
      </div>
    </div>

    <div class="form-group">
      <label for="backfill-start-date">Start Date</label>
      <input type="date" id="backfill-start-date" class="form-input">
    </div>

    <div class="form-group">
      <label for="backfill-end-date">End Date</label>
      <input type="date" id="backfill-end-date" class="form-input">
    </div>

    <div class="form-group">
      <label for="backfill-timeframes">Timeframes</label>
      <div id="backfill-timeframes" class="checkbox-group">
        <label><input type="checkbox" value="5m" checked> 5m</label>
        <label><input type="checkbox" value="15m" checked> 15m</label>
        <label><input type="checkbox" value="1h" checked> 1h</label>
        <label><input type="checkbox" value="1d" checked> 1d</label>
      </div>
    </div>

    <div class="form-actions">
      <button class="btn btn-secondary" onclick="closeBackfillModal()">Cancel</button>
      <button class="btn btn-primary" onclick="submitBackfill()">Start Backfill</button>
    </div>
  </div>
</div>
```

#### Step 2.2.2: Create Enrichment Modal
```html
<!-- Similar to backfill, simplified -->
<div id="enrich-modal" class="modal" style="display: none;">
  <div class="modal-overlay" onclick="closeEnrichModal()"></div>
  <div class="modal-content modal-form">
    <div class="modal-header">
      <h2>Re-Enrich Data</h2>
      <button class="modal-close" onclick="closeEnrichModal()">×</button>
    </div>

    <div class="form-group">
      <label for="enrich-symbols">Symbols</label>
      <div id="enrich-symbols" class="selected-symbols-display"></div>
    </div>

    <div class="form-group">
      <label for="enrich-timeframe">Timeframe</label>
      <select id="enrich-timeframe" class="form-input">
        <option value="5m">5 Minutes</option>
        <option value="15m">15 Minutes</option>
        <option value="1h" selected>1 Hour</option>
        <option value="1d">Daily</option>
      </select>
    </div>

    <div class="form-actions">
      <button class="btn btn-secondary" onclick="closeEnrichModal()">Cancel</button>
      <button class="btn btn-primary" onclick="submitEnrich()">Start Enrichment</button>
    </div>
  </div>
</div>
```

#### Step 2.2.3: Add Form Styling
```css
.modal-form {
  max-width: 500px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  color: var(--text-secondary);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
  font-weight: 600;
}

.form-input {
  width: 100%;
  padding: 10px 12px;
  background: var(--bg-dark);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  font-family: inherit;
}

.form-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(15, 147, 112, 0.1);
}

.selected-symbols-display {
  background: rgba(15, 147, 112, 0.05);
  border: 1px solid rgba(15, 147, 112, 0.2);
  border-radius: 6px;
  padding: 12px;
  max-height: 150px;
  overflow-y: auto;
}

.selected-symbols-display .symbol-tag {
  display: inline-block;
  background: var(--primary);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  margin: 4px;
  font-size: 12px;
  font-weight: 600;
}

.checkbox-group {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.checkbox-group label {
  display: flex;
  align-items: center;
  gap: 8px;
  text-transform: none;
  text-transform: uppercase;
  letter-spacing: 0;
  margin-bottom: 0;
}

.checkbox-group input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.form-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--border-color);
}
```

#### Step 2.2.4: Add Modal JavaScript
```javascript
/**
 * Open backfill modal
 */
function openBackfillModal() {
  const symbols = getSelectedSymbols();
  if (symbols.length === 0) {
    alert('Please select at least one symbol');
    return;
  }

  document.getElementById('backfill-modal').style.display = 'flex';
  populateSelectedSymbols('backfill-symbols', symbols);
  
  // Set date defaults
  const endDate = new Date();
  const startDate = new Date(endDate.getTime() - 7 * 24 * 60 * 60 * 1000); // 7 days ago
  
  document.getElementById('backfill-start-date').value = startDate.toISOString().split('T')[0];
  document.getElementById('backfill-end-date').value = endDate.toISOString().split('T')[0];
}

/**
 * Close backfill modal
 */
function closeBackfillModal() {
  document.getElementById('backfill-modal').style.display = 'none';
}

/**
 * Submit backfill request
 */
async function submitBackfill() {
  const symbols = getSelectedSymbols();
  const startDate = document.getElementById('backfill-start-date').value;
  const endDate = document.getElementById('backfill-end-date').value;
  
  const timeframes = Array.from(document.querySelectorAll('#backfill-timeframes input:checked'))
    .map(input => input.value);

  if (!startDate || !endDate) {
    alert('Please select both start and end dates');
    return;
  }

  if (timeframes.length === 0) {
    alert('Please select at least one timeframe');
    return;
  }

  try {
    const response = await fetch(`${CONFIG.API_BASE}/api/v1/backfill`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbols,
        start_date: startDate,
        end_date: endDate,
        timeframes,
      }),
    });

    if (!response.ok) throw new Error(`API error: ${response.status}`);
    
    const result = await response.json();
    alert(`✓ Backfill started (Job ID: ${result.job_id})`);
    closeBackfillModal();
    clearSelection();
    refreshDashboard();
  } catch (error) {
    console.error('Backfill error:', error);
    alert(`✗ Backfill failed: ${error.message}`);
  }
}

/**
 * Open enrichment modal
 */
function openEnrichModal() {
  const symbols = getSelectedSymbols();
  if (symbols.length === 0) {
    alert('Please select at least one symbol');
    return;
  }

  document.getElementById('enrich-modal').style.display = 'flex';
  populateSelectedSymbols('enrich-symbols', symbols);
}

/**
 * Close enrichment modal
 */
function closeEnrichModal() {
  document.getElementById('enrich-modal').style.display = 'none';
}

/**
 * Submit enrichment request
 */
async function submitEnrich() {
  const symbols = getSelectedSymbols();
  const timeframe = document.getElementById('enrich-timeframe').value;

  try {
    const response = await fetch(`${CONFIG.API_BASE}/api/v1/enrich`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbols,
        timeframe,
      }),
    });

    if (!response.ok) throw new Error(`API error: ${response.status}`);
    
    const result = await response.json();
    alert(`✓ Enrichment started (Job ID: ${result.job_id})`);
    closeEnrichModal();
    clearSelection();
    refreshDashboard();
  } catch (error) {
    console.error('Enrichment error:', error);
    alert(`✗ Enrichment failed: ${error.message}`);
  }
}

/**
 * Populate selected symbols display
 */
function populateSelectedSymbols(elementId, symbols) {
  const container = document.getElementById(elementId);
  container.innerHTML = symbols
    .map(symbol => `<span class="symbol-tag">${escapeHtml(symbol)}</span>`)
    .join('');
}
```

---

### Phase 2.3: Admin Control Panel

**File**: `/dashboard/index.html` + `/dashboard/script.js`

#### Step 2.3.1: Add Admin Panel HTML
```html
<!-- Inside admin-section, after the section-header -->
<div class="section-content">
  <div class="admin-panel">
    
    <!-- Scheduler Controls -->
    <div class="admin-card">
      <h4>Scheduler Controls</h4>
      <p class="admin-description">Start or stop the automatic backfill scheduler</p>
      <div class="admin-controls">
        <button class="btn btn-sm btn-primary" onclick="startScheduler()">Start Scheduler</button>
        <button class="btn btn-sm btn-secondary" onclick="stopScheduler()">Stop Scheduler</button>
      </div>
      <div id="scheduler-status-admin" class="status-line">Status: --</div>
    </div>

    <!-- Manual Operations -->
    <div class="admin-card">
      <h4>Manual Operations</h4>
      <p class="admin-description">Trigger operations without using bulk selection</p>
      <div class="admin-controls">
        <button class="btn btn-sm btn-secondary" onclick="openManualBackfillModal()">Backfill All...</button>
        <button class="btn btn-sm btn-secondary" onclick="openManualEnrichModal()">Enrich All...</button>
      </div>
    </div>

    <!-- Maintenance -->
    <div class="admin-card">
      <h4>Maintenance</h4>
      <p class="admin-description">Database and cache operations</p>
      <div class="admin-controls">
        <button class="btn btn-sm btn-secondary" onclick="clearQueryCache()">Clear Cache</button>
        <button class="btn btn-sm btn-secondary" onclick="vacuumDatabase()">Vacuum Database</button>
        <button class="btn btn-sm btn-secondary" onclick="reindexDatabase()">Reindex DB</button>
      </div>
    </div>

  </div>
</div>
```

#### Step 2.3.2: Add Admin Panel CSS
```css
.admin-panel {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.admin-card {
  background: rgba(239, 68, 68, 0.05);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 8px;
  padding: 16px;
}

.admin-card h4 {
  color: var(--danger);
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 8px;
}

.admin-description {
  color: var(--text-secondary);
  font-size: 12px;
  margin-bottom: 16px;
}

.admin-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.status-line {
  padding-top: 12px;
  border-top: 1px solid rgba(239, 68, 68, 0.1);
  font-size: 12px;
  color: var(--text-secondary);
}
```

#### Step 2.3.3: Add Admin Functions to JavaScript
```javascript
/**
 * Start scheduler
 */
async function startScheduler() {
  try {
    const response = await fetch(`${CONFIG.API_BASE}/api/v1/scheduler/start`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    alert('✓ Scheduler started');
    refreshDashboard();
  } catch (error) {
    alert(`✗ Failed to start scheduler: ${error.message}`);
  }
}

/**
 * Stop scheduler
 */
async function stopScheduler() {
  if (!confirm('Are you sure? This will stop automatic backfills.')) return;
  
  try {
    const response = await fetch(`${CONFIG.API_BASE}/api/v1/scheduler/stop`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    alert('✓ Scheduler stopped');
    refreshDashboard();
  } catch (error) {
    alert(`✗ Failed to stop scheduler: ${error.message}`);
  }
}

/**
 * Clear query cache
 */
async function clearQueryCache() {
  if (!confirm('Clear all cached queries?')) return;
  
  try {
    const response = await fetch(`${CONFIG.API_BASE}/api/v1/cache/clear`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    alert('✓ Cache cleared');
    refreshDashboard();
  } catch (error) {
    alert(`✗ Failed to clear cache: ${error.message}`);
  }
}

/**
 * Vacuum database
 */
async function vacuumDatabase() {
  if (!confirm('Vacuum database? This may take a moment.')) return;
  
  try {
    const response = await fetch(`${CONFIG.API_BASE}/api/v1/database/vacuum`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    alert('✓ Database vacuumed');
  } catch (error) {
    alert(`✗ Failed to vacuum database: ${error.message}`);
  }
}

/**
 * Reindex database
 */
async function reindexDatabase() {
  if (!confirm('Reindex database? This may take a moment.')) return;
  
  try {
    const response = await fetch(`${CONFIG.API_BASE}/api/v1/database/reindex`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    alert('✓ Database reindexed');
  } catch (error) {
    alert(`✗ Failed to reindex database: ${error.message}`);
  }
}

/**
 * Open manual backfill modal (for all symbols or custom list)
 */
function openManualBackfillModal() {
  // Similar to bulk backfill, but without pre-selected symbols
  document.getElementById('backfill-modal').style.display = 'flex';
  document.getElementById('backfill-symbols').innerHTML = '<span class="symbol-tag">All Symbols</span>';
}

/**
 * Open manual enrich modal (for all symbols or custom list)
 */
function openManualEnrichModal() {
  document.getElementById('enrich-modal').style.display = 'flex';
  document.getElementById('enrich-symbols').innerHTML = '<span class="symbol-tag">All Symbols</span>';
}
```

---

### Phase 2 Verification Checklist

- [ ] Checkboxes appear on symbol table
- [ ] Select/Deselect All works
- [ ] Selection toolbar appears when symbols selected
- [ ] Toolbar disappears when no symbols selected
- [ ] Selected rows are highlighted
- [ ] Selection persists while filtering/searching
- [ ] Backfill modal opens with selected symbols
- [ ] Enrichment modal opens with selected symbols
- [ ] Date picker defaults to sensible values (last 7 days)
- [ ] Form validation works (prevents empty submissions)
- [ ] API calls are made correctly
- [ ] User gets feedback (success/error messages)
- [ ] Admin panel is in collapsible section
- [ ] Scheduler start/stop buttons work
- [ ] Cache clearing works
- [ ] No console errors
- [ ] Modals can be closed with X button and ESC key
- [ ] Form looks good on mobile

---

## Phase 3: Polish & Admin Features

**Duration**: Days 5-7  
**Deliverables**: Keyboard shortcuts, empty states, final styling, accessibility  
**No Backend Changes Needed**

### Phase 3.1: Keyboard Shortcuts

**File**: `/dashboard/script.js`

#### Step 3.1.1: Create Shortcut Handler
```javascript
/**
 * Setup keyboard shortcuts
 */
function setupKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Ignore if user is typing in input
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
      return;
    }

    const ctrlOrCmd = e.ctrlKey || e.metaKey;

    // Ctrl/Cmd + R = Refresh dashboard
    if (ctrlOrCmd && e.key.toLowerCase() === 'r') {
      e.preventDefault();
      refreshDashboard();
      return;
    }

    // ? = Show help modal
    if (e.key === '?') {
      e.preventDefault();
      showKeyboardHelp();
      return;
    }

    // S = Focus search box
    if (e.key.toLowerCase() === 's') {
      e.preventDefault();
      const searchBox = document.getElementById('symbol-search');
      if (searchBox) searchBox.focus();
      return;
    }

    // ESC = Close modals
    if (e.key === 'Escape') {
      closeAssetModal();
      closeBackfillModal();
      closeEnrichModal();
      return;
    }

    // B = Open backfill modal (if symbols selected)
    if (e.key.toLowerCase() === 'b' && selectedSymbols.size > 0) {
      e.preventDefault();
      openBackfillModal();
      return;
    }

    // E = Open enrich modal (if symbols selected)
    if (e.key.toLowerCase() === 'e' && selectedSymbols.size > 0) {
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
    <div id="help-modal" class="modal" style="display: flex;">
      <div class="modal-overlay" onclick="closeHelpModal()"></div>
      <div class="modal-content">
        <div class="modal-header">
          <h2>Keyboard Shortcuts</h2>
          <button class="modal-close" onclick="closeHelpModal()">×</button>
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
            <span class="shortcut-desc">Open enrich modal (with symbols selected)</span>
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
  document.body.insertAdjacentHTML('beforeend', helpHTML);
}

function closeHelpModal() {
  const modal = document.getElementById('help-modal');
  if (modal) modal.remove();
}

// Call in DOMContentLoaded
setupKeyboardShortcuts();
```

#### Step 3.1.2: Add Shortcut CSS
```css
.shortcuts-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.shortcut-item {
  display: flex;
  gap: 24px;
  align-items: center;
  padding: 12px;
  background: rgba(15, 147, 112, 0.05);
  border-radius: 6px;
}

.shortcut-key {
  font-family: 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
  min-width: 120px;
  background: rgba(15, 147, 112, 0.1);
  padding: 4px 8px;
  border-radius: 4px;
}

.shortcut-desc {
  color: var(--text-secondary);
  font-size: 13px;
}
```

---

### Phase 3.2: Empty State Improvements

**File**: `/dashboard/style.css` + `/dashboard/script.js`

#### Step 3.2.1: Create Empty State Components
```css
.empty-state {
  text-align: center;
  padding: 48px 24px;
  color: var(--text-secondary);
}

.empty-state-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.empty-state-description {
  font-size: 13px;
  margin-bottom: 24px;
  max-width: 400px;
  margin-left: auto;
  margin-right: auto;
}

.empty-state-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}
```

#### Step 3.2.2: Update Symbol Table Empty State
**Before**:
```html
<tr><td colspan="8" style="text-align: center; color: var(--text-secondary);">No symbols in database</td></tr>
```

**After**:
```javascript
function renderEmptySymbolState() {
  return `
    <tr>
      <td colspan="8">
        <div class="empty-state">
          <div class="empty-state-icon">📊</div>
          <div class="empty-state-title">No Symbols Loaded</div>
          <p class="empty-state-description">
            No symbols are currently in the database. Start by backfilling data.
          </p>
          <div class="empty-state-actions">
            <button class="btn btn-primary" onclick="openManualBackfillModal()">Backfill Now</button>
            <button class="btn btn-secondary" onclick="viewDocs()">View Docs</button>
          </div>
        </div>
      </td>
    </tr>
  `;
}
```

#### Step 3.2.3: Update Modal Tab Content Empty States
```javascript
// In renderCandles() function
if (!data.candles || data.candles.length === 0) {
  tbody.innerHTML = `
    <tr>
      <td colspan="8">
        <div class="empty-state" style="padding: 32px 16px;">
          <div class="empty-state-icon">📋</div>
          <div class="empty-state-title">No Candles Available</div>
          <p class="empty-state-description">
            Data for this timeframe hasn't been loaded yet. Try backfilling this symbol.
          </p>
        </div>
      </td>
    </tr>
  `;
  return;
}
```

---

### Phase 3.3: Modal Enhancements

**File**: `/dashboard/script.js` + `/dashboard/style.css`

#### Step 3.3.1: Improve Modal Tab Styling
```css
.asset-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 24px;
  overflow-x: auto;
}

.asset-tab-btn {
  padding: 12px 16px;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 2px solid transparent;
  transition: all 0.3s ease;
  position: relative;
  bottom: -2px;
}

.asset-tab-btn:hover {
  color: var(--text-primary);
}

.asset-tab-btn.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
}
```

#### Step 3.3.2: Add Modal Action Buttons
```html
<!-- Update modal-content structure -->
<div class="modal-content modal-with-actions">
  <div class="modal-header">
    <h2 id="modal-symbol">--</h2>
    <button class="modal-close" onclick="closeAssetModal()">×</button>
  </div>

  <!-- Tabs -->
  <div class="asset-tabs"> ... </div>

  <!-- Tab Content -->
  <div id="tab-overview" class="asset-tab-content active"> ... </div>
  
  <!-- Modal Footer with Actions -->
  <div class="modal-footer">
    <button class="btn btn-secondary" onclick="closeAssetModal()">Close</button>
    <button class="btn btn-primary" onclick="quickBackfillSymbol()">Backfill This Symbol</button>
    <button class="btn btn-primary" onclick="quickEnrichSymbol()">Re-Enrich This Symbol</button>
  </div>
</div>
```

#### Step 3.3.3: Add Modal Footer Styles
```css
.modal-with-actions {
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  padding-top: 24px;
  margin-top: 24px;
  border-top: 1px solid var(--border-color);
  margin-top: auto;
}
```

#### Step 3.3.4: Add Quick Action Functions
```javascript
/**
 * Quick backfill for single symbol
 */
function quickBackfillSymbol() {
  selectedSymbols.clear();
  selectedSymbols.add(currentSymbol);
  closeAssetModal();
  openBackfillModal();
}

/**
 * Quick enrich for single symbol
 */
function quickEnrichSymbol() {
  selectedSymbols.clear();
  selectedSymbols.add(currentSymbol);
  closeAssetModal();
  openEnrichModal();
}
```

---

### Phase 3.4: Accessibility & Final Polish

**File**: `/dashboard/style.css` + `/dashboard/script.js`

#### Step 3.4.1: ARIA Labels and Accessibility
```html
<!-- Add to modal -->
<div id="asset-modal" class="modal" role="dialog" aria-labelledby="modal-symbol" aria-modal="true">

<!-- Add to buttons -->
<button class="btn" aria-label="Close modal">×</button>

<!-- Add to searchbox -->
<input type="text" id="symbol-search" aria-label="Search symbols" aria-describedby="search-help">
<span id="search-help" style="display: none;">Type symbol name to filter table</span>

<!-- Add to tables -->
<table id="symbol-table" role="grid" aria-label="Symbol status and quality metrics">
```

#### Step 3.4.2: Focus Management
```javascript
/**
 * Trap focus within modal
 */
function trapFocusInModal(modalElement) {
  const focusableElements = modalElement.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  const firstElement = focusableElements[0];
  const lastElement = focusableElements[focusableElements.length - 1];

  modalElement.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    }
  });
}
```

#### Step 3.4.3: Color Contrast Verification
- All text should have WCAG AA contrast (4.5:1 for small text, 3:1 for large)
- Use this CSS to verify:
```css
/* Run a contrast check tool against these colors */
:root {
  --primary: #0f9370;        /* Check against --bg-card, --bg-dark */
  --danger: #ef4444;         /* Check against alert backgrounds */
  --warning: #f59e0b;        /* Check against warning backgrounds */
  --text-primary: #f1f5f9;   /* Check against all backgrounds */
  --text-secondary: #94a3b8; /* Check against card backgrounds */
}
```

#### Step 3.4.4: Loading States
```javascript
/**
 * Show loading state on button
 */
function setButtonLoading(button, isLoading) {
  if (isLoading) {
    button.disabled = true;
    button.classList.add('loading');
    button.dataset.originalText = button.textContent;
    button.textContent = '⏳ Loading...';
  } else {
    button.disabled = false;
    button.classList.remove('loading');
    button.textContent = button.dataset.originalText;
  }
}
```

---

### Phase 3 Verification Checklist

- [ ] Keyboard shortcuts work (?, R, S, B, E, ESC)
- [ ] Help modal displays and closes properly
- [ ] Empty states display with icons and actions
- [ ] Modal tabs visually indicate active state
- [ ] Modal footer buttons work
- [ ] Quick backfill/enrich from modal works
- [ ] Focus trap works in modals
- [ ] All buttons have aria-labels
- [ ] Tables have role="grid"
- [ ] Color contrast passes WCAG AA
- [ ] Loading states show on async operations
- [ ] No console errors
- [ ] Mobile responsive (test on 375px width)
- [ ] Tablet responsive (test on 768px width)
- [ ] Desktop looks polished (test on 1400px)
- [ ] All sections can be collapsed/expanded
- [ ] State persists on page reload (localStorage)

---

## Best Practices & Standards

### Code Organization
- **Single Responsibility**: Each function does one thing
- **Naming**: `camelCase` for functions, UPPERCASE for constants
- **Comments**: JSDoc comments for public functions
- **DRY**: Reuse functions, avoid duplication

### Error Handling
```javascript
try {
  // Async operation
  const response = await fetch(...);
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return await response.json();
} catch (error) {
  console.error('Operation failed:', error);
  // Show user-friendly error message
  alert(`✗ Failed: ${error.message}`);
}
```

### Performance
- Cache API responses (existing 1-minute TTL is good)
- Lazy load modals (load data only when opened)
- Use event delegation for dynamic elements
- Minimize DOM reflows (batch updates)

### User Feedback
- Always confirm destructive actions (stop scheduler, vacuum DB)
- Show loading states during async operations
- Display success/error messages with emoji context (✓/✗)
- Log errors to console for debugging

### Accessibility
- All interactive elements keyboard-accessible
- ARIA labels on landmarks and buttons
- Focus management in modals (trap focus)
- Color not the only indicator (icons + text)
- Sufficient color contrast (WCAG AA minimum)

### Testing Strategy
- Manual testing at each phase
- Test across browsers (Chrome, Safari, Firefox)
- Test at multiple viewport sizes (mobile, tablet, desktop)
- Check console for errors
- Verify localStorage persistence

---

## Testing Strategy

### Phase 1 Testing
```
1. Visual Layout
   - [ ] Sections appear in correct order
   - [ ] No overflow on desktop (1400px)
   - [ ] Proper stacking on mobile (<640px)
   - [ ] Collapsible sections toggle

2. Functionality
   - [ ] Symbol search still works
   - [ ] Status filter still works
   - [ ] Table sorting still works
   - [ ] All data loads correctly

3. Responsiveness
   - [ ] Desktop: 1400px+ (3-column layout)
   - [ ] Tablet: 768px-1024px (2-column layout)
   - [ ] Mobile: <640px (single column)
```

### Phase 2 Testing
```
1. Selection System
   - [ ] Checkboxes render and function
   - [ ] "Select All" works correctly
   - [ ] Toolbar shows/hides appropriately
   - [ ] Selected rows highlight
   - [ ] Count updates in real-time

2. Bulk Operations
   - [ ] Modal opens with selected symbols
   - [ ] Form validation prevents empty submission
   - [ ] API call is made with correct payload
   - [ ] User gets success/error feedback
   - [ ] Selection clears after operation

3. Admin Panel
   - [ ] Buttons are visible and clickable
   - [ ] API calls work (or mock correctly)
   - [ ] Confirmation dialogs appear for destructive actions
   - [ ] User feedback after operations
```

### Phase 3 Testing
```
1. Keyboard Shortcuts
   - [ ] All shortcuts documented
   - [ ] Shortcuts don't trigger in inputs
   - [ ] Help modal displays and closes
   - [ ] Shortcuts work on multiple browsers

2. Empty States
   - [ ] Display when appropriate
   - [ ] Include helpful action buttons
   - [ ] Look visually distinct from normal content

3. Accessibility
   - [ ] Test with keyboard only (no mouse)
   - [ ] Run automated a11y scanner
   - [ ] Check color contrast
   - [ ] Test focus management

4. Cross-Browser
   - [ ] Chrome (latest)
   - [ ] Safari (latest)
   - [ ] Firefox (latest)
   - [ ] Mobile Safari
   - [ ] Chrome Mobile
```

---

## Success Criteria

### Usability Goals
- [ ] Users can find a symbol and open details in <10 seconds
- [ ] Users can select and backfill symbols in <30 seconds
- [ ] All operations have clear visual feedback
- [ ] No confusion about "what to do next"

### Performance Goals
- [ ] Dashboard loads in <2 seconds
- [ ] Search filters in <200ms
- [ ] Modal opens in <500ms
- [ ] No console errors

### Code Quality
- [ ] All functions documented
- [ ] No duplicate code
- [ ] Consistent naming/style
- [ ] Proper error handling
- [ ] No console warnings

### Accessibility Goals
- [ ] WCAG AA compliant
- [ ] Fully keyboard navigable
- [ ] Screen reader friendly
- [ ] Color contrast verified

---

## Implementation Checklist

### Pre-Implementation
- [ ] Read this entire document
- [ ] Confirm all decisions with Stephen
- [ ] Verify backend APIs exist or create mocks
- [ ] Set up git branch for changes

### Phase 1
- [ ] Reorganize HTML sections
- [ ] Update CSS for new layout
- [ ] Add collapsible functionality
- [ ] Fix symbol table
- [ ] Test all existing features
- [ ] Commit changes

### Phase 2
- [ ] Add selection system (checkboxes)
- [ ] Create bulk action toolbar
- [ ] Build backfill modal
- [ ] Build enrichment modal
- [ ] Create admin panel
- [ ] Test all new features
- [ ] Commit changes

### Phase 3
- [ ] Add keyboard shortcuts
- [ ] Improve empty states
- [ ] Enhance modals
- [ ] Add accessibility features
- [ ] Polish styling
- [ ] Final testing
- [ ] Commit changes

### Post-Implementation
- [ ] Code review
- [ ] User acceptance testing
- [ ] Performance audit
- [ ] Accessibility audit
- [ ] Deploy to production
- [ ] Monitor for issues

---

## Quick Reference

### Key Files
- `/dashboard/index.html` - HTML structure
- `/dashboard/style.css` - Styling
- `/dashboard/script.js` - JavaScript logic

### API Endpoints (to verify)
```
POST /api/v1/backfill              - Start backfill job
POST /api/v1/enrich                - Start enrichment job
POST /api/v1/scheduler/start        - Start scheduler
POST /api/v1/scheduler/stop         - Stop scheduler
POST /api/v1/cache/clear            - Clear query cache
POST /api/v1/database/vacuum        - Vacuum database
POST /api/v1/database/reindex       - Reindex database
```

### Important CSS Variables
```css
--primary: #0f9370              (Main brand color)
--primary-dark: #067857         (Darker variant)
--bg-dark: #0f172a              (Very dark background)
--bg-card: #1e293b              (Card background)
--text-primary: #f1f5f9         (Main text)
--text-secondary: #94a3b8       (Muted text)
--success: #0f9370              (Green for success)
--warning: #f59e0b              (Amber for warning)
--danger: #ef4444               (Red for danger)
```

### Important JavaScript State
```javascript
let selectedSymbols = new Set();  // Track selected symbols
let currentSymbol = null;          // Current modal symbol
const CACHE_TTL = 60000;          // 1 minute cache
```

---

## Notes & Assumptions

- Backend APIs for bulk operations may need to be created
- Mock implementations can return success responses if APIs don't exist
- All times are UTC
- localStorage is available for section state persistence
- No authentication required (assumes trusted environment)
- Bulk operations are synchronous (return job_id, user can check status)

---

## Questions & Clarifications

If during implementation you encounter:

1. **Missing Backend API**: Create a mock that returns `{ job_id: "uuid", status: "queued" }`
2. **Styling Conflict**: Keep existing classes, add new ones prefixed with phase number
3. **Performance Issue**: Check browser DevTools, optimize fetches first
4. **Accessibility Question**: Refer to WCAG 2.1 AA standard
5. **Scope Creep**: Reference "Explicitly Out of Scope" section

---

**Document Status**: Ready for Implementation ✓  
**Last Review**: November 14, 2025  
**Next Review**: After Phase 1 completion
