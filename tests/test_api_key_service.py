"""Tests for APIKeyService CRUD operations"""

import pytest
import asyncpg
import os
from datetime import datetime, timedelta

from src.services.auth import APIKeyService


@pytest.fixture
async def auth_service():
    """Create auth service for testing"""
    database_url = os.getenv("DATABASE_URL", "postgresql://testuser:testpass@localhost:5432/market_data_test")
    return APIKeyService(database_url)


@pytest.fixture
async def setup_and_cleanup(auth_service):
    """Setup and cleanup database for tests"""
    # This assumes migrations have been run
    yield
    
    # Cleanup - delete all test data
    try:
        conn = await asyncpg.connect(auth_service.database_url)
        await conn.execute("DELETE FROM api_key_audit")
        await conn.execute("DELETE FROM api_keys")
        await conn.close()
    except Exception:
        pass


# ==================== CREATE API KEY TESTS ====================

@pytest.mark.asyncio
async def test_create_api_key_success(auth_service, setup_and_cleanup):
    """Test creating an API key"""
    result = await auth_service.create_api_key("Test Key")
    
    assert result is not None
    assert 'id' in result
    assert 'api_key' in result
    assert 'key_preview' in result
    assert 'name' in result
    assert 'created_at' in result
    
    assert result['name'] == "Test Key"
    assert result['api_key'].startswith('mdw_')
    assert len(result['api_key']) > 10
    assert result['key_preview'] == result['api_key'][:12] + '...'


@pytest.mark.asyncio
async def test_create_api_key_generates_unique_keys(auth_service, setup_and_cleanup):
    """Test that each created key is unique"""
    result1 = await auth_service.create_api_key("Key 1")
    result2 = await auth_service.create_api_key("Key 2")
    
    assert result1['api_key'] != result2['api_key']
    assert result1['id'] != result2['id']


@pytest.mark.asyncio
async def test_create_api_key_with_long_name(auth_service, setup_and_cleanup):
    """Test creating key with long name"""
    long_name = "A" * 100
    result = await auth_service.create_api_key(long_name)
    
    assert result['name'] == long_name


# ==================== LIST API KEYS TESTS ====================

@pytest.mark.asyncio
async def test_list_api_keys_empty(auth_service, setup_and_cleanup):
    """Test listing when no keys exist"""
    result = await auth_service.list_api_keys()
    
    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_list_api_keys_multiple(auth_service, setup_and_cleanup):
    """Test listing multiple keys"""
    # Create multiple keys
    await auth_service.create_api_key("Key 1")
    await auth_service.create_api_key("Key 2")
    await auth_service.create_api_key("Key 3")
    
    result = await auth_service.list_api_keys()
    
    assert len(result) == 3
    assert all('id' in key for key in result)
    assert all('name' in key for key in result)
    assert all('active' in key for key in result)


@pytest.mark.asyncio
async def test_list_api_keys_contains_required_fields(auth_service, setup_and_cleanup):
    """Test list response contains all required fields"""
    await auth_service.create_api_key("Test Key")
    
    result = await auth_service.list_api_keys()
    
    assert len(result) > 0
    key = result[0]
    assert 'id' in key
    assert 'name' in key
    assert 'active' in key
    assert 'created_at' in key
    assert 'last_used' in key
    assert 'request_count' in key


@pytest.mark.asyncio
async def test_list_api_keys_active_only_filter(auth_service, setup_and_cleanup):
    """Test active_only filter"""
    # Create key
    result1 = await auth_service.create_api_key("Active Key")
    key_id = result1['id']
    
    # List all - should include the key
    all_keys = await auth_service.list_api_keys(active_only=False)
    assert len(all_keys) == 1
    
    # Revoke the key
    await auth_service.revoke_key(key_id)
    
    # List active only - should be empty
    active_keys = await auth_service.list_api_keys(active_only=True)
    assert len(active_keys) == 0
    
    # List all - should still include the revoked key
    all_keys = await auth_service.list_api_keys(active_only=False)
    assert len(all_keys) == 1


@pytest.mark.asyncio
async def test_list_api_keys_ordered_by_creation(auth_service, setup_and_cleanup):
    """Test that keys are ordered newest first"""
    import time
    
    await auth_service.create_api_key("Key 1")
    await asyncio.sleep(0.1)  # Small delay to ensure different timestamps
    await auth_service.create_api_key("Key 2")
    
    result = await auth_service.list_api_keys()
    
    # Most recent should be first
    assert result[0]['name'] == "Key 2"
    assert result[1]['name'] == "Key 1"


# ==================== AUDIT LOG TESTS ====================

@pytest.mark.asyncio
async def test_get_audit_log_empty(auth_service, setup_and_cleanup):
    """Test audit log for key with no usage"""
    result = await auth_service.create_api_key("Test Key")
    key_id = result['id']
    
    audit = await auth_service.get_audit_log(key_id)
    
    assert isinstance(audit, list)
    assert len(audit) == 0


@pytest.mark.asyncio
async def test_get_audit_log_with_entries(auth_service, setup_and_cleanup):
    """Test audit log with entries"""
    # Create key
    result = await auth_service.create_api_key("Test Key")
    key_id = result['id']
    api_key = result['api_key']
    
    # Log some usage
    await auth_service.log_api_usage(api_key, "/api/v1/symbols", "GET", 200)
    await auth_service.log_api_usage(api_key, "/api/v1/admin/symbols", "POST", 201)
    
    # Get audit log
    audit = await auth_service.get_audit_log(key_id)
    
    assert len(audit) == 2
    assert all('id' in entry for entry in audit)
    assert all('endpoint' in entry for entry in audit)
    assert all('method' in entry for entry in audit)
    assert all('status_code' in entry for entry in audit)
    assert all('timestamp' in entry for entry in audit)


