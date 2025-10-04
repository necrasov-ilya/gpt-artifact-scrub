from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import Message

from ...modules.text.services.normalization import TextNormalizationService
from ...modules.text.utils.stats import format_stats


def create_text_router(service: TextNormalizationService) -> Router:
    router = Router(name="text_handler")

    @router.message(F.text & ~F.via_bot & ~F.text.startswith("/"))
    async def handle_text(message: Message) -> None:
        assert message.text is not None
        result = await service.process(message.text)
        formatted = f"<pre><code>{escape(result.edited_text)}</code></pre>"
        await message.answer(formatted, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        summary = f"🧹 {result.summary}\n{format_stats(result.stats)}"
        await message.answer(summary)

    return router
