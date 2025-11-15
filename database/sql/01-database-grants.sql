-- Grant privileges to market_user on market_data database
GRANT CONNECT ON DATABASE market_data TO market_user;
GRANT USAGE ON SCHEMA public TO market_user;
GRANT CREATE ON SCHEMA public TO market_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO market_user;

-- Transfer database ownership to market_user
ALTER DATABASE market_data OWNER TO market_user;
