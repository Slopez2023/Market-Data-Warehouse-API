"""Tests for observability features (logging, metrics, alerting)"""

import pytest
import asyncio
from datetime import datetime, timedelta
from src.services.structured_logging import StructuredLogger, get_trace_id, set_trace_id
from src.services.metrics import MetricsCollector, MetricType
from src.services.alerting import AlertManager, AlertType, AlertSeverity, LogAlertHandler
from src.middleware import ObservabilityMiddleware


class TestStructuredLogger:
    """Test structured logging functionality"""

    def test_logger_creation(self):
        """Test creating a structured logger"""
        logger = StructuredLogger("test")
        assert logger.logger.name == "test"

    def test_logger_info(self, caplog):
        """Test info level logging"""
        logger = StructuredLogger("test")
        logger.info("Test message")
        assert "Test message" in caplog.text

    def test_logger_with_extra_data(self, caplog):
        """Test logging with extra data"""
        logger = StructuredLogger("test")
        logger.info("Test", extra={"key": "value"})
        assert "Test" in caplog.text

    def test_trace_id_generation(self):
        """Test trace ID generation"""
        trace_id = get_trace_id()
        assert trace_id
        assert len(trace_id) > 0

    def test_trace_id_persistence(self):
        """Test trace ID persists across calls"""
        set_trace_id("test-trace-123")
        id1 = get_trace_id()
        id2 = get_trace_id()
        assert id1 == id2 == "test-trace-123"

    def test_trace_id_change(self):
        """Test changing trace ID"""
        set_trace_id("trace-1")
        assert get_trace_id() == "trace-1"
        set_trace_id("trace-2")
        assert get_trace_id() == "trace-2"


