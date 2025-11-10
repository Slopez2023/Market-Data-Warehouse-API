-- Load 5 years of test data for 5 assets
-- This generates realistic OHLCV data from 5 years ago to now

WITH RECURSIVE date_series AS (
    -- Generate all dates from 5 years ago to today
    SELECT CURRENT_DATE - INTERVAL '5 years' as date
    UNION ALL
    SELECT date + INTERVAL '1 day'
    FROM date_series
    WHERE date < CURRENT_DATE
),
symbols_list AS (
    SELECT 'AAPL' as symbol, 'stock' as asset_class, 150.0 as base_price
    UNION ALL SELECT 'MSFT', 'stock', 300.0
    UNION ALL SELECT 'GOOGL', 'stock', 140.0
    UNION ALL SELECT 'BTC', 'crypto', 45000.0
    UNION ALL SELECT 'ETH', 'crypto', 2500.0
),
candle_data AS (
    SELECT
        to_timestamp(
            extract(epoch from date) + 
            round(random() * 3600)::int
        ) as time,
        s.symbol,
        -- Generate realistic OHLC data with price drift
        (s.base_price * (1 + (random() - 0.5) * 0.1))::decimal(19,8) as open,
        (s.base_price * (1 + abs(random() - 0.5) * 0.15))::decimal(19,8) as high,
        (s.base_price * (1 - abs(random() - 0.5) * 0.15))::decimal(19,8) as low,
        (s.base_price * (1 + (random() - 0.5) * 0.1))::decimal(19,8) as close,
        -- Generate realistic volume
        (1000000 * (1 + abs(random() - 0.5) * 2))::bigint as volume,
        'polygon'::varchar as source,
        true as validated,
        (0.85 + random() * 0.15)::numeric(3,2) as quality_score,
        null as validation_notes,
        false as gap_detected,
        false as volume_anomaly
    FROM date_series d
    CROSS JOIN symbols_list s
    WHERE 
        -- Skip weekends for stocks
        (s.asset_class = 'crypto' OR extract(dow from d.date) NOT IN (0, 6))
)
INSERT INTO market_data 
(time, symbol, open, high, low, close, volume, source, validated, quality_score, validation_notes, gap_detected, volume_anomaly)
SELECT 
    time, symbol, open, high, low, close, volume, source, 
    validated, quality_score, validation_notes, gap_detected, volume_anomaly
FROM candle_data
ON CONFLICT (symbol, time) DO NOTHING;

-- Verify the load
SELECT 
    symbol,
    COUNT(*) as record_count,
    MIN(time)::date as earliest_date,
    MAX(time)::date as latest_date,
    ROUND(AVG(volume)::numeric) as avg_volume,
    ROUND(AVG(quality_score::numeric), 2) as avg_quality
FROM market_data
GROUP BY symbol
ORDER BY symbol;
