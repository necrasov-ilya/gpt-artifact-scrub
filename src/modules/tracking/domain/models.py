"""
Domain models for tracking module.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class TrackingLink:
    link_id: int
    tag: str
    slug: str
    created_at: datetime
    deleted_at: Optional[datetime] = None
    
    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


@dataclass(frozen=True)
class TrackingEvent:
    event_id: int
    link_id: int
    tg_user_id: int
    event_type: str
    first_start: bool
    created_at: datetime


@dataclass(frozen=True)
class LinkStats:
    link_id: int
    tag: str
    slug: str
    date: Optional[datetime]
    total_events: int
    unique_users: int
    first_starts: int
