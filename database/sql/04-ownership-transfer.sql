-- Transfer table ownership from postgres to market_user
-- This must run AFTER all schemas are created

DO $$ 
DECLARE
    table_record RECORD;
BEGIN
    FOR table_record IN 
        SELECT tablename FROM pg_tables WHERE schemaname = 'public'
    LOOP
        EXECUTE 'ALTER TABLE ' || quote_ident(table_record.tablename) || ' OWNER TO market_user';
        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE ' || quote_ident(table_record.tablename) || ' TO market_user';
    END LOOP;
EXCEPTION WHEN OTHERS THEN
    NULL;  -- Silently skip if error (user may not have privilege)
END $$;

-- Grant sequence ownership
DO $$ 
DECLARE
    seq_record RECORD;
BEGIN
    FOR seq_record IN 
        SELECT sequencename FROM pg_sequences WHERE schemaname = 'public'
    LOOP
        EXECUTE 'ALTER SEQUENCE ' || quote_ident(seq_record.sequencename) || ' OWNER TO market_user';
        EXECUTE 'GRANT ALL PRIVILEGES ON SEQUENCE ' || quote_ident(seq_record.sequencename) || ' TO market_user';
    END LOOP;
EXCEPTION WHEN OTHERS THEN
    NULL;  -- Silently skip if error
END $$;
