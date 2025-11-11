"""Application configuration and environment validation"""

import os
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

# Allowed timeframes for OHLCV data
ALLOWED_TIMEFRAMES: List[str] = ['5m', '15m', '30m', '1h', '4h', '1d', '1w']
DEFAULT_TIMEFRAMES: List[str] = ['1h', '1d']


class ConfigError(Exception):
    """Configuration validation error"""
    pass


class AppConfig:
    """Application configuration with validation"""

    def __init__(self):
        """Load and validate configuration from environment"""
        self.database_url = self._get_required("DATABASE_URL", "PostgreSQL connection URL")
        self.polygon_api_key = self._get_required("POLYGON_API_KEY", "Polygon.io API key")
        self.log_level = self._get_optional("LOG_LEVEL", "INFO", "Logging level (DEBUG, INFO, WARNING, ERROR)")
        self.api_host = self._get_optional("API_HOST", "0.0.0.0", "API host")
        self.api_port = self._get_int("API_PORT", 8000, "API port")
        self.api_workers = self._get_int("API_WORKERS", 4, "API worker threads")
        self.backfill_schedule_hour = self._get_int("BACKFILL_SCHEDULE_HOUR", 2, "Backfill schedule hour (UTC 0-23)")
        self.backfill_schedule_minute = self._get_int("BACKFILL_SCHEDULE_MINUTE", 0, "Backfill schedule minute (0-59)")

        # Alerting configuration (optional)
        self.alert_email_enabled = self._get_bool("ALERT_EMAIL_ENABLED", False, "Enable email alerts")
        self.alert_email_to = self._get_optional("ALERT_EMAIL_TO", "", "Email recipient for alerts")
        self.alert_email_from = self._get_optional("ALERT_EMAIL_FROM", "", "Email sender address")
        self.alert_smtp_host = self._get_optional("ALERT_SMTP_HOST", "", "SMTP host for email alerts")
        self.alert_smtp_port = self._get_int("ALERT_SMTP_PORT", 587, "SMTP port")
        self.alert_smtp_password = self._get_optional("ALERT_SMTP_PASSWORD", "", "SMTP password")

        self.alert_webhook_enabled = self._get_bool("ALERT_WEBHOOK_ENABLED", False, "Enable webhook alerts")
        self.alert_webhook_url = self._get_optional("ALERT_WEBHOOK_URL", "", "Webhook URL for alerts")

        # Validate backfill schedule
        if not (0 <= self.backfill_schedule_hour <= 23):
            raise ConfigError(f"BACKFILL_SCHEDULE_HOUR must be 0-23, got {self.backfill_schedule_hour}")
        if not (0 <= self.backfill_schedule_minute <= 59):
            raise ConfigError(f"BACKFILL_SCHEDULE_MINUTE must be 0-59, got {self.backfill_schedule_minute}")

        # Validate API port
        if not (1 <= self.api_port <= 65535):
            raise ConfigError(f"API_PORT must be 1-65535, got {self.api_port}")

        # Validate API workers
        if self.api_workers < 1:
            raise ConfigError(f"API_WORKERS must be >= 1, got {self.api_workers}")

        # Validate email alerting config if enabled
        if self.alert_email_enabled:
            if not self.alert_email_to:
                raise ConfigError("ALERT_EMAIL_TO required when ALERT_EMAIL_ENABLED=true")
            if not self.alert_email_from:
                raise ConfigError("ALERT_EMAIL_FROM required when ALERT_EMAIL_ENABLED=true")
            if not self.alert_smtp_host:
                raise ConfigError("ALERT_SMTP_HOST required when ALERT_EMAIL_ENABLED=true")
            if not self.alert_smtp_password:
                raise ConfigError("ALERT_SMTP_PASSWORD required when ALERT_EMAIL_ENABLED=true")

        # Validate webhook alerting config if enabled
        if self.alert_webhook_enabled:
            if not self.alert_webhook_url:
                raise ConfigError("ALERT_WEBHOOK_URL required when ALERT_WEBHOOK_ENABLED=true")

        logger.info("✓ Configuration loaded and validated")

    def _get_required(self, key: str, description: str) -> str:
        """Get required environment variable"""
        value = os.getenv(key)
        if not value:
            raise ConfigError(f"Missing required environment variable: {key} ({description})")
        return value

    def _get_optional(self, key: str, default: str, description: str) -> str:
        """Get optional environment variable with default"""
        value = os.getenv(key, default)
        if value == default and default:
            logger.debug(f"Using default for {key}: {default}")
        return value

    def _get_int(self, key: str, default: int, description: str) -> int:
        """Get integer environment variable"""
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            raise ConfigError(f"Invalid integer for {key}: {value} ({description})")

    def _get_bool(self, key: str, default: bool, description: str) -> bool:
        """Get boolean environment variable"""
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    def log_summary(self):
        """Log configuration summary (redacting secrets)"""
        logger.info("Application Configuration:")
        logger.info(f"  Database: {self._redact_url(self.database_url)}")
        logger.info(f"  Polygon API Key: {self._redact_key(self.polygon_api_key)}")
        logger.info(f"  Log Level: {self.log_level}")
        logger.info(f"  API: {self.api_host}:{self.api_port} ({self.api_workers} workers)")
        logger.info(f"  Backfill Schedule: {self.backfill_schedule_hour:02d}:{self.backfill_schedule_minute:02d} UTC daily")
        if self.alert_email_enabled:
            logger.info(f"  Email Alerts: {self.alert_email_to}")
        if self.alert_webhook_enabled:
            logger.info(f"  Webhook Alerts: {self._redact_url(self.alert_webhook_url)}")

    @staticmethod
    def _redact_url(url: str) -> str:
        """Redact credentials from URL"""
        if not url:
            return url
        try:
            parts = url.split("@")
            if len(parts) == 2:
                return f"***@{parts[1]}"
            return url[:10] + "***"
        except Exception:
            return url[:10] + "***"

    @staticmethod
    def _redact_key(key: str) -> str:
        """Redact API key"""
        if not key or len(key) < 4:
            return "***"
        return f"{key[:4]}...{key[-4:]}"


# Global config instance
try:
    config = AppConfig()
except ConfigError as e:
    logger.error(f"Configuration error: {e}")
    raise
