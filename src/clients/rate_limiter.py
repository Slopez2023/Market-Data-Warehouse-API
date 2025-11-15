"""Rate limiter for API requests to prevent hitting limits"""

import asyncio
import time
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Simple token bucket rate limiter"""
    
    def __init__(self, requests_per_second: float = 2.5):
        """
        Initialize rate limiter.
        
        Polygon.io free tier: 150 requests/minute = 2.5 req/sec
        """
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second  # seconds between requests
        self.last_request_time = 0
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait until rate limit allows next request"""
        async with self.lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                await asyncio.sleep(wait_time)
            self.last_request_time = time.time()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with rate limiting"""
        await self.acquire()
        return await func(*args, **kwargs)


# Global rate limiter instance
_global_rate_limiter = RateLimiter(requests_per_second=2.5)


async def rate_limited_call(func: Callable, *args, **kwargs) -> Any:
    """Execute function with global rate limiting"""
    return await _global_rate_limiter.call(func, *args, **kwargs)


def set_rate_limit(requests_per_second: float):
    """Configure global rate limit"""
    global _global_rate_limiter
    _global_rate_limiter = RateLimiter(requests_per_second)
    logger.info(f"Rate limit set to {requests_per_second} req/sec")