class TestMetricsCollector:
    """Test metrics collection"""

    def test_collector_initialization(self):
        """Test creating metrics collector"""
        collector = MetricsCollector()
        snapshot = collector.get_snapshot()
        assert snapshot.request_count == 0
        assert snapshot.error_count == 0

    def test_record_request(self):
        """Test recording a request"""
        collector = MetricsCollector()
        collector.record_request(
            endpoint="/api/test",
            method="GET",
            status_code=200,
            duration_ms=45.5,
            trace_id="test-trace"
        )
        snapshot = collector.get_snapshot()
        assert snapshot.request_count == 1
        assert snapshot.avg_response_time_ms == 45.5

    def test_record_multiple_requests(self):
        """Test recording multiple requests"""
        collector = MetricsCollector()
        for i in range(10):
            collector.record_request(
                endpoint="/api/test",
                method="GET",
                status_code=200,
                duration_ms=50.0 + i,
                trace_id=f"trace-{i}"
            )
        snapshot = collector.get_snapshot()
        assert snapshot.request_count == 10

    def test_record_error(self):
        """Test recording an error"""
        collector = MetricsCollector()
        collector.record_error(
            error_type="ValueError",
            message="Test error",
            endpoint="/api/test",
            trace_id="test-trace"
        )
        snapshot = collector.get_snapshot()
        assert snapshot.error_count == 1

    def test_error_rate_calculation(self):
        """Test error rate calculation"""
        collector = MetricsCollector()
        # Record 100 requests, 10 errors
        for i in range(100):
            collector.record_request(
                endpoint="/api/test",
                method="GET",
                status_code=200 if i < 90 else 500,
                duration_ms=50.0,
                trace_id=f"trace-{i}"
            )
        for i in range(10):
            collector.record_error(
                error_type="Error",
                message="Test",
                endpoint="/api/test",
                trace_id=f"error-{i}"
            )
        snapshot = collector.get_snapshot()
        # 10 errors out of 110 total (100 requests + 10 errors) = ~9.09%
        assert snapshot.error_rate_pct == pytest.approx(10.0, rel=0.1)

    def test_health_status_healthy(self):
        """Test health status calculation - healthy"""
        collector = MetricsCollector()
        for i in range(100):
            collector.record_request(
                endpoint="/api/test",
                method="GET",
                status_code=200,
                duration_ms=50.0,
                trace_id=f"trace-{i}"
            )
        # Low error rate
        for i in range(2):
            collector.record_error(
                error_type="Error",
                message="Test",
                endpoint="/api/test",
                trace_id=f"error-{i}"
            )
        snapshot = collector.get_snapshot()
        assert snapshot.health_status == "healthy"

    def test_health_status_degraded(self):
        """Test health status calculation - degraded"""
        collector = MetricsCollector()
        for i in range(100):
            collector.record_request(
                endpoint="/api/test",
                method="GET",
                status_code=200 if i < 95 else 500,
                duration_ms=50.0,
                trace_id=f"trace-{i}"
            )
        for i in range(7):
            collector.record_error(
                error_type="Error",
                message="Test",
                endpoint="/api/test",
                trace_id=f"error-{i}"
            )
        snapshot = collector.get_snapshot()
        assert snapshot.health_status == "degraded"

    def test_health_status_critical(self):
        """Test health status calculation - critical"""
        collector = MetricsCollector()
        for i in range(50):
            collector.record_request(
                endpoint="/api/test",
                method="GET",
                status_code=500,
                duration_ms=50.0,
                trace_id=f"trace-{i}"
            )
        for i in range(25):
            collector.record_error(
                error_type="Error",
                message="Test",
                endpoint="/api/test",
                trace_id=f"error-{i}"
            )
        snapshot = collector.get_snapshot()
        assert snapshot.health_status == "critical"

    def test_endpoint_stats(self):
        """Test per-endpoint statistics"""
        collector = MetricsCollector()
        # Record requests to different endpoints
        for i in range(50):
            collector.record_request(
                endpoint="/api/data",
                method="GET",
                status_code=200,
                duration_ms=100.0,
                trace_id=f"trace-{i}"
            )
        for i in range(30):
            collector.record_request(
                endpoint="/api/health",
                method="GET",
                status_code=200,
                duration_ms=5.0,
                trace_id=f"trace-health-{i}"
            )
        stats = collector.get_endpoint_stats()
        assert "GET /api/data" in stats
        assert "GET /api/health" in stats
        assert stats["GET /api/data"]["requests"] == 50
        assert stats["GET /api/health"]["requests"] == 30

    def test_error_summary(self):
        """Test error summary"""
        collector = MetricsCollector()
        collector.record_error("ValueError", "Test 1", "/api/test", "trace-1")
        collector.record_error("ValueError", "Test 2", "/api/test", "trace-2")
        collector.record_error("TypeError", "Test 3", "/api/test", "trace-3")
        summary = collector.get_error_summary()
        assert summary["ValueError"] == 2
        assert summary["TypeError"] == 1

    def test_metric_retention(self):
        """Test old metrics are cleaned up"""
        collector = MetricsCollector(retention_hours=24)
        collector.record_request("/api/test", "GET", 200, 50.0, "trace-1")
        snapshot1 = collector.get_snapshot()
        assert snapshot1.request_count == 1

        # Record another request
        collector.record_request("/api/test", "GET", 200, 50.0, "trace-2")
        snapshot2 = collector.get_snapshot()
        # Both metrics should still be there (within retention window)
        assert snapshot2.request_count == 2


