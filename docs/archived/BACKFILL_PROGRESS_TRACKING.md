# Backfill Progress Tracking Implementation

## Overview
This document describes the complete implementation of live progress tracking for backfill operations. Currently, the backfill endpoint returns a job_id but doesn't actually process data or track progress. This implementation adds:

1. **Background job queue** to process backfill requests
2. **Progress tracking** (symbols completed, timeframes, percentage)
3. **Live dashboard updates** with real-time progress bar
4. **Job status API** to query backfill progress

## Architecture

### Components
```
Dashboard (UI)
    ↓ POST /api/v1/backfill
API Endpoint (validates, creates job)
    ↓ Enqueues
Background Queue (Redis/APScheduler)
    ↓ Processes
Backfill Worker (fetches OHLCV data)
    ↓ Updates
Database (tracks progress)
    ↑ Polls
Status API (GET /api/v1/backfill/status/{job_id})
    ↑ Returns
Dashboard (displays progress)
```

## Database Schema Changes

Add two new tables to track backfill jobs:

### backfill_jobs table
```sql
CREATE TABLE IF NOT EXISTS backfill_jobs (
    id UUID PRIMARY KEY,
    symbols TEXT[] NOT NULL,              -- Array of symbols
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    timeframes TEXT[] NOT NULL,           -- Array of timeframes
    status VARCHAR(20) DEFAULT 'queued',  -- queued, running, completed, failed
    progress_pct INTEGER DEFAULT 0,       -- 0-100
    symbols_completed INTEGER DEFAULT 0,
    symbols_total INTEGER NOT NULL,
    current_symbol VARCHAR(20),
    current_timeframe VARCHAR(10),
    total_records_fetched INTEGER DEFAULT 0,
    total_records_inserted INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    estimated_completion_time TIMESTAMP
);

CREATE INDEX idx_backfill_jobs_status ON backfill_jobs(status);
CREATE INDEX idx_backfill_jobs_created_at ON backfill_jobs(created_at DESC);
```

### backfill_job_progress table (detailed tracking per symbol)
```sql
CREATE TABLE IF NOT EXISTS backfill_job_progress (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES backfill_jobs(id),
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, running, completed, failed
    records_fetched INTEGER DEFAULT 0,
    records_inserted INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(job_id, symbol, timeframe)
);

CREATE INDEX idx_backfill_progress_job_id ON backfill_job_progress(job_id);
```

## Backend Implementation

### 1. Database Service Methods (src/services/database.py)

```python
def create_backfill_job(self, job_id: str, symbols: List[str], 
                        start_date: str, end_date: str, 
                        timeframes: List[str]) -> Dict:
    """Create a new backfill job record."""
    session = self.SessionLocal()
    try:
        job = BackfillJob(
            id=job_id,
            symbols=symbols,
            start_date=datetime.strptime(start_date, '%Y-%m-%d').date(),
            end_date=datetime.strptime(end_date, '%Y-%m-%d').date(),
            timeframes=timeframes,
            status='queued',
            symbols_total=len(symbols)
        )
        session.add(job)
        session.commit()
        return {'job_id': job_id, 'status': 'created'}
    finally:
        session.close()

def get_backfill_job_status(self, job_id: str) -> Dict:
    """Get current status of a backfill job."""
    session = self.SessionLocal()
    try:
        job = session.query(BackfillJob).filter(
            BackfillJob.id == job_id
        ).first()
        
        if not job:
            return {'error': 'Job not found'}
        
        # Get progress details
        progress_details = session.query(BackfillJobProgress).filter(
            BackfillJobProgress.job_id == job_id
        ).all()
        
        return {
            'job_id': job_id,
            'status': job.status,
            'progress_pct': job.progress_pct,
            'symbols_completed': job.symbols_completed,
            'symbols_total': job.symbols_total,
            'current_symbol': job.current_symbol,
            'current_timeframe': job.current_timeframe,
            'total_records_fetched': job.total_records_fetched,
            'total_records_inserted': job.total_records_inserted,
            'created_at': job.created_at.isoformat(),
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'estimated_completion': job.estimated_completion_time.isoformat() if job.estimated_completion_time else None,
            'error': job.error_message,
            'details': [
                {
                    'symbol': p.symbol,
                    'timeframe': p.timeframe,
                    'status': p.status,
                    'records_fetched': p.records_fetched,
                    'records_inserted': p.records_inserted,
                    'duration_seconds': p.duration_seconds
                }
                for p in progress_details
            ]
        }
    finally:
        session.close()

def update_backfill_progress(self, job_id: str, symbol: str, 
                            timeframe: str, records_fetched: int,
                            records_inserted: int, error: str = None) -> None:
    """Update progress for a symbol-timeframe combination."""
    session = self.SessionLocal()
    try:
        progress = session.query(BackfillJobProgress).filter(
            BackfillJobProgress.job_id == job_id,
            BackfillJobProgress.symbol == symbol,
            BackfillJobProgress.timeframe == timeframe
        ).first()
        
        if not progress:
            progress = BackfillJobProgress(
                job_id=job_id,
                symbol=symbol,
                timeframe=timeframe
            )
            session.add(progress)
        
        progress.status = 'completed' if not error else 'failed'
        progress.records_fetched = records_fetched
        progress.records_inserted = records_inserted
        progress.error_message = error
        progress.completed_at = datetime.utcnow()
        
        # Update parent job
        job = session.query(BackfillJob).filter(
            BackfillJob.id == job_id
        ).first()
        
        if job:
            job.total_records_fetched += records_fetched
            job.total_records_inserted += records_inserted
            
            completed = session.query(BackfillJobProgress).filter(
                BackfillJobProgress.job_id == job_id,
                BackfillJobProgress.status == 'completed'
            ).count()
            
            total = len(job.symbols) * len(job.timeframes)
            job.progress_pct = int((completed / total) * 100) if total > 0 else 0
        
        session.commit()
    finally:
        session.close()

def mark_backfill_job_completed(self, job_id: str) -> None:
    """Mark a backfill job as completed."""
    session = self.SessionLocal()
    try:
        job = session.query(BackfillJob).filter(
            BackfillJob.id == job_id
        ).first()
        
        if job:
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            job.progress_pct = 100
        
        session.commit()
    finally:
        session.close()
```

