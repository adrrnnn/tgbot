"""
Handles incoming private messages and sends AI-generated replies.
"""

import asyncio
import logging
import random
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.enums import ChatAction, ChatType

from src.database import DatabaseManager
from src.llm import LLMClient

logger = logging.getLogger(__name__)

# Approximate chars per second a person types on mobile
_TYPING_SPEED = 12
# Hard cap so the bot never waits more than this before sending (seconds)
_MAX_TYPING_DELAY = 12


class AIReplyHandler:
    """Processes incoming private messages and replies using the configured LLM."""

    def __init__(self, db: DatabaseManager, llm_client: LLMClient):
        self.db = db
        self.llm = llm_client

    async def handle_message(self, client: Client, message: Message) -> bool:
        """Generate and send an AI reply. Returns True if a reply was sent."""
        try:
            if message.chat.type != ChatType.PRIVATE or not message.text or message.outgoing:
                return False

            user_name = message.from_user.first_name if message.from_user else "User"
            logger.info(f"Message from {user_name}: {message.text[:60]}")

            # Simulate reading the incoming message before typing
            read_delay = random.uniform(1.5, 4.0)
            await asyncio.sleep(read_delay)

            response_text = await self.llm.generate_response(message.text, self.db)

            if not response_text:
                logger.warning(f"No response generated for message from {user_name}")
                return False

            await self._simulate_typing(client, message, response_text)
            await message.reply(response_text)
            logger.info(f"Reply sent to {user_name}")

            self._store_conversation(message, response_text)
            return True

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return False

    async def _simulate_typing(self, client: Client, message: Message, response_text: str) -> None:
        """Show a typing indicator for a duration proportional to the response length."""
        # How long it would realistically take to type this response
        typing_delay = len(response_text) / _TYPING_SPEED
        # Add a small random variance so it doesn't feel mechanical
        typing_delay = min(typing_delay * random.uniform(0.8, 1.2), _MAX_TYPING_DELAY)

        elapsed = 0.0
        # Telegram's typing action expires after 5s, so refresh it in a loop
        while elapsed < typing_delay:
            await client.send_chat_action(message.chat.id, ChatAction.TYPING)
            tick = min(4.0, typing_delay - elapsed)
            await asyncio.sleep(tick)
            elapsed += tick

    def _store_conversation(self, message: Message, reply_text: str) -> None:
        """Upsert the conversation row and append both messages to the messages table."""
        user_id = message.from_user.id if message.from_user else None
        account_id = 1  # TODO: replace with active account id once multi-account is wired

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                row = cursor.execute(
                    "SELECT id FROM conversations WHERE user_id = ? AND account_id = ?",
                    (user_id, account_id),
                ).fetchone()

                if row:
                    conversation_id = row[0]
                    cursor.execute(
                        """UPDATE conversations
                           SET state = 'ACTIVE',
                               last_activity_at = datetime('now'),
                               timeout_until = datetime('now', '+180 seconds')
                           WHERE id = ?""",
                        (conversation_id,),
                    )
                else:
                    cursor.execute(
                        """INSERT INTO conversations (user_id, account_id, chat_id, chat_type, state, last_activity_at)
                           VALUES (?, ?, ?, 'private', 'ACTIVE', datetime('now'))""",
                        (user_id, account_id, message.chat.id),
                    )
                    conversation_id = cursor.lastrowid

                cursor.executemany(
                    """INSERT INTO messages (conversation_id, sender_id, text, message_type, telegram_message_id)
                       VALUES (?, ?, ?, 'text', ?)""",
                    [
                        (conversation_id, user_id, message.text, message.id),
                        (conversation_id, account_id, reply_text, None),
                    ],
                )

        except Exception as e:
            logger.error(f"Error storing conversation: {e}")
