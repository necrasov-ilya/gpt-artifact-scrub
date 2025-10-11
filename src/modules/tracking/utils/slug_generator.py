"""
Slug generation utilities with normalization and collision resolution.
"""
import hashlib
import re
import unicodedata
from typing import Optional


MAX_SLUG_LENGTH = 50
SLUG_PATTERN = re.compile(r'^[a-z0-9-]+$')


def normalize_slug(text: str) -> str:
    """
    Normalize text to create a valid slug.
    
    Rules:
    - Convert to lowercase
    - Remove accents and normalize Unicode
    - Replace spaces and underscores with hyphens
    - Remove invalid characters (only [a-z0-9-] allowed)
    - Collapse multiple hyphens
    - Strip leading/trailing hyphens
    - Limit to MAX_SLUG_LENGTH characters
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized slug string
        
    Examples:
        >>> normalize_slug("Hello World!")
        'hello-world'
        >>> normalize_slug("Привет_мир 123")
        'privet-mir-123'
        >>> normalize_slug("Multiple---Hyphens")
        'multiple-hyphens'
    """
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = text.lower()
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'[^a-z0-9-]', '', text)
    text = re.sub(r'-+', '-', text)
    text = text.strip('-')
    text = text[:MAX_SLUG_LENGTH]
    text = text.rstrip('-')
    return text


def generate_slug_with_fallback(tag: str, fallback_prefix: str = "link") -> str:
    """
    Generate slug from tag with automatic fallback.
    
    If normalized tag is empty or invalid, generates a fallback slug
    using the provided prefix.
    
    Args:
        tag: Human-readable tag
        fallback_prefix: Prefix for auto-generated fallback (default: "link")
        
    Returns:
        Valid slug string
        
    Examples:
        >>> generate_slug_with_fallback("My Campaign")
        'my-campaign'
        >>> generate_slug_with_fallback("!!!")
        'link-...'  # fallback with hash
    """
    slug = normalize_slug(tag)
    
    if not slug:
        tag_hash = hashlib.md5(tag.encode('utf-8')).hexdigest()[:8]
        slug = f"{fallback_prefix}-{tag_hash}"
    
    return slug


def resolve_slug_collision(base_slug: str, existing_slugs: set[str]) -> str:
    """
    Resolve slug collision by appending numeric suffix.
    
    Uses deterministic numeric suffix to ensure uniqueness.
    Format: base-slug-2, base-slug-3, etc.
    
    Args:
        base_slug: Base slug that has collision
        existing_slugs: Set of existing slugs to check against
        
    Returns:
        Unique slug with numeric suffix
        
    Examples:
        >>> resolve_slug_collision("my-link", {"my-link"})
        'my-link-2'
        >>> resolve_slug_collision("my-link", {"my-link", "my-link-2"})
        'my-link-3'
    """
    if base_slug not in existing_slugs:
        return base_slug
    
    counter = 2
    while True:
        candidate = f"{base_slug}-{counter}"
        if candidate not in existing_slugs:
            return candidate
        counter += 1


def validate_slug(slug: str) -> bool:
    """
    Validate if slug meets requirements.
    
    Requirements:
    - Only lowercase letters, digits, and hyphens
    - Length between 1 and MAX_SLUG_LENGTH
    - No leading/trailing hyphens
    
    Args:
        slug: Slug to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not slug or len(slug) > MAX_SLUG_LENGTH:
        return False
    
    if slug.startswith('-') or slug.endswith('-'):
        return False
    
    return bool(SLUG_PATTERN.match(slug))
