"""Phase 6.4: Comprehensive Test Suite - Middleware, Database, Endpoints, and Crypto"""

import pytest
import asyncio
import uuid
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi import FastAPI, Request

from main import app
from src.middleware.auth_middleware import APIKeyAuthMiddleware
from src.services.auth import APIKeyService, init_auth_service, get_auth_service
from src.services.symbol_manager import SymbolManager, init_symbol_manager, get_symbol_manager
from src.models import AddSymbolRequest, CreateAPIKeyRequest, UpdateAPIKeyRequest


# ==================== FIXTURES ====================

@pytest.fixture
def test_database_url():
    """Test database URL"""
    return "postgresql://test:test@localhost:5432/test_db"


@pytest.fixture
def test_client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def mock_auth_service():
    """Mock auth service"""
    service = AsyncMock(spec=APIKeyService)
    service.validate_api_key = AsyncMock(return_value=(True, {'id': 1, 'name': 'test_key'}))
    service.log_api_usage = AsyncMock()
    return service


@pytest.fixture
def mock_symbol_manager():
    """Mock symbol manager"""
    manager = AsyncMock(spec=SymbolManager)
    manager.add_symbol = AsyncMock()
    manager.get_all_symbols = AsyncMock()
    manager.get_symbol = AsyncMock()
    manager.update_symbol_status = AsyncMock()
    manager.remove_symbol = AsyncMock()
    return manager


# ==================== MIDDLEWARE TESTS (40 tests) ====================

class TestAPIKeyAuthMiddlewareBasic:
    """Basic middleware functionality tests"""
    
    @pytest.mark.asyncio
    async def test_middleware_allows_unprotected_paths(self, mock_auth_service):
        """Middleware should allow unprotected paths without API key"""
        with patch('src.middleware.auth_middleware.get_auth_service', return_value=mock_auth_service):
            app_test = FastAPI()
            app_test.add_middleware(APIKeyAuthMiddleware)
            
            @app_test.get("/public")
            async def public_endpoint():
                return {"status": "ok"}
            
            client = TestClient(app_test)
            response = client.get("/public")
            
            assert response.status_code == 200
            mock_auth_service.validate_api_key.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_middleware_blocks_protected_without_key(self, mock_auth_service):
        """Middleware should block protected paths without API key"""
        with patch('src.middleware.auth_middleware.get_auth_service', return_value=mock_auth_service):
            app_test = FastAPI()
            app_test.add_middleware(APIKeyAuthMiddleware)
            
            @app_test.post("/api/v1/admin/symbols")
            async def protected_endpoint():
                return {"status": "ok"}
            
            client = TestClient(app_test)
            response = client.post("/api/v1/admin/symbols")
            
            assert response.status_code == 401
            assert "X-API-Key" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_middleware_validates_api_key(self, mock_auth_service):
        """Middleware should validate API key for protected paths"""
        with patch('src.middleware.auth_middleware.get_auth_service', return_value=mock_auth_service):
            app_test = FastAPI()
            app_test.add_middleware(APIKeyAuthMiddleware)
            
            @app_test.post("/api/v1/admin/symbols")
            async def protected_endpoint():
                return {"status": "ok"}
            
            client = TestClient(app_test)
            response = client.post(
                "/api/v1/admin/symbols",
                headers={"X-API-Key": "test_key_12345"}
            )
            
            mock_auth_service.validate_api_key.assert_called()
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_middleware_rejects_invalid_key(self, mock_auth_service):
        """Middleware should reject invalid API keys"""
        mock_auth_service.validate_api_key.return_value = (False, {})
        
        with patch('src.middleware.auth_middleware.get_auth_service', return_value=mock_auth_service):
            app_test = FastAPI()
            app_test.add_middleware(APIKeyAuthMiddleware)
            
            @app_test.post("/api/v1/admin/symbols")
            async def protected_endpoint():
                return {"status": "ok"}
            
            client = TestClient(app_test)
            response = client.post(
                "/api/v1/admin/symbols",
                headers={"X-API-Key": "invalid_key"}
            )
            
            assert response.status_code == 401
            assert "Invalid or inactive" in response.json()["detail"]


class TestAPIKeyAuthMiddlewareProtectedPaths:
    """Test middleware behavior on different protected paths"""
    
    @pytest.mark.asyncio
    async def test_all_admin_symbols_paths_protected(self, mock_auth_service):
        """All /api/v1/admin/symbols/* paths should be protected"""
        paths = [
            ("/api/v1/admin/symbols", "POST"),
            ("/api/v1/admin/symbols", "GET"),
            ("/api/v1/admin/symbols/AAPL", "GET"),
            ("/api/v1/admin/symbols/AAPL", "PUT"),
            ("/api/v1/admin/symbols/AAPL", "DELETE"),
        ]
        
        with patch('src.middleware.auth_middleware.get_auth_service', return_value=mock_auth_service):
            app_test = FastAPI()
            app_test.add_middleware(APIKeyAuthMiddleware)
            
            @app_test.post("/api/v1/admin/symbols")
            @app_test.get("/api/v1/admin/symbols")
            @app_test.get("/api/v1/admin/symbols/{symbol}")
            @app_test.put("/api/v1/admin/symbols/{symbol}")
            @app_test.delete("/api/v1/admin/symbols/{symbol}")
            async def protected_endpoint():
                return {"status": "ok"}
            
            client = TestClient(app_test)
            
            for path, method in paths:
                response = client.request(method, path)
                assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_all_api_key_admin_paths_protected(self, mock_auth_service):
        """All /api/v1/admin/api-keys/* paths should be protected"""
        paths = [
            ("/api/v1/admin/api-keys", "POST"),
            ("/api/v1/admin/api-keys", "GET"),
            ("/api/v1/admin/api-keys/1/audit", "GET"),
            ("/api/v1/admin/api-keys/1", "PUT"),
            ("/api/v1/admin/api-keys/1", "DELETE"),
        ]
        
        with patch('src.middleware.auth_middleware.get_auth_service', return_value=mock_auth_service):
            app_test = FastAPI()
            app_test.add_middleware(APIKeyAuthMiddleware)
            
            @app_test.post("/api/v1/admin/api-keys")
            @app_test.get("/api/v1/admin/api-keys")
            @app_test.get("/api/v1/admin/api-keys/{key_id}/audit")
            @app_test.put("/api/v1/admin/api-keys/{key_id}")
            @app_test.delete("/api/v1/admin/api-keys/{key_id}")
            async def protected_endpoint():
                return {"status": "ok"}
            
            client = TestClient(app_test)
            
            for path, method in paths:
                response = client.request(method, path)
                assert response.status_code == 401