@pytest.mark.asyncio
async def test_get_audit_log_with_pagination(auth_service, setup_and_cleanup):
    """Test audit log pagination"""
    # Create key and log many requests
    result = await auth_service.create_api_key("Test Key")
    key_id = result['id']
    api_key = result['api_key']
    
    # Log 10 requests
    for i in range(10):
        await auth_service.log_api_usage(api_key, f"/endpoint/{i}", "GET", 200)
    
    # Get with limit
    audit = await auth_service.get_audit_log(key_id, limit=5, offset=0)
    assert len(audit) == 5
    
    # Get with offset
    audit = await auth_service.get_audit_log(key_id, limit=5, offset=5)
    assert len(audit) == 5


@pytest.mark.asyncio
async def test_get_audit_log_ordered_by_timestamp(auth_service, setup_and_cleanup):
    """Test audit log is ordered newest first"""
    import asyncio
    
    result = await auth_service.create_api_key("Test Key")
    api_key = result['api_key']
    
    # Log requests with small delays
    await auth_service.log_api_usage(api_key, "/endpoint1", "GET", 200)
    await asyncio.sleep(0.1)
    await auth_service.log_api_usage(api_key, "/endpoint2", "GET", 200)
    
    audit = await auth_service.get_audit_log(result['id'])
    
    # Most recent should be first
    assert audit[0]['endpoint'] == "/endpoint2"
    assert audit[1]['endpoint'] == "/endpoint1"


# ==================== REVOKE KEY TESTS ====================

@pytest.mark.asyncio
async def test_revoke_key_success(auth_service, setup_and_cleanup):
    """Test revoking a key"""
    result = await auth_service.create_api_key("Test Key")
    key_id = result['id']
    
    success = await auth_service.revoke_key(key_id)
    
    assert success is True


@pytest.mark.asyncio
async def test_revoke_key_makes_it_inactive(auth_service, setup_and_cleanup):
    """Test revoked key becomes inactive"""
    result = await auth_service.create_api_key("Test Key")
    key_id = result['id']
    api_key = result['api_key']
    
    # Should be valid before revoke
    is_valid, metadata = await auth_service.validate_api_key(api_key)
    assert is_valid is True
    
    # Revoke
    await auth_service.revoke_key(key_id)
    
    # Should be invalid after revoke
    is_valid, metadata = await auth_service.validate_api_key(api_key)
    assert is_valid is False


@pytest.mark.asyncio
async def test_revoke_nonexistent_key(auth_service, setup_and_cleanup):
    """Test revoking nonexistent key"""
    success = await auth_service.revoke_key(999)
    
    # Should not crash, returns success (idempotent)
    assert isinstance(success, bool)


# ==================== RESTORE KEY TESTS ====================

@pytest.mark.asyncio
async def test_restore_key_success(auth_service, setup_and_cleanup):
    """Test restoring a revoked key"""
    result = await auth_service.create_api_key("Test Key")
    key_id = result['id']
    api_key = result['api_key']
    
    # Revoke
    await auth_service.revoke_key(key_id)
    
    # Should be invalid
    is_valid, _ = await auth_service.validate_api_key(api_key)
    assert is_valid is False
    
    # Restore
    success = await auth_service.restore_key(key_id)
    assert success is True
    
    # Should be valid again
    is_valid, _ = await auth_service.validate_api_key(api_key)
    assert is_valid is True


@pytest.mark.asyncio
async def test_restore_nonexistent_key(auth_service, setup_and_cleanup):
    """Test restoring nonexistent key"""
    success = await auth_service.restore_key(999)
    
    # Should not crash, returns success (idempotent)
    assert isinstance(success, bool)


# ==================== DELETE KEY TESTS ====================

@pytest.mark.asyncio
async def test_delete_key_success(auth_service, setup_and_cleanup):
    """Test deleting a key"""
    result = await auth_service.create_api_key("Test Key")
    key_id = result['id']
    
    success = await auth_service.delete_key(key_id)
    
    assert success is True


@pytest.mark.asyncio
async def test_delete_key_removes_it(auth_service, setup_and_cleanup):
    """Test deleted key is no longer listed"""
    result = await auth_service.create_api_key("Test Key")
    key_id = result['id']
    
    # Should be in list
    keys = await auth_service.list_api_keys()
    assert len(keys) == 1
    
    # Delete
    await auth_service.delete_key(key_id)
    
    # Should not be in list
    keys = await auth_service.list_api_keys()
    assert len(keys) == 0


@pytest.mark.asyncio
async def test_delete_key_removes_audit_logs(auth_service, setup_and_cleanup):
    """Test deleting key also deletes audit logs"""
    result = await auth_service.create_api_key("Test Key")
    key_id = result['id']
    api_key = result['api_key']
    
    # Log usage
    await auth_service.log_api_usage(api_key, "/endpoint", "GET", 200)
    
    # Verify audit log exists
    audit = await auth_service.get_audit_log(key_id)
    assert len(audit) == 1
    
    # Delete key
    await auth_service.delete_key(key_id)
    
    # Audit log should be gone
    # (key_id no longer exists, so get_audit_log returns empty)
    audit = await auth_service.get_audit_log(key_id)
    assert len(audit) == 0


@pytest.mark.asyncio
async def test_delete_nonexistent_key(auth_service, setup_and_cleanup):
    """Test deleting nonexistent key"""
    success = await auth_service.delete_key(999)
    
    # Should not crash
    assert isinstance(success, bool)


# ==================== IMPORT FOR ASYNC ====================

import asyncio
