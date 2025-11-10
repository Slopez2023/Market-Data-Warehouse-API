"""Tests for API key authentication service"""

import pytest
import hashlib
from src.services.auth import APIKeyService


class TestAPIKeyGeneration:
    """Test API key generation"""
    
    def test_generate_api_key_format(self):
        """Test that generated API key has correct format"""
        key = APIKeyService.generate_api_key("Test Project")
        
        # Should start with mdw_
        assert key.startswith("mdw_")
        # Should be long enough (prefix + 64 hex chars)
        assert len(key) > 30
    
    def test_generate_unique_keys(self):
        """Test that each generated key is unique"""
        key1 = APIKeyService.generate_api_key("Project 1")
        key2 = APIKeyService.generate_api_key("Project 2")
        
        assert key1 != key2
    
    def test_hash_api_key(self):
        """Test API key hashing"""
        api_key = APIKeyService.generate_api_key("Test")
        hashed = APIKeyService.hash_api_key(api_key)
        
        # Should be SHA256 hex (64 chars)
        assert len(hashed) == 64
        assert all(c in '0123456789abcdef' for c in hashed)
    
    def test_hash_deterministic(self):
        """Test that hashing is deterministic"""
        api_key = "test_key_12345"
        hash1 = APIKeyService.hash_api_key(api_key)
        hash2 = APIKeyService.hash_api_key(api_key)
        
        assert hash1 == hash2
    
    def test_hash_matches_sha256(self):
        """Test that hash matches SHA256"""
        api_key = "test_key_12345"
        expected = hashlib.sha256(api_key.encode()).hexdigest()
        actual = APIKeyService.hash_api_key(api_key)
        
        assert actual == expected
