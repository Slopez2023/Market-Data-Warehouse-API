"""
Circuit Breaker Pattern Implementation
Prevents cascading failures when APIs are down or rate-limited
"""

from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, Callable, Any
import asyncio

from src.services.structured_logging import StructuredLogger


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failures detected, requests rejected
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker for API resilience
    Monitors failure rates and stops hammering failed APIs
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: int = 300,
        success_threshold: int = 1
    ):
        """
        Initialize circuit breaker
        
        Args:
            name: Identifier for this breaker (e.g., 'polygon-api')
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds to wait before half-open attempt
            success_threshold: Successful calls before closing circuit
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.opened_at: Optional[datetime] = None
        
        self.logger = StructuredLogger(__name__)
    
    async def call(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Optional[Any]:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Async function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result or None if circuit open
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.logger.info(
                    "circuit_breaker_half_open",
                    name=self.name
                )
            else:
                self.logger.warning(
                    "circuit_breaker_open",
                    name=self.name,
                    seconds_until_retry=self._seconds_until_retry()
                )
                return None
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        
        except Exception as e:
            await self._on_failure(str(e))
            return None
    
    async def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        self.last_failure_time = None
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.logger.info(
                    "circuit_breaker_closed",
                    name=self.name
                )
    
    async def _on_failure(self, error: str):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        self.logger.warning(
            "circuit_breaker_failure",
            name=self.name,
            failure_count=self.failure_count,
            error=error[:100]
        )
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = datetime.utcnow()
            self.logger.error(
                "circuit_breaker_opened",
                name=self.name,
                failure_count=self.failure_count,
                recovery_timeout_seconds=self.recovery_timeout
            )
        
        if self.state == CircuitState.HALF_OPEN:
            # Failure while testing recovery, reopen circuit
            self.state = CircuitState.OPEN
            self.opened_at = datetime.utcnow()
            self.logger.error(
                "circuit_breaker_reopened",
                name=self.name
            )
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if not self.opened_at:
            return False
        
        elapsed = (datetime.utcnow() - self.opened_at).total_seconds()
        return elapsed >= self.recovery_timeout
    
    def _seconds_until_retry(self) -> int:
        """Calculate seconds until retry is allowed"""
        if not self.opened_at:
            return self.recovery_timeout
        
        elapsed = (datetime.utcnow() - self.opened_at).total_seconds()
        remaining = max(0, self.recovery_timeout - elapsed)
        return int(remaining)
    
    def get_state(self) -> dict:
        """Get current state for monitoring"""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'seconds_until_retry': self._seconds_until_retry() if self.state == CircuitState.OPEN else 0
        }
    
    def reset(self):
        """Manually reset circuit breaker"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.opened_at = None
        self.logger.info("circuit_breaker_reset", name=self.name)


class CircuitBreakerManager:
    """Manages multiple circuit breakers for different APIs"""
    
    def __init__(self):
        self.breakers: dict[str, CircuitBreaker] = {}
        self.logger = StructuredLogger(__name__)
    
    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: int = 300,
        success_threshold: int = 1
    ) -> CircuitBreaker:
        """Get existing breaker or create new one"""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                success_threshold=success_threshold
            )
        
        return self.breakers[name]
    
    def get_all_states(self) -> dict:
        """Get state of all breakers"""
        return {
            name: breaker.get_state()
            for name, breaker in self.breakers.items()
        }
    
    def reset_all(self):
        """Reset all breakers"""
        for breaker in self.breakers.values():
            breaker.reset()
        self.logger.info("all_circuit_breakers_reset")


# Global circuit breaker manager
_circuit_breaker_manager = CircuitBreakerManager()


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create circuit breaker"""
    return _circuit_breaker_manager.get_or_create(name)


def get_circuit_breaker_states() -> dict:
    """Get all circuit breaker states"""
    return _circuit_breaker_manager.get_all_states()
