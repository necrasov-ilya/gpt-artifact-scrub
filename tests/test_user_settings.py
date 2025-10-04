from __future__ import annotations

import pytest

from pathlib import Path

from src.modules.images.domain.models import EmojiGridOption, UserSettings
from src.modules.images.infrastructure.storage import Storage
from src.modules.images.services.user_settings import UserSettingsService


@pytest.mark.asyncio
async def test_update_rejects_grid_above_limit(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "state.db")
    await storage.initialize()
    service = UserSettingsService(
        storage,
        default_grid=EmojiGridOption(rows=2, cols=2),
        default_padding=2,
        grid_limit=4,
    )

    with pytest.raises(ValueError):
        await service.update(1, EmojiGridOption(rows=3, cols=2), 1)


@pytest.mark.asyncio
async def test_get_sanitizes_stored_grid_above_limit(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "state.db")
    await storage.initialize()
    default_grid = EmojiGridOption(rows=2, cols=2)
    service = UserSettingsService(
        storage,
        default_grid=default_grid,
        default_padding=2,
        grid_limit=4,
    )

    invalid = UserSettings(user_id=1, default_grid=EmojiGridOption(rows=3, cols=3), default_padding=2)
    await storage.upsert_user_settings(invalid)

    sanitized = await service.get(1)
    assert sanitized.default_grid == default_grid
