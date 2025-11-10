"""API key authentication middleware"""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.services.auth import get_auth_service
from src.services.structured_logging import StructuredLogger

logger = StructuredLogger(__name__)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate API keys on protected endpoints.
    
    Protected paths: /api/v1/admin/*
    
    Expects header: X-API-Key: {api_key}
    """
    
    # Paths that require API key authentication
    PROTECTED_PATHS = [
        "/api/v1/admin/",
    ]
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and validate API key if protected.
        """
        # Check if this is a protected path
        is_protected = any(
            request.url.path.startswith(path) for path in self.PROTECTED_PATHS
        )
        
        if not is_protected:
            # Not protected, proceed
            response = await call_next(request)
            return response
        
        # Get API key from header
        api_key = request.headers.get("X-API-Key")
        
        if not api_key:
            logger.warning("API request missing X-API-Key header", extra={
                "path": request.url.path,
                "method": request.method,
                "client": request.client.host if request.client else "unknown"
            })
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing X-API-Key header"}
            )
        
        # Validate API key
        auth_service = get_auth_service()
        is_valid, metadata = await auth_service.validate_api_key(api_key)
        
        if not is_valid:
            logger.warning("API request with invalid key", extra={
                "path": request.url.path,
                "method": request.method,
                "client": request.client.host if request.client else "unknown"
            })
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or inactive API key"}
            )
        
        # Store metadata in request state for later use
        request.state.api_key_id = metadata['id']
        request.state.api_key_name = metadata['name']
        
        # Process request
        response = await call_next(request)
        
        # Log API usage asynchronously
        try:
            await auth_service.log_api_usage(
                api_key,
                str(request.url.path),
                request.method,
                response.status_code
            )
        except Exception as e:
            logger.warning("Failed to log API usage", extra={"error": str(e)})
        
        return response
