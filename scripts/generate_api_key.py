#!/usr/bin/env python3
"""
Generate a new API key for accessing the Market Data API.

Usage:
    python scripts/generate_api_key.py "Project Name"
    
Output:
    - Stores key in database (hashed)
    - Outputs raw API key (only shown once!)
    - Shows key preview for reference
"""

import asyncio
import sys
import asyncpg
from datetime import datetime
import os

from src.services.auth import APIKeyService
from src.config import config


async def generate_and_store_key(name: str):
    """Generate and store a new API key"""
    
    if not name or len(name.strip()) == 0:
        print("Error: Project name cannot be empty")
        sys.exit(1)
    
    name = name.strip()
    
    # Generate raw key
    api_key = APIKeyService.generate_api_key(name)
    key_hash = APIKeyService.hash_api_key(api_key)
    
    # Store in database
    try:
        conn = await asyncpg.connect(config.database_url)
        
        # Check if this name already exists
        existing = await conn.fetchrow(
            "SELECT id FROM api_keys WHERE name = $1",
            name
        )
        
        if existing:
            print(f"Error: API key with name '{name}' already exists")
            await conn.close()
            sys.exit(1)
        
        # Insert new key
        row = await conn.fetchrow(
            """
            INSERT INTO api_keys (key_hash, name, active, created_at)
            VALUES ($1, $2, TRUE, NOW())
            RETURNING id, created_at
            """,
            key_hash, name
        )
        
        await conn.close()
        
        # Show results
        key_preview = api_key[:8]
        
        print("\n" + "="*70)
        print("✓ API Key Generated Successfully")
        print("="*70)
        print(f"\nProject: {name}")
        print(f"Created: {row['created_at'].isoformat()}")
        print(f"\nAPI Key (save this - it won't be shown again):")
        print(f"\n  {api_key}\n")
        print(f"Key Preview (for reference): {key_preview}...")
        print(f"\nUsage in requests:")
        print(f"  curl -H 'X-API-Key: {api_key}' \\")
        print(f"    'http://localhost:8000/api/v1/historical/AAPL?start=2023-01-01&end=2023-12-31'")
        print("\n" + "="*70 + "\n")
        
        return api_key
    
    except asyncpg.UniqueViolationError:
        print(f"Error: This API key already exists (collision - extremely unlikely)")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to generate API key: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_api_key.py \"Project Name\"")
        print("\nExample: python scripts/generate_api_key.py \"My Trading Bot\"")
        sys.exit(1)
    
    project_name = sys.argv[1]
    
    # Run async function
    api_key = asyncio.run(generate_and_store_key(project_name))
