"""
Bot information service for cached access to bot metadata.
"""
from aiogram import Bot


class BotInfoService:
    """
    Service for managing bot information with lazy initialization and caching.
    
    This service provides a single point of access to bot metadata (username, etc.)
    across all modules, eliminating redundant API calls and ensuring consistency.
    """
    
    def __init__(self, bot: Bot, config_username: str | None = None):
        """
        Initialize bot info service.
        
        Args:
            bot: Aiogram Bot instance
            config_username: Pre-configured username from config (optional)
        """
        self._bot = bot
        self._cached_username: str | None = config_username
        self._initialized = config_username is not None
    
    async def get_username(self) -> str:
        """
        Get bot username with lazy initialization and caching.
        
        Returns:
            Bot username without @ prefix
            
        Raises:
            RuntimeError: If bot has no username configured
        """
        if self._initialized and self._cached_username:
            return self._cached_username
        
        me = await self._bot.get_me()
        if not me.username:
            raise RuntimeError("Bot username is required but not configured in Telegram")
        
        self._cached_username = me.username
        self._initialized = True
        
        return self._cached_username
    
    async def get_bot_link(self) -> str:
        """
        Get bot's direct link.
        
        Returns:
            URL like https://t.me/bot_username
        """
        username = await self.get_username()
        return f"https://t.me/{username}"
    
    async def get_start_link(self, payload: str | None = None) -> str:
        """
        Get bot's start link with optional payload.
        
        Args:
            payload: Optional deep link payload
            
        Returns:
            URL like https://t.me/bot_username?start=payload
        """
        username = await self.get_username()
        if payload:
            return f"https://t.me/{username}?start={payload}"
        return f"https://t.me/{username}"
