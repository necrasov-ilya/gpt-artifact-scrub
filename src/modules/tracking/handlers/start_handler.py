import logging
from aiogram import BaseMiddleware
from aiogram.filters.command import CommandObject
from aiogram.types import Message, TelegramObject
from typing import Callable, Dict, Any, Awaitable

from src.modules.tracking.services.tracking_service import TrackingService

logger = logging.getLogger(__name__)


class TrackingMiddleware(BaseMiddleware):
    def __init__(self, tracking_service: TrackingService):
        super().__init__()
        self.tracking_service = tracking_service
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message):
            command = data.get("command")
            
            if isinstance(command, CommandObject) and command.args:
                user = event.from_user
                if user:
                    try:
                        await self.tracking_service.handle_start(command.args, user.id)
                    except Exception as e:
                        logger.error(f"Tracking error: {e}", exc_info=True)
        
        return await handler(event, data)


def create_tracking_middleware(tracking_service: TrackingService) -> TrackingMiddleware:
    return TrackingMiddleware(tracking_service)

