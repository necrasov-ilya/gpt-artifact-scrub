"""
Tracking service for link creation and event logging.
"""
from typing import List, Optional

from src.modules.shared.services.bot_info import BotInfoService
from src.modules.tracking.domain.interfaces import TrackingRepository
from src.modules.tracking.domain.models import TrackingLink, TrackingEvent
from src.modules.tracking.utils.slug_generator import (
    generate_slug_with_fallback,
    resolve_slug_collision,
    validate_slug,
)
from src.modules.tracking.utils.payload_encoder import encode_link_id


class TrackingService:
    """Service for managing tracking links and events."""
    
    def __init__(self, repository: TrackingRepository, bot_info: BotInfoService):
        self._repository = repository
        self._bot_info = bot_info
    
    async def create_tracking_link(
        self,
        tag: str,
        slug: Optional[str] = None
    ) -> tuple[TrackingLink, str]:
        """
        Create a new tracking link.
        
        Args:
            tag: Human-readable label (required)
            slug: Custom slug (optional, will be auto-generated if not provided)
        
        Returns:
            Tuple of (TrackingLink, full_url)
        
        Raises:
            ValueError: If slug is invalid or tag is empty
        """
        if not tag or not tag.strip():
            raise ValueError("Tag is required and cannot be empty")
        
        tag = tag.strip()
        
        if slug:
            slug = slug.strip()
            if not validate_slug(slug):
                raise ValueError(
                    f"Invalid slug: must be lowercase letters, digits, and hyphens only, "
                    f"no leading/trailing hyphens, max 50 characters"
                )
        else:
            slug = generate_slug_with_fallback(tag)
        
        existing_slugs = await self._get_all_active_slugs()
        if slug in existing_slugs:
            slug = resolve_slug_collision(slug, existing_slugs)
        
        link = await self._repository.create_link(tag, slug)
        
        payload = encode_link_id(link.link_id)
        url = await self._bot_info.get_start_link(payload)
        
        return link, url
    
    async def handle_start(
        self,
        payload: str,
        tg_user_id: int
    ) -> Optional[tuple[TrackingLink, bool]]:
        """
        Handle /start command with tracking payload.
        
        Args:
            payload: Encoded payload from /start parameter
            tg_user_id: Telegram user ID
        
        Returns:
            Tuple of (TrackingLink, is_first_start) or None if invalid payload
        """
        from src.modules.tracking.utils.payload_encoder import decode_payload
        
        try:
            link_id = decode_payload(payload)
        except ValueError:
            return None
        
        link = await self._repository.get_link_by_id(link_id, include_deleted=False)
        if not link:
            return None
        
        has_started = await self._repository.has_user_started_link(link_id, tg_user_id)
        is_first_start = not has_started
        
        await self._repository.log_event(
            link_id=link_id,
            tg_user_id=tg_user_id,
            event_type='start',
            first_start=is_first_start
        )
        
        return link, is_first_start
    
    async def log_visit(
        self,
        link_id: int,
        tg_user_id: int
    ) -> TrackingEvent:
        """
        Log a visit event (when user clicks the button).
        
        Args:
            link_id: Link identifier
            tg_user_id: Telegram user ID
        
        Returns:
            Created tracking event
        """
        return await self._repository.log_event(
            link_id=link_id,
            tg_user_id=tg_user_id,
            event_type='visit',
            first_start=False
        )
    
    async def get_link_by_id(self, link_id: int) -> Optional[TrackingLink]:
        """Get active tracking link by ID."""
        return await self._repository.get_link_by_id(link_id, include_deleted=False)
    
    async def get_link_by_slug(self, slug: str) -> Optional[TrackingLink]:
        """Get active tracking link by slug."""
        return await self._repository.get_link_by_slug(slug, include_deleted=False)
    
    async def list_links(self, include_deleted: bool = False) -> List[TrackingLink]:
        """List tracking links."""
        return await self._repository.list_links(include_deleted=include_deleted)
    
    async def delete_link(self, link_id: int) -> bool:
        """
        Soft delete a tracking link.
        
        Args:
            link_id: Link identifier
        
        Returns:
            True if deleted, False if not found or already deleted
        """
        return await self._repository.soft_delete_link(link_id)
    
    async def generate_start_link(self, link_id: int) -> str:
        """
        Generate tracking URL for a link.
        
        Args:
            link_id: Link identifier
        
        Returns:
            Full tracking URL
        """
        payload = encode_link_id(link_id)
        return await self._bot_info.get_start_link(payload)
    
    async def _get_all_active_slugs(self) -> set[str]:
        """Get set of all active (non-deleted) slugs."""
        links = await self._repository.list_links(include_deleted=False)
        return {link.slug for link in links}
