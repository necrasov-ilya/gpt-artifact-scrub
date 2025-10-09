from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from aiogram.types import User

from src.modules.images.infrastructure.storage import Storage
from src.modules.shared.services.usage_stats import UsageStatsService


@pytest.mark.asyncio
async def test_usage_stats_records_and_pages(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "state.db")
    await storage.initialize()
    service = UsageStatsService(storage, page_size=3)

    async def record_times(user: User, count: int, is_message: bool = True) -> None:
        for _ in range(count):
            await service.record_event(user, is_message=is_message)

    users = [
        User(id=1, is_bot=False, first_name="Alex", username="alex"),
        User(id=2, is_bot=False, first_name="Bea"),
        User(id=3, is_bot=False, first_name="Chris", username="chris"),
        User(id=4, is_bot=False, first_name="Dana", username="dana"),
    ]

    # Alex: 5 messages, Bea: 1 command + 1 message, Chris: 3 messages, Dana: 4 messages
    await asyncio.gather(
        record_times(users[0], 5, is_message=True),
        record_times(users[1], 1, is_message=False),  # Just /start command
        record_times(users[1], 1, is_message=True),   # Then 1 actual message
        record_times(users[2], 3, is_message=True),
        record_times(users[3], 4, is_message=True),
    )

    page1 = await service.get_page(1)
    assert page1.total_users == 4
    assert page1.total_events == 14  # 5+2+3+4 total events
    # Check message counts: Alex=5, Dana=4, Chris=3
    assert [entry.message_count for entry in page1.entries] == [5, 4, 3]
    assert page1.page == 1
    assert page1.pages == 2

    page2 = await service.get_page(2)
    assert page2.page == 2
    assert page2.entries[0].message_count == 1  # Bea has 1 message
    assert page2.entries[0].label.startswith("Bea") or page2.entries[0].label.startswith("ID")

    # Requesting out-of-range page returns the last page
    page3 = await service.get_page(99)
    assert page3.page == 2
    assert [entry.total_count for entry in page3.entries] == [2]
