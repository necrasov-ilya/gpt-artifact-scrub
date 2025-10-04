from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from ...modules.images.domain.models import EmojiGridOption
from ...modules.images.services.user_settings import UserSettingsService
from ...modules.shared.services.usage_stats import UsageStatsService

START_TEXT = (
    "Привет! Я — бот, который вычёсывает артефакты из текстов и собирает свежие кастом-эмодзи."
    "\n\nНапишите мне абзац — аккуратно расставлю тире и кавычки, уберу служебный мусор и верну чистый вариант."
    "\nПришлите картинку — подберу сетку по пропорциям, помогу с padding, нарежу PNG и загружу отдельный пак."
    "\n\nХочется деталей — загляните в /help."
)

HELP_TEXT = (
    "🧹 Текстовые сообщения\n"
    "Я выправляю типографику, вычищаю LLM-токены и присылаю короткий отчёт о том, что поменялось. Никаких фантазий — только осторожная правка.\n\n"
    "🧩 Эмодзи из изображений\n"
    "Киньте изображение — я оценю размеры, предложу несколько сеток и попрошу выбрать padding от 0 до 5 пикселей."
    " Тайлы конвертирую в аккуратные PNG 100×100 и создам новый кастом-пак. Премиум в Telegram всё ещё обязателен, зато каждый аплоад — отдельная подборка без мусора.\n\n"
    "⚙️ Настройки и сервис\n"
    "Команда /settings grid=RxC pad=N сохраняет ваш любимый пресет. Если ограничить количество плиток надо заранее, установите переменную EMOJI_GRID_TILE_CAP в .env."
    " Исходные файлы живут недолго и удаляются после обработки, а при слишком частых запросах я вежливо прошу сделать паузу. Нужна диагностика — /logs пришлёт свежие записи журнала."
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


def create_commands_router(user_settings: UserSettingsService, usage_stats: UsageStatsService) -> Router:
    router = Router(name="commands")

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