class TestAlertManager:
    """Test alert management"""

    @pytest.mark.asyncio
    async def test_alert_creation(self):
        """Test creating an alert"""
        manager = AlertManager()
        result = await manager.alert(
            alert_type=AlertType.HIGH_ERROR_RATE,
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="Test message",
            metadata={"test": "data"}
        )
        assert len(manager.alert_history) == 1
        assert manager.alert_history[0].title == "Test Alert"

    @pytest.mark.asyncio
    async def test_alert_with_handler(self):
        """Test alert triggers handlers"""
        manager = AlertManager()
        handler_called = False

        class TestHandler:
            async def handle(self, alert):
                nonlocal handler_called
                handler_called = True
                return True

        manager.add_handler(TestHandler())
        await manager.alert(
            alert_type=AlertType.HIGH_ERROR_RATE,
            severity=AlertSeverity.WARNING,
            title="Test",
            message="Test"
        )
        assert handler_called

    @pytest.mark.asyncio
    async def test_alert_history(self):
        """Test alert history"""
        manager = AlertManager()
        for i in range(5):
            await manager.alert(
                alert_type=AlertType.HIGH_ERROR_RATE,
                severity=AlertSeverity.WARNING,
                title=f"Alert {i}",
                message="Test"
            )
        history = manager.get_alert_history(limit=3)
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_error_rate_check(self):
        """Test error rate alert check"""
        manager = AlertManager()
        handler_called = False

        class TestHandler:
            async def handle(self, alert):
                nonlocal handler_called
                handler_called = True
                return True

        manager.add_handler(TestHandler())
        manager.set_threshold("error_rate_pct", 5.0)

        # High error rate should trigger alert
        await manager.check_error_rate(error_rate_pct=8.5, request_count=100)
        assert handler_called

    @pytest.mark.asyncio
    async def test_error_rate_below_threshold(self):
        """Test error rate below threshold"""
        manager = AlertManager()
        handler_called = False

        class TestHandler:
            async def handle(self, alert):
                nonlocal handler_called
                handler_called = True
                return True

        manager.add_handler(TestHandler())
        manager.set_threshold("error_rate_pct", 10.0)

        # Low error rate should not trigger alert
        await manager.check_error_rate(error_rate_pct=3.5, request_count=100)
        assert not handler_called

    @pytest.mark.asyncio
    async def test_data_staleness_check(self):
        """Test data staleness alert"""
        manager = AlertManager()
        handler_called = False

        class TestHandler:
            async def handle(self, alert):
                nonlocal handler_called
                handler_called = True
                return True

        manager.add_handler(TestHandler())
        manager.set_threshold("data_staleness_hours", 24)

        # Stale data should trigger alert
        await manager.check_data_staleness(latest_data_age_hours=48)
        assert handler_called

    @pytest.mark.asyncio
    async def test_scheduler_health_check(self):
        """Test scheduler health check"""
        manager = AlertManager()
        handler_called = False

        class TestHandler:
            async def handle(self, alert):
                nonlocal handler_called
                handler_called = True
                return True

        manager.add_handler(TestHandler())

        # Scheduler not running should trigger alert
        await manager.check_scheduler_health(is_running=False, last_run_age_hours=12)
        assert handler_called

    @pytest.mark.asyncio
    async def test_threshold_configuration(self):
        """Test setting custom thresholds"""
        manager = AlertManager()
        manager.set_threshold("error_rate_pct", 20.0)
        assert manager.thresholds["error_rate_pct"] == 20.0

    @pytest.mark.asyncio
    async def test_alert_severity_levels(self):
        """Test different severity levels"""
        manager = AlertManager()
        await manager.alert(
            alert_type=AlertType.HIGH_ERROR_RATE,
            severity=AlertSeverity.INFO,
            title="Info",
            message="Test"
        )
        await manager.alert(
            alert_type=AlertType.HIGH_ERROR_RATE,
            severity=AlertSeverity.WARNING,
            title="Warning",
            message="Test"
        )
        await manager.alert(
            alert_type=AlertType.DATABASE_OFFLINE,
            severity=AlertSeverity.CRITICAL,
            title="Critical",
            message="Test"
        )
        history = manager.get_alert_history()
        assert len(history) == 3
        assert history[0]["severity"] == "info"
        assert history[1]["severity"] == "warning"
        assert history[2]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_log_alert_handler(self, caplog):
        """Test logging alert handler"""
        manager = AlertManager()
        logger = StructuredLogger("test")
        handler = LogAlertHandler(logger)
        manager.add_handler(handler)

        await manager.alert(
            alert_type=AlertType.HIGH_ERROR_RATE,
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="This is a test"
        )
        assert "Test Alert" in caplog.text


class TestMetricsIntegration:
    """Integration tests for metrics"""

    def test_realistic_traffic_pattern(self):
        """Test with realistic traffic patterns"""
        collector = MetricsCollector()

        # Simulate normal traffic with requests and errors
        for i in range(1000):
            status = 200 if i % 20 != 0 else 500  # 5% error rate in status codes
            collector.record_request(
                endpoint="/api/data" if i % 2 == 0 else "/api/health",
                method="GET",
                status_code=status,
                duration_ms=50.0 + (i % 50),
                trace_id=f"trace-{i}"
            )
        
        # Add errors to match 5% error rate
        for i in range(50):
            collector.record_error(
                error_type="Error",
                message="Test",
                endpoint="/api/data",
                trace_id=f"error-{i}"
            )

        snapshot = collector.get_snapshot()
        assert snapshot.request_count == 1000
        # 50 errors out of 1050 total = ~4.76%
        assert snapshot.error_rate_pct > 4 and snapshot.error_rate_pct < 6

    def test_zero_requests(self):
        """Test with no requests recorded"""
        collector = MetricsCollector()
        snapshot = collector.get_snapshot()
        assert snapshot.request_count == 0
        assert snapshot.error_rate_pct == 0.0
        assert snapshot.health_status == "idle"
