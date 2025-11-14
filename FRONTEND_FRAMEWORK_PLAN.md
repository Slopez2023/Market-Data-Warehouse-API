# Frontend Framework Implementation: Vue.js 3

## Decision: Vue.js 3 + Vite

**Why Vue over React:**
- ✅ Lighter bundle size (optimal for monitoring dashboard)
- ✅ Single-file components (clean, maintainable)
- ✅ Easier learning curve for backend devs
- ✅ Can integrate gradually (no rip-and-replace)
- ✅ Excellent tooling (Vite for fast development)
- ✅ Better for this use case (not a complex SPA)

---

## Phase 1: Project Setup (20 min)

### 1.1 Initialize Vue Project

```bash
# Install Node.js dependencies
npm create vite@latest market-data-dashboard -- --template vue

cd market-data-dashboard

npm install
npm install -D tailwindcss postcss autoprefixer  # For styling
npm install axios                                  # HTTP client
npm install pinia                                  # State management
npm install vue-router                             # Routing (optional for now)
```

### 1.2 Project Structure

```
market-data-dashboard/
├── src/
│   ├── components/
│   │   ├── AssetCard.vue
│   │   ├── CandleTable.vue
│   │   ├── EnrichmentMetrics.vue
│   │   ├── OverviewTab.vue
│   │   ├── SymbolTable.vue
│   │   └── DashboardHeader.vue
│   ├── stores/
│   │   ├── assetStore.js
│   │   └── dashboardStore.js
│   ├── services/
│   │   ├── api.js
│   │   └── cache.js
│   ├── styles/
│   │   ├── main.css
│   │   ├── variables.css
│   │   └── responsive.css
│   ├── views/
│   │   ├── Dashboard.vue
│   │   └── AssetDetail.vue
│   ├── App.vue
│   └── main.js
├── public/
├── vite.config.js
├── tailwind.config.js
├── package.json
└── index.html
```

### 1.3 Key Files Setup

**vite.config.js:**
```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
```

**tailwind.config.js:**
```javascript
module.exports = {
  content: ['./src/**/*.{vue,js,ts}'],
  theme: {
    extend: {
      colors: {
        dark: {
          50: '#f8f9fa',
          100: '#e9ecef',
          200: '#dee2e6',
          300: '#ced4da',
          400: '#adb5bd',
          500: '#6c757d',
          600: '#495057',
          700: '#343a40',
          800: '#212529',
          900: '#0d1117'
        }
      }
    }
  },
  plugins: []
}
```

---

## Phase 2: Core Components (1.5-2 hours)

### 2.1 Asset Service Layer

**src/services/api.js:**
```javascript
import axios from 'axios'

const API_BASE = '/api/v1'

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 10000
})

export const assetService = {
  // Get asset summary
  getAsset: (symbol) => 
    apiClient.get(`/assets/${symbol}`),
  
  // Get paginated candles
  getCandles: (symbol, timeframe = '1h', limit = 100, offset = 0) =>
    apiClient.get(`/assets/${symbol}/candles`, {
      params: { timeframe, limit, offset }
    }),
  
  // Get enrichment metrics
  getEnrichment: (symbol, timeframe = '1h') =>
    apiClient.get(`/assets/${symbol}/enrichment`, {
      params: { timeframe }
    }),
  
  // Get all symbols
  getSymbols: () =>
    apiClient.get('/health'),
  
  // Get enrichment dashboard
  getEnrichmentDashboard: () =>
    apiClient.get('/enrichment/dashboard/overview')
}

export default apiClient
```

**src/services/cache.js:**
```javascript
const cache = new Map()
const TTL = 60000 // 1 minute

export const cacheService = {
  set: (key, value) => {
    cache.set(key, {
      data: value,
      timestamp: Date.now()
    })
  },
  
  get: (key) => {
    const item = cache.get(key)
    if (!item) return null
    
    if (Date.now() - item.timestamp > TTL) {
      cache.delete(key)
      return null
    }
    
    return item.data
  },
  
  clear: () => cache.clear()
}
```

### 2.2 State Management (Pinia)

