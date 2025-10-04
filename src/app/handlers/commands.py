from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from ...modules.images.domain.models import EmojiGridOption
from ...modules.images.services.user_settings import UserSettingsService
from ...modules.shared.services.usage_stats import UsageStatsService

START_TEXT = (
    "🤖 Работаю с текстами и картинками. Просто отправьте — я верну готовый результат.\n\n"
    "📝 Если текст: убираю признаки ИИ — длинные тире меняю на \"-\", кавычки на \"\", списки на \"-\", удаляю артефакты от GPT вроде [cite], (turn0search1) и т.п.\n\n"
    "🖼️ Если фото: оцениваю размеры, предлагаю сетку, прошу выбрать padding (0–5 px). Тайлы конвертирую в PNG 100×100 и собираю новый кастом-пак. Для загрузки пака у вас на аккаунте должна быть подписка Telegram Premium.\n\n"
    "🔒 Ваши сообщения сохраняются в наших системах для последующего анализа, направленного на повышение эффективности и качества предоставляемых услуг\n\n"
    "💬 Тех. поддержка — @mentsev"
)

HELP_TEXT = (
    "🤖 Работаю с текстами и картинками. Просто отправьте — я верну готовый результат.\n\n"
    "📝 Если текст: убираю признаки ИИ — длинные тире меняю на \"-\", кавычки на \"\", списки на \"-\", удаляю артефакты от GPT вроде [cite], (turn0search1) и т.п.\n\n"
    "🖼️ Если фото: оцениваю размеры, предлагаю сетку, прошу выбрать padding (0–5 px). Тайлы конвертирую в PNG 100×100 и собираю новый кастом-пак. Для загрузки пака у вас на аккаунте должна быть подписка Telegram Premium.\n\n"
    "🔒 Ваши сообщения сохраняются в наших системах для последующего анализа, направленного на повышение эффективности и качества предоставляемых услуг\n\n"
    "💬 Тех. поддержка — @mentsev"
)


def _get_command_args(command: CommandObject | None) -> str:
    if command is None or not command.args:
        return ""
    return command.args.strip()


def _parse_key_value_args(args: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for token in args.split():
        if "=" in token:
            key, value = token.split("=", 1)
            parts[key.lower()] = value
    return parts


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

    @router.message(Command("settings"))
    async def settings_cmd(message: Message, command: CommandObject) -> None:
        user_id = message.from_user.id
        args = _get_command_args(command)
        if not args:
            settings = await user_settings.get(user_id)
            await message.answer(
                "Текущие настройки:\n"
                f"• Сетка: {settings.default_grid.as_label()}\n"
                f"• Padding: {settings.default_padding}px\n\n"
                "Чтобы изменить: /settings grid=3x3 pad=2",
            )
            return
        parts = _parse_key_value_args(args)
        errors = []
        grid_value = parts.get("grid")
        pad_value = parts.get("pad")
        if not grid_value and not pad_value:
            errors.append("Укажите хотя бы один параметр: grid=RxC или pad=N")
        new_grid = None
        if grid_value:
            try:
                new_grid = EmojiGridOption.decode(grid_value)
                if new_grid.tiles > user_settings.grid_limit:
                    raise ValueError
            except Exception:
                errors.append(
                    f"Сетка должна быть в формате 2x2, 3x4 и т.д. и содержать не более {user_settings.grid_limit} тайлов."
                )
        padding = None
        if pad_value:
            try:
                padding_int = int(pad_value)
                if not 0 <= padding_int <= 5:
                    raise ValueError
                padding = padding_int
            except Exception:
                errors.append("Padding укажите как целое число 0–5")
        if errors:
            await message.answer("\n".join(errors))
            return
        current = await user_settings.get(user_id)
        updated_grid = new_grid or current.default_grid
        updated_padding = padding if padding is not None else current.default_padding
        try:
            await user_settings.update(user_id, updated_grid, updated_padding)
        except ValueError:
            await message.answer(
                f"Сетка с {updated_grid.tiles} тайлами превышает лимит {user_settings.grid_limit}. Выберите меньший вариант."
            )
            return
        await message.answer(
            "Готово! Настройки обновлены:\n"
            f"• Сетка: {updated_grid.as_label()}\n"
            f"• Padding: {updated_padding}px"
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

        lines = ["📊 Статистика пользователей", f"Всего: {stats_page.total_events}"]
        start_rank = (stats_page.page - 1) * usage_stats.page_size + 1
        for index, entry in enumerate(stats_page.entries, start=start_rank):
            lines.append(f"{index}. {entry.label} — {entry.total_count}")
        lines.append("")
        lines.append(f"📄 Страница {stats_page.page} из {stats_page.pages}")
        await message.answer("\n".join(lines))

    return router
