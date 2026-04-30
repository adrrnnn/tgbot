#!/usr/bin/env python3
"""
Telegram Bot - Main Application Entry Point

AI-powered multi-account Telegram management system with OpenAI/Gemini integration.

Usage:
    python main.py              # Start the bot UI application
    python main.py --setup      # Run initial configuration wizard
    python main.py --db-init    # Manually initialize database
"""

import sys
import os
import logging
import ctypes
import threading
import asyncio
import time
from pathlib import Path
from typing import Optional

# Hide console window on Windows when GUI is shown
if sys.platform == 'win32':
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd != 0:
            # Show console during startup for errors, hide when GUI appears
            pass  # Will hide after QApplication starts
    except Exception:
        pass

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
log_handlers = [
    logging.FileHandler(PROJECT_ROOT / "logs" / "bot.log")
]

# Only log to console if running from terminal (not .pyw or detached)
if sys.stdin and sys.stdout:
    try:
        log_handlers.append(logging.StreamHandler())
    except Exception:
        pass

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)

# Suppress Pyrogram DEBUG logs (too verbose with session data)
logging.getLogger("pyrogram").setLevel(logging.INFO)
logging.getLogger("pyrogram.session").setLevel(logging.INFO)
logging.getLogger("pyrogram.connection").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Display legal notice on startup
logger.warning("=" * 80)
logger.warning("[LEGAL NOTICE] TELEGRAM USER ACCOUNT BOT - READ CAREFULLY")
logger.warning("=" * 80)
logger.warning("This bot operates in USER ACCOUNT mode (not Bot API).")
logger.warning("Be aware of the following:")
logger.warning("")
logger.warning("1. TERMS OF SERVICE: Automating user accounts violates Telegram ToS")
logger.warning("2. TRANSPARENCY: Users will NOT know they're chatting with automation")
logger.warning("3. SECURITY: Session files contain your Telegram credentials")
logger.warning("4. SCALABILITY: This only works for your personal account")
logger.warning("")
logger.warning("For a compliant, shareable bot, use Bot API (@BotFather instead).")
logger.warning("=" * 80)
logger.warning("")


def run_startup():
    """Run dependency checking and initialization."""
    logger.info("Running startup sequence...")
    
    try:
        from src.startup import StartupOrchestrator
        
        orchestrator = StartupOrchestrator()
        success = orchestrator.run_startup_sequence()
        
        if not success:
            logger.error("Startup sequence failed")
            return False
        
        return True
    
    except Exception as e:
        logger.error(f"Startup error: {e}")
        return False


def run_setup_wizard():
    """Run initial configuration setup."""
    logger.info("Running configuration setup wizard...")
    
    try:
        from src.config import ConfigManager
        
        config = ConfigManager()
        
        # Create default config template
        if not (Path("config") / "config.json").exists():
            config.create_default_config()
        
        print("\n" + "=" * 60)
        print("TELEGRAM BOT - SETUP WIZARD")
        print("=" * 60)
        print("\n1. Get your Telegram API credentials from: https://my.telegram.org/apps")
        print("   - Create an app and copy api_id and api_hash")
        print("\n2. Edit config/config.json and add your credentials")
        print("\n3. (Optional) Add OpenAI API key to config/config.json")
        print("   - Get from: https://platform.openai.com/api-keys")
        print("\n4. (Optional) Add Google Gemini API key")
        print("   - Get from: https://ai.google.dev/")
        print("\n5. Run the bot again: python main.py")
        print("=" * 60 + "\n")
        
        return True
    
    except Exception as e:
        logger.error(f"Setup error: {e}")
        return False


def run_bot_background(db, config):
    """Run Telegram bot client in background thread."""
    try:
        # Create fresh event loop for this thread FIRST (before any imports that need asyncio)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # NOW import pyrogram (which will use the loop we just set)
        from src.bot_server import run_bot_async
        
        try:
            logger.info("[BOT] Background thread starting bot...")
            # Run bot server
            loop.run_until_complete(run_bot_async(db, config))
            logger.info("[BOT] Background thread completed normally")
        except Exception as loop_error:
            logger.error(f"[BOT] Event loop error: {type(loop_error).__name__}: {loop_error}", exc_info=True)
        finally:
            try:
                loop.close()
            except Exception as close_error:
                logger.error(f"[BOT] Error closing loop: {close_error}")
    
    except ImportError as ie:
        logger.error(f"[BOT] Import error: {ie}", exc_info=True)
    except Exception as e:
        logger.error(f"[BOT] Error in bot background thread: {e}", exc_info=True)
        logger.debug("Bot thread will exit - this is non-critical")


def run_application():
    """Launch the main application UI with Telegram bot backend."""
    logger.info("Launching Telegram Bot application...")
    
    try:
        # Initialize backend
        from src.database import DatabaseManager
        from src.config import ConfigManager
        
        config = ConfigManager()
        db = DatabaseManager(config.database.db_path)
        db.initialize_database()  # Create schema if needed
        
        logger.info("Loading PyQt5 GUI...")
        
        # Import PyQt5 and new GUI
        from PyQt5.QtWidgets import QApplication
        from src.ui.main_gui import TelegramBotMainWindow
        
        # Create Qt Application
        app = QApplication(sys.argv)
        
        # Hide console window on Windows (after Qt app created)
        if sys.platform == 'win32':
            try:
                hwnd = ctypes.windll.kernel32.GetConsoleWindow()
                if hwnd != 0:
                    ctypes.windll.kernel32.ShowWindow(hwnd, 0)  # 0 = SW_HIDE
            except Exception:
                pass
        
        # Create and show window
        logger.info("Opening main window...")
        
        window = TelegramBotMainWindow(db_manager=db, config_manager=config)
        window.show()
        
        # Bot will be started when user clicks "Start Bot" tab
        logger.info("GUI ready. Bot will start when user clicks 'Start Bot' tab.")
        
        # Run event loop
        result = app.exec_()
        
        logger.info("Application closed normally")
        return result == 0
    
    except Exception as e:
        logger.error(f"Application error: {e}")
        logger.exception("Full traceback:")
        return False


def parse_args():
    """Parse command line arguments."""
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == "--setup":
            return "setup"
        elif arg == "--db-init":
            return "db-init"
        elif arg in ["--help", "-h"]:
            return "help"
    
    return "run"


def show_help():
    """Show help message."""
    print(__doc__)


def main():
    """Main application entry point."""
    command = parse_args()
    
    if command == "help":
        show_help()
        return 0
    
    elif command == "setup":
        success = run_setup_wizard()
        return 0 if success else 1
    
    elif command == "db-init":
        from src.database import initialize_database_with_defaults
        success = initialize_database_with_defaults()
        return 0 if success else 1
    
    else:  # command == "run"
        success = run_application()
        return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n✓ Shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
