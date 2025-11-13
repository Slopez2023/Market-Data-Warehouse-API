"""Phase 2.1: Tests for environment validation"""

import pytest
import os
from unittest.mock import patch
from src.services.environment_validator import EnvironmentValidator
from src.config import ConfigError


class TestEnvironmentValidator:
    """Test suite for EnvironmentValidator"""
    
    def test_required_vars_present(self):
        """Test that required variables are detected"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "POLYGON_API_KEY": "test_key_123456789"
        }):
            validator = EnvironmentValidator()
            success, errors, warnings = validator.validate_all()
            
            # Should pass with required vars
            assert len(errors) == 0 or any("Missing required" not in e for e in errors)
    
    def test_missing_required_var(self):
        """Test detection of missing required variables"""
        with patch.dict(os.environ, {}, clear=True):
            validator = EnvironmentValidator()
            success, errors, warnings = validator.validate_all()
            
            # Should fail without required vars
            assert not success
            assert any("DATABASE_URL" in e for e in errors)
            assert any("POLYGON_API_KEY" in e for e in errors)
    
    def test_optional_vars_use_defaults(self):
        """Test that optional variables use defaults when not set"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://localhost/db",
            "POLYGON_API_KEY": "key123"
        }, clear=True):
            validator = EnvironmentValidator()
            success, errors, warnings = validator.validate_all()
            
            # Should have warnings about using defaults
            assert any("default" in w.lower() for w in warnings)
    
    def test_invalid_port_number(self):
        """Test validation of port number constraints"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://localhost/db",
            "POLYGON_API_KEY": "key123",
            "API_PORT": "99999"  # Invalid port
        }):
            validator = EnvironmentValidator()
            success, errors, warnings = validator.validate_all()
            
            assert not success
            assert any("port" in e.lower() for e in errors)
    
    def test_invalid_hour_value(self):
        """Test validation of schedule hour constraints"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://localhost/db",
            "POLYGON_API_KEY": "key123",
            "BACKFILL_SCHEDULE_HOUR": "25"  # Invalid hour
        }):
            validator = EnvironmentValidator()
            success, errors, warnings = validator.validate_all()
            
            assert not success
            assert any("hour" in e.lower() for e in errors)
    
    def test_invalid_minute_value(self):
        """Test validation of schedule minute constraints"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://localhost/db",
            "POLYGON_API_KEY": "key123",
            "BACKFILL_SCHEDULE_MINUTE": "75"  # Invalid minute
        }):
            validator = EnvironmentValidator()
            success, errors, warnings = validator.validate_all()
            
            assert not success
            assert any("minute" in e.lower() for e in errors)
    
    def test_invalid_workers_count(self):
        """Test validation of worker count"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://localhost/db",
            "POLYGON_API_KEY": "key123",
            "API_WORKERS": "0"  # Invalid workers count
        }):
            validator = EnvironmentValidator()
            success, errors, warnings = validator.validate_all()
            
            assert not success
            assert any("workers" in e.lower() for e in errors)
    
    def test_email_alerts_missing_config(self):
        """Test email alert configuration validation"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://localhost/db",
            "POLYGON_API_KEY": "key123",
            "ALERT_EMAIL_ENABLED": "true"
            # Missing email config
        }):
            validator = EnvironmentValidator()
            success, errors, warnings = validator.validate_all()
            
            assert not success
            assert any("email" in e.lower() for e in errors)
    
    def test_webhook_alerts_missing_url(self):
        """Test webhook alert configuration validation"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://localhost/db",
            "POLYGON_API_KEY": "key123",
            "ALERT_WEBHOOK_ENABLED": "true"
            # Missing webhook URL
        }):
            validator = EnvironmentValidator()
            success, errors, warnings = validator.validate_all()
            
            assert not success
            assert any("webhook" in e.lower() for e in errors)
    
    def test_valid_configuration(self):
        """Test with all valid configuration"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://user:pass@localhost/testdb",
            "POLYGON_API_KEY": "pk_test_abcd1234efgh5678ijkl9012mnop3456",
            "LOG_LEVEL": "INFO",
            "API_HOST": "0.0.0.0",
            "API_PORT": "8000",
            "API_WORKERS": "4",
            "BACKFILL_SCHEDULE_HOUR": "2",
            "BACKFILL_SCHEDULE_MINUTE": "0"
        }):
            validator = EnvironmentValidator()
            success, errors, warnings = validator.validate_all()
            
            # Should succeed with all valid config
            assert success
            assert len(errors) == 0
    
    def test_postgres_url_format_validation(self):
        """Test PostgreSQL URL format validation"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "mysql://localhost/db",  # Wrong database type
            "POLYGON_API_KEY": "key123"
        }):
            validator = EnvironmentValidator()
            success, errors, warnings = validator.validate_all()
            
            # Should have warning about invalid URL format
            assert any("url" in w.lower() for w in warnings)
    
    def test_api_key_length_validation(self):
        """Test API key length validation"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://localhost/db",
            "POLYGON_API_KEY": "short"  # Too short
        }):
            validator = EnvironmentValidator()
            success, errors, warnings = validator.validate_all()
            
            # Should have warning about short key
            assert any("short" in w.lower() for w in warnings)
    
    def test_sensitive_values_redaction(self):
        """Test that sensitive values are redacted in logs"""
        validator = EnvironmentValidator()
        
        # Test API key redaction
        assert validator._redact_sensitive("POLYGON_API_KEY", "pk_abcd1234efgh5678") == "pk_a...5678"
        
        # Test database URL redaction
        assert validator._redact_sensitive("DATABASE_URL", "postgresql://user:pass@localhost") == "***@localhost"
        
        # Test short key
        assert validator._redact_sensitive("API_KEY", "abc") == "***"
    
    def test_integer_parsing_errors(self):
        """Test handling of non-integer values for integer fields"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://localhost/db",
            "POLYGON_API_KEY": "key123",
            "API_PORT": "not_a_number"
        }):
            validator = EnvironmentValidator()
            success, errors, warnings = validator.validate_all()
            
            assert not success
            assert any("integer" in e.lower() for e in errors)


class TestEnvironmentValidationIntegration:
    """Integration tests for environment validation"""
    
    def test_full_validation_flow(self):
        """Test complete validation flow"""
        validator = EnvironmentValidator()
        success, errors, warnings = validator.validate_all()
        
        # Should return tuple
        assert isinstance(success, bool)
        assert isinstance(errors, list)
        assert isinstance(warnings, list)
    
    def test_config_summary_populated(self):
        """Test that config summary is populated after validation"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://localhost/db",
            "POLYGON_API_KEY": "key123",
            "API_PORT": "8000"
        }):
            validator = EnvironmentValidator()
            validator.validate_all()
            
            # Config summary should be populated
            assert len(validator.config_summary) > 0
            assert "API_PORT" in validator.config_summary
