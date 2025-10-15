from __future__ import annotations

import asyncio
import io
from pathlib import Path
from datetime import UTC, datetime
from typing import Iterable
from uuid import uuid4

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ...modules.images.domain.models import EmojiGridOption, EmojiPackRequest, EmojiPackResult
from ...modules.images.infrastructure.storage import Storage
from ...modules.images.infrastructure.tempfiles import TempFileManager
from ...modules.images.services.queue import EmojiProcessingQueue
from ...modules.images.services.user_settings import UserSettingsService
from ...modules.images.utils.image import compute_image_hash, get_image_size, suggest_grids
from ...modules.images.utils.video import get_video_info, compute_video_hash
from ...modules.shared.services.anti_spam import AntiSpamGuard
from ...modules.shared.services.usage_stats import UsageStatsService


class EmojiStates(StatesGroup):
    waiting_for_grid = State()


def _grid_keyboard(options: Iterable[EmojiGridOption], default: EmojiGridOption) -> InlineKeyboardMarkup:
    buttons = []
    row: list[InlineKeyboardButton] = []
    for option in options:
        label = f"{option.rows}×{option.cols}"
        if option == default:
            label += " ⭐"
        row.append(InlineKeyboardButton(text=label, callback_data=f"grid:{option.encode()}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _resolve_extension(bot, file) -> str:
    mime_type = getattr(file, "mime_type", None)
    if mime_type and "/" in mime_type:
        candidate = mime_type.split("/", 1)[1].lower()
        if candidate:
            return candidate

    file_name = getattr(file, "file_name", None)
    if file_name:
        suffix = Path(file_name).suffix.lstrip(".")
        if suffix:
            return suffix.lower()

    try:
        file_info = await bot.get_file(file.file_id)
    except Exception:
        return "png"
    suffix = Path((file_info.file_path or "")).suffix.lstrip(".")
    return (suffix or "png").lower()


def create_emoji_router(
    *,
    temp_files: TempFileManager,
    queue: EmojiProcessingQueue,
    storage: Storage,
    user_settings: UserSettingsService,
    max_tiles: int,
    creation_limit: int,
    retention_minutes: int,
    fragment_username: str | None,
    anti_spam: AntiSpamGuard,
    grid_option_cap: int | None,
    usage_stats: UsageStatsService,
    video_max_duration: float,
    video_target_fps: int,
) -> Router:
    router = Router(name="emoji_handler")

    @router.message(
        (F.photo | (F.document & F.document.mime_type.startswith("image/")))
        & ~F.via_bot
        & ~F.text.startswith("/")
    )
    async def on_image(message: Message, state: FSMContext) -> None:
        if not message.from_user:
            return
        user_id = message.from_user.id
        if not await anti_spam.try_acquire(user_id):
            await message.answer("Не так быстро, пожалуйста. Дайте боту чуть-чуть времени.")
            return
        try:
            file = message.photo[-1] if message.photo else message.document
            if file is None:
                return
            buffer = io.BytesIO()
            await message.bot.download(file, destination=buffer)
            image_bytes = buffer.getvalue()
            image_hash = compute_image_hash(image_bytes)
            width, height = get_image_size(image_bytes)
            limit_tiles = min(max_tiles, creation_limit)
            plan = suggest_grids(width, height, max_tiles=limit_tiles)
            if grid_option_cap is not None:
                capped_options = [option for option in plan.options if option.tiles <= grid_option_cap]
                if capped_options:
                    plan_options = capped_options
                    fallback = capped_options[0]
                else:
                    plan_options = plan.options
                    fallback = plan.fallback
            else:
                plan_options = plan.options
                fallback = plan.fallback
            settings = await user_settings.get(message.from_user.id)
            extension = await _resolve_extension(message.bot, file)
            default_grid = settings.default_grid
            if default_grid.tiles > limit_tiles or default_grid not in plan_options:
                default_grid = fallback
            await state.clear()
            await state.set_state(EmojiStates.waiting_for_grid)
            await state.update_data(
                image_bytes=image_bytes,
                image_hash=image_hash,
                file_unique_id=file.file_unique_id,
                suggested=[option.encode() for option in plan_options],
                default_padding=settings.default_padding,
                default_grid=default_grid.encode(),
                image_extension=extension,
            )

            warn_text = (
                "⚠️ Для установки кастом-эмодзи паков нужен Telegram Premium.\n\n"
                f"Файлы удаляются через {retention_minutes} мин после обработки."
            )
            description = (
                f"Изображение {width}×{height}px.\nВыберите сетку для нарезки (по умолчанию {default_grid.as_label()})."
            )
            padding_hint = (
                "\n\nТекущий padding-уровень: "
                f"{settings.default_padding}. Изменить можно командой /padding 0..5."
            )
            await message.answer(
                f"{warn_text}\n\n{description}{padding_hint}",
                reply_markup=_grid_keyboard(plan_options, default_grid),
            )
            await usage_stats.record_event(message.from_user, is_message=True)
        finally:
            await anti_spam.release(user_id)

    @router.message(
        (F.video | F.animation)
        & ~F.via_bot
        & ~F.text.startswith("/")
    )
    async def on_video(message: Message, state: FSMContext) -> None:
        if not message.from_user:
            return
        user_id = message.from_user.id
        if not await anti_spam.try_acquire(user_id):
            await message.answer("Не так быстро, пожалуйста. Дайте боту чуть-чуть времени.")
            return
        
        status_message = None
        try:
            file = message.video or message.animation
            if file is None:
                return
            
            # Показываем статус скачивания
            status_message = await message.answer("⏳ Скачиваю видео...")
            
            # Скачиваем файл во временную директорию
            job_token = uuid4().hex[:8]
            job_subdir = Path(str(user_id)) / f"job_video_{job_token}"
            
            extension = await _resolve_extension(message.bot, file)
            if extension not in ("mp4", "avi", "mov", "webm", "gif"):
                extension = "mp4"
            
            temp_video_path = await temp_files.write_bytes(b"", suffix=f".{extension}", subdir=job_subdir)
            
            # Скачиваем с большим таймаутом
            try:
                await asyncio.wait_for(
                    message.bot.download(file, destination=temp_video_path),
                    timeout=120.0  # 2 минуты на скачивание
                )
            except asyncio.TimeoutError:
                await status_message.edit_text("❌ Не удалось скачать видео: превышен таймаут. Попробуйте файл меньшего размера.")
                await anti_spam.release(user_id)
                return
            
            # Обновляем статус
            await status_message.edit_text("🔍 Анализирую видео...")
            
            # Получаем информацию о видео
            video_info = get_video_info(temp_video_path)
            video_hash = compute_video_hash(temp_video_path)
            
            width, height = video_info.width, video_info.height
            duration = video_info.duration
            
            # Проверяем длительность
            duration_warning = ""
            if duration > video_max_duration:
                duration_warning = f"\n⚠️ Видео будет обрезано до {video_max_duration} сек (исходная длительность: {duration:.1f} сек)."
            
            limit_tiles = min(max_tiles, creation_limit)
            plan = suggest_grids(width, height, max_tiles=limit_tiles)
            
            if grid_option_cap is not None:
                capped_options = [option for option in plan.options if option.tiles <= grid_option_cap]
                if capped_options:
                    plan_options = capped_options
                    fallback = capped_options[0]
                else:
                    plan_options = plan.options
                    fallback = plan.fallback
            else:
                plan_options = plan.options
                fallback = plan.fallback
            
            settings = await user_settings.get(message.from_user.id)
            default_grid = settings.default_grid
            if default_grid.tiles > limit_tiles or default_grid not in plan_options:
                default_grid = fallback
            
            await state.clear()
            await state.set_state(EmojiStates.waiting_for_grid)
            await state.update_data(
                video_path=str(temp_video_path),
                video_hash=video_hash,
                file_unique_id=file.file_unique_id,
                suggested=[option.encode() for option in plan_options],
                default_padding=settings.default_padding,
                default_grid=default_grid.encode(),
                video_extension=extension,
                is_animated=True,
                duration=duration,
            )
            
            warn_text = (
                "⚠️ Для установки кастом-эмодзи паков нужен Telegram Premium.\n\n"
                f"Файлы удаляются через {retention_minutes} мин после обработки."
            )
            content_type = "GIF" if message.animation else "Видео"
            description = (
                f"{content_type} {width}×{height}px, {duration:.1f} сек.\n"
                f"Выберите сетку для нарезки (по умолчанию {default_grid.as_label()})."
                f"{duration_warning}"
            )
            padding_hint = (
                "\n\nТекущий padding-уровень: "
                f"{settings.default_padding}. Изменить можно командой /padding 0..5."
            )
            
            # Удаляем статусное сообщение и показываем выбор сетки
            if status_message:
                await status_message.delete()
            
            await message.answer(
                f"{warn_text}\n\n{description}{padding_hint}",
                reply_markup=_grid_keyboard(plan_options, default_grid),
            )
            await usage_stats.record_event(message.from_user, is_message=True)
        except Exception as e:
            if status_message:
                try:
                    await status_message.edit_text(f"❌ Ошибка при обработке видео: {e}")
                except Exception:
                    await message.answer(f"❌ Ошибка при обработке видео: {e}")
            else:
                await message.answer(f"❌ Ошибка при обработке видео: {e}")
            await anti_spam.release(user_id)
            # Очищаем временные файлы
            try:
                if 'temp_video_path' in locals() and temp_video_path.exists():
                    temp_video_path.unlink(missing_ok=True)
                    if temp_video_path.parent != temp_files._temp_dir:
                        import shutil
                        shutil.rmtree(temp_video_path.parent, ignore_errors=True)
            except Exception:
                pass

    @router.callback_query(EmojiStates.waiting_for_grid, F.data.startswith("grid:"))
    async def choose_grid(callback: CallbackQuery, state: FSMContext) -> None:
        grid_value = callback.data.split(":", 1)[1]
        grid = EmojiGridOption.decode(grid_value)
        stored = await state.get_data()
        suggested: list[str] = stored.get("suggested", [])  # type: ignore[assignment]
        if grid.encode() not in suggested:
            await callback.answer("Эта сетка недоступна для этого изображения", show_alert=True)
            return
        data = await state.get_data()
        await state.clear()
        default_padding = int(data.get("default_padding", 2))
        file_unique_id: str = data["file_unique_id"]
        is_animated = data.get("is_animated", False)
        
        if is_animated:
            # Обработка видео/GIF
            video_path_str: str = data["video_path"]
            video_hash: str = data["video_hash"]
            duration: float = data.get("duration", 0.0)
            video_path = Path(video_path_str)
            
            request = EmojiPackRequest(
                user_id=callback.from_user.id,
                chat_id=callback.message.chat.id,
                file_path=video_path,
                image_hash=video_hash,
                grid=grid,
                padding=default_padding,
                file_unique_id=file_unique_id,
                requested_at=datetime.now(UTC),
                is_animated=True,
                duration=min(duration, video_max_duration),
            )
        else:
            # Обработка статичного изображения
            image_bytes: bytes = data["image_bytes"]
            image_hash: str = data["image_hash"]
            extension = data.get("image_extension", "png")
            job_token = uuid4().hex[:8]
            job_subdir = Path(str(callback.from_user.id)) / f"job_{image_hash[:6]}_{job_token}"
            path = await temp_files.write_bytes(image_bytes, suffix=f".{extension}", subdir=job_subdir)
            
            request = EmojiPackRequest(
                user_id=callback.from_user.id,
                chat_id=callback.message.chat.id,
                file_path=path,
                image_hash=image_hash,
                grid=grid,
                padding=default_padding,
                file_unique_id=file_unique_id,
                requested_at=datetime.now(UTC),
                is_animated=False,
            )

        await user_settings.update(callback.from_user.id, grid, default_padding)

        try:
            future = await queue.submit(request)
        except Exception:
            await anti_spam.release(callback.from_user.id)
            raise
        await callback.answer("Запустил нарезку, это займет до минуты")
        content_type = "видео" if is_animated else "фото"
        processing_message = await callback.message.answer(
            f"Режу ваше {content_type} на миниатюры и превращаю их в эмодзи — скоро пришлю ссылку!",
        )

        async def finalize() -> None:
            try:
                outcome = await future
            except Exception as exc:  # noqa: BLE001
                await processing_message.edit_text(
                    f"Не получилось создать пак: {exc}",
                    parse_mode=ParseMode.HTML,
                )
            else:
                await processing_message.edit_text("Готово!", parse_mode=ParseMode.HTML)
                await _send_result(callback.message, outcome.result, fragment_username)
            finally:
                await anti_spam.release(callback.from_user.id)

        asyncio.create_task(finalize())

    async def _send_result(message: Message, result: EmojiPackResult, fragment_username: str | None) -> None:
        link_text = f"🔗 Установить пак: https://t.me/addemoji/{result.short_name}"
        info = f"Добавлено тайлов: {len(result.custom_emoji_ids)}"
        text = f"{info}\n{link_text}"
        if fragment_username and result.fragment_preview_id:
            fragment_link = (
                f"Предпросмотр: https://fragment.com/{fragment_username}?custom_emoji={result.fragment_preview_id}"
            )
            text += f"\n{fragment_link}"
        await message.answer(text)

    return router
