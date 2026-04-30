"""
Pyrogram Client Wrapper for Bot Operation.

Handles:
- Client initialization with Telegram credentials
- Handler registration
- Message listening loop
- Graceful shutdown
"""

import logging
import asyncio
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message

from src.database import DatabaseManager
from src.config import ConfigManager
from .handler_manager import HandlerManager, is_private_message, is_group_message, is_media_message, has_text
from .handlers import (
    NewMessageHandler, PrivateMessageHandler, GroupMessageHandler,
    ChannelMessageHandler, MediaHandler, KeywordHandler,
    UserTypingHandler, UserReadHandler, UserStatusHandler,
    UserJoinedHandler, DeleteMessageHandler
)

logger = logging.getLogger(__name__)


class TelegramBotClient:
    """Wrapper around Pyrogram Client for bot operations."""
    
    def __init__(self, db: DatabaseManager, config: ConfigManager):
        """
        Initialize Telegram bot client.
        
        Args:
            db: Database manager
            config: Configuration manager
        """
        self.db = db
        self.config = config
        self.client: Optional[Client] = None
        self.handler_manager: Optional[HandlerManager] = None
        self.is_running = False
        
        logger.info("Telegram bot client initialized")
    
    def setup(self) -> bool:
        """Setup Pyrogram client with credentials."""
        try:
            # Get Telegram credentials from config
            telegram_config = self.config.telegram
            
            if not telegram_config.api_id or not telegram_config.api_hash:
                logger.error("Telegram API credentials not configured")
                return False
            
            # Create Pyrogram client
            self.client = Client(
                name="telegram_bot",
                api_id=telegram_config.api_id,
                api_hash=telegram_config.api_hash,
                phone_number=telegram_config.phone,
                workdir="pyrogram_sessions"
            )
            
            # Initialize handler manager
            self.handler_manager = HandlerManager(self.db)
            self._register_handlers()
            
            logger.info("Telegram bot client setup complete")
            return True
        
        except Exception as e:
            logger.error(f"Error setting up Telegram client: {e}")
            return False
    
    def _register_handlers(self) -> None:
        """Register all handlers with the manager."""
        if not self.handler_manager:
            return
        
        # Create and register handlers
        handlers_list = [
            (NewMessageHandler(), 'message'),
            (PrivateMessageHandler(), 'message'),
            (GroupMessageHandler(), 'message'),
            (ChannelMessageHandler(), 'message'),
            (MediaHandler(), 'message'),
            (KeywordHandler(), 'message'),
            (UserTypingHandler(), 'typing'),
            (UserReadHandler(), 'read'),
            (UserStatusHandler(), 'status'),
            (UserJoinedHandler(), 'message'),
            (DeleteMessageHandler(), 'delete'),
        ]
        
        # Add filters to handlers where applicable
        private_msg_handler = handlers_list[1][0]
        group_msg_handler = handlers_list[2][0]
        media_handler = handlers_list[4][0]
        keyword_handler = handlers_list[5][0]
        
        private_msg_handler.add_filter(is_private_message)
        group_msg_handler.add_filter(is_group_message)
        media_handler.add_filter(is_media_message)
        keyword_handler.add_filter(has_text)
        
        # Register each handler
        for handler, event_type in handlers_list:
            self.handler_manager.register_handler(event_type, handler)
    
    async def start(self) -> bool:
        """Start listening for messages."""
        try:
            if not self.client:
                logger.error("Client not setup")
                return False
            
            # Start client (login if needed)
            await self.client.start()
            self.is_running = True
            
            logger.info("Telegram client started")
            
            # Register message handler
            @self.client.on_message()
            async def on_message(client: Client, message: Message):
                """Handle incoming messages."""
                if self.handler_manager:
                    await self.handler_manager.handle_message(client, message)
            
            # Keep client running
            logger.info("Bot listening for messages...")
            await self.client.idle()
            
            return True
        
        except Exception as e:
            logger.error(f"Error starting Telegram client: {e}")
            self.is_running = False
            return False
    
    async def stop(self) -> None:
        """Stop the client."""
        try:
            if self.client and self.is_running:
                await self.client.stop()
                self.is_running = False
                logger.info("Telegram client stopped")
        except Exception as e:
            logger.error(f"Error stopping client: {e}")
    
    def get_handler_manager(self) -> Optional[HandlerManager]:
        """Get the handler manager."""
        return self.handler_manager
    
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self.is_running
    
    async def send_message(self, chat_id: int, text: str) -> bool:
        """Send a message to a chat."""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return False
            
            await self.client.send_message(chat_id, text)
            logger.info(f"Message sent to chat {chat_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
