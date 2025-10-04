from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from openai import AsyncOpenAI

from .config import AppConfig
from ..modules.images.domain.models import EmojiGridOption
from .handlers.commands import create_commands_router
from .handlers.emoji import create_emoji_router
from .handlers.text import create_text_router
from .handlers.unsupported import create_unsupported_router
from ..modules.images.infrastructure.storage import Storage
from ..modules.images.infrastructure.telegram_emoji import TelegramEmojiClient
from ..modules.images.infrastructure.tempfiles import TempFileManager
from ..modules.images.services.emoji_pack import EmojiPackService
from ..modules.images.services.queue import EmojiProcessingQueue
from ..modules.images.services.user_settings import UserSettingsService
from ..modules.text.infrastructure.llm_openai import OpenAITextEditor
from ..modules.text.services.normalization import IdentityTextEditor, TextNormalizationService

logger = logging.getLogger(__name__)


@dataclass
class AppContainer:
    config: AppConfig
    openai_client: AsyncOpenAI | None
    storage: Storage
    temp_files: TempFileManager
    text_service: TextNormalizationService
    user_settings: UserSettingsService
    emoji_service: EmojiPackService | None = None
    emoji_queue: EmojiProcessingQueue | None = None
    telegram_client: TelegramEmojiClient | None = None

    @classmethod
    async def build(cls, config: AppConfig) -> "AppContainer":
        openai_client: AsyncOpenAI | None = None
        if config.openai_api_key:
            openai_client = AsyncOpenAI(api_key=config.openai_api_key)
        else:
            logger.warning("OPENAI_API_KEY not set; falling back to normalization-only editor")
        storage = Storage(config.storage_path)
        await storage.initialize()
        temp_files = TempFileManager(config.temp_dir, retention_minutes=config.temp_retention_minutes)
        await temp_files.start()
        default_grid = EmojiGridOption.decode(config.emoji_grid_default.replace("×", "x"))
        grid_limit = min(config.emoji_max_tiles, config.emoji_creation_limit)
        user_settings = UserSettingsService(
            storage,
            default_grid=default_grid,
            default_padding=config.emoji_padding_default,
            grid_limit=grid_limit,
        )
        if openai_client is None:
            llm_editor = IdentityTextEditor()
        else:
            llm_editor = OpenAITextEditor(
                client=openai_client,
                model=config.openai_model,
                temperature=config.openai_temperature,
            )
        text_service = TextNormalizationService(llm_editor)
        return cls(
            config=config,
            openai_client=openai_client,
            storage=storage,
            temp_files=temp_files,
            text_service=text_service,
            user_settings=user_settings,
        )

    def create_bot(self) -> Bot:
        return Bot(
            token=self.config.telegram_bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )

    def create_dispatcher(self, bot: Bot) -> Dispatcher:
        self.telegram_client = TelegramEmojiClient(
            bot=bot,
            bot_username=self.config.bot_username,
            fragment_username=self.config.fragment_username,
            creation_limit=self.config.emoji_creation_limit,
            total_limit=self.config.emoji_max_tiles,
        )
        self.emoji_service = EmojiPackService(
            storage=self.storage,
            telegram_client=self.telegram_client,
            temp_dir=self.config.temp_dir,
            tile_size=self.config.emoji_tile_size,
        )
        self.emoji_queue = EmojiProcessingQueue(
            self.emoji_service,
            workers=self.config.emoji_queue_workers,
        )
        dispatcher = Dispatcher()
        dispatcher.include_router(create_commands_router(self.user_settings))
        dispatcher.include_router(create_text_router(self.text_service))
        dispatcher.include_router(
            create_emoji_router(
                temp_files=self.temp_files,
                queue=self.emoji_queue,
                storage=self.storage,
                user_settings=self.user_settings,
                max_tiles=self.config.emoji_max_tiles,
                creation_limit=self.config.emoji_creation_limit,
                retention_minutes=self.config.temp_retention_minutes,
                fragment_username=self.config.fragment_username,
            )
        )
        dispatcher.include_router(create_unsupported_router())
        dispatcher.startup.register(self.on_startup)
        dispatcher.shutdown.register(self.on_shutdown)
        return dispatcher

    async def on_startup(self, bot: Bot) -> None:
        if self.emoji_queue:
            await self.emoji_queue.start()

    async def on_shutdown(self, bot: Bot) -> None:
        if self.emoji_queue:
            await self.emoji_queue.stop()
        await self.temp_files.stop()
        if self.openai_client is not None:
            await self.openai_client.close()
