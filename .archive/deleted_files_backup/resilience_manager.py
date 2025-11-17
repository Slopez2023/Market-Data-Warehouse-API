"""Resilience patterns: circuit breaker, rate limiter, retry policies, bulkhead isolation."""

import logging
import time
from enum import Enum
from typing import Optional, Callable, Dict
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)

_resilience_manager: Optional['ResilienceManager'] = None


class CircuitState(Enum):
    """States of a circuit breaker."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failures exceed threshold
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(
        self,
        name: str,
        failure_threshold: float = 0.5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Breaker name
            failure_threshold: Failure rate threshold (0.0-1.0)
            recovery_timeout: Seconds before attempting recovery
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
        
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
            else:
                raise RuntimeError(f"Circuit breaker '{self.name}' is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except self.expected_exception as e:
            self.on_failure()
            raise
    
    def on_success(self):
        """Record successful call."""
        self.success_count += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            logger.info(f"Circuit breaker '{self.name}' recovered - CLOSED")
    
    def on_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        total_calls = self.failure_count + self.success_count
        if total_calls > 0:
            failure_rate = self.failure_count / total_calls
            
            if failure_rate >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}' OPENED (failure_rate={failure_rate:.2%})"
                )


class RateLimiter:
    """Rate limiter using token bucket algorithm."""
    
    def __init__(
        self,
        name: str,
        rate: int,
        interval: int,
        burst: Optional[int] = None
    ):
        """
        Initialize rate limiter.
        
        Args:
            name: Limiter name
            rate: Number of requests allowed
            interval: Time window in seconds
            burst: Maximum burst size (optional)
        """
        self.name = name
        self.rate = rate
        self.interval = interval
        self.burst = burst or rate
        
        self.tokens = self.burst
        self.last_update = time.time()
        self.requests = deque(maxlen=rate)
        
    def is_allowed(self) -> bool:
        """Check if request is allowed."""
        now = time.time()
        elapsed = now - self.last_update
        
        # Replenish tokens
        self.tokens = min(
            self.burst,
            self.tokens + (elapsed * self.rate / self.interval)
        )
        self.last_update = now
        
        if self.tokens >= 1:
            self.tokens -= 1
            self.requests.append(now)
            return True
        
        return False
    
    def get_retry_after(self) -> int:
        """Get seconds until next request is allowed."""
        if self.tokens >= 1:
            return 0
        return int((1 - self.tokens) * self.interval / self.rate) + 1


class RetryPolicy:
    """Retry policy with exponential backoff."""
    
    def __init__(
        self,
        name: str,
        max_retries: int = 3,
        initial_delay: int = 1,
        max_delay: int = 60,
        exponential_base: float = 2.0
    ):
        """
        Initialize retry policy.
        
        Args:
            name: Policy name
            max_retries: Maximum number of retries
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff
        """
        self.name = name
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
    
    def execute(self, func: Callable, *args, **kwargs):
        """Execute function with retry logic."""
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt >= self.max_retries:
                    logger.error(
                        f"Retry policy '{self.name}' exhausted after {self.max_retries} retries"
                    )
                    raise
                
                delay = min(
                    self.max_delay,
                    self.initial_delay * (self.exponential_base ** attempt)
                )
                logger.warning(
                    f"Retry policy '{self.name}' attempt {attempt + 1}/{self.max_retries + 1}, "
                    f"retrying after {delay}s: {e}"
                )
                time.sleep(delay)


class BulkheadIsolation:
    """Bulkhead isolation pattern for resource isolation."""
    
    def __init__(self, name: str, max_concurrent: int = 10):
        """
        Initialize bulkhead isolation.
        
        Args:
            name: Bulkhead name
            max_concurrent: Maximum concurrent executions
        """
        self.name = name
        self.max_concurrent = max_concurrent
        self.current_count = 0
        self.queue = deque()
    
    def is_allowed(self) -> bool:
        """Check if resource is available."""
        return self.current_count < self.max_concurrent
    
    def acquire(self) -> bool:
        """Acquire a resource."""
        if self.is_allowed():
            self.current_count += 1
            return True
        return False
    
    def release(self):
        """Release a resource."""
        if self.current_count > 0:
            self.current_count -= 1


class ResilienceManager:
    """Central manager for all resilience patterns."""
    
    def __init__(self):
        """Initialize resilience manager."""
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.retry_policies: Dict[str, RetryPolicy] = {}
        self.bulkheads: Dict[str, BulkheadIsolation] = {}
        
        logger.info("Resilience manager initialized")
    
    def register_circuit_breaker(
        self,
        name: str,
        failure_threshold: float = 0.5,
        recovery_timeout: int = 60
    ) -> CircuitBreaker:
        """Register a circuit breaker."""
        breaker = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )
        self.circuit_breakers[name] = breaker
        logger.info(f"Circuit breaker registered: {name}")
        return breaker
    
    def register_rate_limiter(
        self,
        name: str,
        rate: int,
        interval: int,
        burst: Optional[int] = None
    ) -> RateLimiter:
        """Register a rate limiter."""
        limiter = RateLimiter(
            name=name,
            rate=rate,
            interval=interval,
            burst=burst
        )
        self.rate_limiters[name] = limiter
        logger.info(f"Rate limiter registered: {name} ({rate} req/{interval}s)")
        return limiter
    
    def register_retry_policy(
        self,
        name: str,
        max_retries: int = 3,
        initial_delay: int = 1,
        max_delay: int = 60
    ) -> RetryPolicy:
        """Register a retry policy."""
        policy = RetryPolicy(
            name=name,
            max_retries=max_retries,
            initial_delay=initial_delay,
            max_delay=max_delay
        )
        self.retry_policies[name] = policy
        logger.info(f"Retry policy registered: {name} ({max_retries} retries)")
        return policy
    
    def register_bulkhead(self, name: str, max_concurrent: int = 10) -> BulkheadIsolation:
        """Register bulkhead isolation."""
        bulkhead = BulkheadIsolation(name=name, max_concurrent=max_concurrent)
        self.bulkheads[name] = bulkhead
        logger.info(f"Bulkhead registered: {name} (max_concurrent={max_concurrent})")
        return bulkhead
    
    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self.circuit_breakers.get(name)
    
    def get_rate_limiter(self, name: str) -> Optional[RateLimiter]:
        """Get rate limiter by name."""
        return self.rate_limiters.get(name)
    
    def get_retry_policy(self, name: str) -> Optional[RetryPolicy]:
        """Get retry policy by name."""
        return self.retry_policies.get(name)
    
    def get_bulkhead(self, name: str) -> Optional[BulkheadIsolation]:
        """Get bulkhead by name."""
        return self.bulkheads.get(name)
    
    def get_status(self) -> Dict:
        """Get status of all resilience patterns."""
        return {
            'circuit_breakers': {
                name: {'state': breaker.state.value}
                for name, breaker in self.circuit_breakers.items()
            },
            'rate_limiters': {
                name: {'tokens': limiter.tokens}
                for name, limiter in self.rate_limiters.items()
            },
            'retry_policies': {
                name: {'max_retries': policy.max_retries}
                for name, policy in self.retry_policies.items()
            },
            'bulkheads': {
                name: {
                    'current': bulkhead.current_count,
                    'max': bulkhead.max_concurrent
                }
                for name, bulkhead in self.bulkheads.items()
            }
        }


def init_resilience_manager() -> ResilienceManager:
    """Initialize the global resilience manager."""
    global _resilience_manager
    _resilience_manager = ResilienceManager()
    return _resilience_manager


def get_resilience_manager() -> Optional[ResilienceManager]:
    """Get the global resilience manager instance."""
    return _resilience_manager
