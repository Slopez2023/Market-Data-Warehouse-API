"""Structured logging service with JSON output and trace IDs"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar

# Context variable for storing trace ID across async operations
trace_id_context: ContextVar[str] = ContextVar("trace_id", default="")


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id_context.get() or "",
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data)


class StructuredLogger:
    """Wrapper for structured logging with trace ID support"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def _log(
        self,
        level: int,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """Internal log method with extra data support"""
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            "(unknown file)",
            0,
            message,
            (),
            exc_info=exc_info if exc_info else None,
        )
        if extra_data:
            record.extra_data = extra_data
        self.logger.handle(record)

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._log(logging.DEBUG, message, extra)

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._log(logging.INFO, message, extra)

    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._log(logging.WARNING, message, extra)

    def error(self, message: str, extra: Optional[Dict[str, Any]] = None, exc_info: bool = False) -> None:
        self._log(logging.ERROR, message, extra, exc_info)

    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None, exc_info: bool = False) -> None:
        self._log(logging.CRITICAL, message, extra, exc_info)


def setup_structured_logging(level: str = "INFO") -> None:
    """Configure structured logging for the application"""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add new structured handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(console_handler)


def get_trace_id() -> str:
    """Get current trace ID or generate new one"""
    current = trace_id_context.get()
    if not current:
        current = str(uuid.uuid4())
        trace_id_context.set(current)
    return current


def set_trace_id(trace_id: str) -> None:
    """Set trace ID for logging context"""
    trace_id_context.set(trace_id)
