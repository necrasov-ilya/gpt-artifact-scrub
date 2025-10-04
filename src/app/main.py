from __future__ import annotations

import asyncio
import logging

from .config import AppConfig
from .di import AppContainer


async def main() -> None:
    config = AppConfig()
    config.ensure_dirs()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    container = await AppContainer.build(config)
    bot = container.create_bot()
    dispatcher = container.create_dispatcher(bot)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
