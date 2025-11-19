#!/usr/bin/env python3
"""
Validation script for backfill dashboard functionality.
Tests all core components are properly configured.
"""

import os
import sys
from pathlib import Path

def check_file_exists(path: str, description: str) -> bool:
    """Check if a file exists and report."""
    exists = Path(path).exists()
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {path}")
    return exists

def check_imports() -> bool:
    """Check if all required modules can be imported."""
    print("\n=== CHECKING IMPORTS ===")
    try:
        from src.services.migrations import run_migrations
        print("✓ Migration runner imports correctly")
    except Exception as e:
        print(f"✗ Migration runner import failed: {e}")
        return False
    
    try:
        from src.services.backfill_worker import init_backfill_worker
        print("✓ Backfill worker imports correctly")
    except Exception as e:
        print(f"✗ Backfill worker import failed: {e}")
        return False
    
    try:
        from src.services.database_service import DatabaseService
        print("✓ Database service imports correctly")
    except Exception as e:
        print(f"✗ Database service import failed: {e}")
        return False
    
    return True

def check_database_schema() -> bool:
    """Check if backfill tables exist."""
    print("\n=== CHECKING DATABASE SCHEMA ===")
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from src.config import config
        from sqlalchemy import inspect, create_engine
        
        engine = create_engine(config.database_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        required_tables = ['backfill_jobs', 'backfill_job_progress']
        all_exist = True
        
        for table in required_tables:
            exists = table in tables
            status = "✓" if exists else "✗"
            print(f"{status} Table '{table}' exists")
            all_exist = all_exist and exists
        
        return all_exist
        
    except Exception as e:
        print(f"✗ Could not check database: {e}")
        return False

def check_files() -> bool:
    """Check if all required files exist."""
    print("\n=== CHECKING FILES ===")
    
    files_to_check = [
        ("main.py", "Main FastAPI application"),
        ("src/services/migrations.py", "Migration runner"),
        ("src/services/backfill_worker.py", "Backfill worker"),
        ("dashboard/index.html", "Dashboard HTML"),
        ("dashboard/script.js", "Dashboard JavaScript"),
        ("dashboard/style.css", "Dashboard CSS"),
        ("database/004_backfill_jobs.sql", "Backfill migration SQL"),
    ]
    
    all_exist = True
    for file_path, description in files_to_check:
        exists = check_file_exists(file_path, description)
        all_exist = all_exist and exists
    
    return all_exist

def check_api_endpoints() -> bool:
    """Check if backfill endpoints are defined in main.py."""
    print("\n=== CHECKING API ENDPOINTS ===")
    
    try:
        with open("main.py", "r") as f:
            content = f.read()
        
        endpoints = [
            ("@app.post(\"/api/v1/backfill\")", "POST /api/v1/backfill"),
            ("@app.get(\"/api/v1/backfill/status/{job_id}\")", "GET /api/v1/backfill/status/{job_id}"),
            ("@app.get(\"/api/v1/backfill/recent\")", "GET /api/v1/backfill/recent"),
        ]
        
        all_found = True
        for endpoint_text, endpoint_desc in endpoints:
            found = endpoint_text in content
            status = "✓" if found else "✗"
            print(f"{status} Endpoint defined: {endpoint_desc}")
            all_found = all_found and found
        
        return all_found
        
    except Exception as e:
        print(f"✗ Could not check endpoints: {e}")
        return False

def check_dashboard_functions() -> bool:
    """Check if dashboard has required functions."""
    print("\n=== CHECKING DASHBOARD FUNCTIONS ===")
    
    try:
        with open("dashboard/script.js", "r") as f:
            content = f.read()
        
        functions = [
            ("triggerManualBackfill", "Manual backfill trigger"),
            ("submitBackfill", "Backfill submission"),
            ("openBackfillModal", "Backfill modal opener"),
            ("getSelectedSymbols", "Symbol selection getter"),
            ("formatNumber", "Number formatter"),
            ("formatDate", "Date formatter"),
            ("pollBackfillStatus", "Status polling"),
        ]
        
        all_found = True
        for func_name, func_desc in functions:
            found = f"function {func_name}" in content or f"async function {func_name}" in content
            status = "✓" if found else "✗"
            print(f"{status} Function exists: {func_desc} ({func_name})")
            all_found = all_found and found
        
        return all_found
        
    except Exception as e:
        print(f"✗ Could not check dashboard: {e}")
        return False

def main():
    """Run all validation checks."""
    print("=" * 60)
    print("BACKFILL DASHBOARD VALIDATION")
    print("=" * 60)
    
    os.chdir(Path(__file__).parent)
    
    results = []
    
    # Run checks
    results.append(("Files exist", check_files()))
    results.append(("API endpoints defined", check_api_endpoints()))
    results.append(("Dashboard functions", check_dashboard_functions()))
    results.append(("Imports work", check_imports()))
    results.append(("Database schema", check_database_schema()))
    
    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for check_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {check_name}")
        all_passed = all_passed and passed
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ All validations passed! Backfill dashboard is ready.")
        return 0
    else:
        print("\n✗ Some validations failed. Please review errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