**src/stores/assetStore.js:**
```javascript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { assetService } from '../services/api'
import { cacheService } from '../services/cache'

export const useAssetStore = defineStore('asset', () => {
  const assets = ref([])
  const selectedAsset = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const candles = ref([])
  const enrichment = ref(null)
  
  const candleCount = computed(() => candles.value.length)
  
  const loadAssets = async () => {
    loading.value = true
    error.value = null
    
    try {
      const cached = cacheService.get('assets-list')
      if (cached) {
        assets.value = cached
        return
      }
      
      const health = await assetService.getSymbols()
      assets.value = health.data.symbols_in_database || []
      cacheService.set('assets-list', assets.value)
    } catch (err) {
      error.value = err.message
      console.error('Failed to load assets:', err)
    } finally {
      loading.value = false
    }
  }
  
  const loadAssetData = async (symbol) => {
    loading.value = true
    error.value = null
    
    try {
      const response = await assetService.getAsset(symbol)
      selectedAsset.value = response.data
    } catch (err) {
      error.value = err.message
      console.error(`Failed to load asset ${symbol}:`, err)
    } finally {
      loading.value = false
    }
  }
  
  const loadCandles = async (symbol, timeframe = '1h', limit = 100, offset = 0) => {
    const cacheKey = `candles-${symbol}-${timeframe}-${offset}`
    const cached = cacheService.get(cacheKey)
    
    if (cached) {
      candles.value = cached
      return
    }
    
    try {
      const response = await assetService.getCandles(symbol, timeframe, limit, offset)
      candles.value = response.data.candles || []
      cacheService.set(cacheKey, candles.value)
    } catch (err) {
      error.value = err.message
      console.error('Failed to load candles:', err)
    }
  }
  
  const loadEnrichment = async (symbol, timeframe = '1h') => {
    const cacheKey = `enrichment-${symbol}-${timeframe}`
    const cached = cacheService.get(cacheKey)
    
    if (cached) {
      enrichment.value = cached
      return
    }
    
    try {
      const response = await assetService.getEnrichment(symbol, timeframe)
      enrichment.value = response.data
      cacheService.set(cacheKey, enrichment.value)
    } catch (err) {
      error.value = err.message
      console.error('Failed to load enrichment:', err)
    }
  }
  
  return {
    assets,
    selectedAsset,
    loading,
    error,
    candles,
    enrichment,
    candleCount,
    loadAssets,
    loadAssetData,
    loadCandles,
    loadEnrichment
  }
})
```

### 2.3 Vue Components

**src/components/SymbolTable.vue:**
```vue
<template>
  <div class="symbol-table-container">
    <div class="table-header">
      <h3>Tracked Symbols</h3>
      <div class="controls">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search symbols..."
          class="search-input"
        />
      </div>
    </div>

    <table v-if="filteredAssets.length" class="symbol-table">
      <thead>
        <tr>
          <th>Symbol</th>
          <th>Status</th>
          <th>Records</th>
          <th>Quality</th>
          <th>Last Update</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="asset in filteredAssets" :key="asset.symbol">
          <td class="font-bold">{{ asset.symbol }}</td>
          <td>
            <span :class="['status-badge', asset.status?.toLowerCase()]">
              {{ asset.status }}
            </span>
          </td>
          <td>{{ asset.total_records?.toLocaleString() }}</td>
          <td>{{ (asset.quality?.quality_score * 100).toFixed(1) }}%</td>
          <td>{{ formatDate(asset.last_update) }}</td>
          <td>
            <button
              @click="selectAsset(asset.symbol)"
              class="btn btn-sm btn-primary"
            >
              View
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-else class="empty-state">
      No symbols found
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useAssetStore } from '../stores/assetStore'
import { formatDate } from '../utils/format'

const assetStore = useAssetStore()
const searchQuery = ref('')
const emit = defineEmits(['select-asset'])

const filteredAssets = computed(() => {
  if (!searchQuery.value) return assetStore.assets
  
  return assetStore.assets.filter(asset =>
    asset.symbol.toUpperCase().includes(searchQuery.value.toUpperCase())
  )
})

const selectAsset = (symbol) => {
  emit('select-asset', symbol)
}
</script>

<style scoped>
.symbol-table-container {
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 16px;
  margin: 16px 0;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.controls {
  display: flex;
  gap: 8px;
}

.search-input {
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--bg-primary);
  color: var(--text-primary);
  width: 250px;
}

.symbol-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.symbol-table thead {
  background: var(--bg-tertiary);
}

.symbol-table th,
.symbol-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

.symbol-table tbody tr:hover {
  background: var(--bg-tertiary);
}

.status-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.healthy {
  background: rgba(76, 175, 80, 0.2);
  color: #4caf50;
}

.status-badge.warning {
  background: rgba(255, 193, 7, 0.2);
  color: #ffc107;
}

.status-badge.stale {
  background: rgba(244, 67, 54, 0.2);
  color: #f44336;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--text-secondary);
}
</style>
```