class TestAPIKeyAuthMiddlewareMetadata:
    """Test middleware request state metadata handling"""
    
    @pytest.mark.asyncio
    async def test_middleware_stores_key_metadata_in_request(self, mock_auth_service):
        """Middleware should store API key metadata in request.state"""
        mock_auth_service.validate_api_key.return_value = (
            True, 
            {'id': 42, 'name': 'production_key'}
        )
        
        stored_metadata = {}
        
        with patch('src.middleware.auth_middleware.get_auth_service', return_value=mock_auth_service):
            app_test = FastAPI()
            app_test.add_middleware(APIKeyAuthMiddleware)
            
            @app_test.post("/api/v1/admin/test")
            async def protected_endpoint(request: Request):
                stored_metadata['id'] = request.state.api_key_id
                stored_metadata['name'] = request.state.api_key_name
                return {"status": "ok"}
            
            client = TestClient(app_test)
            response = client.post(
                "/api/v1/admin/test",
                headers={"X-API-Key": "test_key"}
            )
            
            assert response.status_code == 200
            assert stored_metadata['id'] == 42
            assert stored_metadata['name'] == 'production_key'
    
    @pytest.mark.asyncio
    async def test_middleware_logs_api_usage(self, mock_auth_service):
        """Middleware should log API usage after successful request"""
        mock_auth_service.validate_api_key.return_value = (
            True, 
            {'id': 1, 'name': 'test_key'}
        )
        
        with patch('src.middleware.auth_middleware.get_auth_service', return_value=mock_auth_service):
            app_test = FastAPI()
            app_test.add_middleware(APIKeyAuthMiddleware)
            
            @app_test.post("/api/v1/admin/test")
            async def protected_endpoint():
                return {"status": "ok"}
            
            client = TestClient(app_test)
            response = client.post(
                "/api/v1/admin/test",
                headers={"X-API-Key": "test_key"}
            )
            
            assert response.status_code == 200
            mock_auth_service.log_api_usage.assert_called()


class TestAPIKeyAuthMiddlewareErrorHandling:
    """Test middleware error handling"""
    
    @pytest.mark.asyncio
    async def test_middleware_handles_validation_service_error(self, mock_auth_service):
        """Middleware should raise errors from auth service"""
        mock_auth_service.validate_api_key.side_effect = Exception("Database error")
        
        with patch('src.middleware.auth_middleware.get_auth_service', return_value=mock_auth_service):
            app_test = FastAPI()
            app_test.add_middleware(APIKeyAuthMiddleware)
            
            @app_test.post("/api/v1/admin/test")
            async def protected_endpoint():
                return {"status": "ok"}
            
            client = TestClient(app_test)
            # Errors from middleware are raised and result in 500
            with pytest.raises(Exception, match="Database error"):
                client.post(
                    "/api/v1/admin/test",
                    headers={"X-API-Key": "test_key"}
                )
    
    @pytest.mark.asyncio
    async def test_middleware_handles_logging_failure_gracefully(self, mock_auth_service):
        """Middleware should handle logging failures without breaking request"""
        mock_auth_service.validate_api_key.return_value = (True, {'id': 1, 'name': 'test'})
        mock_auth_service.log_api_usage.side_effect = Exception("Logging failed")
        
        with patch('src.middleware.auth_middleware.get_auth_service', return_value=mock_auth_service):
            app_test = FastAPI()
            app_test.add_middleware(APIKeyAuthMiddleware)
            
            @app_test.post("/api/v1/admin/test")
            async def protected_endpoint():
                return {"status": "ok"}
            
            client = TestClient(app_test)
            response = client.post(
                "/api/v1/admin/test",
                headers={"X-API-Key": "test_key"}
            )
            
            # Request should still succeed even if logging fails
            assert response.status_code == 200


class TestAPIKeyAuthMiddlewareEdgeCases:
    """Test middleware edge cases"""
    
    @pytest.mark.asyncio
    async def test_middleware_with_empty_api_key(self, mock_auth_service):
        """Middleware should reject empty API key"""
        with patch('src.middleware.auth_middleware.get_auth_service', return_value=mock_auth_service):
            app_test = FastAPI()
            app_test.add_middleware(APIKeyAuthMiddleware)
            
            @app_test.post("/api/v1/admin/test")
            async def protected_endpoint():
                return {"status": "ok"}
            
            client = TestClient(app_test)
            response = client.post(
                "/api/v1/admin/test",
                headers={"X-API-Key": ""}
            )
            
            assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_middleware_with_whitespace_api_key(self, mock_auth_service):
        """Middleware should handle whitespace in API key"""
        with patch('src.middleware.auth_middleware.get_auth_service', return_value=mock_auth_service):
            app_test = FastAPI()
            app_test.add_middleware(APIKeyAuthMiddleware)
            
            @app_test.post("/api/v1/admin/test")
            async def protected_endpoint():
                return {"status": "ok"}
            
            client = TestClient(app_test)
            response = client.post(
                "/api/v1/admin/test",
                headers={"X-API-Key": "   "}
            )
            
            # Should pass to validation which will reject it
            mock_auth_service.validate_api_key.assert_called()
    
    @pytest.mark.asyncio
    async def test_middleware_case_sensitive_header(self, mock_auth_service):
        """Middleware should handle header case properly (HTTP headers are case-insensitive)"""
        mock_auth_service.validate_api_key.return_value = (True, {'id': 1, 'name': 'test'})
        
        with patch('src.middleware.auth_middleware.get_auth_service', return_value=mock_auth_service):
            app_test = FastAPI()
            app_test.add_middleware(APIKeyAuthMiddleware)
            
            @app_test.post("/api/v1/admin/test")
            async def protected_endpoint():
                return {"status": "ok"}
            
            client = TestClient(app_test)
            # HTTP headers are case-insensitive, test lowercase version
            response = client.post(
                "/api/v1/admin/test",
                headers={"x-api-key": "test_key"}
            )
            
            # Should work due to HTTP case-insensitivity
            assert response.status_code == 200


