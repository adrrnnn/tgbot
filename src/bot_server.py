"""
Telegram Bot Server - Manages Pyrogram client and message handlers.
"""

import logging
import asyncio
import sys
import builtins
from typing import Optional, Callable
from pyrogram import Client, filters

from src.database import DatabaseManager
from src.config import ConfigManager
from src.llm import LLMClient
from src.handlers.ai_reply_handler import AIReplyHandler

logger = logging.getLogger(__name__)

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_MAX_RETRIES = 5
_RETRY_BASE_DELAY = 5  # seconds; doubles each attempt (5, 10, 20, 40, 80)

_verification_callback: Optional[Callable[[], Optional[str]]] = None
_original_input = builtins.input


def set_verification_callback(callback: Callable[[], Optional[str]]):
    """Route Pyrogram's verification code prompt through a custom handler (e.g. a GUI dialog)."""
    global _verification_callback
    _verification_callback = callback

    def custom_input(prompt: str = "") -> str:
        if _verification_callback and ("code" in prompt.lower() or "token" in prompt.lower()):
            logger.info("Verification code requested")
            code = _verification_callback()
            if code:
                return code
        return _original_input(prompt)

    builtins.input = custom_input


class TelegramBotServer:
    """Manages the Pyrogram client lifecycle and AI message handling."""

    def __init__(self, db: DatabaseManager, config: ConfigManager, warning_callback=None, stop_event=None):
        self.db = db
        self.config = config
        self.client: Optional[Client] = None
        self.llm_client: Optional[LLMClient] = None
        self.ai_handler: Optional[AIReplyHandler] = None
        self.is_running = False
        self.warning_callback = warning_callback
        self.stop_event = stop_event

    async def start(self, verify_only: bool = False) -> bool:
        """Start the bot. If verify_only=True, authenticate and exit without listening."""
        try:
            logger.warning(
                "Running in USER ACCOUNT mode — recipients will not know this is automated. "
                "Keep session files secure."
            )

            if not self._validate_credentials():
                logger.error("Missing Telegram credentials — check config.json")
                return False

            if not verify_only:
                self.llm_client = LLMClient(self.config)
                if self.warning_callback:
                    self.llm_client.set_warning_callback(self.warning_callback)

            self._create_pyrogram_client()

            if not verify_only:
                self.ai_handler = AIReplyHandler(self.db, self.llm_client)
                self._register_handlers()

            logger.info("Starting Telegram client...")
            await self.client.start()
            self.is_running = True

            if verify_only:
                logger.info("Authentication successful")
                await self.stop()
                return True

            logger.info("Bot started — listening for messages")

            while True:
                if self.stop_event and self.stop_event.is_set():
                    logger.info("Stop signal received, shutting down")
                    break
                await asyncio.sleep(1)

            await self.stop()
            return True

        except asyncio.CancelledError:
            return False
        except Exception as e:
            logger.error(f"Bot error: {e}", exc_info=True)
            raise  # let run_bot_async decide whether to retry

    def _validate_credentials(self) -> bool:
        t = self.config.telegram
        return bool(t and t.api_id and t.api_hash and t.phone_number)

    def _create_pyrogram_client(self) -> None:
        t = self.config.telegram
        self.client = Client(
            name="telegram_bot",
            api_id=t.api_id,
            api_hash=t.api_hash,
            phone_number=t.phone_number,
            workdir="pyrogram_sessions",
        )

    def _register_handlers(self) -> None:
        @self.client.on_message(filters.private & filters.incoming & filters.text)
        async def handle_private_message(client, message):
            await self.ai_handler.handle_message(client, message)

        logger.info("Message handlers registered")

    async def stop(self) -> None:
        try:
            if self.client and self.is_running:
                await self.client.stop()
                self.is_running = False
                logger.info("Bot stopped")
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")


async def run_bot_async(
    db: DatabaseManager,
    config: ConfigManager,
    verify_only: bool = False,
    warning_callback=None,
    stop_event=None,
) -> bool:
    """
    Run the bot with automatic reconnection on failure.

    On a clean stop (stop_event set) or verify_only run, exits immediately.
    On unexpected disconnects, retries up to _MAX_RETRIES times with
    exponential backoff before giving up.
    """
    if verify_only:
        server = TelegramBotServer(db, config, warning_callback=warning_callback, stop_event=stop_event)
        try:
            return await server.start(verify_only=True)
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False
        finally:
            await server.stop()

    attempt = 0
    while attempt < _MAX_RETRIES:
        # Check stop before each attempt
        if stop_event and stop_event.is_set():
            logger.info("Stop requested before reconnect attempt")
            return True

        if attempt > 0:
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(f"Reconnecting in {delay}s (attempt {attempt}/{_MAX_RETRIES})")
            # Wait for the delay but bail early if stop is requested
            for _ in range(delay):
                if stop_event and stop_event.is_set():
                    return True
                await asyncio.sleep(1)

        server = TelegramBotServer(db, config, warning_callback=warning_callback, stop_event=stop_event)
        try:
            await server.start(verify_only=False)

            # If we get here the bot ran and stopped cleanly (stop_event was set)
            return True

        except KeyboardInterrupt:
            logger.info("Bot interrupted by user")
            return False

        except Exception as e:
            logger.error(f"Bot disconnected: {e}")
            attempt += 1

        finally:
            await server.stop()

    logger.error(f"Bot failed to stay connected after {_MAX_RETRIES} attempts — giving up")
    if warning_callback:
        warning_callback(
            f"Bot lost connection and could not reconnect after {_MAX_RETRIES} attempts.\n"
            "Check your internet connection and restart the bot."
        )
    return False
