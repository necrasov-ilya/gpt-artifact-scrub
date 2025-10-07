from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

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
from ..modules.text.services.normalization import TextNormalizationService
from ..modules.shared.services.anti_spam import AntiSpamGuard
from ..modules.shared.services.usage_stats import UsageStatsService

logger = logging.getLogger(__name__)


@dataclass
class AppContainer:
    config: AppConfig
    storage: Storage
    temp_files: TempFileManager
    text_service: TextNormalizationService
    user_settings: UserSettingsService
    anti_spam: AntiSpamGuard
    usage_stats: UsageStatsService
    emoji_service: EmojiPackService | None = None
    emoji_queue: EmojiProcessingQueue | None = None
    telegram_client: TelegramEmojiClient | None = None

    @classmethod
    async def build(cls, config: AppConfig) -> "AppContainer":
        storage = Storage(config.storage_path)
        await storage.initialize()
        temp_files = TempFileManager(config.temp_dir, retention_minutes=config.temp_retention_minutes)
        await temp_files.start()
        default_grid = EmojiGridOption.decode(config.emoji_grid_default.replace("×", "x"))
        grid_limit = min(config.emoji_max_tiles, config.emoji_creation_limit)
        anti_spam = AntiSpamGuard()
        usage_stats = UsageStatsService(storage, page_size=config.logs_page_size)
        user_settings = UserSettingsService(
            storage,
            default_grid=default_grid,
            default_padding=config.emoji_padding_default,
            grid_limit=grid_limit,
        )
        text_service = TextNormalizationService()
        return cls(
            config=config,
            storage=storage,
            temp_files=temp_files,
            text_service=text_service,
            user_settings=user_settings,
            anti_spam=anti_spam,
            usage_stats=usage_stats,
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
        dispatcher.include_router(
            create_commands_router(
                self.user_settings,
                self.usage_stats,
                tile_size=self.config.emoji_tile_size,
                logs_whitelist_ids=self.config.logs_whitelist_ids,
            )
        )
        dispatcher.include_router(create_text_router(self.text_service, self.anti_spam, self.usage_stats))
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
                anti_spam=self.anti_spam,
                grid_option_cap=self.config.emoji_grid_tile_cap,
                usage_stats=self.usage_stats,
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
