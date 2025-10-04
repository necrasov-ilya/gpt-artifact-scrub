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

    async def record_times(user: User, count: int) -> None:
        for _ in range(count):
            await service.record_event(user)

    users = [
        User(id=1, is_bot=False, first_name="Alex", username="alex"),
        User(id=2, is_bot=False, first_name="Bea"),
        User(id=3, is_bot=False, first_name="Chris", username="chris"),
        User(id=4, is_bot=False, first_name="Dana", username="dana"),
    ]

    await asyncio.gather(
        record_times(users[0], 5),
        record_times(users[1], 2),
        record_times(users[2], 3),
        record_times(users[3], 4),
    )

    page1 = await service.get_page(1)
    assert page1.total_users == 4
    assert page1.total_events == 14
    assert [entry.total_count for entry in page1.entries] == [5, 4, 3]
    assert page1.page == 1
    assert page1.pages == 2

    page2 = await service.get_page(2)
    assert page2.page == 2
    assert [entry.total_count for entry in page2.entries] == [2]
    assert page2.entries[0].label.startswith("Bea") or page2.entries[0].label.startswith("ID")

    # Requesting out-of-range page returns the last page
    page3 = await service.get_page(99)
    assert page3.page == 2
    assert [entry.total_count for entry in page3.entries] == [2]