### 2. API Endpoints (main.py)

```python
@app.post("/api/v1/backfill")
async def bulk_backfill(
    symbols: List[str] = Query(..., description="List of symbols to backfill"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    timeframes: List[str] = Query(['1d'], description="Timeframes to backfill")
):
    """Trigger backfill for multiple symbols (non-blocking)."""
    try:
        import uuid
        from datetime import datetime as dt
        
        # Validate inputs
        if not symbols:
            raise ValueError("At least one symbol required")
        if len(symbols) > 100:
            raise ValueError("Maximum 100 symbols per request")
        
        try:
            start = dt.strptime(start_date, '%Y-%m-%d')
            end = dt.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD")
        
        if start > end:
            raise ValueError("Start date must be before end date")
        
        # Create job ID
        job_id = str(uuid.uuid4())
        
        # Create job record in database
        db_service.create_backfill_job(job_id, symbols, start_date, end_date, timeframes)
        
        # Queue the backfill task (runs in background)
        from src.services.backfill_worker import enqueue_backfill_job
        enqueue_backfill_job(job_id, symbols, start_date, end_date, timeframes)
        
        logger.info(f"Backfill job created: {job_id}")
        
        return {
            'job_id': job_id,
            'status': 'queued',
            'symbols_count': len(symbols),
            'symbols': symbols[:10] + (['...'] if len(symbols) > 10 else []),
            'date_range': {'start': start_date, 'end': end_date},
            'timeframes': timeframes,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error in backfill: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/backfill/status/{job_id}")
async def get_backfill_status(job_id: str):
    """Get progress status of a backfill job."""
    try:
        status = db_service.get_backfill_job_status(job_id)
        
        if 'error' in status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return status
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting backfill status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/backfill/recent")
async def get_recent_backfill_jobs(limit: int = Query(10, ge=1, le=100)):
    """Get recent backfill jobs."""
    try:
        jobs = db_service.get_recent_backfill_jobs(limit)
        return {
            'jobs': jobs,
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting recent backfill jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 3. Backfill Worker (src/services/backfill_worker.py)

```python
"""Background worker for processing backfill jobs."""

import asyncio
import logging
from typing import List
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

