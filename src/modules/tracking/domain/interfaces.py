"""
Domain interfaces for tracking module.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from src.modules.tracking.domain.models import TrackingLink, TrackingEvent, LinkStats


class TrackingRepository(ABC):
    """Repository interface for tracking data persistence."""
    
    @abstractmethod
    async def create_link(self, tag: str, slug: str) -> TrackingLink:
        """
        Create a new tracking link.
        
        Args:
            tag: Human-readable label
            slug: URL-safe identifier
            
        Returns:
            Created tracking link
        """
        pass
    
    @abstractmethod
    async def get_link_by_id(self, link_id: int, include_deleted: bool = False) -> Optional[TrackingLink]:
        """
        Get tracking link by ID.
        
        Args:
            link_id: Link identifier
            include_deleted: Whether to include soft-deleted links
            
        Returns:
            Tracking link or None if not found
        """
        pass
    
    @abstractmethod
    async def get_link_by_slug(self, slug: str, include_deleted: bool = False) -> Optional[TrackingLink]:
        """
        Get tracking link by slug.
        
        Args:
            slug: URL-safe identifier
            include_deleted: Whether to include soft-deleted links
            
        Returns:
            Tracking link or None if not found
        """
        pass
    
    @abstractmethod
    async def list_links(self, include_deleted: bool = False) -> List[TrackingLink]:
        """
        List all tracking links.
        
        Args:
            include_deleted: Whether to include soft-deleted links
            
        Returns:
            List of tracking links
        """
        pass
    
    @abstractmethod
    async def soft_delete_link(self, link_id: int) -> bool:
        """
        Soft delete a tracking link.
        
        Args:
            link_id: Link identifier
            
        Returns:
            True if deleted, False if not found or already deleted
        """
        pass
    
    @abstractmethod
    async def log_event(
        self,
        link_id: int,
        tg_user_id: int,
        event_type: str,
        first_start: bool
    ) -> TrackingEvent:
        """
        Log a tracking event.
        
        Args:
            link_id: Link identifier
            tg_user_id: Telegram user ID
            event_type: Type of event ('start' or 'visit')
            first_start: Whether this is the first start for this link+user
            
        Returns:
            Created tracking event
        """
        pass
    
    @abstractmethod
    async def has_user_started_link(self, link_id: int, tg_user_id: int) -> bool:
        """
        Check if user has already started this link.
        
        Args:
            link_id: Link identifier
            tg_user_id: Telegram user ID
            
        Returns:
            True if user has started this link before
        """
        pass
    
    @abstractmethod
    async def get_events_for_link(
        self,
        link_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[TrackingEvent]:
        """
        Get all events for a link with optional date filtering.
        
        Args:
            link_id: Link identifier
            start_date: Start date (inclusive, UTC)
            end_date: End date (inclusive, UTC)
            
        Returns:
            List of tracking events
        """
        pass
    
    @abstractmethod
    async def get_aggregated_stats(
        self,
        link_ids: Optional[List[int]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        daily: bool = False
    ) -> List[LinkStats]:
        """
        Get aggregated statistics.
        
        Args:
            link_ids: Filter by specific link IDs (None for all active links)
            start_date: Start date (inclusive, UTC)
            end_date: End date (inclusive, UTC)
            daily: Whether to aggregate by day (True) or all-time (False)
            
        Returns:
            List of aggregated statistics
        """
        pass
