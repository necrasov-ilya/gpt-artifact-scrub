from __future__ import annotations

from ..domain.models import EmojiGridOption, UserSettings
from ..infrastructure.storage import Storage


class UserSettingsService:
    def __init__(
        self,
        storage: Storage,
        *,
        default_grid: EmojiGridOption,
        default_padding: int,
        grid_limit: int,
    ) -> None:
        self._storage = storage
        self._default_grid = default_grid
        self._default_padding = default_padding
        self._grid_limit = grid_limit

    async def get(self, user_id: int) -> UserSettings:
        stored = await self._storage.get_user_settings(user_id)
        if stored:
            if stored.default_grid.tiles <= self._grid_limit:
                return stored
            sanitized = UserSettings(
                user_id=user_id,
                default_grid=self._ensure_default_grid(),
                default_padding=stored.default_padding,
            )
            await self._storage.upsert_user_settings(sanitized)
            return sanitized
        return UserSettings(user_id=user_id, default_grid=self._ensure_default_grid(), default_padding=self._default_padding)

    async def update(self, user_id: int, grid: EmojiGridOption, padding: int) -> UserSettings:
        if grid.tiles > self._grid_limit:
            raise ValueError("grid_limit_exceeded")
        new_settings = UserSettings(user_id=user_id, default_grid=grid, default_padding=padding)
        await self._storage.upsert_user_settings(new_settings)
        return new_settings

    def _ensure_default_grid(self) -> EmojiGridOption:
        if self._default_grid.tiles <= self._grid_limit:
            return self._default_grid
        return EmojiGridOption(rows=1, cols=1)

    @property
    def grid_limit(self) -> int:
        return self._grid_limit
