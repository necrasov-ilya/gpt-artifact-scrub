"""
Start handler for tracking deep links.

This module provides a MIDDLEWARE (not a handler) that tracks deep link events
while allowing the normal /start command to proceed.
"""
import logging
from aiogram import Router, BaseMiddleware
from aiogram.filters import CommandStart
from aiogram.filters.command import CommandObject
from aiogram.types import Message, TelegramObject
from typing import Callable, Dict, Any, Awaitable

from src.modules.shared.services.bot_info import BotInfoService
from src.modules.tracking.services.tracking_service import TrackingService

logger = logging.getLogger(__name__)


class TrackingMiddleware(BaseMiddleware):
    """
    Middleware that silently tracks /start deep link events.
    
    This middleware intercepts /start commands with deep links, logs the tracking event,
    and then allows the event to continue to the normal /start handler.
    
    User experience: completely transparent - user sees normal /start response.
    Admin experience: events are logged for analytics.
    """
    
    def __init__(self, tracking_service: TrackingService):
        super().__init__()
        self.tracking_service = tracking_service
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Process the event and track if it's a deep link start command."""
        
        # Check if this is a Message with /start command
        if isinstance(event, Message):
            message = event
            
            logger.info(f"TrackingMiddleware: Processing message from user_id={message.from_user.id if message.from_user else None}")
            logger.info(f"TrackingMiddleware: Message text: {message.text}")
            logger.info(f"TrackingMiddleware: Data keys: {list(data.keys())}")
            
            command = data.get("command")
            logger.info(f"TrackingMiddleware: Command object: {command}, type: {type(command)}")
            
            # Check if it's a CommandStart with deep link
            if (isinstance(command, CommandObject) and 
                command.command == "start" and 
                command.args):
                
                user = message.from_user
                if user:
                    # Silently track the event in background
                    try:
                        logger.info(f"Tracking deep link: payload={command.args}, user_id={user.id}")
                        result = await self.tracking_service.handle_start(command.args, user.id)
                        logger.info(f"Tracking result: {result}")
                    except Exception as e:
                        # Don't let tracking errors affect normal flow
                        logger.error(f"Tracking error: {e}", exc_info=True)
                        pass
        
        # Continue to the next handler (normal /start response)
        return await handler(event, data)


def create_start_handler_router(
    tracking_service: TrackingService,
    bot_info: BotInfoService
) -> Router:
    """
    Create router with tracking middleware.
    
    This router doesn't handle any messages itself - it just adds a middleware
    that tracks deep link events before passing them to the normal /start handler.
    """
    router = Router(name="tracking_start")
    
    # Add middleware that will track deep links
    router.message.middleware(TrackingMiddleware(tracking_service))
    
    return router

