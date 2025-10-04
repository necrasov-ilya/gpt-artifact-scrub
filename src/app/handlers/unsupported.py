from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message


def create_unsupported_router() -> Router:
    router = Router(name="unsupported")

    @router.message(~F.via_bot)
    async def handle_unknown(message: Message) -> None:
        if message.text and not message.text.startswith("/"):
            return
        if message.photo:
            return
        document = message.document
        if document and (document.mime_type or "").startswith("image/"):
            return
        if message.animation or message.video or message.audio or message.voice or message.video_note:
            await message.answer("Пока я не умею обрабатывать это :(")
            return
        if document:
            await message.answer("Пока я не умею обрабатывать это :(")
            return
        if message.sticker or message.poll or message.dice or message.game:
            await message.answer("Пока я не умею обрабатывать это :(")
            return
        if message.location or message.contact or message.invoice or message.successful_payment:
            await message.answer("Пока я не умею обрабатывать это :(")
            return
        # Fallback for any other content types not explicitly supported
        if message.content_type not in {"text", "photo"}:
            await message.answer("Пока я не умею обрабатывать это :(")

    return router
