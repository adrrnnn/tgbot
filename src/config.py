"""
Configuration management for Telegram Bot application.

Loads and validates configuration from JSON files and environment variables.
Manages API credentials, database paths, and runtime settings.
Supports remote API key management via Cloudflare Workers.
"""

import json
import os
import logging
import sys
from typing import Any, Dict, Optional
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Default Telegram API credentials (shared for all users)
# These allow Pyrogram to connect - users provide their own phone number
DEFAULT_TELEGRAM_API_ID = 12345  # Placeholder - will be set in production
DEFAULT_TELEGRAM_API_HASH = "abcdef1234567890abcdef1234567890"  # Placeholder - will be set in production


@dataclass
class TelegramConfig:
    """Telegram API credentials and settings."""
    api_id: int = DEFAULT_TELEGRAM_API_ID
    api_hash: str = DEFAULT_TELEGRAM_API_HASH
    phone_number: Optional[str] = None
    
    def validate(self) -> bool:
        """Validate that required fields are set."""
        if not self.api_id or not self.api_hash:
            logger.error("Missing Telegram API credentials (api_id, api_hash)")
            return False
        return True


@dataclass
class DatabaseConfig:
    """Database configuration."""
    db_path: str = "telegrambot.db"
    session_dir: str = "pyrogram_sessions"
    backup_dir: str = "backups"
    
    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        Path(self.session_dir).mkdir(exist_ok=True)
        Path(self.backup_dir).mkdir(exist_ok=True)


@dataclass
class ApiConfig:
    """API provider configuration."""
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_rate_limit: int = 3500  # requests/min
    
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_rate_limit: int = 1500  # requests/min
    
    request_timeout: int = 30  # seconds
    retry_attempts: int = 3
    retry_backoff_factor: float = 2.0
    
    # Property aliases for backward compatibility
    @property
    def openai_key(self) -> Optional[str]:
        """Backward compatibility alias for openai_api_key."""
        return self.openai_api_key
    
    @openai_key.setter
    def openai_key(self, value: Optional[str]):
        """Backward compatibility alias for openai_api_key."""
        self.openai_api_key = value
    
    @property
    def gemini_key(self) -> Optional[str]:
        """Backward compatibility alias for gemini_api_key."""
        return self.gemini_api_key
    
    @gemini_key.setter
    def gemini_key(self, value: Optional[str]):
        """Backward compatibility alias for gemini_api_key."""
        self.gemini_api_key = value


@dataclass
class UiConfig:
    """UI/Desktop application configuration."""
    theme: str = "Dark"
    window_width: int = 1200
    window_height: int = 800
    font_size: int = 10
    log_panel_height: int = 200


@dataclass
class BotConfig:
    """Bot-specific settings (links, profiles, etc)."""
    of_link: Optional[str] = None


@dataclass
class CloudflareConfig:
    """Cloudflare Workers configuration for remote API key management."""
    enabled: bool = False
    worker_url: Optional[str] = None
    auth_token: Optional[str] = None
    fallback_to_local: bool = False  # Fall back to local config if Cloudflare fails
    timeout: int = 10  # seconds to wait for Cloudflare response
    
    def is_configured(self) -> bool:
        """Check if Cloudflare is properly configured."""
        return self.enabled and self.worker_url and self.auth_token


