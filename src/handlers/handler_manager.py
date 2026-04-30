"""
Handler Manager for Pyrogram Event System.

Manages:
- Handler registration and priority
- Filter matching and routing
- Event dispatching to handlers
- Conversation storage via database integration
"""

import logging
from typing import Callable, List, Dict, Optional, Any
from datetime import datetime

from pyrogram import Client
from pyrogram.types import (
    Message, Update, User, Chat,
    ChatMember, ChatMemberUpdated
)

from src.database import DatabaseManager

logger = logging.getLogger(__name__)


class Handler:
    """Base handler class."""
    
    def __init__(self, name: str, priority: int = 0, enabled: bool = True):
        """
        Initialize handler.
        
        Args:
            name: Handler name (e.g., 'new_message', 'private_message')
            priority: Execution priority (higher = earlier)
            enabled: Whether handler is active
        """
        self.name = name
        self.priority = priority
        self.enabled = enabled
        self.filters = []
    
    async def execute(self, client: Client, message: Message, db: DatabaseManager) -> bool:
        """
        Execute handler logic.
        
        Args:
            client: Pyrogram client
            message: Telegram message
            db: Database manager
            
        Returns:
            bool: True if handled, False otherwise
        """
        raise NotImplementedError
    
    def add_filter(self, filter_fn: Callable) -> 'Handler':
        """Add filter function."""
        self.filters.append(filter_fn)
        return self
    
    async def check_filters(self, client: Client, message: Message) -> bool:
        """Check if all filters pass."""
        for filter_fn in self.filters:
            try:
                if not await filter_fn(client, message):
                    return False
            except Exception as e:
                logger.error(f"Filter error in {self.name}: {e}")
                return False
        return True


class HandlerManager:
    """Manages all event handlers."""
    
    def __init__(self, db: DatabaseManager):
        """
        Initialize handler manager.
        
        Args:
            db: Database manager instance
        """
        self.db = db
        self.handlers: Dict[str, List[Handler]] = {}
        self.client: Optional[Client] = None
        
        logger.info("Handler manager initialized")
    
    def register_handler(self, event_type: str, handler: Handler) -> None:
        """
        Register a handler for an event type.
        
        Args:
            event_type: Type of event (e.g., 'message', 'user_status')
            handler: Handler instance
        """
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        
        self.handlers[event_type].append(handler)
        # Sort by priority (higher first)
        self.handlers[event_type].sort(key=lambda h: -h.priority)
        
        logger.info(f"Registered handler: {handler.name} (priority: {handler.priority})")
    
    async def handle_message(self, client: Client, message: Message) -> None:
        """
        Route message to appropriate handlers.
        
        Args:
            client: Pyrogram client
            message: Telegram message
        """
        try:
            # Store conversation
            await self._store_conversation(message)
            
            # Execute handlers
            handlers = self.handlers.get('message', [])
            for handler in handlers:
                if not handler.enabled:
                    continue
                
                # Check filters
                if not await handler.check_filters(client, message):
                    continue
                
                # Execute handler
                try:
                    result = await handler.execute(client, message, self.db)
                    if result:
                        logger.debug(f"Handler {handler.name} handled message")
                        break  # Stop after first successful handler
                except Exception as e:
                    logger.error(f"Error in handler {handler.name}: {e}")
        
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _store_conversation(self, message: Message) -> None:
        """Store conversation in database."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get or create account
                account_name = message.sender_chat.username if message.sender_chat else "unknown"
                cursor.execute(
                    "SELECT id FROM accounts WHERE username = ?",
                    (account_name,)
                )
                account = cursor.fetchone()
                if not account:
                    cursor.execute(
                        "INSERT INTO accounts (username, email, status) VALUES (?, ?, ?)",
                        (account_name, "", "active")
                    )
                    conn.commit()
                    account_id = cursor.lastrowid
                else:
                    account_id = account[0]
                
                # Get or create conversation
                chat_id = message.chat.id
                cursor.execute(
                    "SELECT id FROM conversations WHERE chat_id = ? AND account_id = ?",
                    (chat_id, account_id)
                )
                conv = cursor.fetchone()
                if not conv:
                    cursor.execute(
                        """INSERT INTO conversations 
                           (chat_id, account_id, chat_type, status, created_at) 
                           VALUES (?, ?, ?, ?, ?)""",
                        (chat_id, account_id, message.chat.type, "active", datetime.now())
                    )
                    conn.commit()
                    conversation_id = cursor.lastrowid
                else:
                    conversation_id = conv[0]
                
                # Store message
                sender_id = message.from_user.id if message.from_user else 0
                text = message.text or ""
                
                cursor.execute(
                    """INSERT INTO messages 
                       (conversation_id, sender_id, text, message_type, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (conversation_id, sender_id, text, "text", datetime.now())
                )
                conn.commit()
                
                logger.debug(f"Stored conversation message from {sender_id}")
        
        except Exception as e:
            logger.error(f"Error storing conversation: {e}")
    
    def get_handlers(self, event_type: str) -> List[Handler]:
        """Get handlers for event type."""
        return self.handlers.get(event_type, [])
    
    def enable_handler(self, handler_name: str) -> None:
        """Enable a handler by name."""
        for event_handlers in self.handlers.values():
            for handler in event_handlers:
                if handler.name == handler_name:
                    handler.enabled = True
                    logger.info(f"Enabled handler: {handler_name}")
    
    def disable_handler(self, handler_name: str) -> None:
        """Disable a handler by name."""
        for event_handlers in self.handlers.values():
            for handler in event_handlers:
                if handler.name == handler_name:
                    handler.enabled = False
                    logger.info(f"Disabled handler: {handler_name}")


# Filter functions (custom predicates)
async def is_private_message(client: Client, message: Message) -> bool:
    """Check if message is from private chat."""
    return message.chat.type == "private"


async def is_group_message(client: Client, message: Message) -> bool:
    """Check if message is from group chat."""
    return message.chat.type in ("group", "supergroup")


async def is_media_message(client: Client, message: Message) -> bool:
    """Check if message contains media."""
    return bool(
        message.photo or message.video or message.audio or 
        message.document or message.voice or message.video_note
    )


async def has_text(client: Client, message: Message) -> bool:
    """Check if message has text content."""
    return bool(message.text)


async def is_not_from_bot(client: Client, message: Message) -> bool:
    """Check if message is not from a bot."""
    return not (message.from_user and message.from_user.is_bot)


async def contains_keyword(keywords: List[str]):
    """Create filter for messages containing keywords."""
    async def filter_func(client: Client, message: Message) -> bool:
        if not message.text:
            return False
        text_lower = message.text.lower()
        return any(kw.lower() in text_lower for kw in keywords)
    return filter_func
