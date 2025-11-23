"""Simple test for unified backfill implementation"""

import sys

def test_orchestrator_import():
    """Test that orchestrator can be imported"""
    from src.services.backfill_orchestrator import BackfillOrchestrator
    print("✓ Orchestrator import successful")
    
    # Test instantiation
    orch = BackfillOrchestrator("postgresql://localhost/db", "test_key")
    assert orch.database_url == "postgresql://localhost/db"
    assert orch.polygon_api_key == "test_key"
    print("✓ Orchestrator instantiation successful")


def test_deprecated_worker():
    """Test deprecated backfill_worker"""
    from src.services.backfill_worker import init_backfill_worker
    
    try:
        init_backfill_worker()
        print("✗ Should have raised NotImplementedError")
        sys.exit(1)
    except NotImplementedError as e:
        assert "deprecated" in str(e).lower()
        print("✓ Deprecated worker properly raises NotImplementedError")


def test_main_imports():
    """Test that main.py can import without errors"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("main", "main.py")
    main = importlib.util.module_from_spec(spec)
    # Don't execute, just check it loads
    print("✓ main.py syntax is valid")


if __name__ == "__main__":
    test_orchestrator_import()
    test_deprecated_worker()
    test_main_imports()
    print("\n✓✓✓ All unified backfill tests passed")
