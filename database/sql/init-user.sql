-- Create user (password will be set via environment variable)
DO $$ BEGIN
    CREATE USER market_user WITH PASSWORD 'changeMe123' CREATEDB;
EXCEPTION WHEN DUPLICATE_OBJECT THEN
    NULL;
END $$;

-- Create market_data database (outside of transaction)
-- Note: CREATEDB privilege already granted to user above
-- This is handled by docker-entrypoint with POSTGRES_DB environment variable