**src/components/AssetDetail.vue:**
```vue
<template>
  <div class="asset-detail-modal">
    <div class="modal-overlay" @click="closeModal"></div>
    
    <div class="modal-content">
      <div class="modal-header">
        <h2>{{ symbol }}</h2>
        <button @click="closeModal" class="close-btn">×</button>
      </div>

      <div class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab"
          @click="activeTab = tab"
          :class="['tab-btn', { active: activeTab === tab }]"
        >
          {{ tab }}
        </button>
      </div>

      <div class="tab-content">
        <OverviewTab v-if="activeTab === 'Overview'" :asset="asset" />
        <CandleTable v-if="activeTab === 'Candles'" :symbol="symbol" />
        <EnrichmentMetrics v-if="activeTab === 'Enrichment'" :symbol="symbol" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useAssetStore } from '../stores/assetStore'
import OverviewTab from './OverviewTab.vue'
import CandleTable from './CandleTable.vue'
import EnrichmentMetrics from './EnrichmentMetrics.vue'

const props = defineProps({
  symbol: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['close'])

const assetStore = useAssetStore()
const activeTab = ref('Overview')
const tabs = ['Overview', 'Candles', 'Enrichment']

const asset = assetStore.selectedAsset

watch(() => props.symbol, async (newSymbol) => {
  await assetStore.loadAssetData(newSymbol)
}, { immediate: true })

const closeModal = () => {
  emit('close')
}
</script>

<style scoped>
.asset-detail-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
}

.modal-content {
  position: relative;
  background: var(--bg-primary);
  border-radius: 8px;
  width: 90%;
  max-width: 1000px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h2 {
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 28px;
  cursor: pointer;
  color: var(--text-secondary);
}

.close-btn:hover {
  color: var(--text-primary);
}

.tabs {
  display: flex;
  border-bottom: 1px solid var(--border-color);
  padding: 0 20px;
  gap: 0;
}

.tab-btn {
  padding: 12px 16px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn.active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
}

.tab-content {
  padding: 20px;
}
</style>
```

**src/components/CandleTable.vue:**
```vue
<template>
  <div class="candle-section">
    <div class="candle-controls">
      <select v-model="selectedTimeframe" @change="loadCandles" class="timeframe-select">
        <option value="1m">1 Minute</option>
        <option value="5m">5 Minutes</option>
        <option value="15m">15 Minutes</option>
        <option value="1h">1 Hour</option>
        <option value="1d">Daily</option>
      </select>
      <span class="record-count">{{ candleCount }} candles loaded</span>
      <button @click="loadMore" class="btn btn-sm btn-secondary">Load More</button>
    </div>

    <table v-if="candles.length" class="candles-table">
      <thead>
        <tr>
          <th>Timestamp</th>
          <th>Open</th>
          <th>High</th>
          <th>Low</th>
          <th>Close</th>
          <th>Volume</th>
          <th>VWAP</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(candle, idx) in candles" :key="idx">
          <td>{{ formatDateTime(candle.timestamp) }}</td>
          <td>${{ candle.open?.toFixed(2) }}</td>
          <td>${{ candle.high?.toFixed(2) }}</td>
          <td>${{ candle.low?.toFixed(2) }}</td>
          <td>${{ candle.close?.toFixed(2) }}</td>
          <td>{{ candle.volume?.toLocaleString() }}</td>
          <td>${{ candle.vwap?.toFixed(2) }}</td>
          <td>
            <span :class="['badge', candle.enrichment_status?.toLowerCase()]">
              {{ candle.enrichment_status }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-else-if="loading" class="loading">Loading candles...</div>
    <div v-else class="empty-state">No candles available</div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAssetStore } from '../stores/assetStore'
import { formatDateTime } from '../utils/format'

const props = defineProps({
  symbol: {
    type: String,
    required: true
  }
})

const assetStore = useAssetStore()
const selectedTimeframe = ref('1h')
const offset = ref(0)
const loading = ref(false)

const candles = computed(() => assetStore.candles)
const candleCount = computed(() => candles.value.length)

const loadCandles = async () => {
  loading.value = true
  offset.value = 0
  await assetStore.loadCandles(props.symbol, selectedTimeframe.value, 100, 0)
  loading.value = false
}

const loadMore = async () => {
  offset.value += 100
  loading.value = true
  await assetStore.loadCandles(props.symbol, selectedTimeframe.value, 100, offset.value)
  loading.value = false
}

// Load initial data
loadCandles()
</script>

<style scoped>
.candle-section {
  width: 100%;
}

.candle-controls {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}

.timeframe-select {
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  cursor: pointer;
}

.record-count {
  font-size: 14px;
  color: var(--text-secondary);
  flex: 1;
}

.candles-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.candles-table thead {
  background: var(--bg-tertiary);
}

.candles-table th,
.candles-table td {
  padding: 10px;
  text-align: right;
  border-bottom: 1px solid var(--border-color);
}

.candles-table th:first-child,
.candles-table td:first-child {
  text-align: left;
}

.candles-table tbody tr:hover {
  background: var(--bg-tertiary);
}

.badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 500;
}

.badge.complete {
  background: rgba(76, 175, 80, 0.2);
  color: #4caf50;
}

.badge.partial {
  background: rgba(255, 193, 7, 0.2);
  color: #ffc107;
}

.loading,
.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--text-secondary);
}
</style>
```

