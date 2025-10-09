from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import Message

from ...modules.text.services.normalization import TextNormalizationService
from ...modules.text.utils.stats import format_stats
from ...modules.shared.services.anti_spam import AntiSpamGuard
from ...modules.shared.services.usage_stats import UsageStatsService


def create_text_router(
    service: TextNormalizationService,
    guard: AntiSpamGuard,
    usage_stats: UsageStatsService,
) -> Router:
    router = Router(name="text_handler")

    @router.message(F.text & ~F.via_bot & ~F.text.startswith("/"))
    async def handle_text(message: Message) -> None:
        assert message.text is not None
        user_id = message.from_user.id if message.from_user else message.chat.id
        if not await guard.try_acquire(user_id):
            await message.answer("Не так быстро, пожалуйста. Дайте боту чуть-чуть времени.")
            return

        try:
            result = await service.process(message.text)
            formatted = f"<pre><code>{escape(result.edited_text)}</code></pre>"
            await message.answer(formatted, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            stats_text = format_stats(result.stats)
            await message.answer(f"🧹 {stats_text}")
            await usage_stats.record_event(message.from_user, is_message=True)
        finally:
            await guard.release(user_id)

    return router
