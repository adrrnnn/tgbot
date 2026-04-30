"""
Main GUI Window for Telegram Bot Manager
Implements PyQt5 interface with 6 tabs
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QStatusBar, QStackedWidget
)
from PyQt5.QtCore import Qt, QTimer, QDateTime
from PyQt5.QtGui import QFont
from src.database import DatabaseManager
from src.config import ConfigManager


class TelegramBotMainWindow(QMainWindow):
    """Main application window with 6 tabs"""
    
    SCREEN_VERIFICATION = 0
    SCREEN_MAIN = 1
    
    def __init__(self, db_manager: DatabaseManager, config_manager: ConfigManager):
        super().__init__()
        self.db = db_manager
        self.config = config_manager
        self.bot_running = False
        self.verification_callback = None
        self.verification_code_result = None
        
        self.setWindowTitle("Telegram Bot Manager")
        self.setGeometry(100, 100, 1000, 700)
        self.setMinimumSize(800, 600)
        
        # Setup UI with stacked widget for different screens
        self._setup_ui()
        self._setup_status_bar()
        self._setup_timer()
        
        # Check if account exists, show setup dialog if not
        self._check_and_setup_account()
    
    def _setup_ui(self):
        """Initialize all UI components"""
        # Central widget with stacked widget for multiple screens
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Stacked widget for switching between screens
        self.stacked_widget = QStackedWidget()
        
        # Screen 0: Verification waiting screen
        # Create verification screen inline (no separate module needed)
        verification_widget = QWidget()
        verification_layout = QVBoxLayout(verification_widget)
        verification_layout.setSpacing(20)
        verification_layout.setContentsMargins(40, 40, 40, 40)
        
        verification_layout.addStretch()
        
        title = QLabel("Verification Required")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        verification_layout.addWidget(title)
        
        instructions = QLabel(
            "A verification code has been sent to your Telegram app.\n\n"
            "Please check your Telegram messages and enter the code\n"
            "when prompted.\n\n"
            "Waiting for verification..."
        )
        instructions_font = QFont()
        instructions_font.setPointSize(11)
        instructions.setFont(instructions_font)
        instructions.setAlignment(Qt.AlignCenter)
        instructions.setStyleSheet("color: #666; line-height: 1.6;")
        verification_layout.addWidget(instructions)
        
        from PyQt5.QtWidgets import QProgressBar
        progress = QProgressBar()
        progress.setMaximum(0)
        progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f5f5f5;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #007AFF;
            }
        """)
        verification_layout.addWidget(progress)
        
        verification_layout.addStretch()
        verification_widget.setLayout(verification_layout)
        
        self.verification_screen = verification_widget
        self.stacked_widget.addWidget(self.verification_screen)
        
        # Screen 1: Main panel with tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(self._get_tab_stylesheet())
        
        # Import tabs lazily to avoid circular imports
        from src.ui.tabs.accounts_tab import TelegramAccountsTab
        from src.ui.tabs.profiles_tab import ModelProfilesTab
        from src.ui.tabs.link_tab import ChangeOFLinkTab
        from src.ui.tabs.start_bot_tab import StartBotTab
        from src.ui.tabs.reset_tab import ResetBotTab
        from src.ui.tabs.delete_tab import DeleteBotTab
        
        # Create tabs
        self.accounts_tab = TelegramAccountsTab(self.db, self.config)
        self.profiles_tab = ModelProfilesTab(self.db, self.config)
        self.link_tab = ChangeOFLinkTab(self.db, self.config)
        self.start_bot_tab = StartBotTab(self.db, self.config)
        self.reset_tab = ResetBotTab(self.db, self.config)
        self.delete_tab = DeleteBotTab(self.db, self.config)
        
        # Add tabs
        self.tab_widget.addTab(self.accounts_tab, "Telegram Accounts")
        self.tab_widget.addTab(self.link_tab, "Change OF Link")
        self.tab_widget.addTab(self.profiles_tab, "Model Profiles")
        self.tab_widget.addTab(self.start_bot_tab, "Start Bot")
        self.tab_widget.addTab(self.reset_tab, "Reset Bot")
        self.tab_widget.addTab(self.delete_tab, "Delete Bot")
        
        self.stacked_widget.addWidget(self.tab_widget)
        
        main_layout.addWidget(self.stacked_widget)
        central_widget.setLayout(main_layout)
    
    def _setup_status_bar(self):
        """Setup status bar at bottom"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Left section: Active account
        self.account_label = QLabel("✓ Active Account: ---")
        self.account_label.setStyleSheet("color: #009900; margin-left: 10px;")
        self.status_bar.addWidget(self.account_label)
        
        # Middle section (permanent widget): Bot status
        self.bot_status_label = QLabel("Bot Status: Stopped")
        self.bot_status_label.setStyleSheet("color: #CC0000; text-align: center;")
        self.status_bar.addPermanentWidget(self.bot_status_label)
        
        # Right section: Time
        self.time_label = QLabel("00:00:00")
        self.time_label.setStyleSheet("margin-right: 10px;")
        self.status_bar.addPermanentWidget(self.time_label)
        
        # Load initial values
        self._update_status_bar()
    
    def _setup_timer(self):
        """Setup timer for status bar updates"""
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_time)
        self.timer.start(1000)  # Update every second
    
    def _update_status_bar(self):
        """Update status bar with current info"""
        # Get active account
        try:
            cursor = self.db.get_connection().cursor()
            cursor.execute(
                "SELECT phone FROM accounts WHERE account_type = 'telegram' AND is_active = 1 LIMIT 1"
            )
            result = cursor.fetchone()
            if result:
                phone = result[0]
                self.account_label.setText(f"✓ Active Account: {phone}")
                self.account_label.setStyleSheet("color: #009900; margin-left: 10px;")
            else:
                self.account_label.setText("✓ Active Account: None")
                self.account_label.setStyleSheet("color: #FF9900; margin-left: 10px;")
        except:
            self.account_label.setText("✓ Active Account: Error")
    
    def _update_time(self):
        """Update time in status bar"""
        current_time = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.time_label.setText(current_time)
    
    def set_bot_running(self, running: bool):
        """Update bot status in status bar"""
        self.bot_running = running
        if running:
            self.bot_status_label.setText("Bot Status: Running")
            self.bot_status_label.setStyleSheet("color: #009900;")
        else:
            self.bot_status_label.setText("Bot Status: Stopped")
            self.bot_status_label.setStyleSheet("color: #CC0000;")
    
    def _get_tab_stylesheet(self) -> str:
        """Get CSS stylesheet for tabs"""
        return """
        QTabWidget::pane {
            border: 1px solid #E0E0E0;
        }
        QTabBar::tab {
            background-color: #f5f5f5;
            color: #212121;
            padding: 8px 16px;
            margin-right: 2px;
            border: 1px solid #E0E0E0;
            border-bottom: none;
        }
        QTabBar::tab:selected {
            background-color: #FFFFFF;
            color: #2196F3;
            border-bottom: 2px solid #2196F3;
        }
        QTabBar::tab:hover {
            background-color: #EEEEEE;
        }
        """
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Stop any running processes
        if self.start_bot_tab:
            try:
                self.start_bot_tab.stop_bot()
            except:
                pass
        
        # Stop timer
        if self.timer:
            self.timer.stop()
        
        event.accept()
    
    def _check_and_setup_account(self):
        """Check if account exists, show setup dialog if not"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM accounts WHERE account_type = 'telegram' LIMIT 1"
                )
                account_exists = cursor.fetchone() is not None
            
            if not account_exists:
                # Show setup dialog
                from src.ui.dialogs.setup_dialog import TelegramSetupDialog
                dialog = TelegramSetupDialog(self, self.db, self.config)
                if dialog.exec_():
                    # Account was created, start verification flow
                    self.show_verification_screen()
                    # Trigger verification in background
                    import threading
                    thread = threading.Thread(target=self._trigger_verification, daemon=True)
                    thread.start()
            else:
                # Account exists, show main panel
                self.show_main_screen()
        
        except Exception as e:
            print(f"Error checking account: {e}")
    
    def show_verification_screen(self):
        """Show the verification waiting screen"""
        self.stacked_widget.setCurrentIndex(self.SCREEN_VERIFICATION)
    
    def show_main_screen(self):
        """Show the main panel with tabs"""
        self.stacked_widget.setCurrentIndex(self.SCREEN_MAIN)
    
    def _trigger_verification(self):
        """Trigger Pyrogram verification and show code dialog"""
        import logging
        import asyncio
        
        logger = logging.getLogger(__name__)
        
        try:
            logger.info("[GUI] Starting verification process...")
            
            # Create event loop FIRST in this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # NOW import pyrogram (needs event loop)
            from src.bot_server import set_verification_callback
            
            # Create a callback for verification code input
            def get_verification_code():
                """Show verification dialog on main thread"""
                logger.info("[GUI] Showing verification code dialog...")
                from src.ui.dialogs.verification_dialog import VerificationCodeDialog
                
                dialog = VerificationCodeDialog(parent=self)
                result = dialog.exec_()
                
                if result == dialog.Accepted:
                    code = dialog.get_code()
                    logger.info(f"[GUI] Code received: {code}")
                    return code
                else:
                    logger.warning("[GUI] Verification cancelled")
                    return None
            
            # Set up verification callback in bot_server
            set_verification_callback(get_verification_code)
            
            # Create a callback for API warning messages
            def show_api_warning(message: str):
                """Show API exhaustion warning dialog on main thread"""
                from PyQt5.QtWidgets import QMessageBox
                logger.warning(f"[GUI] Showing API warning: {message}")
                QMessageBox.warning(self, "API Quota Exhausted", message)
            
            # Import and run bot verification
            from src.bot_server import run_bot_async
            
            logger.info("[GUI] Running Pyrogram authentication...")
            result = loop.run_until_complete(run_bot_async(self.db, self.config, verify_only=True, warning_callback=show_api_warning))
            
            loop.close()
            
            if result:
                logger.info("[GUI] Verification successful! Showing main screen...")
                # Switch to main screen
                self.show_main_screen()
                self.accounts_tab.load_accounts()
                self._update_status_bar()
            else:
                logger.error("[GUI] Verification failed")
                # Show error dialog and go back to setup
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Verification Failed", "Failed to verify your account. Please try again.")
                self._check_and_setup_account()
        
        except Exception as e:
            logger.error(f"[GUI] Verification error: {e}", exc_info=True)
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Verification error: {e}")
            self._check_and_setup_account()
