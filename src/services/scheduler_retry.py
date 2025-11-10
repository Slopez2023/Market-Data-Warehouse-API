"""Phase 2.2: Scheduler retry and backoff mechanisms with circuit breaker"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Callable, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class BackoffStrategy(Enum):
    """Retry backoff strategies"""
    EXPONENTIAL = "exponential"  # 2s, 4s, 8s, 16s...
    LINEAR = "linear"            # 1s, 2s, 3s, 4s...
    FIXED = "fixed"              # 2s, 2s, 2s, 2s...


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff: float = 2.0,
        max_backoff: float = 60.0,
        strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.strategy = strategy
        self.jitter = jitter


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests rejected immediately
    - HALF_OPEN: Testing recovery, allow one request
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
    
    def can_execute(self) -> bool:
        """Check if request can execute"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            # Check if timeout has passed
            if (datetime.utcnow() - self.last_failure_time).total_seconds() >= self.timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                return True
            return False
        
        # HALF_OPEN: allow single request
        return True
    
    def record_success(self) -> None:
        """Record successful request"""
        self.failure_count = 0
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                logger.info("Circuit breaker closed - service recovered")
    
    def record_failure(self) -> None:
        """Record failed request"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            logger.error("Circuit breaker opened again - recovery failed")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.error(f"Circuit breaker opened after {self.failure_count} failures")


class RetryableOperation:
    """Manages retry logic for a single operation"""
    
    def __init__(
        self,
        config: RetryConfig = None,
        circuit_breaker: CircuitBreaker = None
    ):
        self.config = config or RetryConfig()
        self.circuit_breaker = circuit_breaker
    
    async def execute(
        self,
        operation: Callable,
        *args,
        **kwargs
    ) -> Tuple[Any, bool, Optional[Exception]]:
        """
        Execute operation with retries.
        
        Args:
            operation: Async callable to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Tuple of (result, success: bool, last_error: Optional[Exception])
        """
        # Check circuit breaker
        if self.circuit_breaker and not self.circuit_breaker.can_execute():
            error = Exception("Circuit breaker is OPEN")
            logger.error(f"Request blocked: {error}")
            return None, False, error
        
        last_error = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                result = await operation(*args, **kwargs)
                
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()
                
                if attempt > 0:
                    logger.info(f"Operation succeeded on attempt {attempt + 1}")
                
                return result, True, None
            
            except Exception as e:
                last_error = e
                
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()
                
                if attempt < self.config.max_retries:
                    wait_time = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Operation failed after {self.config.max_retries + 1} attempts: {e}")
        
        return None, False, last_error
    
    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate backoff time based on strategy"""
        import random
        
        if self.config.strategy == BackoffStrategy.EXPONENTIAL:
            wait_time = self.config.initial_backoff ** (attempt + 1)
        elif self.config.strategy == BackoffStrategy.LINEAR:
            wait_time = self.config.initial_backoff * (attempt + 1)
        else:  # FIXED
            wait_time = self.config.initial_backoff
        
        # Cap at max_backoff
        wait_time = min(wait_time, self.config.max_backoff)
        
        # Add jitter (±20%)
        if self.config.jitter:
            jitter = random.uniform(0.8, 1.2)
            wait_time *= jitter
        
        return wait_time


class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, max_requests: int, window_seconds: float):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: list = []
    
    async def acquire(self) -> None:
        """
        Acquire a rate limit token.
        Blocks if limit exceeded.
        """
        now = datetime.utcnow()
        
        # Remove old requests outside window
        self.requests = [
            req_time for req_time in self.requests
            if (now - req_time).total_seconds() < self.window_seconds
        ]
        
        # Wait if at limit
        while len(self.requests) >= self.max_requests:
            # Wait until oldest request expires
            oldest = self.requests[0]
            wait_time = (oldest - now).total_seconds() + self.window_seconds
            if wait_time > 0:
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
                await asyncio.sleep(min(wait_time, 1.0))
            
            now = datetime.utcnow()
            self.requests = [
                req_time for req_time in self.requests
                if (now - req_time).total_seconds() < self.window_seconds
            ]
        
        # Record this request
        self.requests.append(now)
    
    def get_next_available_time(self) -> datetime:
        """Get when the next request can be made"""
        if len(self.requests) < self.max_requests:
            return datetime.utcnow()
        
        oldest = self.requests[0]
        return oldest + timedelta(seconds=self.window_seconds)