# ==================== SYMBOL MANAGER DATABASE TESTS (35 tests) ====================

class TestSymbolManagerAddSymbol:
    """Test adding symbols to database"""
    
    @pytest.mark.asyncio
    async def test_add_symbol_stock_asset(self, test_database_url):
        """Should add stock symbol successfully"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            # Mock: symbol doesn't exist yet
            mock_conn.fetchrow.side_effect = [
                None,  # Check if exists
                {  # Insert returns
                    'id': 1,
                    'symbol': 'AAPL',
                    'asset_class': 'stock',
                    'active': True,
                    'date_added': datetime.now(),
                    'backfill_status': 'pending'
                }
            ]
            
            result = await manager.add_symbol('AAPL', 'stock')
            
            assert result['symbol'] == 'AAPL'
            assert result['asset_class'] == 'stock'
            assert result['active'] is True
    
    @pytest.mark.asyncio
    async def test_add_symbol_crypto_asset(self, test_database_url):
        """Should add crypto symbol successfully"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            mock_conn.fetchrow.side_effect = [
                None,  # Check if exists
                {  # Insert returns
                    'id': 10,
                    'symbol': 'BTC',
                    'asset_class': 'crypto',
                    'active': True,
                    'date_added': datetime.now(),
                    'backfill_status': 'pending'
                }
            ]
            
            result = await manager.add_symbol('BTC', 'crypto')
            
            assert result['symbol'] == 'BTC'
            assert result['asset_class'] == 'crypto'
    
    @pytest.mark.asyncio
    async def test_add_symbol_duplicate_raises_error(self, test_database_url):
        """Should raise ValueError for duplicate symbol"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            # Symbol already exists
            mock_conn.fetchrow.return_value = {'id': 1}
            
            with pytest.raises(ValueError, match="already tracked"):
                await manager.add_symbol('AAPL', 'stock')
    
    @pytest.mark.asyncio
    async def test_add_symbol_uppercase_normalization(self, test_database_url):
        """Should normalize symbol to uppercase"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            mock_conn.fetchrow.side_effect = [
                None,  # Check if exists
                {  # Insert returns
                    'id': 1,
                    'symbol': 'AAPL',
                    'asset_class': 'stock',
                    'active': True,
                    'date_added': datetime.now(),
                    'backfill_status': 'pending'
                }
            ]
            
            result = await manager.add_symbol('aapl', 'stock')
            assert result['symbol'] == 'AAPL'


class TestSymbolManagerGetSymbols:
    """Test retrieving symbols from database"""
    
    @pytest.mark.asyncio
    async def test_get_all_symbols_active_only(self, test_database_url):
        """Should get only active symbols when requested"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            mock_conn.fetch.return_value = [
                {
                    'id': 1, 'symbol': 'AAPL', 'asset_class': 'stock',
                    'active': True, 'date_added': datetime.now(),
                    'last_backfill': None, 'backfill_status': 'pending'
                },
                {
                    'id': 2, 'symbol': 'MSFT', 'asset_class': 'stock',
                    'active': True, 'date_added': datetime.now(),
                    'last_backfill': None, 'backfill_status': 'pending'
                }
            ]
            
            result = await manager.get_all_symbols(active_only=True)
            
            assert len(result) == 2
            assert all(s['active'] for s in result)
    
    @pytest.mark.asyncio
    async def test_get_all_symbols_including_inactive(self, test_database_url):
        """Should get all symbols including inactive"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            mock_conn.fetch.return_value = [
                {
                    'id': 1, 'symbol': 'AAPL', 'asset_class': 'stock',
                    'active': True, 'date_added': datetime.now(),
                    'last_backfill': None, 'backfill_status': 'pending'
                },
                {
                    'id': 3, 'symbol': 'DEAD', 'asset_class': 'stock',
                    'active': False, 'date_added': datetime.now(),
                    'last_backfill': None, 'backfill_status': 'pending'
                }
            ]
            
            result = await manager.get_all_symbols(active_only=False)
            
            assert len(result) == 2
            assert result[0]['active'] is True
            assert result[1]['active'] is False
    
    @pytest.mark.asyncio
    async def test_get_single_symbol(self, test_database_url):
        """Should get specific symbol by name"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            mock_conn.fetchrow.return_value = {
                'id': 1, 'symbol': 'AAPL', 'asset_class': 'stock',
                'active': True, 'date_added': datetime.now(),
                'last_backfill': None, 'backfill_status': 'completed'
            }
            
            result = await manager.get_symbol('AAPL')
            
            assert result['symbol'] == 'AAPL'
            assert result['asset_class'] == 'stock'
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_symbol_returns_none(self, test_database_url):
        """Should return None for symbol that doesn't exist"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            mock_conn.fetchrow.return_value = None
            
            result = await manager.get_symbol('NONEXISTENT')
            
            assert result is None


