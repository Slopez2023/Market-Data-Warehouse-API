"""Tests for API key management endpoints"""

import pytest
import os
import asyncpg
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from main import app
from src.services.auth import APIKeyService
from src.models import CreateAPIKeyRequest


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
async def auth_service():
    """Create auth service for testing"""
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/market_data")
    return APIKeyService(database_url)


@pytest.fixture
async def admin_api_key(auth_service):
    """Create and return an actual admin API key for testing"""
    result = await auth_service.create_api_key("Test Admin Key")
    yield result['api_key']
    
    # Cleanup - delete the key after test
    try:
        conn = await asyncpg.connect(auth_service.database_url)
        await conn.execute("DELETE FROM api_keys WHERE id = $1", result['id'])
        await conn.close()
    except Exception:
        pass


# ==================== CREATE API KEY ENDPOINT TESTS ====================

@pytest.mark.asyncio
async def test_create_api_key_success(client, admin_api_key):
    """Test creating a new API key"""
    # Mock the auth service
    with patch('main.get_auth_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.create_api_key.return_value = {
            'id': 1,
            'api_key': 'mdw_new_key_1234567890',
            'key_preview': 'mdw_new_ke...',
            'name': 'Production Key',
            'created_at': '2025-11-10T12:00:00'
        }
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/api/v1/admin/api-keys",
            headers={"X-API-Key": admin_api_key},
            json={"name": "Production Key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['id'] == 1
        assert data['name'] == 'Production Key'
        assert 'api_key' in data
        assert 'key_preview' in data


@pytest.mark.asyncio
async def test_create_api_key_with_empty_name(client, admin_api_key):
    """Test creating API key with empty name fails validation"""
    response = client.post(
        "/api/v1/admin/api-keys",
        headers={"X-API-Key": admin_api_key},
        json={"name": ""}
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_api_key_missing_name(client, admin_api_key):
    """Test creating API key without name fails validation"""
    response = client.post(
        "/api/v1/admin/api-keys",
        headers={"X-API-Key": admin_api_key},
        json={}
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_api_key_missing_auth_header(client):
    """Test creating API key without auth header fails"""
    response = client.post(
        "/api/v1/admin/api-keys",
        json={"name": "Production Key"}
    )
    
    # Should be rejected by middleware
    assert response.status_code in [401, 403]


# ==================== LIST API KEYS ENDPOINT TESTS ====================

@pytest.mark.asyncio
async def test_list_api_keys_success(client, admin_api_key):
    """Test listing API keys"""
    with patch('main.get_auth_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.list_api_keys.return_value = [
            {
                'id': 1,
                'name': 'Admin Key',
                'active': True,
                'created_at': '2025-11-10T12:00:00',
                'last_used': '2025-11-10T13:00:00',
                'request_count': 100
            },
            {
                'id': 2,
                'name': 'Production Key',
                'active': True,
                'created_at': '2025-11-10T12:00:00',
                'last_used': None,
                'request_count': 0
            }
        ]
        mock_get_service.return_value = mock_service
        
        response = client.get(
            "/api/v1/admin/api-keys",
            headers={"X-API-Key": admin_api_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]['name'] == 'Admin Key'
        assert data[1]['name'] == 'Production Key'


@pytest.mark.asyncio
async def test_list_api_keys_active_only(client, admin_api_key):
    """Test listing only active API keys"""
    with patch('main.get_auth_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.list_api_keys.return_value = [
            {
                'id': 1,
                'name': 'Active Key',
                'active': True,
                'created_at': '2025-11-10T12:00:00',
                'last_used': None,
                'request_count': 0
            }
        ]
        mock_get_service.return_value = mock_service
        
        response = client.get(
            "/api/v1/admin/api-keys?active_only=true",
            headers={"X-API-Key": admin_api_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]['active'] is True
        
        # Verify the service was called with correct parameter
        mock_service.list_api_keys.assert_called_with(active_only=True)


@pytest.mark.asyncio
async def test_list_api_keys_empty(client, admin_api_key):
    """Test listing when no API keys exist"""
    with patch('main.get_auth_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.list_api_keys.return_value = []
        mock_get_service.return_value = mock_service
        
        response = client.get(
            "/api/v1/admin/api-keys",
            headers={"X-API-Key": admin_api_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0


# ==================== AUDIT LOG ENDPOINT TESTS ====================

@pytest.mark.asyncio
async def test_get_audit_log_success(client, admin_api_key):
    """Test getting audit log for a key"""
    with patch('main.get_auth_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.get_audit_log.return_value = [
            {
                'id': 1,
                'endpoint': '/api/v1/symbols',
                'method': 'GET',
                'status_code': 200,
                'timestamp': '2025-11-10T12:00:00'
            },
            {
                'id': 2,
                'endpoint': '/api/v1/admin/symbols',
                'method': 'POST',
                'status_code': 201,
                'timestamp': '2025-11-10T12:05:00'
            }
        ]
        mock_get_service.return_value = mock_service
        
        response = client.get(
            "/api/v1/admin/api-keys/1/audit",
            headers={"X-API-Key": admin_api_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['key_id'] == 1
        assert len(data['entries']) == 2
        assert data['entries'][0]['endpoint'] == '/api/v1/symbols'
        assert data['entries'][0]['method'] == 'GET'
        assert data['total'] == 2
        assert data['limit'] == 100
        assert data['offset'] == 0


@pytest.mark.asyncio
async def test_get_audit_log_with_pagination(client, admin_api_key):
    """Test audit log with limit and offset"""
    with patch('main.get_auth_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.get_audit_log.return_value = []
        mock_get_service.return_value = mock_service
        
        response = client.get(
            "/api/v1/admin/api-keys/1/audit?limit=50&offset=25",
            headers={"X-API-Key": admin_api_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['limit'] == 50
        assert data['offset'] == 25
        
        # Verify service was called with correct parameters
        mock_service.get_audit_log.assert_called_with(1, limit=50, offset=25)


@pytest.mark.asyncio
async def test_get_audit_log_limit_validation(client, admin_api_key):
    """Test audit log respects limit constraints"""
    with patch('main.get_auth_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_get_service.return_value = mock_service
        
        # Try with limit > 1000 (should be rejected)
        response = client.get(
            "/api/v1/admin/api-keys/1/audit?limit=2000",
            headers={"X-API-Key": admin_api_key}
        )
        
        assert response.status_code == 422  # Validation error


# ==================== UPDATE API KEY ENDPOINT TESTS ====================

@pytest.mark.asyncio
async def test_revoke_api_key(client, admin_api_key):
    """Test revoking an API key"""
    with patch('main.get_auth_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.revoke_key.return_value = True
        mock_get_service.return_value = mock_service
        
        response = client.put(
            "/api/v1/admin/api-keys/1",
            headers={"X-API-Key": admin_api_key},
            json={"active": False}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['message'] == 'API key revoked'
        assert data['key_id'] == 1
        assert data['active'] is False
        
        # Verify revoke_key was called
        mock_service.revoke_key.assert_called_with(1)


@pytest.mark.asyncio
async def test_restore_api_key(client, admin_api_key):
    """Test restoring a revoked API key"""
    with patch('main.get_auth_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.restore_key.return_value = True
        mock_get_service.return_value = mock_service
        
        response = client.put(
            "/api/v1/admin/api-keys/1",
            headers={"X-API-Key": admin_api_key},
            json={"active": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['message'] == 'API key restored'
        assert data['key_id'] == 1
        assert data['active'] is True
        
        # Verify restore_key was called
        mock_service.restore_key.assert_called_with(1)


@pytest.mark.asyncio
async def test_update_api_key_missing_active_field(client, admin_api_key):
    """Test update without active field fails validation"""
    response = client.put(
        "/api/v1/admin/api-keys/1",
        headers={"X-API-Key": admin_api_key},
        json={}
    )
    
    assert response.status_code == 422  # Validation error


# ==================== DELETE API KEY ENDPOINT TESTS ====================

@pytest.mark.asyncio
async def test_delete_api_key_success(client, admin_api_key):
    """Test deleting an API key"""
    with patch('main.get_auth_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.delete_key.return_value = True
        mock_get_service.return_value = mock_service
        
        response = client.delete(
            "/api/v1/admin/api-keys/1",
            headers={"X-API-Key": admin_api_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['message'] == 'API key permanently deleted'
        assert data['key_id'] == 1
        
        # Verify delete_key was called
        mock_service.delete_key.assert_called_with(1)


@pytest.mark.asyncio
async def test_delete_api_key_failure(client, admin_api_key):
    """Test delete failure returns error"""
    with patch('main.get_auth_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.delete_key.return_value = False
        mock_get_service.return_value = mock_service
        
        response = client.delete(
            "/api/v1/admin/api-keys/999",
            headers={"X-API-Key": admin_api_key}
        )
        
        assert response.status_code == 500


# ==================== AUTHENTICATION TESTS ====================

@pytest.mark.asyncio
async def test_api_key_endpoint_requires_auth_header(client):
    """Test all endpoints require auth header"""
    endpoints = [
        ("POST", "/api/v1/admin/api-keys", {"name": "Test"}),
        ("GET", "/api/v1/admin/api-keys", None),
        ("GET", "/api/v1/admin/api-keys/1/audit", None),
        ("PUT", "/api/v1/admin/api-keys/1", {"active": False}),
        ("DELETE", "/api/v1/admin/api-keys/1", None),
    ]
    
    for method, path, data in endpoints:
        if method == "GET":
            response = client.get(path)
        elif method == "POST":
            response = client.post(path, json=data)
        elif method == "PUT":
            response = client.put(path, json=data)
        elif method == "DELETE":
            response = client.delete(path)
        
        # Should be rejected without auth header
        assert response.status_code in [401, 403], f"{method} {path} should require auth"


# ==================== INTEGRATION-LIKE TESTS ====================

@pytest.mark.asyncio
async def test_create_list_keys_workflow(client, admin_api_key):
    """Test workflow: create key then list it"""
    with patch('main.get_auth_service') as mock_get_service:
        mock_service = AsyncMock()
        
        # Mock create response
        mock_service.create_api_key.return_value = {
            'id': 1,
            'api_key': 'mdw_new_key_xyz',
            'key_preview': 'mdw_new_k...',
            'name': 'Test Key',
            'created_at': '2025-11-10T12:00:00'
        }
        
        mock_get_service.return_value = mock_service
        
        # Create key
        create_response = client.post(
            "/api/v1/admin/api-keys",
            headers={"X-API-Key": admin_api_key},
            json={"name": "Test Key"}
        )
        assert create_response.status_code == 200
        
        # Mock list response
        mock_service.list_api_keys.return_value = [
            {
                'id': 1,
                'name': 'Test Key',
                'active': True,
                'created_at': '2025-11-10T12:00:00',
                'last_used': None,
                'request_count': 0
            }
        ]
        
        # List keys
        list_response = client.get(
            "/api/v1/admin/api-keys",
            headers={"X-API-Key": admin_api_key}
        )
        assert list_response.status_code == 200
        data = list_response.json()
        assert len(data) == 1
        assert data[0]['name'] == 'Test Key'
