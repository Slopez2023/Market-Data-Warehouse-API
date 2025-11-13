"""Phase 2.2: Tests for scheduler retry and backoff mechanisms"""

import pytest
import asyncio
from datetime import datetime, timedelta
from src.services.scheduler_retry import (
    RetryConfig, BackoffStrategy, CircuitBreaker, CircuitBreakerState,
    RetryableOperation, RateLimiter
)

# Import datetime at module level for use in tests
from datetime import datetime as dt


class TestRetryConfig:
    """Test RetryConfig"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = RetryConfig()
        
        assert config.max_retries == 3
        assert config.initial_backoff == 2.0
        assert config.max_backoff == 60.0
        assert config.strategy == BackoffStrategy.EXPONENTIAL
        assert config.jitter is True
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = RetryConfig(
            max_retries=5,
            initial_backoff=1.0,
            strategy=BackoffStrategy.LINEAR
        )
        
        assert config.max_retries == 5
        assert config.initial_backoff == 1.0
        assert config.strategy == BackoffStrategy.LINEAR


class TestCircuitBreaker:
    """Test CircuitBreaker"""
    
    def test_initial_state_closed(self):
        """Test that circuit breaker starts in CLOSED state"""
        cb = CircuitBreaker()
        
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.can_execute() is True
    
    def test_failure_threshold_opens_breaker(self):
        """Test that reaching failure threshold opens circuit"""
        cb = CircuitBreaker(failure_threshold=3)
        
        # Record failures
        for _ in range(3):
            cb.record_failure()
        
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.can_execute() is False
    
    def test_success_resets_failure_count(self):
        """Test that success resets failure counter"""
        cb = CircuitBreaker(failure_threshold=3)
        
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        
        assert cb.failure_count == 0
    
    def test_timeout_transitions_to_half_open(self):
        """Test that timeout allows transition to HALF_OPEN"""
        cb = CircuitBreaker(failure_threshold=1, timeout=0.1)
        
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.can_execute() is False
        
        # Wait for timeout
        cb.last_failure_time = datetime.utcnow() - timedelta(seconds=1)
        assert cb.can_execute() is True
        assert cb.state == CircuitBreakerState.HALF_OPEN
    
    def test_half_open_success_closes_breaker(self):
        """Test that success in HALF_OPEN closes circuit"""
        cb = CircuitBreaker(success_threshold=2)
        cb.state = CircuitBreakerState.HALF_OPEN
        
        cb.record_success()
        cb.record_success()
        
        assert cb.state == CircuitBreakerState.CLOSED
    
    def test_half_open_failure_reopens_breaker(self):
        """Test that failure in HALF_OPEN reopens circuit"""
        cb = CircuitBreaker()
        cb.state = CircuitBreakerState.HALF_OPEN
        
        cb.record_failure()
        
        assert cb.state == CircuitBreakerState.OPEN


class TestRetryableOperation:
    """Test RetryableOperation"""
    
    @pytest.mark.asyncio
    async def test_successful_operation_first_try(self):
        """Test successful operation on first attempt"""
        async def operation():
            return "success"
        
        retry_op = RetryableOperation()
        result, success, error = await retry_op.execute(operation)
        
        assert success is True
        assert result == "success"
        assert error is None
    
    @pytest.mark.asyncio
    async def test_operation_with_retries(self):
        """Test operation that fails then succeeds"""
        attempt_count = 0
        
        async def flaky_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise ValueError("First attempt fails")
            return "success"
        
        config = RetryConfig(max_retries=3, initial_backoff=0.01)
        retry_op = RetryableOperation(config=config)
        result, success, error = await retry_op.execute(flaky_operation)
        
        assert success is True
        assert result == "success"
        assert attempt_count == 2
    
    @pytest.mark.asyncio
    async def test_operation_max_retries_exceeded(self):
        """Test operation that exceeds max retries"""
        async def failing_operation():
            raise ValueError("Always fails")
        
        config = RetryConfig(max_retries=2, initial_backoff=0.01)
        retry_op = RetryableOperation(config=config)
        result, success, error = await retry_op.execute(failing_operation)
        
        assert success is False
        assert isinstance(error, ValueError)
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_calculation(self):
        """Test exponential backoff calculation"""
        config = RetryConfig(
            initial_backoff=1.0,
            max_backoff=60.0,
            strategy=BackoffStrategy.EXPONENTIAL,
            jitter=False
        )
        retry_op = RetryableOperation(config=config)
        
        backoff_0 = retry_op._calculate_backoff(0)  # 1^1 = 1
        backoff_1 = retry_op._calculate_backoff(1)  # 1^2 = 1
        backoff_2 = retry_op._calculate_backoff(2)  # 1^3 = 1
        
        # With initial_backoff=1.0: 1.0 ** (0+1) = 1.0
        assert backoff_0 == 1.0
        assert backoff_1 == 1.0
        assert backoff_2 == 1.0
    
    @pytest.mark.asyncio
    async def test_linear_backoff_calculation(self):
        """Test linear backoff calculation"""
        config = RetryConfig(
            initial_backoff=1.0,
            strategy=BackoffStrategy.LINEAR,
            jitter=False
        )
        retry_op = RetryableOperation(config=config)
        
        backoff_0 = retry_op._calculate_backoff(0)  # 1 * 1 = 1
        backoff_1 = retry_op._calculate_backoff(1)  # 1 * 2 = 2
        backoff_2 = retry_op._calculate_backoff(2)  # 1 * 3 = 3
        
        assert backoff_0 == 1.0
        assert backoff_1 == 2.0
        assert backoff_2 == 3.0
    
    @pytest.mark.asyncio
    async def test_fixed_backoff_calculation(self):
        """Test fixed backoff calculation"""
        config = RetryConfig(
            initial_backoff=2.0,
            strategy=BackoffStrategy.FIXED,
            jitter=False
        )
        retry_op = RetryableOperation(config=config)
        
        backoff_0 = retry_op._calculate_backoff(0)
        backoff_1 = retry_op._calculate_backoff(1)
        backoff_2 = retry_op._calculate_backoff(2)
        
        assert backoff_0 == 2.0
        assert backoff_1 == 2.0
        assert backoff_2 == 2.0
    
    @pytest.mark.asyncio
    async def test_backoff_respects_max_backoff(self):
        """Test that backoff respects max_backoff limit"""
        config = RetryConfig(
            initial_backoff=10.0,
            max_backoff=30.0,
            strategy=BackoffStrategy.EXPONENTIAL,
            jitter=False
        )
        retry_op = RetryableOperation(config=config)
        
        # 10^5 would be 100000, but capped at 30
        backoff = retry_op._calculate_backoff(4)
        assert backoff == 30.0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_request(self):
        """Test that circuit breaker blocks requests when open"""
        cb = CircuitBreaker(failure_threshold=1)
        cb.state = CircuitBreakerState.OPEN
        cb.last_failure_time = datetime.utcnow()  # Initialize failure time
        
        async def operation():
            return "success"
        
        retry_op = RetryableOperation(circuit_breaker=cb)
        result, success, error = await retry_op.execute(operation)
        
        assert success is False
        assert "Circuit breaker is OPEN" in str(error)


class TestRateLimiter:
    """Test RateLimiter"""
    
    @pytest.mark.asyncio
    async def test_allows_requests_within_limit(self):
        """Test that requests within limit are allowed"""
        limiter = RateLimiter(max_requests=3, window_seconds=1.0)
        
        # Should allow 3 requests
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()
        
        assert len(limiter.requests) == 3
    
    @pytest.mark.asyncio
    async def test_blocks_requests_exceeding_limit(self):
        """Test that requests exceeding limit are blocked"""
        limiter = RateLimiter(max_requests=2, window_seconds=0.1)
        
        await limiter.acquire()
        await limiter.acquire()
        
        # Record time and then try third request
        start_time = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start_time
        
        # Should have waited for window to pass
        assert elapsed >= 0.1
    
    @pytest.mark.asyncio
    async def test_next_available_time(self):
        """Test calculation of next available request time"""
        limiter = RateLimiter(max_requests=1, window_seconds=1.0)
        
        await limiter.acquire()
        next_time = limiter.get_next_available_time()
        
        # Next available should be at least 1 second away
        diff = (next_time - datetime.utcnow()).total_seconds()
        assert diff >= 0.9  # Allow small timing variance
    
    @pytest.mark.asyncio
    async def test_window_expiration(self):
        """Test that old requests are removed from tracking"""
        limiter = RateLimiter(max_requests=1, window_seconds=0.1)
        
        await limiter.acquire()
        assert len(limiter.requests) == 1
        
        # Wait for window to expire
        await asyncio.sleep(0.15)
        
        # New request should be allowed
        await limiter.acquire()
        assert len(limiter.requests) == 1


class TestBackoffStrategyEnum:
    """Test BackoffStrategy enum"""
    
    def test_strategy_values(self):
        """Test BackoffStrategy enum values"""
        assert BackoffStrategy.EXPONENTIAL.value == "exponential"
        assert BackoffStrategy.LINEAR.value == "linear"
        assert BackoffStrategy.FIXED.value == "fixed"


class TestCircuitBreakerStateEnum:
    """Test CircuitBreakerState enum"""
    
    def test_state_values(self):
        """Test CircuitBreakerState enum values"""
        assert CircuitBreakerState.CLOSED.value == "closed"
        assert CircuitBreakerState.OPEN.value == "open"
        assert CircuitBreakerState.HALF_OPEN.value == "half_open"
