"""
Handler for /start command with tracking payload.
"""
from aiogram import Router
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from src.modules.tracking.services.tracking_service import TrackingService


def create_start_handler_router(
    tracking_service: TrackingService,
    bot_username: str
) -> Router:
    """
    Create router for /start command with tracking.
    
    Intercepts /start commands with deep link payloads for tracking purposes.
    Regular /start commands without payloads are handled by commands router.
    """
    router = Router(name="tracking_start")
    
    @router.message(CommandStart(deep_link=True))
    async def handle_tracking_start(message: Message, command: CommandObject) -> None:
        """Handle /start with deep link payload."""
        user = message.from_user
        if not user:
            return
        
        payload = command.args if command and command.args else None
        if not payload:
            return
        
        result = await tracking_service.handle_start(payload, user.id)
        
        if not result:
            await message.answer(
                "👋 Добро пожаловать!\n\n"
                "Отправьте текст или изображение для обработки."
            )
            return
        
        link, is_first_start = result
        
        external_url = f"https://t.me/{bot_username}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать работу", url=external_url)]
        ])
        
        if is_first_start:
            text = (
                f"👋 Добро пожаловать!\n\n"
                f"Вы перешли по ссылке: **{link.tag}**\n\n"
                f"Нажмите кнопку ниже, чтобы начать работу с ботом."
            )
        else:
            text = (
                f"👋 С возвращением!\n\n"
                f"Ссылка: **{link.tag}**\n\n"
                f"Нажмите кнопку ниже, чтобы продолжить."
            )
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    
    return router
