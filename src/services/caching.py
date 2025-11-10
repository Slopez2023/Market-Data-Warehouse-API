"""Response caching service for high-frequency queries"""

import hashlib
import json
import time
from typing import Any, Callable, Dict, Optional
from datetime import datetime
from functools import wraps
from asyncio import Lock

from src.services.structured_logging import StructuredLogger

logger = StructuredLogger(__name__)


class CacheEntry:
    """Single cache entry with TTL"""
    
    def __init__(self, value: Any, ttl_seconds: int):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl_seconds
    
    def is_expired(self) -> bool:
        """Check if entry has expired"""
        return (time.time() - self.created_at) > self.ttl
    
    def get(self) -> Optional[Any]:
        """Get value if not expired"""
        if self.is_expired():
            return None
        return self.value


class QueryCache:
    """
    Thread-safe cache for database query results.
    Improves performance for repeated queries with same parameters.
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Initialize cache.
        
        Args:
            max_size: Maximum number of entries to store
            default_ttl: Default time-to-live in seconds
        """
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.lock = Lock()
        self.hits = 0
        self.misses = 0
    
    def _generate_key(self, namespace: str, **kwargs) -> str:
        """Generate cache key from namespace and parameters"""
        key_str = f"{namespace}:{json.dumps(kwargs, sort_keys=True, default=str)}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def get(self, namespace: str, **kwargs) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            namespace: Cache namespace (e.g., 'historical_data')
            **kwargs: Parameters to include in cache key
        
        Returns:
            Cached value or None if not found/expired
        """
        key = self._generate_key(namespace, **kwargs)
        
        async with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                value = entry.get()
                if value is not None:
                    self.hits += 1
                    logger.debug(f"Cache hit: {namespace}", extra={
                        "key": key[:8],
                        "hit_rate": f"{self.hit_rate:.1%}"
                    })
                    return value
                else:
                    del self.cache[key]
            
            self.misses += 1
            return None
    
    async def set(self, namespace: str, value: Any, ttl: Optional[int] = None, **kwargs):
        """
        Store value in cache.
        
        Args:
            namespace: Cache namespace
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
            **kwargs: Parameters to include in cache key
        """
        if ttl is None:
            ttl = self.default_ttl
        
        key = self._generate_key(namespace, **kwargs)
        
        async with self.lock:
            # Evict oldest entry if at max size
            if len(self.cache) >= self.max_size:
                oldest_key = min(
                    self.cache.keys(),
                    key=lambda k: self.cache[k].created_at
                )
                del self.cache[oldest_key]
                logger.debug(f"Cache evicted entry: {oldest_key[:8]}")
            
            self.cache[key] = CacheEntry(value, ttl)
            logger.debug(f"Cache set: {namespace}", extra={
                "key": key[:8],
                "size": len(self.cache)
            })
    
    async def invalidate(self, namespace: str = None, **kwargs):
        """
        Invalidate cache entries.
        
        Args:
            namespace: If provided, only invalidate this namespace
            **kwargs: If provided, only invalidate entries matching these params
        """
        async with self.lock:
            if namespace is None:
                self.cache.clear()
                logger.info("Cache cleared")
                return
            
            if not kwargs:
                # Clear all entries in namespace
                keys_to_delete = [
                    k for k in self.cache.keys()
                    if k.startswith(namespace)
                ]
            else:
                # Clear specific entry
                key = self._generate_key(namespace, **kwargs)
                keys_to_delete = [key] if key in self.cache else []
            
            for key in keys_to_delete:
                del self.cache[key]
            
            logger.info(f"Cache invalidated {len(keys_to_delete)} entries", extra={
                "namespace": namespace
            })
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_pct": round(self.hit_rate * 100, 2),
            "default_ttl_seconds": self.default_ttl
        }


# Global cache instance
_cache_instance: Optional[QueryCache] = None


def init_query_cache(max_size: int = 1000, default_ttl: int = 300) -> QueryCache:
    """Initialize global query cache"""
    global _cache_instance
    _cache_instance = QueryCache(max_size=max_size, default_ttl=default_ttl)
    logger.info("Query cache initialized", extra=_cache_instance.stats())
    return _cache_instance


def get_query_cache() -> QueryCache:
    """Get global query cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = QueryCache()
    return _cache_instance


def cached_query(namespace: str, ttl: int = 300):
    """
    Decorator for caching async query results.
    
    Args:
        namespace: Cache namespace
        ttl: Time-to-live in seconds
    
    Usage:
        @cached_query("historical_data", ttl=600)
        async def get_historical_data(symbol, start, end):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_query_cache()
            
            # Generate cache key from kwargs
            cached_value = await cache.get(namespace, **kwargs)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(namespace, result, ttl=ttl, **kwargs)
            return result
        
        return wrapper
    return decorator