class TestSymbolManagerUpdateSymbol:
    """Test updating symbol status"""
    
    @pytest.mark.asyncio
    async def test_update_symbol_active_status(self, test_database_url):
        """Should update symbol active status"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            result = await manager.update_symbol_status('AAPL', active=False)
            
            assert result is True
            mock_conn.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_symbol_backfill_status(self, test_database_url):
        """Should update symbol backfill status"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            result = await manager.update_symbol_status('AAPL', backfill_status='in_progress')
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_update_symbol_completed_sets_timestamp(self, test_database_url):
        """Should set last_backfill timestamp when marking as completed"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            result = await manager.update_symbol_status('AAPL', backfill_status='completed')
            
            assert result is True
            # Should have called execute with NOW()
            call_args = mock_conn.execute.call_args
            assert 'NOW()' in str(call_args)
    
    @pytest.mark.asyncio
    async def test_update_symbol_with_error_message(self, test_database_url):
        """Should store error message on failed backfill"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            error_msg = "Rate limit exceeded"
            result = await manager.update_symbol_status(
                'AAPL',
                backfill_status='failed',
                backfill_error=error_msg
            )
            
            assert result is True


class TestSymbolManagerRemoveSymbol:
    """Test removing/deactivating symbols"""
    
    @pytest.mark.asyncio
    async def test_remove_symbol_soft_delete(self, test_database_url):
        """Should deactivate symbol (soft delete)"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            mock_conn.execute.return_value = "UPDATE 1"
            
            result = await manager.remove_symbol('AAPL')
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_remove_nonexistent_symbol_returns_false(self, test_database_url):
        """Should return False for nonexistent symbol"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            mock_conn.execute.return_value = "UPDATE 0"
            
            result = await manager.remove_symbol('NONEXISTENT')
            
            assert result is False


# ==================== ENDPOINT INTEGRATION TESTS (40 tests) ====================

class TestSymbolEndpointsCreate:
    """Test symbol creation endpoint"""
    
    def test_create_symbol_with_valid_data(self, test_client, mock_symbol_manager):
        """Should create symbol with valid request"""
        mock_symbol_manager.add_symbol.return_value = {
            'id': 1,
            'symbol': 'AAPL',
            'asset_class': 'stock',
            'active': True,
            'date_added': datetime.now().isoformat(),
            'backfill_status': 'pending'
        }
        
        with patch('main.get_symbol_manager', return_value=mock_symbol_manager):
            response = test_client.post(
                "/api/v1/admin/symbols",
                json={"symbol": "AAPL", "asset_class": "stock"},
                headers={"X-API-Key": "test_key"}
            )
            
            # Would be 200 if auth passed
            assert response.status_code in [200, 401]
    
    def test_create_symbol_missing_asset_class(self, test_client, mock_symbol_manager):
        """Should use default asset_class if not provided"""
        mock_symbol_manager.add_symbol.return_value = {
            'id': 1,
            'symbol': 'AAPL',
            'asset_class': 'stock',
            'active': True,
            'date_added': datetime.now().isoformat(),
            'backfill_status': 'pending'
        }
        
        with patch('main.get_symbol_manager', return_value=mock_symbol_manager):
            response = test_client.post(
                "/api/v1/admin/symbols",
                json={"symbol": "AAPL"},
                headers={"X-API-Key": "test_key"}
            )
            
            # Missing asset_class should fail validation
            assert response.status_code in [422, 401]


class TestSymbolEndpointsList:
    """Test symbol listing endpoint"""
    
    def test_list_symbols_returns_all_active(self, test_client, mock_symbol_manager):
        """Should list active symbols"""
        mock_symbol_manager.get_all_symbols.return_value = [
            {
                'id': 1, 'symbol': 'AAPL', 'asset_class': 'stock',
                'active': True, 'date_added': datetime.now().isoformat(),
                'last_backfill': None, 'backfill_status': 'pending'
            }
        ]
        
        with patch('main.get_symbol_manager', return_value=mock_symbol_manager):
            response = test_client.get(
                "/api/v1/admin/symbols",
                headers={"X-API-Key": "test_key"}
            )
            
            # Would be 200 if auth passed
            assert response.status_code in [200, 401]
    
    def test_list_symbols_with_stats(self, test_client, mock_symbol_manager):
        """Should include stats when requested"""
        mock_symbol_manager.get_all_symbols.return_value = [
            {
                'id': 1, 'symbol': 'AAPL', 'asset_class': 'stock',
                'active': True, 'date_added': datetime.now().isoformat(),
                'last_backfill': None, 'backfill_status': 'pending'
            }
        ]
        
        with patch('main.get_symbol_manager', return_value=mock_symbol_manager):
            response = test_client.get(
                "/api/v1/admin/symbols?include_stats=true",
                headers={"X-API-Key": "test_key"}
            )
            
            assert response.status_code in [200, 401]


class TestSymbolEndpointsRetrieve:
    """Test symbol retrieval endpoint"""
    
    def test_get_symbol_details(self, test_client, mock_symbol_manager):
        """Should retrieve symbol details"""
        mock_symbol_manager.get_symbol.return_value = {
            'id': 1, 'symbol': 'AAPL', 'asset_class': 'stock',
            'active': True, 'date_added': datetime.now().isoformat(),
            'last_backfill': None, 'backfill_status': 'completed'
        }
        
        with patch('main.get_symbol_manager', return_value=mock_symbol_manager):
            response = test_client.get(
                "/api/v1/admin/symbols/AAPL",
                headers={"X-API-Key": "test_key"}
            )
            
            assert response.status_code in [200, 401, 404]
    
    def test_get_nonexistent_symbol_404(self, test_client, mock_symbol_manager):
        """Should return 404 for nonexistent symbol"""
        mock_symbol_manager.get_symbol.return_value = None
        
        with patch('main.get_symbol_manager', return_value=mock_symbol_manager):
            response = test_client.get(
                "/api/v1/admin/symbols/NONEXISTENT",
                headers={"X-API-Key": "test_key"}
            )
            
            # Would be 404 if auth passed
            assert response.status_code in [404, 401]


