"""API key authentication service"""

import hashlib
import secrets
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any
import asyncpg

from src.services.structured_logging import StructuredLogger

logger = StructuredLogger(__name__)


class APIKeyService:
    """Manages API key generation, validation, and audit logging"""
    
    def __init__(self, database_url: str):
        """
        Initialize API key service.
        
        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url
    
    async def validate_api_key(self, api_key: str) -> Tuple[bool, Optional[dict]]:
        """
        Validate an API key and return key metadata.
        
        Args:
            api_key: Raw API key from request header
        
        Returns:
            Tuple of (is_valid, key_metadata)
            key_metadata contains: id, name, created_at, request_count
        """
        if not api_key:
            return False, None
        
        # Hash the key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        try:
            conn = await asyncpg.connect(self.database_url)
            
            # Get key from database
            row = await conn.fetchrow(
                """
                SELECT id, name, active, created_at, request_count
                FROM api_keys
                WHERE key_hash = $1
                """,
                key_hash
            )
            
            await conn.close()
            
            if not row:
                logger.warning("API key validation failed", extra={"reason": "key_not_found"})
                return False, None
            
            if not row['active']:
                logger.warning("API key validation failed", extra={"reason": "key_inactive"})
                return False, None
            
            # Return key metadata
            metadata = {
                'id': row['id'],
                'name': row['name'],
                'created_at': row['created_at'].isoformat(),
                'request_count': row['request_count']
            }
            
            return True, metadata
        
        except Exception as e:
            logger.error("API key validation error", extra={"error": str(e)})
            return False, None
    
    async def log_api_usage(
        self,
        api_key: str,
        endpoint: str,
        method: str,
        status_code: int
    ) -> bool:
        """
        Log API key usage for audit trail.
        
        Args:
            api_key: Raw API key
            endpoint: Request endpoint
            method: HTTP method
            status_code: Response status code
        
        Returns:
            Success boolean
        """
        if not api_key:
            return False
        
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        try:
            conn = await asyncpg.connect(self.database_url)
            
            # Get key ID
            key_row = await conn.fetchrow(
                "SELECT id FROM api_keys WHERE key_hash = $1",
                key_hash
            )
            
            if not key_row:
                await conn.close()
                return False
            
            key_id = key_row['id']
            
            # Insert audit record
            await conn.execute(
                """
                INSERT INTO api_key_audit (api_key_id, endpoint, method, status_code)
                VALUES ($1, $2, $3, $4)
                """,
                key_id, endpoint, method, status_code
            )
            
            # Update last_used timestamp and increment counter
            await conn.execute(
                """
                UPDATE api_keys
                SET last_used = NOW(),
                    last_used_endpoint = $1,
                    request_count = request_count + 1
                WHERE id = $2
                """,
                endpoint, key_id
            )
            
            await conn.close()
            return True
        
        except Exception as e:
            logger.error("API usage logging error", extra={"error": str(e)})
            return False
    
    @staticmethod
    def generate_api_key(name: str) -> str:
        """
        Generate a new API key.
        
        Args:
            name: Human-readable name for the key
        
        Returns:
            Raw API key (format: "mdw_{32_random_hex}")
        """
        # Generate 32 random bytes and convert to hex
        random_part = secrets.token_hex(32)
        api_key = f"mdw_{random_part}"
        return api_key
    
    async def create_api_key(self, name: str) -> Dict[str, Any]:
        """
        Generate and store a new API key.
        
        Args:
            name: Human-readable name for the key
        
        Returns:
            Dictionary with: api_key (raw key), key_preview, name, created_at, id
        """
        try:
            conn = await asyncpg.connect(self.database_url)
            
            # Generate raw key
            api_key = self.generate_api_key(name)
            key_hash = self.hash_api_key(api_key)
            
            # Insert into database
            result = await conn.fetchrow(
                """
                INSERT INTO api_keys (key_hash, name, active)
                VALUES ($1, $2, $3)
                RETURNING id, created_at
                """,
                key_hash, name, True
            )
            
            await conn.close()
            
            if not result:
                logger.error("Failed to store API key", extra={"name": name})
                return {}
            
            logger.info("API key created", extra={
                "key_id": result['id'],
                "name": name
            })
            
            return {
                'id': result['id'],
                'api_key': api_key,
                'key_preview': api_key[:12] + '...',
                'name': name,
                'created_at': result['created_at'].isoformat()
            }
        
        except Exception as e:
            logger.error("API key creation error", extra={"name": name, "error": str(e)}, exc_info=True)
            return {}
    
    async def list_api_keys(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """
        List all API keys with metadata.
        
        Args:
            active_only: If True, only return active keys
        
        Returns:
            List of key metadata dictionaries
        """
        try:
            conn = await asyncpg.connect(self.database_url)
            
            # Get keys
            query = """
                SELECT id, name, active, created_at, last_used, request_count
                FROM api_keys
            """
            params = []
            
            if active_only:
                query += " WHERE active = TRUE"
            
            query += " ORDER BY created_at DESC"
            
            rows = await conn.fetch(query, *params)
            
            await conn.close()
            
            result = []
            for row in rows:
                result.append({
                    'id': row['id'],
                    'name': row['name'],
                    'active': row['active'],
                    'created_at': row['created_at'].isoformat(),
                    'last_used': row['last_used'].isoformat() if row['last_used'] else None,
                    'request_count': row['request_count']
                })
            
            return result
        
        except Exception as e:
            logger.error("API key list error", extra={"error": str(e)})
            return []
    
    async def get_audit_log(self, key_id: int, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get audit log entries for a specific API key.
        
        Args:
            key_id: ID of the API key
            limit: Maximum number of results
            offset: Number of results to skip
        
        Returns:
            List of audit log entries
        """
        try:
            conn = await asyncpg.connect(self.database_url)
            
            # Get audit records
            rows = await conn.fetch(
                """
                SELECT id, endpoint, method, status_code, timestamp
                FROM api_key_audit
                WHERE api_key_id = $1
                ORDER BY timestamp DESC
                LIMIT $2 OFFSET $3
                """,
                key_id, limit, offset
            )
            
            await conn.close()
            
            result = []
            for row in rows:
                result.append({
                    'id': row['id'],
                    'endpoint': row['endpoint'],
                    'method': row['method'],
                    'status_code': row['status_code'],
                    'timestamp': row['timestamp'].isoformat()
                })
            
            return result
        
        except Exception as e:
            logger.error("Audit log fetch error", extra={"key_id": key_id, "error": str(e)})
            return []
    
    async def revoke_key(self, key_id: int) -> bool:
        """
        Deactivate an API key (soft delete).
        
        Args:
            key_id: ID of the API key to revoke
        
        Returns:
            True if successful
        """
        try:
            conn = await asyncpg.connect(self.database_url)
            
            result = await conn.execute(
                "UPDATE api_keys SET active = FALSE WHERE id = $1",
                key_id
            )
            
            await conn.close()
            
            logger.info("API key revoked", extra={"key_id": key_id})
            return True
        
        except Exception as e:
            logger.error("API key revoke error", extra={"key_id": key_id, "error": str(e)})
            return False
    
    async def restore_key(self, key_id: int) -> bool:
        """
        Reactivate a previously revoked API key.
        
        Args:
            key_id: ID of the API key to restore
        
        Returns:
            True if successful
        """
        try:
            conn = await asyncpg.connect(self.database_url)
            
            result = await conn.execute(
                "UPDATE api_keys SET active = TRUE WHERE id = $1",
                key_id
            )
            
            await conn.close()
            
            logger.info("API key restored", extra={"key_id": key_id})
            return True
        
        except Exception as e:
            logger.error("API key restore error", extra={"key_id": key_id, "error": str(e)})
            return False
    
    async def delete_key(self, key_id: int) -> bool:
        """
        Permanently delete an API key and its audit logs.
        
        Args:
            key_id: ID of the API key to delete
        
        Returns:
            True if successful
        """
        try:
            conn = await asyncpg.connect(self.database_url)
            
            # Delete audit logs first (cascades due to FK constraint)
            await conn.execute(
                "DELETE FROM api_key_audit WHERE api_key_id = $1",
                key_id
            )
            
            # Delete the key
            result = await conn.execute(
                "DELETE FROM api_keys WHERE id = $1",
                key_id
            )
            
            await conn.close()
            
            logger.info("API key deleted", extra={"key_id": key_id})
            return True
        
        except Exception as e:
            logger.error("API key delete error", extra={"key_id": key_id, "error": str(e)})
            return False
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """
        Hash an API key for storage.
        
        Args:
            api_key: Raw API key
        
        Returns:
            SHA256 hash as hex string
        """
        return hashlib.sha256(api_key.encode()).hexdigest()


# Global instance holder
_auth_service: Optional[APIKeyService] = None


def init_auth_service(database_url: str) -> APIKeyService:
    """Initialize global auth service"""
    global _auth_service
    _auth_service = APIKeyService(database_url)
    return _auth_service


def get_auth_service() -> APIKeyService:
    """Get global auth service instance"""
    if _auth_service is None:
        raise RuntimeError("Auth service not initialized. Call init_auth_service() first.")
    return _auth_service
