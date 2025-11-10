"""Alert management and notification service"""

import asyncio
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Callable, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts"""
    HIGH_ERROR_RATE = "high_error_rate"
    DATABASE_OFFLINE = "database_offline"
    SCHEDULER_FAILED = "scheduler_failed"
    DATA_STALENESS = "data_staleness"
    API_TIMEOUT = "api_timeout"
    CUSTOM = "custom"


@dataclass
class Alert:
    """Alert data structure"""
    type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    timestamp: str
    metadata: dict


class AlertHandler:
    """Base class for alert handlers"""

    async def handle(self, alert: Alert) -> bool:
        """Handle an alert. Return True if successful."""
        raise NotImplementedError


class EmailAlertHandler(AlertHandler):
    """Send alerts via email"""

    def __init__(self, smtp_server: str, smtp_port: int, sender_email: str, sender_password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.recipients: List[str] = []

    def add_recipient(self, email: str) -> None:
        """Add a recipient email"""
        if email not in self.recipients:
            self.recipients.append(email)

    async def handle(self, alert: Alert) -> bool:
        """Send alert via email"""
        if not self.recipients:
            return False

        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = ", ".join(self.recipients)
            msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.title}"

            # Build body
            body = f"""
Alert Type: {alert.type.value}
Severity: {alert.severity.value.upper()}
Timestamp: {alert.timestamp}

Message:
{alert.message}

Metadata:
{self._format_metadata(alert.metadata)}
"""
            msg.attach(MIMEText(body, "plain"))

            # Send in async context
            await asyncio.to_thread(self._send_email, msg)
            return True

        except Exception as e:
            print(f"Failed to send email alert: {e}")
            return False

    def _send_email(self, msg: MIMEMultipart) -> None:
        """Actually send the email (blocking operation)"""
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.send_message(msg)

    @staticmethod
    def _format_metadata(metadata: dict) -> str:
        """Format metadata for display"""
        return "\n".join(f"  {k}: {v}" for k, v in metadata.items())


class LogAlertHandler(AlertHandler):
    """Log alerts"""

    def __init__(self, logger):
        self.logger = logger

    async def handle(self, alert: Alert) -> bool:
        """Log alert"""
        try:
            log_method = getattr(self.logger, alert.severity.value, self.logger.info)
            log_method(
                f"[{alert.type.value}] {alert.title}: {alert.message}",
                extra={"alert_metadata": alert.metadata}
            )
            return True
        except Exception as e:
            print(f"Failed to log alert: {e}")
            return False


class AlertManager:
    """Manages alerts and notifies handlers"""

    def __init__(self):
        self.handlers: List[AlertHandler] = []
        self.alert_history: List[Alert] = []
        self.max_history = 1000
        self.thresholds = {
            "error_rate_pct": 10.0,
            "data_staleness_hours": 24,
            "api_timeout_seconds": 30,
        }

    def add_handler(self, handler: AlertHandler) -> None:
        """Add an alert handler"""
        self.handlers.append(handler)

    def remove_handler(self, handler: AlertHandler) -> None:
        """Remove an alert handler"""
        if handler in self.handlers:
            self.handlers.remove(handler)

    def set_threshold(self, name: str, value: float) -> None:
        """Set an alert threshold"""
        self.thresholds[name] = value

    async def alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Trigger an alert"""
        alert = Alert(
            type=alert_type,
            severity=severity,
            title=title,
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            metadata=metadata or {},
        )

        # Store in history
        self.alert_history.append(alert)
        if len(self.alert_history) > self.max_history:
            self.alert_history.pop(0)

        # Notify all handlers
        results = await asyncio.gather(
            *[handler.handle(alert) for handler in self.handlers],
            return_exceptions=True
        )

        return all(isinstance(r, bool) and r for r in results)

    def get_alert_history(self, limit: int = 100) -> List[dict]:
        """Get recent alerts"""
        return [
            {
                "type": a.type.value,
                "severity": a.severity.value,
                "title": a.title,
                "message": a.message,
                "timestamp": a.timestamp,
                "metadata": a.metadata,
            }
            for a in self.alert_history[-limit:]
        ]

    async def check_error_rate(self, error_rate_pct: float, request_count: int) -> None:
        """Check if error rate exceeds threshold"""
        threshold = self.thresholds.get("error_rate_pct", 10.0)
        if error_rate_pct > threshold and request_count > 10:
            await self.alert(
                alert_type=AlertType.HIGH_ERROR_RATE,
                severity=AlertSeverity.CRITICAL if error_rate_pct > 20 else AlertSeverity.WARNING,
                title="High Error Rate Detected",
                message=f"Error rate is {error_rate_pct}% (threshold: {threshold}%)",
                metadata={
                    "error_rate_pct": error_rate_pct,
                    "request_count": request_count,
                    "threshold": threshold,
                }
            )

    async def check_data_staleness(self, latest_data_age_hours: float) -> None:
        """Check if data is too stale"""
        threshold = self.thresholds.get("data_staleness_hours", 24)
        if latest_data_age_hours > threshold:
            await self.alert(
                alert_type=AlertType.DATA_STALENESS,
                severity=AlertSeverity.WARNING,
                title="Data Staleness Alert",
                message=f"Latest data is {latest_data_age_hours:.1f} hours old (threshold: {threshold} hours)",
                metadata={
                    "age_hours": latest_data_age_hours,
                    "threshold": threshold,
                }
            )

    async def check_scheduler_health(self, is_running: bool, last_run_age_hours: float) -> None:
        """Check scheduler health"""
        if not is_running:
            await self.alert(
                alert_type=AlertType.SCHEDULER_FAILED,
                severity=AlertSeverity.CRITICAL,
                title="Scheduler Not Running",
                message="Data backfill scheduler has stopped",
                metadata={"last_run_age_hours": last_run_age_hours}
            )
        elif last_run_age_hours > 30:  # More than 30 hours since last run
            await self.alert(
                alert_type=AlertType.SCHEDULER_FAILED,
                severity=AlertSeverity.WARNING,
                title="Scheduler May Be Stuck",
                message=f"No successful scheduler run in {last_run_age_hours:.1f} hours",
                metadata={"last_run_age_hours": last_run_age_hours}
            )


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def init_alert_manager() -> AlertManager:
    """Initialize the global alert manager"""
    global _alert_manager
    _alert_manager = AlertManager()
    return _alert_manager


def get_alert_manager() -> AlertManager:
    """Get the global alert manager"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
