"""
Tests for Phase 1i: Resilience Manager
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from src.services.resilience_manager import (
    CircuitBreaker,
    CircuitState,
    RateLimiter,
    RetryPolicy,
    BulkheadIsolation,
    ResilienceManager,
    init_resilience_manager
)


class TestCircuitBreaker:
    """Tests for circuit breaker"""
    
    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initializes in CLOSED state"""
        cb = CircuitBreaker("test", failure_threshold=0.5, recovery_timeout=60)
        
        assert cb.name == "test"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_threshold == 0.5
        assert cb.recovery_timeout == 60
    
    def test_circuit_breaker_success(self):
        """Test circuit breaker on successful call"""
        cb = CircuitBreaker("test")
        
        def success_func():
            return "success"
        
        result = cb.call(success_func)
        assert result == "success"
        assert cb.success_count == 1
    
    def test_circuit_breaker_failure(self):
        """Test circuit breaker on failed call"""
        cb = CircuitBreaker("test")
        
        def fail_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            cb.call(fail_func)
        
        assert cb.failure_count == 1
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after failure threshold"""
        cb = CircuitBreaker("test", failure_threshold=0.5)
        
        def fail_func():
            raise ValueError("Test error")
        
        # Generate failures to exceed threshold
        for _ in range(5):
            with pytest.raises(ValueError):
                cb.call(fail_func)
        
        # Circuit should be OPEN after 50% failure rate (5 failures)
        assert cb.state == CircuitState.OPEN
    
    def test_circuit_breaker_rejects_when_open(self):
        """Test circuit breaker rejects calls when OPEN"""
        cb = CircuitBreaker("test")
        cb.state = CircuitState.OPEN
        
        def any_func():
            return "success"
        
        with pytest.raises(Exception, match="Circuit breaker .* is OPEN"):
            cb.call(any_func)
    
    def test_circuit_breaker_status(self):
        """Test circuit breaker status reporting"""
        cb = CircuitBreaker("test")
        
        status = cb.get_status()
        assert status["name"] == "test"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["success_count"] == 0


class TestRateLimiter:
    """Tests for rate limiter"""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter initializes correctly"""
        rl = RateLimiter("test", rate=10, interval=60, burst=15)
        
        assert rl.name == "test"
        assert rl.rate == 10
        assert rl.interval == 60
        assert rl.burst == 15
        assert rl.tokens == 15.0
    
    def test_rate_limiter_allows_requests(self):
        """Test rate limiter allows requests within limit"""
        rl = RateLimiter("test", rate=10, interval=60, burst=10)
        
        for _ in range(10):
            assert rl.allow_request() == True
        
        # Next request should be rejected
        assert rl.allow_request() == False
    
    def test_rate_limiter_refills_tokens(self):
        """Test rate limiter refills tokens over time"""
        rl = RateLimiter("test", rate=10, interval=60)
        
        # Use all tokens
        for _ in range(10):
            rl.allow_request()
        
        assert rl.allow_request() == False
        
        # Simulate token refill
        rl.tokens = 5.0
        
        assert rl.allow_request() == True
    
    def test_rate_limiter_status(self):
        """Test rate limiter status reporting"""
        rl = RateLimiter("test", rate=10, interval=60, burst=10)
        
        status = rl.get_status()
        assert status["name"] == "test"
        assert status["rate"] == 10
        assert status["burst"] == 10
        assert status["rejected_count"] == 0


