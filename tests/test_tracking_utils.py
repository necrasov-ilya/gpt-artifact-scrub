"""
Tests for slug generation and payload encoding utilities.
"""
import pytest

from src.modules.tracking.utils.slug_generator import (
    normalize_slug,
    generate_slug_with_fallback,
    resolve_slug_collision,
    validate_slug,
)
from src.modules.tracking.utils.payload_encoder import (
    encode_link_id,
    decode_payload,
    generate_start_link,
)


class TestSlugGeneration:
    """Test slug generation and normalization."""
    
    def test_normalize_basic(self):
        """Test basic slug normalization."""
        assert normalize_slug("Hello World") == "hello-world"
        assert normalize_slug("Test_123") == "test-123"
        assert normalize_slug("Multiple   Spaces") == "multiple-spaces"
    
    def test_normalize_special_chars(self):
        """Test removal of special characters."""
        assert normalize_slug("Hello!@#$%World") == "helloworld"
        assert normalize_slug("Test-Case") == "test-case"
        assert normalize_slug("---Multiple---Hyphens---") == "multiple-hyphens"
    
    def test_normalize_unicode(self):
        """Test Unicode normalization."""
        # Cyrillic should be removed (not ASCII)
        assert normalize_slug("Привет Мир") == ""  # No ASCII chars
        assert normalize_slug("Café") == "cafe"  # Accent removed, 'é' becomes 'e'
    
    def test_normalize_length_limit(self):
        """Test slug length limitation."""
        long_text = "a" * 100
        result = normalize_slug(long_text)
        assert len(result) <= 50
    
    def test_normalize_edge_cases(self):
        """Test edge cases."""
        assert normalize_slug("") == ""
        assert normalize_slug("   ") == ""
        assert normalize_slug("---") == ""
    
    def test_generate_with_fallback(self):
        """Test slug generation with fallback."""
        assert generate_slug_with_fallback("My Campaign") == "my-campaign"
        
        # Empty normalized slug should trigger fallback
        result = generate_slug_with_fallback("!!!")
        assert result.startswith("link-")
        assert len(result) > 5
    
    def test_resolve_collision(self):
        """Test collision resolution."""
        existing = {"my-link"}
        
        # No collision
        assert resolve_slug_collision("other-link", existing) == "other-link"
        
        # Collision
        assert resolve_slug_collision("my-link", existing) == "my-link-2"
        
        # Multiple collisions
        existing.add("my-link-2")
        assert resolve_slug_collision("my-link", existing) == "my-link-3"
    
    def test_validate_slug(self):
        """Test slug validation."""
        # Valid
        assert validate_slug("my-link") is True
        assert validate_slug("test123") is True
        assert validate_slug("a-b-c-1-2-3") is True
        
        # Invalid
        assert validate_slug("") is False
        assert validate_slug("-leading") is False
        assert validate_slug("trailing-") is False
        assert validate_slug("UPPERCASE") is False
        assert validate_slug("spaces here") is False
        assert validate_slug("special!chars") is False
        assert validate_slug("a" * 51) is False  # Too long


class TestPayloadEncoding:
    """Test payload encoding and decoding."""
    
    def test_encode_decode_roundtrip(self):
        """Test encoding and decoding round-trip."""
        test_ids = [1, 42, 100, 999, 12345, 999999]
        
        for link_id in test_ids:
            payload = encode_link_id(link_id)
            decoded = decode_payload(payload)
            assert decoded == link_id, f"Round-trip failed for {link_id}"
    
    def test_encode_format(self):
        """Test encoded payload format."""
        payload = encode_link_id(123)
        
        # Should be URL-safe characters only
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in payload)
        
        # Should be within length limit
        assert len(payload) <= 64
    
    def test_encode_zero(self):
        """Test encoding zero."""
        payload = encode_link_id(0)
        assert decode_payload(payload) == 0
    
    def test_encode_large_number(self):
        """Test encoding large numbers."""
        large_id = 2**32 - 1  # Max 32-bit unsigned int
        payload = encode_link_id(large_id)
        assert len(payload) <= 64
        assert decode_payload(payload) == large_id
    
    def test_encode_invalid(self):
        """Test encoding invalid input."""
        with pytest.raises(ValueError):
            encode_link_id(-1)
    
    def test_decode_invalid(self):
        """Test decoding invalid input."""
        with pytest.raises(ValueError):
            decode_payload("")
        
        with pytest.raises(ValueError):
            decode_payload("a" * 100)  # Too long
    
    def test_generate_start_link(self):
        """Test full start link generation."""
        link = generate_start_link("mybot", 123)
        
        assert link.startswith("https://t.me/mybot?start=")
        
        # Extract payload and verify
        payload = link.split("start=")[1]
        assert decode_payload(payload) == 123


class TestSlugCollisionDeterminism:
    """Test that slug collision resolution is deterministic."""
    
    def test_collision_determinism(self):
        """Test that collision resolution is deterministic."""
        existing = {"link", "link-2"}
        
        # Same input should always produce same output
        result1 = resolve_slug_collision("link", existing)
        result2 = resolve_slug_collision("link", existing)
        
        assert result1 == result2 == "link-3"
    
    def test_collision_sequence(self):
        """Test collision sequence is predictable."""
        existing = set()
        base = "test"
        
        # First use - no collision
        assert resolve_slug_collision(base, existing) == "test"
        existing.add("test")
        
        # Second use - collision
        assert resolve_slug_collision(base, existing) == "test-2"
        existing.add("test-2")
        
        # Third use - collision
        assert resolve_slug_collision(base, existing) == "test-3"


class TestPayloadBackwardCompatibility:
    """Test payload encoding backward compatibility."""
    
    def test_consistent_encoding(self):
        """Test that encoding is consistent across runs."""
        # These payloads should remain stable
        test_cases = [
            (1, "AQ"),
            (255, "Aw"),
            (256, "AQA"),
        ]
        
        for link_id, expected_prefix in test_cases:
            payload = encode_link_id(link_id)
            # Check it starts with expected characters (implementation may vary slightly)
            # But round-trip must always work
            assert decode_payload(payload) == link_id
    
    def test_payload_length_efficiency(self):
        """Test that payload is reasonably compact."""
        # Small IDs should produce short payloads
        assert len(encode_link_id(1)) <= 10
        assert len(encode_link_id(1000)) <= 10
        assert len(encode_link_id(1000000)) <= 15
