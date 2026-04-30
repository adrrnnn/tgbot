"""
Start Bot Tab - Start and control the message listener bot
"""

import logging
import threading
import asyncio
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QPlainTextEdit, QMessageBox
from PyQt5.QtCore import Qt
from src.database import DatabaseManager
from src.config import ConfigManager

logger = logging.getLogger(__name__)


class StartBotTab(QWidget):
    """Tab for starting bot and viewing logs"""
    
    def __init__(self, db: DatabaseManager, config: ConfigManager):
        super().__init__()
        self.db = db
        self.config = config
        self.bot_running = False
        self.bot_thread = None
        self.stop_event = threading.Event()
        self._setup_ui()
        self._setup_logging()
    
    def _setup_logging(self):
        """Capture logs from bot to display in GUI"""
        # Add a custom handler to capture logs
        self.log_handler = LogCaptureHandler(self.log_display)
        self.log_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)
        logging.getLogger().addHandler(self.log_handler)
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        
        # Status
        self.status_label = QLabel("Status: ⚫ Ready to Start")
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ Start Bot")
        self.start_btn.clicked.connect(self.start_bot)
        self.stop_btn = QPushButton("■ Stop Bot")
        self.stop_btn.clicked.connect(self.stop_bot)
        self.stop_btn.setEnabled(False)
        clear_logs_btn = QPushButton("Clear Logs")
        clear_logs_btn.clicked.connect(lambda: self.log_display.clear())
        
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addWidget(clear_logs_btn)
        layout.addLayout(button_layout)
        
        # Log display
        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setPlaceholderText("Logs will appear here when bot runs...")
        layout.addWidget(self.log_display)
        
        self.setLayout(layout)
    
    def start_bot(self):
        """Start the bot in background thread"""
        if self.bot_running:
            QMessageBox.warning(self, "Already Running", "Bot is already running!")
            return
        
        try:
            self.bot_running = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_label.setText("Status: 🟢 Running")
            self.log_display.appendPlainText("\n[Bot Starting...]")
            
            # Create background thread for bot
            self.stop_event.clear()
            self.bot_thread = threading.Thread(target=self._run_bot_thread, daemon=True)
            self.bot_thread.start()
            
            logger.info("[GUI] Bot thread started")
        
        except Exception as e:
            logger.error(f"[GUI] Failed to start bot: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to start bot: {e}")
            self.bot_running = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_label.setText("Status: ⚫ Ready to Start")
    
    def _run_bot_thread(self):
        """Run bot in background thread"""
        try:
            # Create event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Create warning callback
            def show_warning(message: str):
                logger.warning(f"API Warning: {message}")
            
            # Import bot runner
            from src.bot_server import run_bot_async
            
            # Run bot (verify_only=False means listen for messages)
            logger.info("[BOT] Starting message listener...")
            result = loop.run_until_complete(
                run_bot_async(self.db, self.config, verify_only=False, warning_callback=show_warning, stop_event=self.stop_event)
            )
            
            if result:
                logger.info("[BOT] Bot started successfully")
            else:
                logger.error("[BOT] Bot failed to start")
            
            loop.close()
        
        except Exception as e:
            logger.error(f"[BOT] Error in bot thread: {e}", exc_info=True)
        
        finally:
            # Ensure bot is marked as stopped
            self.bot_running = False
            if self.stop_event.is_set():
                logger.info("[BOT] Bot stopped by user")
            else:
                logger.warning("[BOT] Bot stopped unexpectedly")
    
    def stop_bot(self):
        """Stop the bot"""
        if not self.bot_running:
            QMessageBox.warning(self, "Not Running", "Bot is not running!")
            return
        
        try:
            self.bot_running = False
            self.stop_event.set()
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_label.setText("Status: ⚫ Ready to Start")
            self.log_display.appendPlainText("[Bot Stopping...]")
            
            logger.info("[GUI] Stop bot requested")
            
            # Wait for thread to finish (timeout after 5 seconds)
            if self.bot_thread and self.bot_thread.is_alive():
                self.bot_thread.join(timeout=5)
            
            self.log_display.appendPlainText("[Bot Stopped]")
        
        except Exception as e:
            logger.error(f"[GUI] Error stopping bot: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error stopping bot: {e}")


class LogCaptureHandler(logging.Handler):
    """Custom logging handler to capture logs in GUI"""
    
    def __init__(self, text_edit):
        super().__init__()
        self.text_edit = text_edit
    
    def emit(self, record):
        """Send log record to text edit"""
        try:
            msg = self.format(record)
            # Only show bot-related logs in the tab
            if any(x in msg for x in ["BOT", "Pyrogram", "telegram", "handler"]):
                self.text_edit.appendPlainText(msg)
        except Exception:
            self.handleError(record)
