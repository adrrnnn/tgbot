"""Telegram verification code dialog for PyQt5 GUI."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt


class VerificationCodeDialog(QDialog):
    """Dialog for entering Telegram verification code."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Telegram Verification")
        self.setGeometry(300, 300, 400, 200)
        self.setModal(True)
        self.code = None
        
        self._setup_ui()
        self._apply_styling()
    
    def _setup_ui(self):
        """Build the dialog UI layout."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Verification Code Required")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel(
            "A verification code has been sent to your Telegram app.\n"
            "Enter the 5-digit code below:"
        )
        instructions.setStyleSheet("color: #666; margin: 10px 0;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Code input
        code_label = QLabel("Verification Code *")
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("e.g., 12345")
        self.code_input.setMaxLength(5)
        self.code_input.setAlignment(Qt.AlignCenter)
        code_font = QFont()
        code_font.setPointSize(16)
        code_font.setBold(True)
        self.code_input.setFont(code_font)
        self.code_input.setStyleSheet("""
            QLineEdit {
                padding: 15px;
                font-size: 24px;
                letter-spacing: 5px;
            }
        """)
        
        layout.addWidget(code_label)
        layout.addWidget(self.code_input)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        verify_btn = QPushButton("Verify")
        verify_btn.clicked.connect(self._verify_code)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(verify_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Focus code input on show
        self.code_input.setFocus()
    
    def _apply_styling(self):
        """Apply modern PyQt5 styling."""
        stylesheet = """
            QDialog {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #333;
            }
            QLineEdit {
                padding: 10px;
                border: 2px solid #ccc;
                border-radius: 4px;
                background-color: white;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 2px solid #2196F3;
                background-color: #f0f8ff;
            }
            QPushButton {
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                background-color: #2196F3;
                color: white;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """
        self.setStyleSheet(stylesheet)
    
    def _verify_code(self):
        """Verify and save the code."""
        code = self.code_input.text().strip()
        
        if not code:
            QMessageBox.warning(self, "Validation Error", "Please enter a code")
            return
        
        if len(code) != 5 or not code.isdigit():
            QMessageBox.warning(
                self,
                "Validation Error",
                "Code must be 5 digits (e.g., 12345)"
            )
            return
        
        self.code = code
        self.accept()
    
    def get_code(self) -> str:
        """Get the entered verification code."""
        return self.code
