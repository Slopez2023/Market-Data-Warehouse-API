-- Create user (password will be set via environment variable)
DO $$ BEGIN
    CREATE USER market_user WITH PASSWORD 'changeMe123' CREATEDB;
EXCEPTION WHEN DUPLICATE_OBJECT THEN
    NULL;
END $$;

-- Grant privileges to market_user
GRANT CONNECT ON DATABASE market_data TO market_user;
GRANT USAGE ON SCHEMA public TO market_user;
GRANT CREATE ON SCHEMA public TO market_user;

-- Transfer database ownership to market_user
ALTER DATABASE market_data OWNER TO market_user;
