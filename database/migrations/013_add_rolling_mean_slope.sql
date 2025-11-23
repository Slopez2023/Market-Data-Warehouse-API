-- Add rolling mean and slope features to market_data table
-- Version: 1.0
-- Date: 2024-11-22

-- Add new feature columns to market_data table
ALTER TABLE market_data
ADD COLUMN IF NOT EXISTS rolling_mean_10 DECIMAL(19, 10),
ADD COLUMN IF NOT EXISTS rolling_slope_10 DECIMAL(19, 10);

-- Add new feature columns to quant_feature_summary table
ALTER TABLE quant_feature_summary
ADD COLUMN IF NOT EXISTS rolling_mean_10 DECIMAL(19, 10),
ADD COLUMN IF NOT EXISTS rolling_slope_10 DECIMAL(19, 10);

-- Create index for rolling_mean queries
CREATE INDEX IF NOT EXISTS idx_market_data_rolling_mean_10
    ON market_data(rolling_mean_10)
    WHERE rolling_mean_10 IS NOT NULL;

-- Create index for rolling_slope queries  
CREATE INDEX IF NOT EXISTS idx_market_data_rolling_slope_10
    ON market_data(rolling_slope_10)
    WHERE rolling_slope_10 IS NOT NULL;
