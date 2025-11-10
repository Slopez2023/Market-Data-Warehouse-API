#!/usr/bin/env python3
"""Database bootstrap script for initial setup"""

import asyncio
import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.migration_service import MigrationService
from src.services.auth import APIKeyService
from src.services.symbol_manager import SymbolManager
from src.services.structured_logging import StructuredLogger

logger = StructuredLogger(__name__)


async def bootstrap_database():
    """Initialize database for first-time use"""
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("Database Bootstrap Script")
    print("="*60)
    
    # Step 1: Run migrations
    print("\n1️⃣  Running database migrations...")
    migration_service = MigrationService(database_url)
    
    if not await migration_service.run_migrations():
        print("❌ Migrations failed")
        sys.exit(1)
    print("✅ Migrations applied successfully")
    
    # Step 2: Verify schema
    print("\n2️⃣  Verifying database schema...")
    schema_status = await migration_service.verify_schema()
    
    all_valid = all(schema_status.values())
    if not all_valid:
        print("❌ Schema verification failed")
        for table, valid in schema_status.items():
            status = "✅" if valid else "❌"
            print(f"   {status} {table}")
        sys.exit(1)
    
    print("✅ Schema verified")
    for table in schema_status.keys():
        print(f"   ✅ {table}")
    
    # Step 3: Generate initial admin key
    print("\n3️⃣  Generating initial admin API key...")
    auth_service = APIKeyService(database_url)
    
    admin_key = APIKeyService.generate_api_key("admin")
    key_hash = APIKeyService.hash_api_key(admin_key)
    
    try:
        import asyncpg
        conn = await asyncpg.connect(database_url)
        
        # Insert admin key
        await conn.execute(
            """
            INSERT INTO api_keys (key_hash, name, active)
            VALUES ($1, $2, $3)
            ON CONFLICT (key_hash) DO NOTHING
            """,
            key_hash, "admin", True
        )
        
        await conn.close()
        
        print(f"✅ Initial API key generated")
        print(f"   Key preview: {admin_key[:12]}...")
        print(f"   Full key: {admin_key}")
        print(f"   ⚠️  Save this key securely! It will not be shown again.")
    
    except Exception as e:
        print(f"⚠️  Could not insert admin key: {str(e)}")
        print(f"   You can manually insert with:")
        print(f"   INSERT INTO api_keys (key_hash, name, active)")
        print(f"   VALUES ('{key_hash}', 'admin', TRUE);")
    
    # Step 4: Seed core symbols
    print("\n4️⃣  Seeding core symbols...")
    symbol_manager = SymbolManager(database_url)
    
    core_symbols = [
        ("AAPL", "stock"),
        ("MSFT", "stock"),
        ("GOOGL", "stock"),
        ("AMZN", "stock"),
        ("TSLA", "stock"),
        ("META", "stock"),
        ("NVDA", "stock"),
        ("AMD", "stock"),
        ("INTC", "stock"),
        ("QCOM", "stock"),
        ("SPY", "etf"),
        ("QQQ", "etf"),
        ("IWM", "etf"),
        ("BTC", "crypto"),
        ("ETH", "crypto"),
    ]
    
    seeded_count = 0
    for symbol, asset_class in core_symbols:
        try:
            result = await symbol_manager.add_symbol(symbol, asset_class)
            if result:
                print(f"   ✅ {symbol} ({asset_class})")
                seeded_count += 1
            else:
                print(f"   ⚠️  {symbol} (already exists or error)")
        except Exception as e:
            print(f"   ⚠️  {symbol}: {str(e)}")
    
    print(f"✅ Symbols seeded: {seeded_count}/{len(core_symbols)}")
    
    # Step 5: Print summary
    print("\n" + "="*60)
    print("Bootstrap Complete!")
    print("="*60)
    
    migration_status = await migration_service.get_migration_status()
    
    print("\n📊 Summary:")
    print(f"   Migrations: {len(migration_status['migration_files'])} file(s)")
    print(f"   Tables: {migration_status['tables_valid']}/{migration_status['tables_checked']} valid")
    print(f"   Admin Key: Generated (save securely)")
    print(f"   Symbols: {seeded_count} seeded")
    
    print("\n✅ Database is ready for use!")
    
    print("\n📝 Next steps:")
    print("   1. Save the admin API key in a secure location")
    print("   2. Update your .env file with DATABASE_URL")
    print("   3. Start the application: python main.py")
    print("   4. Test endpoints with the admin API key")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(bootstrap_database())
    except KeyboardInterrupt:
        print("\n❌ Bootstrap interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Bootstrap failed: {str(e)}")
        sys.exit(1)
