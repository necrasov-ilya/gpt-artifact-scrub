from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

import aiofiles

from ..domain.models import EmojiJobOutcome, EmojiPackRequest
from ..infrastructure.storage import Storage
from ..infrastructure.telegram_emoji import TelegramEmojiClient
from ..utils.image import slice_into_tiles

logger = logging.getLogger(__name__)


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
        async with aiofiles.open(request.file_path, "rb") as f:
            data = await f.read()

        job_dir = request.file_path.parent
        prefix = request.file_path.stem
        tiles = slice_into_tiles(
            image_bytes=data,
            grid=request.grid,
            padding=request.padding,
            tile_size=self._tile_size,
            temp_dir=job_dir,
            prefix=prefix,
        )

        try:
            result = await self._telegram.create_or_extend(request, tiles)
        finally:
            # Cleanup tile files
            for path in tiles:
                try:
                    path.unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("Failed to delete tile %s: %s", path, exc)
            
            # Cleanup source file
            try:
                request.file_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Failed to delete source file %s: %s", request.file_path, exc)
            
            # Cleanup job directory
            if job_dir != self._temp_dir:
                try:
                    await asyncio.to_thread(shutil.rmtree, job_dir, ignore_errors=True)
                except OSError as exc:
                    logger.warning("Failed to delete job directory %s: %s", job_dir, exc)

        outcome = EmojiJobOutcome(request=request, result=result)
        await self._storage.save_job_outcome(outcome)
        return outcome
