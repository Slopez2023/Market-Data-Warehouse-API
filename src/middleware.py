"""FastAPI middleware for observability"""

import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.services.structured_logging import get_trace_id, set_trace_id, StructuredLogger
from src.services.metrics import get_metrics_collector
from src.services.alerting import get_alert_manager, AlertType, AlertSeverity

logger = StructuredLogger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware for request logging, metrics, and tracing"""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Get or create trace ID
        trace_id = request.headers.get("X-Trace-ID", "")
        if trace_id:
            set_trace_id(trace_id)
        else:
            trace_id = get_trace_id()

        # Add trace ID to response headers
        start_time = time.time()

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            # Record metrics
            metrics = get_metrics_collector()
            metrics.record_request(
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                duration_ms=duration_ms,
                trace_id=trace_id,
            )

            # Log request
            logger.info(
                f"{request.method} {request.url.path}",
                extra={
                    "method": request.method,
                    "endpoint": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                }
            )

            # Add trace ID to response
            response.headers["X-Trace-ID"] = trace_id
            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Record error
            metrics = get_metrics_collector()
            metrics.record_error(
                error_type=type(e).__name__,
                message=str(e),
                endpoint=request.url.path,
                trace_id=trace_id,
            )

            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    "method": request.method,
                    "endpoint": request.url.path,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True,
            )

            # Trigger alert for errors
            alert_manager = get_alert_manager()
            await alert_manager.alert(
                alert_type=AlertType.API_TIMEOUT,
                severity=AlertSeverity.WARNING,
                title="Request Error",
                message=f"{type(e).__name__}: {str(e)}",
                metadata={
                    "endpoint": request.url.path,
                    "method": request.method,
                    "duration_ms": round(duration_ms, 2),
                }
            )

            raise
