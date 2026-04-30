"""
Reset Bot Tab - Placeholder
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QCheckBox, QPushButton, QHBoxLayout, QMessageBox
from src.database import DatabaseManager
from src.config import ConfigManager


class ResetBotTab(QWidget):
    """Tab for resetting all data"""
    
    def __init__(self, db: DatabaseManager, config: ConfigManager):
        super().__init__()
        self.db = db
        self.config = config
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        
        # Warning
        warning = QLabel("⚠ WARNING: DESTRUCTIVE OPERATION")
        warning.setStyleSheet("font-weight: bold; color: #FF9900;")
        layout.addWidget(warning)
        
        # Info
        info = QLabel("""This will DELETE all of the following:

• All Telegram Accounts
• All Model Profiles  
• All Conversations & Messages
• All Activity Logs
• All Log Files

The Database Schema will remain intact.""")
        layout.addWidget(info)
        
        # Checkbox
        self.confirm_checkbox = QCheckBox("I understand the consequences and accept responsibility")
        layout.addWidget(self.confirm_checkbox)
        
        # Buttons
        button_layout = QHBoxLayout()
        reset_btn = QPushButton("Reset Everything")
        reset_btn.clicked.connect(self._reset)
        reset_btn.setEnabled(False)
        cancel_btn = QPushButton("Cancel")
        
        self.confirm_checkbox.stateChanged.connect(
            lambda state: reset_btn.setEnabled(state == 2)
        )
        
        button_layout.addWidget(reset_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def _reset(self):
        """Reset all data"""
        reply = QMessageBox.question(self, "Final Confirmation", 
                                     "Are you absolutely sure? This cannot be undone.",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            QMessageBox.information(self, "Success", "Reset complete (feature in development)")
