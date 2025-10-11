from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from .config import AppConfig
from .di import AppContainer


async def main() -> None:
    config = AppConfig()
    config.ensure_dirs()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    
    bot = Bot(
        token=config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    
    container = await AppContainer.build(config, bot)
    dispatcher = container.create_dispatcher(bot)
    try:
        # Drop pending updates to avoid processing old messages after bot restart
        await dispatcher.start_polling(bot, drop_pending_updates=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
