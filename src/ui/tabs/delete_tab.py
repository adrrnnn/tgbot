"""
Delete Bot Tab - Placeholder
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QCheckBox, QPushButton, QHBoxLayout, QMessageBox
from src.database import DatabaseManager
from src.config import ConfigManager


class DeleteBotTab(QWidget):
    """Tab for deleting entire program"""
    
    def __init__(self, db: DatabaseManager, config: ConfigManager):
        super().__init__()
        self.db = db
        self.config = config
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        
        # Danger warning
        warning = QLabel("🗑 DELETE BOT - POINT OF NO RETURN")
        warning.setStyleSheet("font-weight: bold; color: #FFFFFF; background-color: #CC0000; padding: 10px;")
        layout.addWidget(warning)
        
        # Info
        info = QLabel("""This will DELETE the entire program and all data.

Files that will be DELETED:
• Database (telegrambot.db)
• Configuration (config.json)
• Log Files
• Session Files
• Program Files

Files that will REMAIN:
• Python Dependencies (you must uninstall manually)

This action CANNOT be undone!""")
        layout.addWidget(info)
        
        # Dual checkboxes
        self.confirm1_checkbox = QCheckBox("I understand this will DELETE the entire program")
        self.confirm2_checkbox = QCheckBox("I accept responsibility for this action")
        layout.addWidget(self.confirm1_checkbox)
        layout.addWidget(self.confirm2_checkbox)
        
        # Buttons
        button_layout = QHBoxLayout()
        delete_btn = QPushButton("Delete Entire Program")
        delete_btn.clicked.connect(self._delete)
        delete_btn.setEnabled(False)
        cancel_btn = QPushButton("No, Take Me Back")
        help_btn = QPushButton("Help")
        
        # Enable button only when both checked
        def update_delete_btn():
            delete_btn.setEnabled(
                self.confirm1_checkbox.isChecked() and self.confirm2_checkbox.isChecked()
            )
        
        self.confirm1_checkbox.stateChanged.connect(update_delete_btn)
        self.confirm2_checkbox.stateChanged.connect(update_delete_btn)
        
        button_layout.addWidget(delete_btn)
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(help_btn)
        layout.addLayout(button_layout)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def _delete(self):
        """Delete entire program"""
        reply = QMessageBox.question(self, "FINAL WARNING", 
                                     "This will PERMANENTLY DELETE everything. You cannot recover from this.\n\nType 'DELETE' to confirm:",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            QMessageBox.information(self, "Cancelled", "Delete feature in development")
