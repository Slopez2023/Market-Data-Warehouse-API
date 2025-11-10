"""Metrics collection and monitoring service"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading


class MetricType(Enum):
    """Types of metrics"""
    REQUEST = "request"
    ERROR = "error"
    DATABASE = "database"
    SCHEDULER = "scheduler"
    DATA_QUALITY = "data_quality"


@dataclass
class RequestMetric:
    """Request metrics"""
    endpoint: str
    method: str
    status_code: int
    duration_ms: float
    timestamp: str
    trace_id: str


@dataclass
class ErrorMetric:
    """Error metrics"""
    error_type: str
    message: str
    endpoint: str
    timestamp: str
    trace_id: str


@dataclass
class MetricsSnapshot:
    """Snapshot of current metrics"""
    timestamp: str
    request_count: int
    error_count: int
    avg_response_time_ms: float
    error_rate_pct: float
    requests_last_hour: int
    errors_last_hour: int
    health_status: str


class MetricsCollector:
    """Collects and aggregates metrics"""

    def __init__(self, retention_hours: int = 24):
        self.retention_hours = retention_hours
        self.requests: List[RequestMetric] = []
        self.errors: List[ErrorMetric] = []
        self.lock = threading.Lock()

    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        trace_id: str,
    ) -> None:
        """Record a request metric"""
        with self.lock:
            self.requests.append(
                RequestMetric(
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    timestamp=datetime.utcnow().isoformat(),
                    trace_id=trace_id,
                )
            )
            self._cleanup_old_metrics()

    def record_error(
        self,
        error_type: str,
        message: str,
        endpoint: str,
        trace_id: str,
    ) -> None:
        """Record an error metric"""
        with self.lock:
            self.errors.append(
                ErrorMetric(
                    error_type=error_type,
                    message=message,
                    endpoint=endpoint,
                    timestamp=datetime.utcnow().isoformat(),
                    trace_id=trace_id,
                )
            )
            self._cleanup_old_metrics()

    def _cleanup_old_metrics(self) -> None:
        """Remove metrics older than retention period"""
        cutoff_time = datetime.utcnow() - timedelta(hours=self.retention_hours)
        cutoff_iso = cutoff_time.isoformat()

        self.requests = [r for r in self.requests if r.timestamp > cutoff_iso]
        self.errors = [e for e in self.errors if e.timestamp > cutoff_iso]

    def get_snapshot(self) -> MetricsSnapshot:
        """Get current metrics snapshot"""
        with self.lock:
            now = datetime.utcnow()
            one_hour_ago = (now - timedelta(hours=1)).isoformat()

            # All time metrics
            total_requests = len(self.requests)
            total_errors = len(self.errors)
            error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0

            # Average response time
            avg_response_time = 0.0
            if self.requests:
                avg_response_time = sum(r.duration_ms for r in self.requests) / len(self.requests)

            # Last hour metrics
            requests_last_hour = len([r for r in self.requests if r.timestamp > one_hour_ago])
            errors_last_hour = len([e for e in self.errors if e.timestamp > one_hour_ago])

            # Health status
            if error_rate > 10:
                health_status = "critical"
            elif error_rate > 5:
                health_status = "degraded"
            elif requests_last_hour == 0:
                health_status = "idle"
            else:
                health_status = "healthy"

            return MetricsSnapshot(
                timestamp=now.isoformat(),
                request_count=total_requests,
                error_count=total_errors,
                avg_response_time_ms=round(avg_response_time, 2),
                error_rate_pct=round(error_rate, 2),
                requests_last_hour=requests_last_hour,
                errors_last_hour=errors_last_hour,
                health_status=health_status,
            )

    def get_endpoint_stats(self) -> Dict[str, Dict]:
        """Get stats per endpoint"""
        with self.lock:
            stats: Dict[str, Dict] = {}

            # Group requests by endpoint
            for req in self.requests:
                key = f"{req.method} {req.endpoint}"
                if key not in stats:
                    stats[key] = {
                        "requests": 0,
                        "errors": 0,
                        "avg_duration_ms": 0,
                        "status_codes": {},
                    }
                stats[key]["requests"] += 1
                stats[key]["status_codes"][req.status_code] = stats[key]["status_codes"].get(req.status_code, 0) + 1

            # Add error counts and calculate averages
            for err in self.errors:
                key = f"{err.error_type} {err.endpoint}"
                if key not in stats:
                    stats[key] = {"requests": 0, "errors": 0, "avg_duration_ms": 0}
                stats[key]["errors"] += 1

            # Calculate averages
            for key, data in stats.items():
                if data["requests"] > 0:
                    matching_requests = [
                        r for r in self.requests
                        if f"{r.method} {r.endpoint}" == key
                    ]
                    if matching_requests:
                        data["avg_duration_ms"] = round(
                            sum(r.duration_ms for r in matching_requests) / len(matching_requests),
                            2
                        )

            return stats

    def get_error_summary(self) -> Dict[str, int]:
        """Get count of errors by type"""
        with self.lock:
            summary: Dict[str, int] = {}
            for err in self.errors:
                summary[err.error_type] = summary.get(err.error_type, 0) + 1
            return summary


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def init_metrics(retention_hours: int = 24) -> MetricsCollector:
    """Initialize the global metrics collector"""
    global _metrics_collector
    _metrics_collector = MetricsCollector(retention_hours=retention_hours)
    return _metrics_collector


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
