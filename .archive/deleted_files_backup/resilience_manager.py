"""
Phase 1i: Production Hardening - Resilience Manager
Provides circuit breaker, rate limiting, and fault tolerance patterns.
"""

import logging
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, Any
from enum import Enum
import asyncio
from collections import deque

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Implements circuit breaker pattern for resilient API calls.
    
    Prevents cascading failures by:
    - Tracking failure rate
    - Opening circuit when failure threshold exceeded
    - Half-open state to test recovery
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: float = 0.5,  # Open after 50% failures
        recovery_timeout: int = 60,  # Try recovery after 60s
        expected_exception: Exception = Exception
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name
            failure_threshold: Failure rate to open circuit (0.0-1.0)
            recovery_timeout: Seconds to wait before trying recovery
            expected_exception: Exception type to catch
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.opened_at: Optional[datetime] = None
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Function result
        
        Raises:
            Exception: If circuit is open or function fails
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
            else:
                raise Exception(f"Circuit breaker '{self.name}' is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try recovery"""
        if not self.last_failure_time:
            return True
        
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout
    
    def _on_success(self) -> None:
        """Handle successful call"""
        self.success_count += 1
        self.failure_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info(f"Circuit breaker '{self.name}' closed (recovered)")
    
    def _on_failure(self) -> None:
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        total_calls = self.failure_count + self.success_count
        failure_rate = self.failure_count / total_calls if total_calls > 0 else 0
        
        if failure_rate >= self.failure_threshold and total_calls >= 5:
            # Only open after at least 5 calls to avoid flapping
            self.state = CircuitState.OPEN
            self.opened_at = datetime.utcnow()
            logger.warning(
                f"Circuit breaker '{self.name}' opened "
                f"(failure rate: {failure_rate:.2%})"
            )
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_rate": (
                self.failure_count / (self.failure_count + self.success_count)
                if (self.failure_count + self.success_count) > 0
                else 0
            ),
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None
        }