class ConfigManager:
    """Manages application configuration from JSON and environment."""
    
    def __init__(self, config_dir: str = "config"):
        """
        Initialize configuration manager.
        
        Args:
            config_dir: Directory containing config files
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        # Configuration objects
        self.telegram: Optional[TelegramConfig] = None
        self.database: DatabaseConfig = DatabaseConfig()
        self.api: ApiConfig = ApiConfig()
        self.ui: UiConfig = UiConfig()
        self.bot: BotConfig = BotConfig()
        self.cloudflare: CloudflareConfig = CloudflareConfig()
        
        # Load configuration
        self._load_config()
    
    def _load_config(self):
        """Load configuration from files and environment."""
        # Load from JSON if exists
        config_file = self.config_dir / "config.json"
        if config_file.exists():
            self._load_json_config(str(config_file))
        
        # Override with environment variables
        self._load_env_config()
        
        # Fetch from Cloudflare if enabled
        if self.cloudflare.is_configured():
            self._fetch_from_cloudflare()
        
        # Ensure directories exist
        self.database.ensure_directories()
        
        # Validate critical configuration
        if not self.telegram:
            logger.warning("Telegram configuration not found. Run setup wizard.")
    
    def _load_json_config(self, config_path: str):
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # Load Telegram config
            if 'telegram' in config_data:
                telegram_data = config_data['telegram']
                self.telegram = TelegramConfig(
                    api_id=telegram_data.get('api_id'),
                    api_hash=telegram_data.get('api_hash'),
                    phone_number=telegram_data.get('phone_number')
                )
            
            # Load API config
            if 'api' in config_data:
                api_data = config_data['api']
                # Support both 'openai_api_key' and 'openai_key' for backward compatibility
                self.api.openai_api_key = api_data.get('openai_api_key') or api_data.get('openai_key')
                self.api.openai_model = api_data.get('openai_model', 'gpt-4o-mini')
                # Support both 'gemini_api_key' and 'gemini_key' for backward compatibility
                self.api.gemini_api_key = api_data.get('gemini_api_key') or api_data.get('gemini_key')
                self.api.gemini_model = api_data.get('gemini_model', 'gemini-1.5-flash')
                self.api.request_timeout = api_data.get('timeout', 30)
                
                logger.info(f"API keys loaded: gemini={'set' if self.api.gemini_api_key else 'not set'}, openai={'set' if self.api.openai_api_key else 'not set'}")
            
            # Load Database config
            if 'database' in config_data:
                db_data = config_data['database']
                self.database.db_path = db_data.get('path', 'telegrambot.db')
                self.database.session_dir = db_data.get('session_dir', 'pyrogram_sessions')
                self.database.backup_dir = db_data.get('backup_dir', 'backups')
            
            # Load UI config
            if 'ui' in config_data:
                ui_data = config_data['ui']
                self.ui.theme = ui_data.get('theme', 'Dark')
                self.ui.window_width = ui_data.get('window_width', 1200)
                self.ui.window_height = ui_data.get('window_height', 800)
            
            # Load Bot config
            if 'bot' in config_data:
                bot_data = config_data['bot']
                self.bot.of_link = bot_data.get('of_link')
            
            # Load Cloudflare config
            if 'cloudflare' in config_data:
                cf_data = config_data['cloudflare']
                self.cloudflare = CloudflareConfig(
                    enabled=cf_data.get('enabled', False),
                    worker_url=cf_data.get('worker_url'),
                    auth_token=cf_data.get('auth_token'),
                    fallback_to_local=cf_data.get('fallback_to_local', False),
                    timeout=cf_data.get('timeout', 10)
                )
            
            logger.info(f"Configuration loaded from {config_path}")
        
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
    
    def _load_env_config(self):
        """Load configuration from environment variables."""
        # Telegram
        if os.getenv('TELEGRAM_API_ID'):
            if not self.telegram:
                self.telegram = TelegramConfig(
                    api_id=int(os.getenv('TELEGRAM_API_ID')),
                    api_hash=os.getenv('TELEGRAM_API_HASH'),
                    phone_number=os.getenv('TELEGRAM_PHONE')
                )
        
        # API Keys
        if os.getenv('OPENAI_API_KEY'):
            self.api.openai_api_key = os.getenv('OPENAI_API_KEY')
            logger.info("Loaded OPENAI_API_KEY from environment")

        if os.getenv('GEMINI_API_KEY'):
            self.api.gemini_api_key = os.getenv('GEMINI_API_KEY')
            logger.info("Loaded GEMINI_API_KEY from environment")

        if os.getenv('TELEGRAM_BOT_DB'):
            self.database.db_path = os.getenv('TELEGRAM_BOT_DB')
    
    def _fetch_from_cloudflare(self) -> bool:
        """
        Fetch API keys from Cloudflare Worker.
        
        Returns:
            True if successful, False otherwise
        """
        import urllib.request
        import urllib.error
        
        if not self.cloudflare.is_configured():
            logger.warning("Cloudflare not properly configured (url, token missing)")
            return False
        
        try:
            logger.info(f"Fetching API keys from Cloudflare: {self.cloudflare.worker_url}")
            
            # Prepare request
            url = f"{self.cloudflare.worker_url.rstrip('/')}/api/keys"
            headers = {
                'Authorization': f'Bearer {self.cloudflare.auth_token}',
                'Content-Type': 'application/json'
            }
            
            # Create request
            req = urllib.request.Request(url, headers=headers)
            
            # Fetch with timeout
            with urllib.request.urlopen(req, timeout=self.cloudflare.timeout) as response:
                data = json.loads(response.read().decode())
            
            # Update API keys from Cloudflare
            if data.get('gemini_key'):
                self.api.gemini_api_key = data['gemini_key']
                logger.info("Gemini API key loaded from Cloudflare")

            if data.get('openai_key'):
                self.api.openai_api_key = data['openai_key']
                logger.info("OpenAI API key loaded from Cloudflare")

            logger.info("API keys fetched from Cloudflare successfully")
            return True

        except urllib.error.HTTPError as e:
            if e.code == 401:
                logger.error("Cloudflare authentication failed (401) — check auth_token in config.json")
            elif e.code == 404:
                logger.error(f"Cloudflare worker not found (404) — check worker_url in config.json")
            else:
                logger.error(f"Cloudflare HTTP error {e.code}: {e.reason}")

            if not self.cloudflare.fallback_to_local:
                logger.critical("Cloudflare unreachable and fallback disabled — bot cannot start")
                sys.exit(1)

            logger.warning("Falling back to local config")
            return False

        except urllib.error.URLError as e:
            logger.error(f"Cloudflare unreachable: {e.reason}")

            if not self.cloudflare.fallback_to_local:
                logger.critical("Cloudflare unreachable and fallback disabled — bot cannot start")
                sys.exit(1)

            logger.warning("Falling back to local config")
            return False

        except json.JSONDecodeError as e:
            logger.error(f"Cloudflare returned invalid JSON: {e}")

            if not self.cloudflare.fallback_to_local:
                logger.critical("Cloudflare response invalid and fallback disabled — bot cannot start")
                sys.exit(1)

            return False

        except Exception as e:
            logger.error(f"Unexpected error fetching from Cloudflare: {e}")

            if not self.cloudflare.fallback_to_local:
                logger.critical("Could not fetch from Cloudflare and fallback disabled — bot cannot start")
                sys.exit(1)

            return False
    
    def save_config(self) -> bool:
        """Save current configuration to JSON file."""
        try:
            config_data = {
                'telegram': asdict(self.telegram) if self.telegram else {},
                'api': asdict(self.api),
                'database': asdict(self.database),
                'ui': asdict(self.ui),
                'bot': asdict(self.bot),
                'cloudflare': asdict(self.cloudflare)
            }
            
            config_file = self.config_dir / "config.json"
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Configuration saved to {config_file}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def create_default_config(self) -> bool:
        """Create a default configuration template."""
        default_config = {
            "_WARNING": "DO NOT SHARE THIS FILE - IT CONTAINS SENSITIVE CREDENTIALS",
            "_LEGAL_NOTICE": {
                "mode": "USER ACCOUNT (not Bot API)",
                "risks": [
                    "Users will NOT know they're chatting with automation - they'll think you're replying",
                    "Automating user accounts violates Telegram Terms of Service",
                    "If this file is compromised, your entire Telegram account is at risk",
                    "Session files in pyrogram_sessions/ contain your login credentials",
                    "This setup ONLY works for your personal account - cannot be shared with others",
                    "For a compliant, shareable bot use Bot API with @BotFather instead"
                ],
                "how_to_get_credentials": "Visit https://my.telegram.org/apps with YOUR Telegram account and create an app"
            },
            "telegram": {
                "api_id": 0,
                "api_hash": "YOUR_API_HASH_HERE (get from my.telegram.org/apps)",
                "phone_number": "+1234567890 (your Telegram account phone)"
            },
            "api": {
                "openai_key": "sk-...",
                "openai_model": "gpt-4o-mini",
                "gemini_key": "YOUR_GEMINI_KEY_HERE",
                "gemini_model": "gemini-1.5-flash",
                "timeout": 30
            },
            "database": {
                "path": "telegrambot.db",
                "session_dir": "pyrogram_sessions",
                "backup_dir": "backups"
            },
            "ui": {
                "theme": "Dark",
                "window_width": 1200,
                "window_height": 800,
                "font_size": 10
            }
        }
        
        try:
            config_file = self.config_dir / "config.json"
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            
            logger.info(f"Default configuration created at {config_file}")
            print(f"\nIMPORTANT: Edit {config_file} with your Telegram API credentials.")
            print("  Get API credentials from: https://my.telegram.org/apps")
            return True
        
        except Exception as e:
            logger.error(f"Failed to create default config: {e}")
            return False
    
    def validate(self) -> bool:
        """Validate that all required configuration is present."""
        errors = []
        
        # Check Telegram credentials
        if not self.telegram or not self.telegram.validate():
            errors.append("Telegram API credentials missing (api_id, api_hash)")
        
        # Check database path
        if not self.database.db_path:
            errors.append("Database path not configured")
        
        # Check for at least one API provider
        if not self.api.openai_api_key and not self.api.gemini_api_key:
            errors.append("No API provider configured (OpenAI or Gemini)")
        
        if errors:
            for error in errors:
                logger.error(f"Configuration error: {error}")
            return False

        logger.info("Configuration validation passed")
        return True


def get_config() -> ConfigManager:
    """Get or create global configuration instance."""
    if not hasattr(get_config, '_instance'):
        get_config._instance = ConfigManager()
    return get_config._instance


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and show default configuration
    config = ConfigManager()
    success = config.create_default_config()
    
    if success:
        print("\nConfiguration template created.")
        print("  Edit config/config.json with your credentials and run the app again.")
    else:
        print("\nFailed to create configuration")