**src/components/EnrichmentMetrics.vue:**
```vue
<template>
  <div class="enrichment-section">
    <div class="enrichment-grid" v-if="enrichment">
      <div class="enrichment-card">
        <h4>Fetch Pipeline</h4>
        <div class="metric">
          <span>Success Rate</span>
          <span class="value">{{ enrichment.fetch_metrics?.success_rate?.toFixed(1) }}%</span>
        </div>
        <div class="metric">
          <span>Avg Response</span>
          <span class="value">{{ enrichment.fetch_metrics?.avg_response_time }} ms</span>
        </div>
        <div class="metric">
          <span>Total Fetches</span>
          <span class="value">{{ enrichment.fetch_metrics?.total_fetches }}</span>
        </div>
      </div>

      <div class="enrichment-card">
        <h4>Compute Pipeline</h4>
        <div class="metric">
          <span>Success Rate</span>
          <span class="value">{{ enrichment.compute_metrics?.success_rate?.toFixed(1) }}%</span>
        </div>
        <div class="metric">
          <span>Avg Time</span>
          <span class="value">{{ enrichment.compute_metrics?.avg_compute_time }} ms</span>
        </div>
        <div class="metric">
          <span>Total Computations</span>
          <span class="value">{{ enrichment.compute_metrics?.total_computations }}</span>
        </div>
      </div>

      <div class="enrichment-card">
        <h4>Data Quality</h4>
        <div class="metric">
          <span>Validation Rate</span>
          <span class="value">{{ enrichment.quality_metrics?.validation_rate?.toFixed(1) }}%</span>
        </div>
        <div class="metric">
          <span>Quality Score</span>
          <span class="value">{{ enrichment.quality_metrics?.quality_score?.toFixed(2) }}</span>
        </div>
        <div class="metric">
          <span>Missing Features</span>
          <span class="value">{{ enrichment.quality_metrics?.missing_features || 0 }}</span>
        </div>
      </div>
    </div>

    <div v-else-if="loading" class="loading">Loading enrichment metrics...</div>
    <div v-else class="empty-state">No enrichment data available</div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useAssetStore } from '../stores/assetStore'

const props = defineProps({
  symbol: {
    type: String,
    required: true
  }
})

const assetStore = useAssetStore()
const loading = ref(false)

const enrichment = assetStore.enrichment

const loadEnrichment = async () => {
  loading.value = true
  await assetStore.loadEnrichment(props.symbol, '1h')
  loading.value = false
}

watch(() => props.symbol, loadEnrichment, { immediate: true })
</script>

<style scoped>
.enrichment-section {
  width: 100%;
}

.enrichment-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
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
  font-size: 13px;
}

.metric:last-child {
  border-bottom: none;
}

.metric span:first-child {
  color: var(--text-secondary);
}

.value {
  font-weight: 600;
  color: var(--text-primary);
}

.loading,
.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--text-secondary);
}
</style>
```