class RateLimiter:
    """
    Implements token bucket rate limiting.
    
    Allows configurable request rates with burst capacity.
    """
    
    def __init__(
        self,
        name: str,
        rate: int,  # Requests per interval
        interval: int = 60,  # Interval in seconds
        burst: int = None  # Max burst size (defaults to rate)
    ):
        """
        Initialize rate limiter.
        
        Args:
            name: Rate limiter name
            rate: Number of requests allowed per interval
            interval: Interval duration in seconds
            burst: Max tokens to accumulate (defaults to rate)
        """
        self.name = name
        self.rate = rate
        self.interval = interval
        self.burst = burst or rate
        
        self.tokens = float(self.burst)
        self.last_update = datetime.utcnow()
        self.rejected_count = 0
    
    def allow_request(self) -> bool:
        """
        Check if request is allowed under rate limit.
        
        Returns:
            True if request allowed, False if rate limited
        """
        now = datetime.utcnow()
        elapsed = (now - self.last_update).total_seconds()
        
        # Refill tokens
        tokens_to_add = (elapsed / self.interval) * self.rate
        self.tokens = min(self.burst, self.tokens + tokens_to_add)
        self.last_update = now
        
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        else:
            self.rejected_count += 1
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get rate limiter status"""
        return {
            "name": self.name,
            "rate": self.rate,
            "interval": self.interval,
            "burst": self.burst,
            "available_tokens": int(self.tokens),
            "rejected_count": self.rejected_count
        }


class RetryPolicy:
    """
    Implements exponential backoff retry logic.
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_multiplier: float = 2.0
    ):
        """
        Initialize retry policy.
        
        Args:
            max_retries: Maximum number of retries
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            backoff_multiplier: Multiplier for exponential backoff
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
    
    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number.
        
        Args:
            attempt: Attempt number (0-indexed)
        
        Returns:
            Delay in seconds
        """
        delay = self.initial_delay * (self.backoff_multiplier ** attempt)
        return min(delay, self.max_delay)
    
    async def execute_async(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute async function with retry logic.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Function result
        
        Raises:
            Exception: If all retries exhausted
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                if attempt < self.max_retries:
                    delay = self.get_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed: {e}")
        
        raise last_error
    
    def execute_sync(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute sync function with retry logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Function result
        
        Raises:
            Exception: If all retries exhausted
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                if attempt < self.max_retries:
                    delay = self.get_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    # Use asyncio.run if available, else time.sleep
                    try:
                        asyncio.run(asyncio.sleep(delay))
                    except RuntimeError:
                        import time
                        time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed: {e}")
        
        raise last_error


class BulkheadIsolation:
    """
    Implements bulkhead isolation pattern.
    
    Limits concurrent operations to prevent resource exhaustion.
    """
    
    def __init__(
        self,
        name: str,
        max_concurrent: int = 10,
        timeout: Optional[float] = None
    ):
        """
        Initialize bulkhead isolation.
        
        Args:
            name: Bulkhead name
            max_concurrent: Maximum concurrent operations
            timeout: Operation timeout in seconds
        """
        self.name = name
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_count = 0
        self.rejected_count = 0
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with bulkhead isolation.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Function result
        
        Raises:
            Exception: If timeout or function raises
        """
        try:
            async with self.semaphore:
                self.active_count += 1
                try:
                    if self.timeout:
                        return await asyncio.wait_for(
                            func(*args, **kwargs),
                            timeout=self.timeout
                        )
                    else:
                        return await func(*args, **kwargs)
                finally:
                    self.active_count -= 1
        except asyncio.TimeoutError:
            self.rejected_count += 1
            logger.error(f"Bulkhead '{self.name}' timeout after {self.timeout}s")
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Get bulkhead status"""
        return {
            "name": self.name,
            "max_concurrent": self.max_concurrent,
            "active_count": self.active_count,
            "available_slots": self.max_concurrent - self.active_count,
            "rejected_count": self.rejected_count
        }


class ResilienceManager:
    """
    Central resilience manager for coordinating circuit breakers,
    rate limiters, retries, and bulkheads.
    """
    
    def __init__(self):
        """Initialize resilience manager"""
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.retry_policies: Dict[str, RetryPolicy] = {}
        self.bulkheads: Dict[str, BulkheadIsolation] = {}
    
    def register_circuit_breaker(
        self,
        name: str,
        failure_threshold: float = 0.5,
        recovery_timeout: int = 60
    ) -> CircuitBreaker:
        """Register a circuit breaker"""
        cb = CircuitBreaker(
            name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )
        self.circuit_breakers[name] = cb
        return cb
    
    def register_rate_limiter(
        self,
        name: str,
        rate: int,
        interval: int = 60,
        burst: Optional[int] = None
    ) -> RateLimiter:
        """Register a rate limiter"""
        rl = RateLimiter(name, rate, interval, burst)
        self.rate_limiters[name] = rl
        return rl
    
    def register_retry_policy(
        self,
        name: str,
        max_retries: int = 3,
        initial_delay: float = 1.0
    ) -> RetryPolicy:
        """Register a retry policy"""
        rp = RetryPolicy(max_retries=max_retries, initial_delay=initial_delay)
        self.retry_policies[name] = rp
        return rp
    
    def register_bulkhead(
        self,
        name: str,
        max_concurrent: int = 10,
        timeout: Optional[float] = None
    ) -> BulkheadIsolation:
        """Register a bulkhead"""
        bh = BulkheadIsolation(name, max_concurrent, timeout)
        self.bulkheads[name] = bh
        return bh
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all resilience patterns"""
        return {
            "circuit_breakers": [
                cb.get_status()
                for cb in self.circuit_breakers.values()
            ],
            "rate_limiters": [
                rl.get_status()
                for rl in self.rate_limiters.values()
            ],
            "bulkheads": [
                bh.get_status()
                for bh in self.bulkheads.values()
            ]
        }


# Global resilience manager instance
_resilience_manager: Optional[ResilienceManager] = None


def init_resilience_manager() -> ResilienceManager:
    """Initialize global resilience manager"""
    global _resilience_manager
    _resilience_manager = ResilienceManager()
    logger.info("Resilience manager initialized")
    return _resilience_manager


def get_resilience_manager() -> ResilienceManager:
    """Get global resilience manager"""
    global _resilience_manager
    if _resilience_manager is None:
        _resilience_manager = init_resilience_manager()
    return _resilience_manager
