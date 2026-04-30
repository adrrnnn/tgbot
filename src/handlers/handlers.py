"""
Individual Handler Implementations.

11 handler types for processing different Telegram events:
1. new_message_handler - All new messages
2. private_message_handler - Private messages only
3. group_message_handler - Group/supergroup messages
4. channel_message_handler - Channel messages
5. media_handler - Messages with media
6. keyword_handler - Messages containing keywords
7. user_typing_handler - User typing notifications
8. user_read_handler - Message read receipts
9. user_status_handler - User online/offline status
10. user_joined_handler - User joins group
11. delete_message_handler - Message deletions
"""

import logging
from typing import List, Optional
from datetime import datetime

from pyrogram import Client
from pyrogram.types import Message, ChatMember

from src.database import DatabaseManager
from .handler_manager import Handler

logger = logging.getLogger(__name__)


class NewMessageHandler(Handler):
    """Handler for all new messages."""
    
    def __init__(self):
        super().__init__("new_message", priority=100, enabled=True)
    
    async def execute(self, client: Client, message: Message, db: DatabaseManager) -> bool:
        """Handle new message."""
        try:
            logger.debug(f"NewMessageHandler: processing message from {message.from_user.id if message.from_user else 'unknown'}")
            # Conversation already stored by HandlerManager
            return True
        except Exception as e:
            logger.error(f"Error in NewMessageHandler: {e}")
            return False


class PrivateMessageHandler(Handler):
    """Handler for private messages only."""
    
    def __init__(self):
        super().__init__("private_message", priority=90, enabled=True)
    
    async def execute(self, client: Client, message: Message, db: DatabaseManager) -> bool:
        """Handle private message."""
        try:
            if message.chat.type != "private":
                return False
            
            logger.info(f"PrivateMessageHandler: {message.text[:50] if message.text else 'media'} from {message.from_user.first_name}")
            
            # Mark as from private chat in database
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE conversations SET chat_type = ? WHERE chat_id = ?",
                    ("private", message.chat.id)
                )
                conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"Error in PrivateMessageHandler: {e}")
            return False


class GroupMessageHandler(Handler):
    """Handler for group/supergroup messages."""
    
    def __init__(self):
        super().__init__("group_message", priority=85, enabled=True)
    
    async def execute(self, client: Client, message: Message, db: DatabaseManager) -> bool:
        """Handle group message."""
        try:
            if message.chat.type not in ("group", "supergroup"):
                return False
            
            logger.info(f"GroupMessageHandler: group {message.chat.title}, user {message.from_user.first_name}")
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE conversations SET chat_type = ? WHERE chat_id = ?",
                    (message.chat.type, message.chat.id)
                )
                conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"Error in GroupMessageHandler: {e}")
            return False


class ChannelMessageHandler(Handler):
    """Handler for channel messages."""
    
    def __init__(self):
        super().__init__("channel_message", priority=80, enabled=True)
    
    async def execute(self, client: Client, message: Message, db: DatabaseManager) -> bool:
        """Handle channel message."""
        try:
            if message.chat.type != "channel":
                return False
            
            logger.debug(f"ChannelMessageHandler: channel {message.chat.title}")
            return True
        except Exception as e:
            logger.error(f"Error in ChannelMessageHandler: {e}")
            return False


class MediaHandler(Handler):
    """Handler for messages with media (photos, videos, documents, etc.)."""
    
    def __init__(self):
        super().__init__("media_handler", priority=75, enabled=True)
    
    async def execute(self, client: Client, message: Message, db: DatabaseManager) -> bool:
        """Handle media message."""
        try:
            media_type = None
            if message.photo:
                media_type = "photo"
            elif message.video:
                media_type = "video"
            elif message.audio:
                media_type = "audio"
            elif message.document:
                media_type = "document"
            elif message.voice:
                media_type = "voice"
            elif message.video_note:
                media_type = "video_note"
            else:
                return False
            
            logger.info(f"MediaHandler: {media_type} from {message.from_user.first_name if message.from_user else 'unknown'}")
            
            # Store media type in database
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE messages SET message_type = ? WHERE message_id = ?",
                    (media_type, message.message_id)
                )
                conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"Error in MediaHandler: {e}")
            return False


