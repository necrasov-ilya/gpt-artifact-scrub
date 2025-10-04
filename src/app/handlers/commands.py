from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ...modules.images.domain.models import EmojiGridOption
from ...modules.images.services.user_settings import UserSettingsService

START_TEXT = (
    "Привет! Я помогаю чистить тексты от LLM-артефактов и делаю кастом-эмодзи паки."
    "\n\nОтправьте текст — я нормализую его и аккуратно отредактирую."
    "\nОтправьте изображение — предложу сетку, нарежу и загружу пак custom emoji."
)

HELP_TEXT = (
    "ℹ️ Что умею:\n"
    "• Тексты: нормализация + орфография/пунктуация/стиль без искажения фактов и краткое резюме правок.\n"
    "• Изображения: анализ пропорций, выбор сетки, padding 0–5 px, нарезка 100×100 PNG, выгрузка custom emoji.\n"
    "• Настройки: /settings grid=2x2 pad=2 — сохраню сетку и padding по умолчанию.\n"
    "\nCustom emoji доступны только в Telegram Premium. Исходные изображения удаляются спустя заданный срок."
)


def create_commands_router(user_settings: UserSettingsService) -> Router:
    router = Router(name="commands")

    @router.message(Command("start"))
    async def start(message: Message) -> None:
        await message.answer(START_TEXT)

    @router.message(Command("help"))
    async def help_cmd(message: Message) -> None:
        await message.answer(HELP_TEXT)

    @router.message(Command("settings"))
    async def settings_cmd(message: Message) -> None:
        user_id = message.from_user.id
        args = message.get_args()
        if not args:
            settings = await user_settings.get(user_id)
            await message.answer(
                "Текущие настройки:\n"
                f"• Сетка: {settings.default_grid.as_label()}\n"
                f"• Padding: {settings.default_padding}px\n\n"
                "Чтобы изменить: /settings grid=3x3 pad=2",
            )
            return
        parts = dict()
        for token in args.split():
            if "=" in token:
                key, value = token.split("=", 1)
                parts[key.lower()] = value
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

    return router
