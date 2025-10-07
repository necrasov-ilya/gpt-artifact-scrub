from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from ...modules.images.services.user_settings import UserSettingsService
from ...modules.shared.services.usage_stats import UsageStatsService
from ...modules.images.utils.image import padding_level_to_pixels

START_TEXT = (
    "🤖 Работаю с текстами и картинками. Просто отправьте — я верну готовый результат.\n\n"
    "📝 Если текст: убираю признаки ИИ — длинные тире меняю на \"-\", кавычки на \"\", списки на \"-\", удаляю артефакты от GPT вроде [cite], (turn0search1) и т.п.\n\n"
    "🖼️ Если фото: смотрю на размер изображения, предлагаю удобную сетку и нарезаю картинку. Отступы добавляю только по краям и беру их из ваших настроек (по умолчанию уровень 2 — умеренная рамка). Готовый пак загружаю в Telegram (нужен Premium). Уровень отступа можно изменить командой /padding — например, /padding 0.\n\n"
    "🔒 Ваши сообщения сохраняются в наших системах для последующего анализа, направленного на повышение эффективности и качества предоставляемых услуг\n\n"
    "💬 Тех. поддержка — @mentsev"
)

HELP_TEXT = (
    "🤖 Работаю с текстами и картинками. Просто отправьте — я верну готовый результат.\n\n"
    "📝 Если текст: убираю признаки ИИ — длинные тире меняю на \"-\", кавычки на \"\", списки на \"-\", удаляю артефакты от GPT вроде [cite], (turn0search1) и т.п.\n\n"
    "🖼️ Если фото: смотрю на размер изображения, предлагаю удобную сетку и нарезаю картинку. Отступы добавляю только по краям и беру их из ваших настроек (по умолчанию уровень 2 — умеренная рамка). Готовый пак загружаю в Telegram (нужен Premium). Уровень отступа можно изменить командой /padding — например, /padding 0.\n\n"
    "🔒 Ваши сообщения сохраняются в наших системах для последующего анализа, направленного на повышение эффективности и качества предоставляемых услуг\n\n"
    "💬 Тех. поддержка — @mentsev"
)


def _get_command_args(command: CommandObject | None) -> str:
    if command is None or not command.args:
        return ""
    return command.args.strip()


def _is_logs_whitelisted(user_id: int | None, whitelist: frozenset[int]) -> bool:
    # Enforce strict whitelist: if whitelist is empty, deny everyone
    if not whitelist:
        return False
    if user_id is None:
        return False
    return user_id in whitelist


def create_commands_router(
    user_settings: UserSettingsService,
    usage_stats: UsageStatsService,
    *,
    tile_size: int,
    logs_whitelist_ids: set[int] | None = None,
) -> Router:
    router = Router(name="commands")
    allowed_logs_users = frozenset(logs_whitelist_ids or set())

    @router.message(Command("start"))
    async def start(message: Message) -> None:
        await message.answer(START_TEXT)

    @router.message(Command("help"))
    async def help_cmd(message: Message) -> None:
        await message.answer(HELP_TEXT)

    @router.message(F.text == "ℹ️ Помощь")
    async def help_text(message: Message) -> None:
        await message.answer(HELP_TEXT)

    @router.message(Command("padding"))
    async def padding_cmd(message: Message, command: CommandObject) -> None:
        user_id = message.from_user.id
        args = _get_command_args(command)
        settings = await user_settings.get(user_id)
        current_level = settings.default_padding
        current_px = padding_level_to_pixels(current_level, tile_size)
        if not args:
            await message.answer(
                "Текущий padding:\n"
                f"• Уровень: {current_level}\n"
                f"• Отступ по краям: ≈{current_px}px\n\n"
                "Чтобы изменить, укажите целое число 0–5: /padding 3",
            )
            return
        try:
            new_level = int(args.split()[0])
        except ValueError:
            await message.answer("Передайте число от 0 до 5: /padding 2")
            return
        if not 0 <= new_level <= 5:
            await message.answer("Выберите целое число от 0 до 5.")
            return
        if new_level == current_level:
            await message.answer("Padding уже установлен на это значение.")
            return
        await user_settings.update(user_id, settings.default_grid, new_level)
        new_px = padding_level_to_pixels(new_level, tile_size)
        await message.answer(
            "Готово! Padding обновлён:\n"
            f"• Уровень: {new_level}\n"
            f"• Отступ по краям: ≈{new_px}px"
        )

    @router.message(Command("logs"))
    async def logs_cmd(message: Message, command: CommandObject) -> None:
        user_id = message.from_user.id if message.from_user else None
        # If user is not whitelisted, do nothing (remain silent)
        if not _is_logs_whitelisted(user_id, allowed_logs_users):
            return

        args = _get_command_args(command)
        page = 1
        if args:
            try:
                page = max(1, int(args.split()[0]))
            except ValueError:
                await message.answer("Укажите номер страницы: /logs 2")
                return

        stats_page = await usage_stats.get_page(page)
        if stats_page.total_users == 0:
            await message.answer("Пока никто не пользовался ботом — статистика появится, когда придут первые запросы.")
            return

        lines = ["📊 Статистика пользователей", f"Всего пользователей: {stats_page.total_users}"]
        start_rank = (stats_page.page - 1) * usage_stats.page_size + 1
        for index, entry in enumerate(stats_page.entries, start=start_rank):
            lines.append(f"{index}. {entry.label} — {entry.total_count}")
        lines.append("")
        lines.append(f"📄 Страница {stats_page.page} из {stats_page.pages}")
        await message.answer("\n".join(lines))

    return router