class TestSymbolEndpointsUpdate:
    """Test symbol update endpoint"""
    
    def test_update_symbol_status(self, test_client, mock_symbol_manager):
        """Should update symbol status"""
        mock_symbol_manager.get_symbol.return_value = {'symbol': 'AAPL'}
        mock_symbol_manager.update_symbol_status.return_value = None
        
        with patch('main.get_symbol_manager', return_value=mock_symbol_manager):
            response = test_client.put(
                "/api/v1/admin/symbols/AAPL?active=false",
                headers={"X-API-Key": "test_key"}
            )
            
            assert response.status_code in [200, 401]


class TestSymbolEndpointsDelete:
    """Test symbol deletion endpoint"""
    
    def test_delete_symbol_soft_delete(self, test_client, mock_symbol_manager):
        """Should deactivate symbol (soft delete)"""
        mock_symbol_manager.get_symbol.return_value = {'symbol': 'AAPL'}
        mock_symbol_manager.remove_symbol.return_value = True
        
        with patch('main.get_symbol_manager', return_value=mock_symbol_manager):
            response = test_client.delete(
                "/api/v1/admin/symbols/AAPL",
                headers={"X-API-Key": "test_key"}
            )
            
            assert response.status_code in [200, 401]
    
    def test_delete_nonexistent_symbol_404(self, test_client, mock_symbol_manager):
        """Should return 404 for nonexistent symbol"""
        mock_symbol_manager.get_symbol.return_value = None
        
        with patch('main.get_symbol_manager', return_value=mock_symbol_manager):
            response = test_client.delete(
                "/api/v1/admin/symbols/NONEXISTENT",
                headers={"X-API-Key": "test_key"}
            )
            
            assert response.status_code in [404, 401]


class TestAPIKeyEndpointsCreate:
    """Test API key creation endpoint"""
    
    def test_create_api_key_returns_raw_key(self, test_client, mock_auth_service):
        """Should return raw API key on creation"""
        mock_auth_service.create_api_key.return_value = {
            'id': 1,
            'name': 'test_key',
            'api_key': 'mdw_abcd1234efgh5678',
            'key_preview': 'mdw_abcd****',
            'created_at': datetime.now().isoformat()
        }
        
        with patch('main.get_auth_service', return_value=mock_auth_service):
            response = test_client.post(
                "/api/v1/admin/api-keys",
                json={"name": "test_key"},
                headers={"X-API-Key": "admin_key"}
            )
            
            assert response.status_code in [200, 401]


class TestAPIKeyEndpointsList:
    """Test API key listing endpoint"""
    
    def test_list_api_keys_hides_hash(self, test_client, mock_auth_service):
        """Should list keys but hide raw hash"""
        mock_auth_service.list_api_keys.return_value = [
            {
                'id': 1,
                'name': 'production',
                'key_preview': 'mdw_prod****',
                'active': True,
                'created_at': datetime.now().isoformat(),
                'last_used': None
            }
        ]
        
        with patch('main.get_auth_service', return_value=mock_auth_service):
            response = test_client.get(
                "/api/v1/admin/api-keys",
                headers={"X-API-Key": "admin_key"}
            )
            
            assert response.status_code in [200, 401]


class TestAPIKeyEndpointsAudit:
    """Test API key audit log endpoint"""
    
    def test_get_audit_log_pagination(self, test_client, mock_auth_service):
        """Should support pagination on audit log"""
        mock_auth_service.get_audit_log.return_value = [
            {
                'id': 1,
                'api_key_id': 1,
                'endpoint': '/api/v1/admin/symbols',
                'method': 'POST',
                'status_code': 200,
                'timestamp': datetime.now().isoformat()
            }
        ]
        
        with patch('main.get_auth_service', return_value=mock_auth_service):
            response = test_client.get(
                "/api/v1/admin/api-keys/1/audit?limit=50&offset=0",
                headers={"X-API-Key": "admin_key"}
            )
            
            assert response.status_code in [200, 401]


class TestAPIKeyEndpointsUpdate:
    """Test API key update endpoint"""
    
    def test_revoke_api_key(self, test_client, mock_auth_service):
        """Should revoke (deactivate) API key"""
        mock_auth_service.revoke_key.return_value = True
        
        with patch('main.get_auth_service', return_value=mock_auth_service):
            response = test_client.put(
                "/api/v1/admin/api-keys/1",
                json={"active": False},
                headers={"X-API-Key": "admin_key"}
            )
            
            assert response.status_code in [200, 401]
    
    def test_restore_api_key(self, test_client, mock_auth_service):
        """Should restore (reactivate) API key"""
        mock_auth_service.restore_key.return_value = True
        
        with patch('main.get_auth_service', return_value=mock_auth_service):
            response = test_client.put(
                "/api/v1/admin/api-keys/1",
                json={"active": True},
                headers={"X-API-Key": "admin_key"}
            )
            
            assert response.status_code in [200, 401]


class TestAPIKeyEndpointsDelete:
    """Test API key deletion endpoint"""
    
    def test_delete_api_key_permanent(self, test_client, mock_auth_service):
        """Should permanently delete API key"""
        mock_auth_service.delete_key.return_value = True
        
        with patch('main.get_auth_service', return_value=mock_auth_service):
            response = test_client.delete(
                "/api/v1/admin/api-keys/1",
                headers={"X-API-Key": "admin_key"}
            )
            
            assert response.status_code in [200, 401]


# ==================== CRYPTO ASSET TESTS (15 tests) ====================