class KeywordHandler(Handler):
    """Handler for messages containing specific keywords."""
    
    def __init__(self, keywords: Optional[List[str]] = None):
        super().__init__("keyword_handler", priority=70, enabled=True)
        self.keywords = keywords or ["alert", "important", "urgent", "help", "support"]
    
    async def execute(self, client: Client, message: Message, db: DatabaseManager) -> bool:
        """Handle keyword message."""
        try:
            if not message.text:
                return False
            
            text_lower = message.text.lower()
            matched_keywords = [kw for kw in self.keywords if kw.lower() in text_lower]
            
            if not matched_keywords:
                return False
            
            logger.info(f"KeywordHandler: matched {matched_keywords} in message from {message.from_user.first_name if message.from_user else 'unknown'}")
            
            # Store keyword match in database
            with db.get_connection() as conn:
                cursor = conn.cursor()
                keywords_str = ",".join(matched_keywords)
                cursor.execute(
                    "INSERT INTO audit_log (timestamp, type, description) VALUES (?, ?, ?)",
                    (datetime.now(), "keyword_match", f"Keywords matched: {keywords_str}")
                )
                conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"Error in KeywordHandler: {e}")
            return False


class UserTypingHandler(Handler):
    """Handler for user typing notifications."""
    
    def __init__(self):
        super().__init__("user_typing", priority=50, enabled=True)
    
    async def execute(self, client: Client, message: Message, db: DatabaseManager) -> bool:
        """Handle user typing (placeholder - requires Update handler)."""
        # This is typically handled via user_status updates, not messages
        logger.debug("UserTypingHandler: typing notification")
        return True


class UserReadHandler(Handler):
    """Handler for message read receipts."""
    
    def __init__(self):
        super().__init__("user_read", priority=45, enabled=True)
    
    async def execute(self, client: Client, message: Message, db: DatabaseManager) -> bool:
        """Handle message read (placeholder - requires Update handler)."""
        # This is typically handled via Update events
        logger.debug("UserReadHandler: message read")
        return True


class UserStatusHandler(Handler):
    """Handler for user online/offline status changes."""
    
    def __init__(self):
        super().__init__("user_status", priority=40, enabled=True)
    
    async def execute(self, client: Client, message: Message, db: DatabaseManager) -> bool:
        """Handle user status (placeholder - requires Update handler)."""
        # This is typically handled via Update events
        logger.debug("UserStatusHandler: user status changed")
        return True


class UserJoinedHandler(Handler):
    """Handler for when users join a group."""
    
    def __init__(self):
        super().__init__("user_joined", priority=35, enabled=True)
    
    async def execute(self, client: Client, message: Message, db: DatabaseManager) -> bool:
        """Handle user joined group."""
        try:
            # Check if this is a service message like "X joined using a link"
            if message.service and hasattr(message, 'new_chat_members'):
                new_members = message.new_chat_members
                for member in new_members:
                    logger.info(f"UserJoinedHandler: {member.first_name} joined group {message.chat.title}")
                    
                    # Store in audit log
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO audit_log (timestamp, type, description) VALUES (?, ?, ?)",
                            (datetime.now(), "user_joined", f"{member.first_name} joined {message.chat.title}")
                        )
                        conn.commit()
                
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error in UserJoinedHandler: {e}")
            return False


class DeleteMessageHandler(Handler):
    """Handler for deleted messages."""
    
    def __init__(self):
        super().__init__("delete_message", priority=30, enabled=True)
    
    async def execute(self, client: Client, message: Message, db: DatabaseManager) -> bool:
        """Handle deleted message (placeholder - requires Update handler)."""
        try:
            # This would be handled via delete_messages updates
            logger.debug(f"DeleteMessageHandler: message deleted")
            
            # Store deletion in audit log
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO audit_log (timestamp, type, description) VALUES (?, ?, ?)",
                    (datetime.now(), "message_deleted", f"Message deleted from chat {message.chat.id}")
                )
                conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"Error in DeleteMessageHandler: {e}")
            return False
