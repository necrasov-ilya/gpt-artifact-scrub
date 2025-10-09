from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from aiogram.types import User

from ...images.infrastructure.storage import Storage, UsageStatRow


@dataclass(frozen=True)
class UsageEntry:
    user_id: int
    username: str | None
    display_name: str | None
    total_count: int
    message_count: int

    @property
    def label(self) -> str:
        if self.username:
            return self.username
        if self.display_name:
            return self.display_name
        return f"ID {self.user_id}"


@dataclass(frozen=True)
class UsagePage:
    entries: list[UsageEntry]
    total_users: int
    total_events: int
    page: int
    pages: int


class UsageStatsService:
    def __init__(self, storage: Storage, page_size: int = 20) -> None:
        self._storage = storage
        self._page_size = max(1, page_size)

    @property
    def page_size(self) -> int:
        return self._page_size

    async def record_event(self, user: Optional[User], *, is_message: bool = False) -> None:
        """
        Record a user event.
        
        Args:
            user: The Telegram user
            is_message: True if this is an actual message (text/image) that was processed,
                       False if this is just a command (like /start)
        """
        if user is None:
            return
        await self._storage.increment_usage(
            user_id=user.id,
            username=user.username,
            display_name=user.full_name or user.first_name or user.last_name,
            is_message=is_message,
        )

    async def get_page(self, page: int) -> UsagePage:
        target_page = max(1, page)
        offset = (target_page - 1) * self._page_size
        rows, total_users, total_events = await self._storage.get_usage_stats(offset=offset, limit=self._page_size)
        pages = max(1, math.ceil(total_users / self._page_size)) if total_users else 1
        # Adjust page if requested page exceeds total pages
        if target_page > pages:
            target_page = pages
            offset = (target_page - 1) * self._page_size
            rows, total_users, total_events = await self._storage.get_usage_stats(offset=offset, limit=self._page_size)
        entries = [
            UsageEntry(
                user_id=row.user_id,
                username=row.username,
                display_name=row.display_name,
                total_count=row.total_count,
                message_count=row.message_count,
            )
            for row in rows
        ]
        return UsagePage(
            entries=entries,
            total_users=total_users,
            total_events=total_events,
            page=target_page,
            pages=pages,
        )
