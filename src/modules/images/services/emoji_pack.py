from __future__ import annotations

import asyncio
from pathlib import Path

import aiofiles

from ..domain.models import EmojiJobOutcome, EmojiPackRequest
from ..infrastructure.storage import Storage
from ..infrastructure.telegram_emoji import TelegramEmojiClient
from ..utils.image import slice_into_tiles


class EmojiPackService:
    def __init__(
        self,
        storage: Storage,
        telegram_client: TelegramEmojiClient,
        *,
        temp_dir: Path,
        tile_size: int,
    ) -> None:
        self._storage = storage
        self._telegram = telegram_client
        self._temp_dir = temp_dir
        self._tile_size = tile_size

    async def process(self, request: EmojiPackRequest) -> EmojiJobOutcome:
        cached = await self._storage.get_cached_job(request)
        if cached:
            return cached

        async with aiofiles.open(request.file_path, "rb") as f:
            data = await f.read()

        prefix = f"emoji_{request.user_id}_{request.image_hash[:6]}"
        tiles = slice_into_tiles(
            image_bytes=data,
            grid=request.grid,
            padding=request.padding,
            tile_size=self._tile_size,
            temp_dir=self._temp_dir,
            prefix=prefix,
        )

        try:
            result = await self._telegram.create_or_extend(request, tiles)
        finally:
            for path in tiles:
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
            try:
                request.file_path.unlink(missing_ok=True)
            except Exception:
                pass

        outcome = EmojiJobOutcome(request=request, result=result)
        await self._storage.save_job_outcome(outcome)
        return outcome
