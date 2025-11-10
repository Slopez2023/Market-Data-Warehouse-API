"""Phase 2.1: Environment variable validation on startup"""

import logging
import os
from typing import Dict, List, Tuple
from src.config import ConfigError

logger = logging.getLogger(__name__)


class EnvironmentValidator:
    """Validates all required environment variables and system state on startup"""
    
    REQUIRED_VARS = {
        "DATABASE_URL": "PostgreSQL connection string",
        "POLYGON_API_KEY": "Polygon.io API key"
    }
    
    OPTIONAL_VARS = {
        "LOG_LEVEL": ("INFO", "Logging level"),
        "API_HOST": ("0.0.0.0", "API host"),
        "API_PORT": ("8000", "API port"),
        "API_WORKERS": ("4", "API worker threads"),
        "BACKFILL_SCHEDULE_HOUR": ("2", "Backfill schedule hour UTC"),
        "BACKFILL_SCHEDULE_MINUTE": ("0", "Backfill schedule minute"),
    }
    
    def __init__(self):
        """Initialize validator"""
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.config_summary: Dict = {}
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """
        Validate all environment variables.
        
        Returns:
            Tuple of (success: bool, errors: List[str], warnings: List[str])
        """
        self.errors = []
        self.warnings = []
        
        # Validate required variables
        self._validate_required_vars()
        
        # Validate optional variables
        self._validate_optional_vars()
        
        # Validate derived constraints
        self._validate_constraints()
        
        # Log results
        self._log_results()
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def _validate_required_vars(self) -> None:
        """Validate required environment variables exist"""
        for var_name, description in self.REQUIRED_VARS.items():
            value = os.getenv(var_name)
            if not value:
                self.errors.append(f"Missing required: {var_name} ({description})")
            else:
                self.config_summary[var_name] = self._redact_sensitive(var_name, value)
    
    def _validate_optional_vars(self) -> None:
        """Validate optional variables have valid formats"""
        for var_name, (default, description) in self.OPTIONAL_VARS.items():
            value = os.getenv(var_name, default)
            
            # Type-specific validation
            if "PORT" in var_name or "HOUR" in var_name or "MINUTE" in var_name or "WORKERS" in var_name:
                try:
                    int_value = int(value)
                    if "PORT" in var_name and not (1 <= int_value <= 65535):
                        self.errors.append(f"{var_name}: port must be 1-65535, got {int_value}")
                    elif "HOUR" in var_name and not (0 <= int_value <= 23):
                        self.errors.append(f"{var_name}: hour must be 0-23, got {int_value}")
                    elif "MINUTE" in var_name and not (0 <= int_value <= 59):
                        self.errors.append(f"{var_name}: minute must be 0-59, got {int_value}")
                    elif "WORKERS" in var_name and int_value < 1:
                        self.errors.append(f"{var_name}: workers must be >= 1, got {int_value}")
                    else:
                        self.config_summary[var_name] = int_value
                except ValueError:
                    self.errors.append(f"{var_name}: invalid integer '{value}'")
            else:
                # String values
                if value == default:
                    self.warnings.append(f"{var_name}: using default '{default}'")
                self.config_summary[var_name] = value
    
    def _validate_constraints(self) -> None:
        """Validate cross-variable constraints"""
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            # Check database URL format
            if not self._is_valid_postgres_url(db_url):
                self.warnings.append("DATABASE_URL: not a standard PostgreSQL URL format")
        
        api_key = os.getenv("POLYGON_API_KEY")
        if api_key and len(api_key) < 10:
            self.warnings.append("POLYGON_API_KEY: suspiciously short, may be invalid")
        
        # Check alert config consistency
        alert_email_enabled = os.getenv("ALERT_EMAIL_ENABLED", "false").lower() in ("true", "1", "yes")
        if alert_email_enabled:
            required_email_vars = ["ALERT_EMAIL_TO", "ALERT_EMAIL_FROM", "ALERT_SMTP_HOST", "ALERT_SMTP_PASSWORD"]
            missing = [v for v in required_email_vars if not os.getenv(v)]
            if missing:
                self.errors.append(f"Email alerts enabled but missing: {', '.join(missing)}")
        
        alert_webhook_enabled = os.getenv("ALERT_WEBHOOK_ENABLED", "false").lower() in ("true", "1", "yes")
        if alert_webhook_enabled and not os.getenv("ALERT_WEBHOOK_URL"):
            self.errors.append("Webhook alerts enabled but ALERT_WEBHOOK_URL not set")
    
    def _is_valid_postgres_url(self, url: str) -> bool:
        """Check if URL looks like a PostgreSQL connection string"""
        return url.startswith("postgresql://") or url.startswith("postgres://")
    
    def _redact_sensitive(self, var_name: str, value: str) -> str:
        """Redact sensitive values for logging"""
        if "KEY" in var_name or "PASSWORD" in var_name or "TOKEN" in var_name:
            if len(value) <= 4:
                return "***"
            return f"{value[:4]}...{value[-4:]}"
        elif "URL" in var_name and "@" in value:
            parts = value.split("@")
            return f"***@{parts[-1]}"
        return value
    
    def _log_results(self) -> None:
        """Log validation results"""
        logger.info("Environment Validation Results:")
        
        if self.errors:
            logger.error(f"❌ {len(self.errors)} validation errors:")
            for error in self.errors:
                logger.error(f"   - {error}")
        
        if self.warnings:
            logger.warning(f"⚠️  {len(self.warnings)} warnings:")
            for warning in self.warnings:
                logger.warning(f"   - {warning}")
        
        if not self.errors:
            logger.info("✓ All required environment variables validated")
            logger.debug("Configuration:")
            for key, value in self.config_summary.items():
                logger.debug(f"  {key}: {value}")


def validate_environment_on_startup() -> None:
    """
    Validate environment on application startup.
    Raises ConfigError if critical issues found.
    """
    validator = EnvironmentValidator()
    success, errors, warnings = validator.validate_all()
    
    if not success:
        error_msg = "Environment validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ConfigError(error_msg)