class BackfillWorker:
    def __init__(self, db_service, polygon_service):
        self.db = db_service
        self.polygon = polygon_service
        self.queue = asyncio.Queue()
        self.scheduler = AsyncIOScheduler()
    
    async def process_job(self, job_id: str, symbols: List[str], 
                         start_date: str, end_date: str, 
                         timeframes: List[str]):
        """Process a backfill job."""
        try:
            # Mark job as running
            session = self.db.SessionLocal()
            job = session.query(BackfillJob).filter(
                BackfillJob.id == job_id
            ).first()
            job.status = 'running'
            job.started_at = datetime.utcnow()
            session.commit()
            session.close()
            
            # Process each symbol-timeframe combination
            total_combinations = len(symbols) * len(timeframes)
            processed = 0
            
            for symbol in symbols:
                for timeframe in timeframes:
                    try:
                        logger.info(f"Processing {symbol} {timeframe}")
                        
                        # Fetch OHLCV data from Polygon
                        candles = await self.polygon.fetch_candles(
                            symbol=symbol,
                            timeframe=timeframe,
                            start_date=start_date,
                            end_date=end_date
                        )
                        
                        records_fetched = len(candles)
                        
                        # Insert into database
                        records_inserted = await self.db.insert_candles(
                            symbol=symbol,
                            timeframe=timeframe,
                            candles=candles
                        )
                        
                        # Update progress
                        self.db.update_backfill_progress(
                            job_id=job_id,
                            symbol=symbol,
                            timeframe=timeframe,
                            records_fetched=records_fetched,
                            records_inserted=records_inserted
                        )
                        
                        processed += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing {symbol} {timeframe}: {e}")
                        self.db.update_backfill_progress(
                            job_id=job_id,
                            symbol=symbol,
                            timeframe=timeframe,
                            records_fetched=0,
                            records_inserted=0,
                            error=str(e)
                        )
                        processed += 1
            
            # Mark job as completed
            self.db.mark_backfill_job_completed(job_id)
            logger.info(f"Backfill job {job_id} completed")
            
        except Exception as e:
            logger.error(f"Critical error in backfill job {job_id}: {e}")
            session = self.db.SessionLocal()
            job = session.query(BackfillJob).filter(
                BackfillJob.id == job_id
            ).first()
            job.status = 'failed'
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            session.commit()
            session.close()


# Global worker instance
_backfill_worker = None


def init_backfill_worker(db_service, polygon_service):
    """Initialize the backfill worker."""
    global _backfill_worker
    _backfill_worker = BackfillWorker(db_service, polygon_service)
    logger.info("Backfill worker initialized")


def enqueue_backfill_job(job_id: str, symbols: List[str], 
                        start_date: str, end_date: str, 
                        timeframes: List[str]):
    """Enqueue a backfill job for processing."""
    if not _backfill_worker:
        raise RuntimeError("Backfill worker not initialized")
    
    # Schedule as a background task
    asyncio.create_task(
        _backfill_worker.process_job(job_id, symbols, start_date, end_date, timeframes)
    )
```

## Frontend Implementation

### 1. Dashboard Updates (dashboard/script.js)

```javascript
/**
 * Global backfill tracking state
 */
let activeBackfillJobs = new Map(); // job_id -> job data

/**
 * Submit backfill operation with progress tracking
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
    if (!symbols || symbols.length === 0) errors.push("No symbols selected");
    if (!startDate) errors.push("Start date is required");
    if (!endDate) errors.push("End date is required");
    if (startDate && endDate && new Date(startDate) >= new Date(endDate)) {
        errors.push("Start date must be before end date");
    }
    if (!validateTimeframeSelection("#backfill-timeframes")) {
        errors.push("Please select at least one timeframe");
    }

    if (errors.length > 0) {
        showValidationError(errors.join(", "));
        return;
    }

    try {
        // Build query string
        const params = new URLSearchParams();
        symbols.forEach((s) => params.append("symbols", s));
        params.append("start_date", startDate);
        params.append("end_date", endDate);
        timeframes.forEach((t) => params.append("timeframes", t));

        const response = await fetch(
            `${CONFIG.API_BASE}/api/v1/backfill?${params.toString()}`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
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
        
        // Refresh dashboard after job completes
        setTimeout(() => refreshDashboard(), 5000);

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
            <div class="modal-content modal-form">
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
                            <span style="color: var(--text-secondary); display: block;">Symbols Completed</span>
                            <span id="symbols-completed" style="font-weight: 600; font-size: 16px;">0 / 0</span>
                        </div>
                        <div>
                            <span style="color: var(--text-secondary); display: block;">Total Records Inserted</span>
                            <span id="records-inserted" style="font-weight: 600; font-size: 16px;">0</span>
                        </div>
                        <div>
                            <span style="color: var(--text-secondary); display: block;">Current Symbol</span>
                            <span id="current-symbol" style="font-weight: 600; font-size: 14px; font-family: monospace;">--</span>
                        </div>
                        <div>
                            <span style="color: var(--text-secondary); display: block;">Elapsed Time</span>
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
            logger.warn(`Backfill job ${jobId} polling timeout`);
            return;
        }

        try {
            const response = await fetch(
                `${CONFIG.API_BASE}/api/v1/backfill/status/${jobId}`
            );

            if (!response.ok) {
                if (response.status === 404) {
                    logger.warn(`Job ${jobId} not found`);
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
                logger.info(`Backfill job ${jobId} finished with status: ${status.status}`);
                activeBackfillJobs.delete(jobId);
                
                // Show completion message
                const message = status.status === "completed" 
                    ? `✓ Backfill completed! ${status.total_records_inserted} records inserted.`
                    : `✗ Backfill failed: ${status.error}`;
                
                showValidationError(message);
                
                // Refresh dashboard
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
```

### 2. CSS Styling (dashboard/style.css)

```css
/* Backfill progress modal specific styles */
#backfill-progress-modal .progress-bar-container {
    position: relative;
    width: 100%;
    height: 32px;
    background: var(--bg-secondary);
    border-radius: 8px;
    overflow: hidden;
    margin: 12px 0;
}

