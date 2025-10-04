from __future__ import annotations

from typing import Protocol

from .models import EmojiPackRequest, EmojiPackResult


class EmojiPackUploader(Protocol):
    async def upload_and_create(self, request: EmojiPackRequest) -> EmojiPackResult:
        """Upload emoji tiles and create or extend the user's sticker set."""


class EmojiTaskQueue(Protocol):
    async def submit(self, request: EmojiPackRequest) -> None:
        """Schedule processing of an emoji-pack request."""
