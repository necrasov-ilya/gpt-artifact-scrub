from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter
from aiogram.types import FSInputFile, InputSticker

from ..domain.models import EmojiPackRequest, EmojiPackResult
from ..utils.retry import retry_async


@dataclass
class TelegramEmojiClient:
    bot: Bot
    bot_username: str | None
    fragment_username: str | None
    creation_limit: int
    total_limit: int

    async def _ensure_bot_username(self) -> str:
        if self.bot_username:
            return self.bot_username
        me = await self.bot.get_me()
        if not me.username:
            raise RuntimeError("Bot username is required to create sticker sets")
        self.bot_username = me.username
        return self.bot_username

    def _build_short_name(self, request: EmojiPackRequest, username: str) -> str:
        suffix = f"_by_{username}".lower()
        # Keep enough entropy while ensuring a unique set per grid/padding combination.
        base = (
            f"emoji_{request.user_id}_{request.image_hash[:4]}_"
            f"{request.grid.rows}x{request.grid.cols}_p{request.padding}"
        ).lower()
        sanitized = re.sub(r"[^a-z0-9_]", "_", base)
        max_base_len = 64 - len(suffix)
        if max_base_len <= 0:
            raise ValueError("Bot username is too long for sticker short name requirements")
        trimmed = sanitized[:max_base_len].rstrip("_") or "emoji"
        return f"{trimmed}{suffix}"

    async def _upload_tiles(self, user_id: int, paths: Sequence[str | bytes | FSInputFile]) -> list[str]:
        file_ids: list[str] = []
        for path in paths:
            async def _call() -> str:
                file = await self.bot.upload_sticker_file(
                    user_id=user_id,
                    sticker=path if isinstance(path, FSInputFile) else FSInputFile(path),
                    sticker_format="static",
                )
                return file.file_id

            file_id = await retry_async(
                _call,
                retry_exceptions=(TelegramRetryAfter, TelegramNetworkError, TelegramBadRequest),
            )
            file_ids.append(file_id)
        return file_ids

    async def create_or_extend(self, request: EmojiPackRequest, tile_paths: Sequence[FSInputFile | str]) -> EmojiPackResult:
        if len(tile_paths) > self.creation_limit:
            raise ValueError("Too many tiles requested for a single run")
        username = await self._ensure_bot_username()
        short_name = self._build_short_name(request, username)
        title = (
            f"Emoji pack {request.grid.rows}x{request.grid.cols}"
            f" (pad {request.padding}) by {request.user_id}"
        )

        fs_inputs = [p if isinstance(p, FSInputFile) else FSInputFile(p) for p in tile_paths]
        file_ids = await self._upload_tiles(request.user_id, fs_inputs)
        stickers = [InputSticker(sticker=file_id, format="static", emoji_list=["😀"]) for file_id in file_ids]

        async def _get_set():
            return await self.bot.get_sticker_set(name=short_name)

        try:
            sticker_set = await retry_async(
                _get_set,
                retry_exceptions=(TelegramRetryAfter, TelegramNetworkError, TelegramBadRequest),
            )
            existing_count = len(sticker_set.stickers)
            if existing_count + len(stickers) > self.total_limit:
                raise ValueError("Sticker set limit exceeded")
            for sticker in stickers:
                await retry_async(
                    lambda: self.bot.add_sticker_to_set(
                        user_id=request.user_id,
                        name=short_name,
                        sticker=sticker,
                    ),
                    retry_exceptions=(TelegramRetryAfter, TelegramNetworkError, TelegramBadRequest),
                )
            sticker_set = await retry_async(
                _get_set,
                retry_exceptions=(TelegramRetryAfter, TelegramNetworkError, TelegramBadRequest),
            )
        except TelegramBadRequest as exc:
            message = (exc.message or "").upper()
            if "STICKER_SET_INVALID" not in message and "STICKERSET_INVALID" not in message:
                raise
            await retry_async(
                lambda: self.bot.create_new_sticker_set(
                    user_id=request.user_id,
                    name=short_name,
                    title=title,
                    stickers=stickers,
                    sticker_type="custom_emoji",
                    needs_repainting=False,
                ),
                retry_exceptions=(TelegramRetryAfter, TelegramNetworkError, TelegramBadRequest),
            )
            sticker_set = await retry_async(
                _get_set,
                retry_exceptions=(TelegramRetryAfter, TelegramNetworkError, TelegramBadRequest),
            )

        custom_ids = [sticker.custom_emoji_id for sticker in sticker_set.stickers if sticker.custom_emoji_id]
        new_ids = custom_ids[-len(file_ids):] if len(custom_ids) >= len(file_ids) else custom_ids
        fragment_preview_id = new_ids[0] if self.fragment_username and new_ids else None
        link = f"https://t.me/addemoji/{short_name}"
        return EmojiPackResult(
            short_name=short_name,
            link=link,
            custom_emoji_ids=new_ids,
            fragment_preview_id=fragment_preview_id,
        )