#progress-bar {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    background: linear-gradient(90deg, var(--success), var(--success-light));
    transition: width 0.3s ease-in-out;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding-right: 12px;
}

#bar-text {
    color: white;
    font-weight: 600;
    font-size: 12px;
}

.backfill-log-entry {
    font-family: 'Monaco', 'Menlo', monospace;
    font-size: 12px;
    padding: 6px 0;
    border-bottom: 1px solid rgba(15, 147, 112, 0.1);
    display: flex;
    gap: 8px;
}

.backfill-log-entry.success {
    color: var(--success);
}

.backfill-log-entry.error {
    color: var(--danger);
}

.backfill-log-entry.pending {
    color: var(--text-secondary);
}
```

## Integration Steps

1. **Create database tables:**
   ```bash
   psql -U postgres -d market_data -f database/backfill_jobs.sql
   ```

2. **Add models to src/models.py:**
   ```python
   class BackfillJob(Base):
       __tablename__ = "backfill_jobs"
       id = Column(String(36), primary_key=True)
       symbols = Column(ARRAY(String))
       start_date = Column(Date)
       end_date = Column(Date)
       timeframes = Column(ARRAY(String))
       status = Column(String(20), default='queued')
       progress_pct = Column(Integer, default=0)
       # ... other fields
   ```

3. **Initialize in main.py:**
   ```python
   from src.services.backfill_worker import init_backfill_worker
   
   init_backfill_worker(db_service, polygon_service)
   ```

4. **Update dashboard/script.js** with progress tracking code above

5. **Test the flow:**
   - Click "Manual Backfill..."
   - Select symbols, dates, timeframes
   - Click "Start Backfill"
   - Progress modal appears with live updates
   - Watch as percentage bar fills and symbols complete

## Usage Example

Dashboard flow:
1. User sees "No data available" message
2. User clicks "Start Backfill Now"
3. Backfill modal opens with date/symbol selectors
4. User selects: AAPL, MSFT (2 symbols) × 1h, 1d (2 timeframes) = 4 jobs
5. Submits backfill
6. Progress modal appears showing 0% completion
7. Each second, dashboard polls `/api/v1/backfill/status/{job_id}`
8. Progress bar updates: 0% → 25% → 50% → 75% → 100%
9. Log shows: "✓ AAPL 1h: 250 records", "✓ AAPL 1d: 60 records", etc.
10. When complete, dashboard refreshes to show loaded data

## Status Codes

- **queued**: Job created, waiting to process
- **running**: Currently fetching/inserting data
- **completed**: All symbols/timeframes processed successfully
- **failed**: Job encountered critical error

## Performance Considerations

- Process jobs sequentially per symbol (not parallel initially)
- Each symbol-timeframe takes ~5-30 seconds depending on date range
- For 50 symbols × 4 timeframes = 200 jobs ≈ 25-160 minutes total
- Polling every second keeps dashboard responsive
- Modal can be closed while job continues in background

## Monitoring

View job status without dashboard:
```bash
curl http://localhost:8000/api/v1/backfill/status/{job_id}
```

View recent jobs:
```bash
curl http://localhost:8000/api/v1/backfill/recent?limit=10
```