**src/components/OverviewTab.vue:**
```vue
<template>
  <div class="overview-section" v-if="asset">
    <div class="overview-grid">
      <div class="stat-box">
        <span class="label">Status</span>
        <span :class="['value', asset.status?.toLowerCase()]">{{ asset.status }}</span>
      </div>
      <div class="stat-box">
        <span class="label">Last Update</span>
        <span class="value">{{ formatDateTime(asset.last_update) }}</span>
      </div>
      <div class="stat-box">
        <span class="label">Data Age</span>
        <span class="value">{{ asset.data_age_hours }} hours</span>
      </div>
      <div class="stat-box">
        <span class="label">Quality Score</span>
        <span class="value">{{ (asset.quality?.quality_score * 100).toFixed(1) }}%</span>
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
          <tr v-for="(data, tf) in asset.timeframes" :key="tf">
            <td><strong>{{ tf }}</strong></td>
            <td>{{ data.records?.toLocaleString() }}</td>
            <td>{{ formatDateTime(data.latest) }}</td>
            <td>
              <span :class="['status-badge', data.status?.toLowerCase()]">
                {{ data.status }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <div v-else class="empty-state">
    Loading asset data...
  </div>
</template>

<script setup>
import { useAssetStore } from '../stores/assetStore'
import { formatDateTime } from '../utils/format'

const props = defineProps({
  asset: {
    type: Object,
    default: null
  }
})
</script>

<style scoped>
.overview-section {
  width: 100%;
}

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

.label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.value {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.value.healthy {
  color: #4caf50;
}

.value.warning {
  color: #ffc107;
}

.value.stale {
  color: #f44336;
}

.timeframes-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
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

.timeframes-table tbody tr:hover {
  background: var(--bg-tertiary);
}

.status-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 500;
}

.status-badge.healthy {
  background: rgba(76, 175, 80, 0.2);
  color: #4caf50;
}

.status-badge.warning {
  background: rgba(255, 193, 7, 0.2);
  color: #ffc107;
}

.status-badge.stale {
  background: rgba(244, 67, 54, 0.2);
  color: #f44336;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--text-secondary);
}
</style>
```

**src/views/Dashboard.vue:**
```vue
<template>
  <div class="dashboard">
    <header class="dashboard-header">
      <h1>Market Data Dashboard</h1>
      <div class="header-stats">
        <div class="stat">
          <span class="label">Symbols</span>
          <span class="value">{{ assetStore.assets.length }}</span>
        </div>
      </div>
    </header>

    <main class="dashboard-main">
      <SymbolTable @select-asset="selectedSymbol = $event" />

      <AssetDetail
        v-if="selectedSymbol"
        :symbol="selectedSymbol"
        @close="selectedSymbol = null"
      />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAssetStore } from '../stores/assetStore'
import SymbolTable from '../components/SymbolTable.vue'
import AssetDetail from '../components/AssetDetail.vue'

const assetStore = useAssetStore()
const selectedSymbol = ref(null)

onMounted(async () => {
  await assetStore.loadAssets()
})
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  background: var(--bg-primary);
  color: var(--text-primary);
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.dashboard-header h1 {
  margin: 0;
  font-size: 28px;
}

.header-stats {
  display: flex;
  gap: 20px;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.value {
  font-size: 20px;
  font-weight: 600;
  color: var(--primary-color);
}

.dashboard-main {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}
</style>
```

### 2.4 Utility Functions

**src/utils/format.js:**
```javascript
export const formatDate = (date) => {
  if (!date) return '--'
  try {
    return new Date(date).toLocaleDateString()
  } catch {
    return date
  }
}

export const formatDateTime = (date) => {
  if (!date) return '--'
  try {
    return new Date(date).toLocaleString()
  } catch {
    return date
  }
}

export const formatNumber = (num) => {
  if (typeof num !== 'number') return '--'
  return num.toLocaleString()
}

export const formatCurrency = (num) => {
  if (typeof num !== 'number') return '--'
  return '$' + num.toFixed(2)
}
```

---

## Phase 3: Integration with Existing Backend (30 min)

### 3.1 Build & Deploy

```bash
# Development
npm run dev

# Production build
npm run build

# Output goes to dist/
```

### 3.2 Docker Integration

**Dockerfile:**
```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 3.3 Nginx Config

**nginx.conf:**
```nginx
upstream api {
  server api:8000;
}

