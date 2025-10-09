from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from ...modules.images.services.user_settings import UserSettingsService
from ...modules.images.utils.image import padding_level_to_pixels
from ...modules.shared.services.usage_stats import UsageStatsService

START_TEXT_TEMPLATE = (
    "🤖 Работаю с текстами и картинками. Просто отправьте — я верну готовый результат.\n\n"
    "📝 Если текст: убираю признаки ИИ — длинные тире меняю на \"-\", кавычки на \"\", списки на \"-\", удаляю артефакты от GPT вроде [cite], (turn0search1) и т.п.\n\n"
    "🖼️ Если фото: смотрю на размер изображения, предлагаю удобную сетку и нарезаю картинку. Отступы добавляю только по краям и беру из ваших настроек (по умолчанию уровень {default_padding}). Готовый пак загружаю в Telegram (нужен Premium). Изменить уровень можно командой /padding, например /padding 2 (умеренная рамка).\n\n"
    "Если просто вызвать \"/padding\" без аргументов — я покажу инструкцию и градации уровней.\n\n"
    "🔒 Ваши сообщения сохраняются в наших системах для последующего анализа, направленного на повышение эффективности и качества предоставляемых услуг\n\n"
    "💬 Тех. поддержка — @mentsev"
)

HELP_TEXT_TEMPLATE = START_TEXT_TEMPLATE


def _get_command_args(command: CommandObject | None) -> str:
    if command is None or not command.args:
        return ""
    return command.args.strip()


def _parse_key_value_args(args: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for token in args.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if key:
            parts[key] = value
    return parts


def _is_logs_admin(user_id: int | None, admins: frozenset[int]) -> bool:
    # Enforce strict whitelist: if whitelist is empty, deny everyone
    if not admins:
        return False
    if user_id is None:
        return False
    return user_id in admins


def create_commands_router(
    user_settings: UserSettingsService,
    usage_stats: UsageStatsService,
    *,
    tile_size: int,
    default_padding: int,
    admin_user_ids: set[int] | None = None,
) -> Router:
    router = Router(name="commands")
    allowed_log_admins = frozenset(admin_user_ids or set())

    @router.message(Command("start"))
    async def start(message: Message) -> None:
        # Record the start event so user appears in logs
        await usage_stats.record_event(message.from_user)
        await message.answer(START_TEXT_TEMPLATE.format(default_padding=default_padding))

    @router.message(Command("help"))
    async def help_cmd(message: Message) -> None:
        await message.answer(HELP_TEXT_TEMPLATE.format(default_padding=default_padding))

    @router.message(F.text == "ℹ️ Помощь")
    async def help_text(message: Message) -> None:
        await message.answer(HELP_TEXT_TEMPLATE.format(default_padding=default_padding))

    @router.message(Command("padding"))
    async def padding_cmd(message: Message, command: CommandObject) -> None:
        user_id = message.from_user.id
        args = _get_command_args(command)
        settings = await user_settings.get(user_id)
        current_level = settings.default_padding
        current_px = padding_level_to_pixels(current_level, tile_size)
        if not args:
            levels = []
            for level in range(0, 6):
                px = padding_level_to_pixels(level, tile_size)
                desc = (
                    "нет рамки" if level == 0 else
                    "очень тонкая" if level == 1 else
                    "умеренная" if level == 2 else
                    "заметная" if level == 3 else
                    "широкая" if level == 4 else
                    "максимальная"
                )
                levels.append(f"{level} — {desc} (~{px}px)")

            await message.answer(
                "Текущий padding:\n"
                f"• Уровень: {current_level}\n"
                f"• Отступ по краям: ≈{current_px}px\n\n"
                "Доступные уровни:\n"
                + "\n".join(levels)
                + "\n\nЧтобы изменить, укажите число 0..5: /padding 3",
            )
            return
        # Only accept a single numeric token: /padding N
        tokens = args.split()
        if len(tokens) != 1 or not tokens[0].isdigit():
            await message.answer("Используйте формат: /padding N, где N — целое число 0..5.")
            return
        new_level = int(tokens[0])
        if not 0 <= new_level <= 5:
            await message.answer("Доступны уровни от 0 до 5.")
            return
        if new_level == current_level:
            await message.answer("Padding уже установлен на этот уровень.")
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
        if not _is_logs_admin(user_id, allowed_log_admins):
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
            await message.answer(
                "Пока никто не пользовался ботом — статистика появится, когда придут первые запросы."
            )
            return

        lines = [
            "📊 Статистика пользователей",
            f"Всего пользователей: {stats_page.total_users}",
            f"Всего сообщений: {stats_page.total_events}",
        ]
        start_rank = (stats_page.page - 1) * usage_stats.page_size + 1
        for index, entry in enumerate(stats_page.entries, start=start_rank):
            msg_count = entry.message_count
            msg_text = f"{msg_count} сообщений" if msg_count != 0 else "нет сообщений"
            lines.append(f"{index}. {entry.label} — {msg_text}")
        lines.append("")
        lines.append(f"📄 Страница {stats_page.page} из {stats_page.pages}")
        await message.answer("\n".join(lines))

    return router
