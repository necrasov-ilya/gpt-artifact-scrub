"""
Domain models for tracking module.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class TrackingLink:
    """
    Represents a tracking link with tag and metadata.
    
    Attributes:
        link_id: Unique identifier for the link
        tag: Human-readable label for reports (admin-defined)
        slug: URL-safe normalized identifier (auto-generated or admin-provided)
        created_at: UTC timestamp of creation
        deleted_at: UTC timestamp of soft deletion (None if active)
    """
    link_id: int
    tag: str
    slug: str
    created_at: datetime
    deleted_at: Optional[datetime] = None
    
    @property
    def is_deleted(self) -> bool:
        """Check if link is soft-deleted."""
        return self.deleted_at is not None


@dataclass(frozen=True)
class TrackingEvent:
    """
    Represents a tracking event (start or visit).
    
    Attributes:
        event_id: Unique identifier for the event
        link_id: Reference to the tracking link
        tg_user_id: Telegram user ID
        event_type: Type of event ('start' or 'visit')
        first_start: True if this is the first start for this link+user combination
        created_at: UTC timestamp of the event
    """
    event_id: int
    link_id: int
    tg_user_id: int
    event_type: str  # 'start' or 'visit'
    first_start: bool
    created_at: datetime


@dataclass(frozen=True)
class LinkStats:
    """
    Aggregated statistics for a tracking link.
    
    Attributes:
        link_id: Reference to the tracking link
        tag: Human-readable tag
        slug: URL-safe slug
        date: Date for daily granularity (None for all-time)
        total_events: Total number of events
        unique_users: Count of unique users
        first_starts: Count of first_start events
    """
    link_id: int
    tag: str
    slug: str
    date: Optional[datetime]  # Date for daily aggregation, None for all-time
    total_events: int
    unique_users: int
    first_starts: int