server {
  listen 80;
  root /usr/share/nginx/html;
  index index.html;

  # Serve Vue app
  location / {
    try_files $uri /index.html;
  }

  # Proxy API calls
  location /api {
    proxy_pass http://api;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

---

## Phase 4: Implementation Steps (Real-World Order)

### Step-by-Step Execution

```bash
# 1. Setup project
npm create vite@latest market-data-dashboard -- --template vue
cd market-data-dashboard
npm install

# 2. Install dependencies
npm install -D tailwindcss postcss autoprefixer
npm install axios pinia

# 3. Copy component files (from plan above)
cp src/components/* src/components/
cp src/stores/* src/stores/
cp src/services/* src/services/
cp src/utils/* src/utils/

# 4. Create main.js
npm run dev

# 5. Test with API
# Make sure backend is running on :8000

# 6. Build for production
npm run build

# 7. Deploy
docker build -t market-dashboard .
docker run -p 3000:80 market-dashboard
```

---

## Architecture Benefits

✅ **Reusable Components**
- CandleTable, EnrichmentMetrics, AssetCard all reusable
- Easy to use in other views
- Consistent styling

✅ **State Management**
- Pinia store = single source of truth
- Components don't manage their own state
- Easy to debug and test

✅ **Service Layer**
- API calls isolated in services
- Easy to mock for testing
- Simple to add new endpoints

✅ **Caching**
- Automatic 1-minute TTL
- Reduces API calls
- Smooth user experience

✅ **Scalability**
- Add new components without touching existing ones
- Easy to add new features (export, alerts, etc)
- Type-safe with proper structure

---

## Development Workflow

```bash
# Terminal 1: Backend
cd /path/to/MarketDataAPI
python main.py

# Terminal 2: Frontend
cd market-data-dashboard
npm run dev

# Visit http://localhost:5173
# API proxied to http://localhost:8000
```

---

## Component Dependency Graph

```
App.vue
├── Dashboard.vue
│   ├── SymbolTable.vue
│   │   └── uses: useAssetStore
│   └── AssetDetail.vue
│       ├── OverviewTab.vue
│       ├── CandleTable.vue
│       └── EnrichmentMetrics.vue
│       └── all use: useAssetStore
├── main.js (pinia store setup)
└── services/ (API & cache layer)
```

---

## Testing Strategy

```bash
# Unit tests (components)
npm run test:unit

# E2E tests
npm run test:e2e

# Vitest integration
npm install -D vitest
npm install -D @vue/test-utils
```

---

## Time Breakdown

| Phase | Task | Time |
|-------|------|------|
| 1 | Project setup + dependencies | 20 min |
| 2 | Components + stores + services | 1.5-2 hrs |
| 3 | Backend integration + build | 30 min |
| 4 | Testing + refinement | 30 min |
| **Total** | | **2.5-3.5 hours** |

---

## Key Differences from Vanilla JS

| Aspect | Vanilla JS | Vue.js |
|--------|-----------|--------|
| State Management | Manual (variables everywhere) | Pinia store (centralized) |
| Reactivity | Manual DOM manipulation | Automatic (computed props) |
| Component Reuse | Copy-paste code | Import + use |
| Testing | Hard (tightly coupled) | Easy (isolated components) |
| Scaling | Gets messy fast | Stays clean |
| Maintenance | 3 months = refactor time | Stays maintainable |

---

## What's Next After This?

Once Vue setup is working:

1. **Advanced Features**
   - Export candles to CSV
   - Chart visualization (Chart.js integration)
   - Real-time updates (WebSocket)
   - Custom alert rules

2. **Better UX**
   - Keyboard shortcuts
   - Drag-and-drop columns
   - Save user preferences
   - Dark/light theme toggle

3. **Performance**
   - Virtual scrolling (100+ candles)
   - Lazy-load images/charts
   - Service worker caching

---

## Files to Create

1. ✅ `src/main.js` (entry point)
2. ✅ `src/App.vue` (root component)
3. ✅ `src/views/Dashboard.vue`
4. ✅ `src/stores/assetStore.js`
5. ✅ `src/services/api.js`
6. ✅ `src/services/cache.js`
7. ✅ `src/components/SymbolTable.vue`
8. ✅ `src/components/AssetDetail.vue`
9. ✅ `src/components/CandleTable.vue`
10. ✅ `src/components/EnrichmentMetrics.vue`
11. ✅ `src/components/OverviewTab.vue`
12. ✅ `src/utils/format.js`

**Total: 12 files, ~1,200 lines of quality, maintainable code**

---

## Ready to Implement?

This plan gives you:
- ✅ Professional frontend architecture
- ✅ Reusable components
- ✅ Proper state management
- ✅ Easy to maintain & scale
- ✅ Industry standard practices

Should I start implementing this now?