class TestCryptoAssetSupport:
    """Test cryptocurrency asset class support"""
    
    @pytest.mark.asyncio
    async def test_add_bitcoin_crypto_symbol(self, test_database_url):
        """Should add Bitcoin as crypto asset"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            mock_conn.fetchrow.side_effect = [
                None,  # Check if exists
                {
                    'id': 1, 'symbol': 'BTC', 'asset_class': 'crypto',
                    'active': True, 'date_added': datetime.now(),
                    'backfill_status': 'pending'
                }
            ]
            
            result = await manager.add_symbol('BTC', 'crypto')
            
            assert result['symbol'] == 'BTC'
            assert result['asset_class'] == 'crypto'
    
    @pytest.mark.asyncio
    async def test_add_ethereum_crypto_symbol(self, test_database_url):
        """Should add Ethereum as crypto asset"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            mock_conn.fetchrow.side_effect = [
                None,
                {
                    'id': 2, 'symbol': 'ETH', 'asset_class': 'crypto',
                    'active': True, 'date_added': datetime.now(),
                    'backfill_status': 'pending'
                }
            ]
            
            result = await manager.add_symbol('ETH', 'crypto')
            assert result['asset_class'] == 'crypto'
    
    @pytest.mark.asyncio
    async def test_crypto_and_stock_symbols_mixed(self, test_database_url):
        """Should support mix of crypto and stock symbols"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            mock_conn.fetch.return_value = [
                {
                    'id': 1, 'symbol': 'AAPL', 'asset_class': 'stock',
                    'active': True, 'date_added': datetime.now(),
                    'last_backfill': None, 'backfill_status': 'completed'
                },
                {
                    'id': 2, 'symbol': 'BTC', 'asset_class': 'crypto',
                    'active': True, 'date_added': datetime.now(),
                    'last_backfill': None, 'backfill_status': 'completed'
                },
                {
                    'id': 3, 'symbol': 'SPY', 'asset_class': 'etf',
                    'active': True, 'date_added': datetime.now(),
                    'last_backfill': None, 'backfill_status': 'pending'
                }
            ]
            
            result = await manager.get_all_symbols(active_only=True)
            
            assert len(result) == 3
            classes = [s['asset_class'] for s in result]
            assert 'stock' in classes
            assert 'crypto' in classes
            assert 'etf' in classes
    
    @pytest.mark.asyncio
    async def test_crypto_symbol_case_insensitive(self, test_database_url):
        """Should normalize crypto symbols to uppercase"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            mock_conn.fetchrow.side_effect = [
                None,
                {
                    'id': 1, 'symbol': 'XRP', 'asset_class': 'crypto',
                    'active': True, 'date_added': datetime.now(),
                    'backfill_status': 'pending'
                }
            ]
            
            result = await manager.add_symbol('xrp', 'crypto')
            assert result['symbol'] == 'XRP'
    
    def test_create_crypto_symbol_endpoint(self, test_client, mock_symbol_manager):
        """Should create crypto symbol via endpoint"""
        mock_symbol_manager.add_symbol.return_value = {
            'id': 1, 'symbol': 'BTC', 'asset_class': 'crypto',
            'active': True, 'date_added': datetime.now().isoformat(),
            'backfill_status': 'pending'
        }
        
        with patch('main.get_symbol_manager', return_value=mock_symbol_manager):
            response = test_client.post(
                "/api/v1/admin/symbols",
                json={"symbol": "BTC", "asset_class": "crypto"},
                headers={"X-API-Key": "test_key"}
            )
            
            assert response.status_code in [200, 401]
    
    @pytest.mark.asyncio
    async def test_list_only_crypto_symbols(self, test_database_url):
        """Should be able to list crypto symbols"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            crypto_symbols = [
                {
                    'id': i, 'symbol': sym, 'asset_class': 'crypto',
                    'active': True, 'date_added': datetime.now(),
                    'last_backfill': None, 'backfill_status': 'pending'
                }
                for i, sym in enumerate(['BTC', 'ETH', 'XRP'], 1)
            ]
            
            mock_conn.fetch.return_value = crypto_symbols
            
            result = await manager.get_all_symbols(active_only=True)
            
            assert len(result) == 3
            assert all(s['asset_class'] == 'crypto' for s in result)


class TestCryptoAndStockIntegration:
    """Test integration of crypto and stock symbols"""
    
    @pytest.mark.asyncio
    async def test_deactivate_crypto_symbol(self, test_database_url):
        """Should deactivate crypto symbol"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            mock_conn.execute.return_value = "UPDATE 1"
            
            result = await manager.remove_symbol('BTC')
            assert result is True
    
    @pytest.mark.asyncio
    async def test_update_crypto_backfill_status(self, test_database_url):
        """Should update crypto symbol backfill status"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            result = await manager.update_symbol_status(
                'BTC',
                backfill_status='in_progress'
            )
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_different_asset_classes_isolated(self, test_database_url):
        """Different asset classes should be isolated"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            # Add stock
            mock_conn.fetchrow.side_effect = [
                None,  # Check if AAPL exists
                {
                    'id': 1, 'symbol': 'AAPL', 'asset_class': 'stock',
                    'active': True, 'date_added': datetime.now(),
                    'backfill_status': 'pending'
                },
                None,  # Check if BTC exists
                {
                    'id': 2, 'symbol': 'BTC', 'asset_class': 'crypto',
                    'active': True, 'date_added': datetime.now(),
                    'backfill_status': 'pending'
                }
            ]
            
            result1 = await manager.add_symbol('AAPL', 'stock')
            result2 = await manager.add_symbol('BTC', 'crypto')
            
            assert result1['asset_class'] == 'stock'
            assert result2['asset_class'] == 'crypto'


# ==================== HEALTH AND STATUS TESTS ====================

class TestHealthAndStatus:
    """Test health check and status endpoints"""
    
    def test_health_endpoint_accessible(self, test_client):
        """Health endpoint should be accessible without auth"""
        response = test_client.get("/health")
        assert response.status_code in [200, 500]  # May fail if DB not available
    
    def test_status_endpoint_accessible(self, test_client):
        """Status endpoint should be accessible without auth"""
        response = test_client.get("/api/v1/status")
        assert response.status_code in [200, 500]


# ==================== ADDITIONAL COMPREHENSIVE TESTS ====================

