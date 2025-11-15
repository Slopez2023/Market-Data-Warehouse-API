-- Backfill jobs tracking tables
-- Created: 2025-11-15

CREATE TABLE IF NOT EXISTS backfill_jobs (
    id UUID PRIMARY KEY,
    symbols TEXT[] NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    timeframes TEXT[] NOT NULL,
    status VARCHAR(20) DEFAULT 'queued',
    progress_pct INTEGER DEFAULT 0,
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


CREATE TABLE IF NOT EXISTS backfill_job_progress (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES backfill_jobs(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
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
CREATE INDEX idx_backfill_progress_status ON backfill_job_progress(status);
