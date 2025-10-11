"""
Payload encoding/decoding for tracking links.

Uses base64url encoding for compact, URL-safe payloads that can be
reversibly decoded to extract link_id. Each encoding includes random
salt to prevent Telegram from caching deep links.
"""
import base64
import secrets
import time


MAX_PAYLOAD_LENGTH = 64
SALT_BYTES = 4  # Random salt to make each link unique


def encode_link_id(link_id: int) -> str:
    """
    Encode link_id into a compact URL-safe payload with random salt.
    
    Format: salt (4 bytes) + timestamp (4 bytes) + link_id (variable bytes)
    This ensures each generated link is unique, preventing Telegram caching.
    
    Uses base64url encoding (RFC 4648) for compact representation.
    The payload is URL-safe and contains only [A-Za-z0-9_-] characters.
    
    Args:
        link_id: Integer link identifier
        
    Returns:
        Encoded payload string (≤64 characters)
        
    Raises:
        ValueError: If link_id is negative or results in payload > 64 chars
        
    Examples:
        >>> payload1 = encode_link_id(1)
        >>> payload2 = encode_link_id(1)
        >>> payload1 != payload2  # Always different due to random salt
        True
    """
    if link_id < 0:
        raise ValueError("link_id must be non-negative")
    
    # Generate random salt (4 bytes)
    salt = secrets.token_bytes(SALT_BYTES)
    
    # Add timestamp (4 bytes) for additional uniqueness
    timestamp = int(time.time()) & 0xFFFFFFFF  # 32-bit timestamp
    timestamp_bytes = timestamp.to_bytes(4, byteorder='big')
    
    # Encode link_id
    if link_id == 0:
        link_bytes = b'\x00'
    else:
        byte_length = (link_id.bit_length() + 7) // 8
        link_bytes = link_id.to_bytes(byte_length, byteorder='big')
    
    # Combine: salt + timestamp + link_id
    combined = salt + timestamp_bytes + link_bytes
    
    encoded = base64.urlsafe_b64encode(combined).rstrip(b'=').decode('ascii')
    
    if len(encoded) > MAX_PAYLOAD_LENGTH:
        raise ValueError(f"Encoded payload exceeds {MAX_PAYLOAD_LENGTH} characters")
    
    return encoded


def decode_payload(payload: str) -> int:
    """
    Decode payload back to link_id.
    
    Extracts link_id from payload format: salt + timestamp + link_id.
    Reverses the encode_link_id operation, ignoring salt and timestamp.
    
    Args:
        payload: Encoded payload string
        
    Returns:
        Original link_id
        
    Raises:
        ValueError: If payload is invalid or cannot be decoded
        
    Examples:
        >>> payload = encode_link_id(12345)
        >>> decode_payload(payload)
        12345
    """
    if not payload:
        raise ValueError("Payload cannot be empty")
    
    if len(payload) > MAX_PAYLOAD_LENGTH:
        raise ValueError(f"Payload exceeds {MAX_PAYLOAD_LENGTH} characters")
    
    try:
        padding = (4 - len(payload) % 4) % 4
        padded = payload + '=' * padding
        combined_bytes = base64.urlsafe_b64decode(padded.encode('ascii'))
        
        # Skip salt (4 bytes) and timestamp (4 bytes)
        if len(combined_bytes) < SALT_BYTES + 4:
            raise ValueError("Payload too short")
        
        link_bytes = combined_bytes[SALT_BYTES + 4:]
        link_id = int.from_bytes(link_bytes, byteorder='big')
        return link_id
        
    except Exception as e:
        raise ValueError(f"Invalid payload format: {e}") from e


def generate_start_link(bot_username: str, link_id: int) -> str:
    """
    Generate complete Telegram start link.
    
    Format: https://t.me/<bot_username>?start=<payload>
    
    Args:
        bot_username: Telegram bot username (without @)
        link_id: Link identifier to encode
        
    Returns:
        Complete tracking link URL
        
    Examples:
        >>> generate_start_link("mybot", 123)
        'https://t.me/mybot?start=...'
    """
    payload = encode_link_id(link_id)
    return f"https://t.me/{bot_username}?start={payload}"