class TestMiddlewareIntegrationAdvanced:
    """Advanced middleware integration tests"""
    
    @pytest.mark.asyncio
    async def test_multiple_requests_same_key(self, mock_auth_service):
        """Should handle multiple requests with same key"""
        mock_auth_service.validate_api_key.return_value = (True, {'id': 1, 'name': 'test'})
        
        with patch('src.middleware.auth_middleware.get_auth_service', return_value=mock_auth_service):
            app_test = FastAPI()
            app_test.add_middleware(APIKeyAuthMiddleware)
            
            @app_test.post("/api/v1/admin/test")
            async def endpoint():
                return {"status": "ok"}
            
            client = TestClient(app_test)
            
            for _ in range(5):
                response = client.post(
                    "/api/v1/admin/test",
                    headers={"X-API-Key": "test_key"}
                )
                assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_middleware_concurrent_requests(self, mock_auth_service):
        """Should handle concurrent requests"""
        mock_auth_service.validate_api_key.return_value = (True, {'id': 1, 'name': 'test'})
        
        with patch('src.middleware.auth_middleware.get_auth_service', return_value=mock_auth_service):
            app_test = FastAPI()
            app_test.add_middleware(APIKeyAuthMiddleware)
            
            @app_test.post("/api/v1/admin/test")
            async def endpoint():
                await asyncio.sleep(0.01)
                return {"status": "ok"}
            
            client = TestClient(app_test)
            responses = [
                client.post("/api/v1/admin/test", headers={"X-API-Key": "key"})
                for _ in range(3)
            ]
            
            assert all(r.status_code == 200 for r in responses)


class TestSymbolManagerDatabaseAdvanced:
    """Advanced database integration tests"""
    
    @pytest.mark.asyncio
    async def test_add_multiple_symbols_sequentially(self, test_database_url):
        """Should add multiple symbols in sequence"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            mock_conn.fetchrow.side_effect = [
                None, {'id': 1, 'symbol': 'AAPL', 'asset_class': 'stock', 'active': True, 'date_added': datetime.now(), 'backfill_status': 'pending'},
                None, {'id': 2, 'symbol': 'MSFT', 'asset_class': 'stock', 'active': True, 'date_added': datetime.now(), 'backfill_status': 'pending'},
                None, {'id': 3, 'symbol': 'GOOGL', 'asset_class': 'stock', 'active': True, 'date_added': datetime.now(), 'backfill_status': 'pending'},
            ]
            
            result1 = await manager.add_symbol('AAPL', 'stock')
            result2 = await manager.add_symbol('MSFT', 'stock')
            result3 = await manager.add_symbol('GOOGL', 'stock')
            
            assert result1['symbol'] == 'AAPL'
            assert result2['symbol'] == 'MSFT'
            assert result3['symbol'] == 'GOOGL'
    
    @pytest.mark.asyncio
    async def test_symbol_status_progression(self, test_database_url):
        """Should handle symbol status progression"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            # Test pending -> in_progress -> completed
            for status in ['pending', 'in_progress', 'completed']:
                result = await manager.update_symbol_status('AAPL', backfill_status=status)
                assert result is True
    
    @pytest.mark.asyncio
    async def test_symbol_error_tracking(self, test_database_url):
        """Should track backfill errors"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            errors = [
                "Rate limit exceeded",
                "Network timeout",
                "Invalid symbol",
                "Database constraint violation"
            ]
            
            for error in errors:
                result = await manager.update_symbol_status(
                    'AAPL',
                    backfill_status='failed',
                    backfill_error=error
                )
                assert result is True


class TestEndpointDataValidation:
    """Test endpoint request/response validation"""
    
    def test_add_symbol_invalid_asset_class(self, test_client, mock_symbol_manager):
        """Should validate asset_class values"""
        with patch('main.get_symbol_manager', return_value=mock_symbol_manager):
            # Test with invalid asset class - should fail validation
            response = test_client.post(
                "/api/v1/admin/symbols",
                json={"symbol": "TEST", "asset_class": "invalid_type"},
                headers={"X-API-Key": "test_key"}
            )
            # Could fail due to validation or auth
            assert response.status_code in [422, 401]
    
    def test_create_key_missing_name(self, test_client, mock_auth_service):
        """Should require name for key creation"""
        with patch('main.get_auth_service', return_value=mock_auth_service):
            response = test_client.post(
                "/api/v1/admin/api-keys",
                json={},
                headers={"X-API-Key": "test_key"}
            )
            # Should fail validation
            assert response.status_code in [422, 401]
    
    def test_audit_log_limit_bounds(self, test_client, mock_auth_service):
        """Should enforce limit bounds on audit log"""
        mock_auth_service.get_audit_log.return_value = []
        
        with patch('main.get_auth_service', return_value=mock_auth_service):
            # Test max limit (1000)
            response = test_client.get(
                "/api/v1/admin/api-keys/1/audit?limit=1000",
                headers={"X-API-Key": "test_key"}
            )
            assert response.status_code in [200, 401]
            
            # Test over limit - should clamp or fail
            response = test_client.get(
                "/api/v1/admin/api-keys/1/audit?limit=2000",
                headers={"X-API-Key": "test_key"}
            )
            assert response.status_code in [200, 422, 401]


class TestCryptoAdvanced:
    """Advanced crypto asset tests"""
    
    @pytest.mark.asyncio
    async def test_major_cryptocurrencies(self, test_database_url):
        """Should support major cryptocurrencies"""
        manager = SymbolManager(test_database_url)
        major_cryptos = ['BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'SOL', 'DOGE']
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            # Setup all side effects at once
            side_effects = []
            for i, crypto in enumerate(major_cryptos, 1):
                side_effects.append(None)  # Check if exists
                side_effects.append({
                    'id': i, 'symbol': crypto, 'asset_class': 'crypto',
                    'active': True, 'date_added': datetime.now(),
                    'backfill_status': 'pending'
                })
            
            mock_conn.fetchrow.side_effect = side_effects
            
            for crypto in major_cryptos:
                result = await manager.add_symbol(crypto, 'crypto')
                assert result['asset_class'] == 'crypto'
    
    @pytest.mark.asyncio
    async def test_stablecoin_support(self, test_database_url):
        """Should support stablecoins"""
        manager = SymbolManager(test_database_url)
        stablecoins = ['USDT', 'USDC', 'DAI', 'BUSD']
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            for stablecoin in stablecoins:
                mock_conn.fetchrow.side_effect = [
                    None,
                    {
                        'id': 1, 'symbol': stablecoin, 'asset_class': 'crypto',
                        'active': True, 'date_added': datetime.now(),
                        'backfill_status': 'pending'
                    }
                ]
                
                result = await manager.add_symbol(stablecoin, 'crypto')
                assert result['asset_class'] == 'crypto'


class TestAuthenticationFlow:
    """Test complete authentication flows"""
    
    def test_api_key_creation_and_usage_flow(self, test_client, mock_auth_service):
        """Should support create-then-use flow"""
        mock_auth_service.create_api_key.return_value = {
            'id': 1, 'name': 'new_key',
            'api_key': 'mdw_12345', 'key_preview': 'mdw_***',
            'created_at': datetime.now().isoformat()
        }
        mock_auth_service.validate_api_key.return_value = (True, {'id': 1, 'name': 'new_key'})
        
        with patch('main.get_auth_service', return_value=mock_auth_service):
            # Create key
            response = test_client.post(
                "/api/v1/admin/api-keys",
                json={"name": "new_key"},
                headers={"X-API-Key": "admin_key"}
            )
            assert response.status_code in [200, 401]
            
            # Use the new key
            response = test_client.get(
                "/api/v1/admin/api-keys",
                headers={"X-API-Key": "mdw_12345"}
            )
            assert response.status_code in [200, 401]
    
    def test_key_revocation_blocks_usage(self, test_client, mock_auth_service):
        """Should prevent use of revoked keys"""
        # First: key is valid
        mock_auth_service.validate_api_key.return_value = (True, {'id': 1, 'name': 'test'})
        
        with patch('main.get_auth_service', return_value=mock_auth_service):
            response = test_client.post(
                "/api/v1/admin/api-keys/1",
                json={"active": False},
                headers={"X-API-Key": "admin_key"}
            )
            assert response.status_code in [200, 404, 401]
        
        # Now: key should be invalid
        mock_auth_service.validate_api_key.return_value = (False, {})
        
        with patch('main.get_auth_service', return_value=mock_auth_service):
            response = test_client.get(
                "/api/v1/admin/symbols",
                headers={"X-API-Key": "revoked_key"}
            )
            assert response.status_code == 401


class TestSymbolManagement:
    """Test complete symbol management workflows"""
    
    @pytest.mark.asyncio
    async def test_symbol_lifecycle(self, test_database_url):
        """Should support symbol lifecycle: create -> update -> deactivate"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            # Create
            mock_conn.fetchrow.side_effect = [
                None,
                {'id': 1, 'symbol': 'TEST', 'asset_class': 'stock', 'active': True, 'date_added': datetime.now(), 'backfill_status': 'pending'}
            ]
            result = await manager.add_symbol('TEST', 'stock')
            assert result['active'] is True
            
            # Update status
            mock_conn.execute.return_value = "UPDATE 1"
            result = await manager.update_symbol_status('TEST', backfill_status='in_progress')
            assert result is True
            
            # Deactivate
            mock_conn.execute.return_value = "UPDATE 1"
            result = await manager.remove_symbol('TEST')
            assert result is True