class TestRetryPolicy:
    """Tests for retry policy"""
    
    def test_retry_policy_initialization(self):
        """Test retry policy initializes correctly"""
        rp = RetryPolicy(max_retries=3, initial_delay=1.0, max_delay=60.0, backoff_multiplier=2.0)
        
        assert rp.max_retries == 3
        assert rp.initial_delay == 1.0
        assert rp.max_delay == 60.0
        assert rp.backoff_multiplier == 2.0
    
    def test_retry_policy_delay_calculation(self):
        """Test exponential backoff delay calculation"""
        rp = RetryPolicy(max_retries=3, initial_delay=1.0, max_delay=60.0, backoff_multiplier=2.0)
        
        # Delays should be: 1s, 2s, 4s, 8s (capped at max_delay)
        assert rp.get_delay(0) == 1.0
        assert rp.get_delay(1) == 2.0
        assert rp.get_delay(2) == 4.0
        assert rp.get_delay(3) == 8.0
        assert rp.get_delay(10) == 60.0  # Capped at max_delay
    
    @pytest.mark.asyncio
    async def test_retry_policy_success(self):
        """Test retry policy succeeds on first attempt"""
        rp = RetryPolicy(max_retries=3)
        
        async def success_func():
            return "success"
        
        result = await rp.execute_async(success_func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_policy_retries_and_succeeds(self):
        """Test retry policy retries and eventually succeeds"""
        rp = RetryPolicy(max_retries=3, initial_delay=0.01, max_delay=0.1)
        
        attempt_count = 0
        
        async def fail_twice_then_succeed():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError("Temporary failure")
            return "success"
        
        result = await rp.execute_async(fail_twice_then_succeed)
        assert result == "success"
        assert attempt_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_policy_exhausts_retries(self):
        """Test retry policy exhausts retries"""
        rp = RetryPolicy(max_retries=2, initial_delay=0.01, max_delay=0.1)
        
        async def always_fail():
            raise ValueError("Permanent failure")
        
        with pytest.raises(ValueError):
            await rp.execute_async(always_fail)


class TestBulkheadIsolation:
    """Tests for bulkhead isolation"""
    
    def test_bulkhead_initialization(self):
        """Test bulkhead initializes correctly"""
        bh = BulkheadIsolation("test", max_concurrent=5, timeout=300)
        
        assert bh.name == "test"
        assert bh.max_concurrent == 5
        assert bh.timeout == 300
        assert bh.active_count == 0
    
    @pytest.mark.asyncio
    async def test_bulkhead_executes_function(self):
        """Test bulkhead executes async function"""
        bh = BulkheadIsolation("test", max_concurrent=5)
        
        async def test_func():
            return "success"
        
        result = await bh.execute(test_func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_bulkhead_limits_concurrency(self):
        """Test bulkhead limits concurrent operations"""
        bh = BulkheadIsolation("test", max_concurrent=2, timeout=10)
        
        concurrent_count = 0
        max_concurrent_observed = 0
        
        async def concurrent_task(delay):
            nonlocal concurrent_count, max_concurrent_observed
            concurrent_count += 1
            max_concurrent_observed = max(max_concurrent_observed, concurrent_count)
            await asyncio.sleep(delay)
            concurrent_count -= 1
        
        # Run 5 tasks with max concurrency 2
        tasks = [
            bh.execute(concurrent_task, 0.1)
            for _ in range(5)
        ]
        await asyncio.gather(*tasks)
        
        # Max concurrent should not exceed 2
        assert max_concurrent_observed <= 2
    
    @pytest.mark.asyncio
    async def test_bulkhead_timeout(self):
        """Test bulkhead timeout on long-running operations"""
        bh = BulkheadIsolation("test", max_concurrent=5, timeout=0.1)
        
        async def long_task():
            await asyncio.sleep(1)
        
        with pytest.raises(asyncio.TimeoutError):
            await bh.execute(long_task)
    
    def test_bulkhead_status(self):
        """Test bulkhead status reporting"""
        bh = BulkheadIsolation("test", max_concurrent=5)
        
        status = bh.get_status()
        assert status["name"] == "test"
        assert status["max_concurrent"] == 5
        assert status["active_count"] == 0
        assert status["available_slots"] == 5


class TestResilienceManager:
    """Tests for resilience manager"""
    
    def test_resilience_manager_initialization(self):
        """Test resilience manager initializes correctly"""
        manager = ResilienceManager()
        
        assert len(manager.circuit_breakers) == 0
        assert len(manager.rate_limiters) == 0
        assert len(manager.retry_policies) == 0
        assert len(manager.bulkheads) == 0
    
    def test_register_circuit_breaker(self):
        """Test registering circuit breaker"""
        manager = ResilienceManager()
        cb = manager.register_circuit_breaker("test")
        
        assert "test" in manager.circuit_breakers
        assert manager.circuit_breakers["test"] == cb
    
    def test_register_rate_limiter(self):
        """Test registering rate limiter"""
        manager = ResilienceManager()
        rl = manager.register_rate_limiter("test", rate=10)
        
        assert "test" in manager.rate_limiters
        assert manager.rate_limiters["test"] == rl
    
    def test_register_retry_policy(self):
        """Test registering retry policy"""
        manager = ResilienceManager()
        rp = manager.register_retry_policy("test")
        
        assert "test" in manager.retry_policies
        assert manager.retry_policies["test"] == rp
    
    def test_register_bulkhead(self):
        """Test registering bulkhead"""
        manager = ResilienceManager()
        bh = manager.register_bulkhead("test")
        
        assert "test" in manager.bulkheads
        assert manager.bulkheads["test"] == bh
    
    def test_resilience_manager_status(self):
        """Test resilience manager status reporting"""
        manager = ResilienceManager()
        manager.register_circuit_breaker("cb")
        manager.register_rate_limiter("rl", rate=10)
        manager.register_bulkhead("bh")
        
        status = manager.get_status()
        assert "circuit_breakers" in status
        assert "rate_limiters" in status
        assert "bulkheads" in status
        assert len(status["circuit_breakers"]) == 1
        assert len(status["rate_limiters"]) == 1
        assert len(status["bulkheads"]) == 1


class TestGlobalResilienceManager:
    """Tests for global resilience manager"""
    
    def test_init_resilience_manager(self):
        """Test initializing global resilience manager"""
        manager = init_resilience_manager()
        
        assert manager is not None
        assert isinstance(manager, ResilienceManager)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
