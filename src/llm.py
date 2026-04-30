"""
LLM Integration for AI responses.

Supports OpenAI GPT and Google Gemini with profile-based personalization.
Falls back from Gemini to OpenAI if the primary fails or quota is exhausted.
"""

import logging
import asyncio
from typing import Optional, Callable
from src.config import ConfigManager
from src.database import DatabaseManager

logger = logging.getLogger(__name__)

QUOTA_KEYWORDS = [
    "quota", "exhausted", "rate limit", "429", "out of tokens",
    "insufficient tokens", "limit exceeded", "payment required",
    "insufficient_quota", "tokens_per_min_limit_exceeded", "billing",
]


class LLMClient:
    """Wrapper for LLM API calls (OpenAI and Google Gemini)."""

    def __init__(self, config: ConfigManager):
        self.config = config
        self.openai_client = None
        self.gemini_client = None
        self.warning_callback: Optional[Callable[[str], None]] = None
        self._init_clients()

    def _init_clients(self) -> None:
        """Initialize API clients for whichever keys are configured."""
        gemini_key = self.config.api.gemini_api_key
        if gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                self.gemini_client = genai
                logger.info("Gemini client initialized (primary)")
            except Exception as e:
                logger.warning(f"Could not initialize Gemini: {e}")
        else:
            logger.warning("Gemini API key not configured")

        openai_key = self.config.api.openai_api_key
        if openai_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=openai_key)
                logger.info("OpenAI client initialized (fallback)")
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI: {e}")
        else:
            logger.warning("OpenAI API key not configured")

        if not self.gemini_client and not self.openai_client:
            logger.error("No LLM clients available — check your API keys in config.json")

    def set_warning_callback(self, callback: Callable[[str], None]) -> None:
        self.warning_callback = callback

    def build_system_prompt(self, db: DatabaseManager) -> str:
        """Build the system prompt from the active profile, or return a generic fallback."""
        try:
            profile = db.get_current_profile()
        except Exception as e:
            logger.error(f"Error fetching current profile: {e}")
            profile = None

        if not profile:
            logger.warning("No active profile found, using generic prompt")
            return "You are a helpful assistant. Be conversational and natural."

        name = profile.get("name", "")
        age = profile.get("age", "")
        location = profile.get("location", "")
        ethnicity = profile.get("ethnicity", "")
        custom_prompt = profile.get("system_prompt_custom", "")
        notes = profile.get("notes", "")

        prompt = f"You are {name}, a {age}-year-old {ethnicity} person from {location}.\n\n"
        prompt += "Personality: Be natural and conversational. Respond like a real person, not an AI.\n"
        prompt += "Tone: Friendly and authentic.\n"

        if custom_prompt:
            prompt += f"\nAdditional instructions: {custom_prompt}\n"
        if notes:
            prompt += f"Notes about you: {notes}\n"

        prompt += "\nBe concise in responses (under 200 tokens). Respond naturally to messages."
        return prompt

    async def generate_response(self, message_text: str, db: DatabaseManager) -> Optional[str]:
        """
        Generate a reply using Gemini (primary) then OpenAI (fallback).
        Returns None if both fail or quota is exhausted.
        """
        system_prompt = self.build_system_prompt(db)

        response = await self._try_gemini(message_text, system_prompt)
        if response:
            return response

        logger.warning("Gemini failed, trying OpenAI fallback")
        response = await self._try_openai(message_text, system_prompt)
        if response:
            return response

        logger.error("Both APIs failed — no response generated")
        self._fire_quota_warning()
        return None

    async def _try_gemini(self, message_text: str, system_prompt: str) -> Optional[str]:
        if not self.gemini_client:
            return None

        try:
            model = self.gemini_client.GenerativeModel(
                model_name=self.config.api.gemini_model,
                system_instruction=system_prompt,
            )
            response = await asyncio.to_thread(model.generate_content, message_text)
            if response and response.text:
                logger.debug(f"Gemini response: {len(response.text)} chars")
                return response.text
            logger.warning("Gemini returned an empty response")
            return None

        except Exception as e:
            if self._is_quota_error(str(e)):
                logger.warning(f"Gemini quota exhausted: {e}")
            else:
                logger.debug(f"Gemini error: {e}")
            return None

    async def _try_openai(self, message_text: str, system_prompt: str) -> Optional[str]:
        if not self.openai_client:
            return None

        try:
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-4o-mini",
                max_tokens=200,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message_text},
                ],
            )
            reply = response.choices[0].message.content
            logger.debug(f"OpenAI response: {len(reply)} chars")
            return reply

        except Exception as e:
            if self._is_quota_error(str(e)):
                logger.warning(f"OpenAI quota exhausted: {e}")
            else:
                logger.debug(f"OpenAI error: {e}")
            return None

    def _is_quota_error(self, error_msg: str) -> bool:
        return any(kw in error_msg.lower() for kw in QUOTA_KEYWORDS)

    def _fire_quota_warning(self) -> None:
        msg = (
            "API QUOTA EXHAUSTED\n\n"
            "No LLM APIs are available to generate responses.\n\n"
            "Solutions:\n"
            "1. Get a free Gemini key at https://ai.google.dev/\n"
            "2. Get an OpenAI key at https://platform.openai.com/api-keys\n\n"
            "Add the key to config.json and restart the bot."
        )
        logger.critical(msg.replace("\n", " "))
        if self.warning_callback:
            self.warning_callback(msg)