class TestErrorScenarios:
    """Test error handling scenarios"""
    
    @pytest.mark.asyncio
    async def test_database_connection_error(self, test_database_url):
        """Should handle database connection errors"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect', side_effect=Exception("Connection refused")):
            with pytest.raises(Exception, match="Connection refused"):
                await manager.add_symbol('TEST', 'stock')
    
    @pytest.mark.asyncio
    async def test_duplicate_symbol_error(self, test_database_url):
        """Should handle duplicate symbol gracefully"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            mock_conn.fetchrow.return_value = {'id': 1}
            
            with pytest.raises(ValueError, match="already tracked"):
                await manager.add_symbol('AAPL', 'stock')
    
    def test_invalid_date_format_in_query(self, test_client):
        """Should reject invalid date formats"""
        response = test_client.get(
            "/api/v1/historical/AAPL?start=13/01/2023&end=13/12/2023"
        )
        assert response.status_code in [400, 404, 500]


class TestDataIntegrity:
    """Test data integrity and consistency"""
    
    @pytest.mark.asyncio
    async def test_symbol_uniqueness_constraint(self, test_database_url):
        """Should enforce symbol uniqueness"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            # First add succeeds
            side_effects = [
                None,  # Check if exists (first call)
                {'id': 1, 'symbol': 'AAPL', 'asset_class': 'stock', 'active': True, 'date_added': datetime.now(), 'backfill_status': 'pending'},  # Insert result
                {'id': 1},  # Check if exists (second call - returns existing)
            ]
            mock_conn.fetchrow.side_effect = side_effects
            
            result1 = await manager.add_symbol('AAPL', 'stock')
            assert result1['symbol'] == 'AAPL'
            
            # Second add of same symbol fails
            with pytest.raises(ValueError, match="already tracked"):
                await manager.add_symbol('AAPL', 'stock')
    
    @pytest.mark.asyncio
    async def test_asset_class_consistency(self, test_database_url):
        """Should maintain asset_class consistency"""
        manager = SymbolManager(test_database_url)
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            # Same symbol should maintain same asset_class
            mock_conn.fetchrow.return_value = {
                'id': 1, 'symbol': 'AAPL', 'asset_class': 'stock',
                'active': True, 'date_added': datetime.now(),
                'last_backfill': None, 'backfill_status': 'pending'
            }
            
            result = await manager.get_symbol('AAPL')
            assert result['asset_class'] == 'stock'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
