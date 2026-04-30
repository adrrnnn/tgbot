"""
Telegram Accounts Tab
Manage profiles for Telegram accounts
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QDialog, QLineEdit, QCheckBox, QFormLayout,
    QMessageBox, QAbstractItemView, QMenu, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from src.database import DatabaseManager
from src.config import ConfigManager


class AccountFormDialog(QDialog):
    """Dialog for adding/editing Telegram accounts"""
    
    def __init__(self, parent=None, db=None, account_data=None):
        super().__init__(parent)
        self.db = db
        self.account_data = account_data
        self.is_edit = account_data is not None
        
        self.setWindowTitle("Edit Account" if self.is_edit else "Add New Account")
        self.setModal(True)
        self.setGeometry(200, 200, 500, 350)
        
        self._setup_ui()
        
        if self.is_edit:
            self._load_account_data()
    
    def _setup_ui(self):
        """Setup form UI"""
        layout = QFormLayout()
        
        # Account Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Personal, Work, Bot Testing")
        layout.addRow("Account Name *", self.name_input)
        
        # Phone
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("+1234567890")
        layout.addRow("Phone Number *", self.phone_input)
        
        # 2FA Password
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Leave blank if not using 2FA")
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addRow("2FA Password (Optional)", self.password_input)
        
        # Set as active (only for add mode)
        if not self.is_edit:
            self.active_checkbox = QCheckBox("Set as active account")
            self.active_checkbox.setChecked(True)
            layout.addRow("", self.active_checkbox)
        
        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        clear_btn = QPushButton("Clear")
        
        save_btn.clicked.connect(self._save)
        cancel_btn.clicked.connect(self.reject)
        clear_btn.clicked.connect(self._clear_fields)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(clear_btn)
        layout.addRow("", button_layout)
        
        self.setLayout(layout)
    
    def _load_account_data(self):
        """Load existing account data into form"""
        if self.account_data:
            self.name_input.setText(self.account_data.get('name', ''))
            self.phone_input.setText(self.account_data.get('phone', ''))
            # Don't load password for security
    
    def _clear_fields(self):
        """Clear all form fields"""
        self.name_input.clear()
        self.phone_input.clear()
        self.password_input.clear()
    
    def _validate_inputs(self) -> bool:
        """Validate form inputs"""
        import re
        name = self.name_input.text().strip()
        phone = self.phone_input.text().strip()
        password = self.password_input.text().strip()
        
        # Check required fields
        if not name:
            QMessageBox.warning(self, "Validation Error", "Account name is required")
            return False
        
        if len(name) < 2 or len(name) > 50:
            QMessageBox.warning(self, "Validation Error", "Account name must be 2-50 characters")
            return False
        
        if not phone:
            QMessageBox.warning(self, "Validation Error", "Phone number is required")
            return False
        
        # Validate phone format
        if not re.match(r'^\+?\d{10,15}$', phone.replace(' ', '').replace('-', '')):
            QMessageBox.warning(self, "Validation Error", "Invalid phone format")
            return False
        
        if password and len(password) < 4:
            QMessageBox.warning(self, "Validation Error", "Password must be at least 4 characters")
            return False
        
        return True
    
    def _save(self):
        """Save account to database"""
        if not self._validate_inputs():
            return
        
        try:
            name = self.name_input.text().strip()
            phone = self.phone_input.text().strip()
            password = self.password_input.text().strip() or None
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                if self.is_edit and self.account_data:
                    # Update
                    cursor.execute(
                        """UPDATE accounts 
                           SET name = ?, phone = ?, password = ?, updated_at = datetime('now')
                           WHERE id = ?""",
                        (name, phone, password, self.account_data['id'])
                    )
                else:
                    # Check for duplicate phone
                    cursor.execute("SELECT id FROM accounts WHERE phone = ?", (phone,))
                    if cursor.fetchone():
                        QMessageBox.warning(self, "Duplicate", "An account with this phone already exists")
                        return
                    
                    # Check for duplicate name
                    cursor.execute("SELECT id FROM accounts WHERE name = ?", (name,))
                    if cursor.fetchone():
                        QMessageBox.warning(self, "Duplicate", "An account with this name already exists")
                        return
                    
                    # Insert new
                    is_active = self.active_checkbox.isChecked() if not self.is_edit else False
                    cursor.execute(
                        """INSERT INTO accounts 
                           (account_type, name, phone, password, is_active, created_at)
                           VALUES (?, ?, ?, ?, ?, datetime('now'))""",
                        ('telegram', name, phone, password, is_active)
                    )
            
            QMessageBox.information(self, "Success", "Account saved successfully")
            self.accept()
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save account: {e}")
    
    def get_account_data(self):
        """Return account data"""
        return {
            'name': self.name_input.text().strip(),
            'phone': self.phone_input.text().strip(),
            'password': self.password_input.text().strip() or None,
        }


class TelegramAccountsTab(QWidget):
    """Tab for managing Telegram accounts"""
    
    def __init__(self, db: DatabaseManager, config: ConfigManager):
        super().__init__()
        self.db = db
        self.config = config
        self._setup_ui()
        self.load_accounts()
    
    def _setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout()
        
        # Current Account Section
        current_group = QGroupBox("Current Account")
        current_layout = QVBoxLayout()
        
        self.current_name_label = QLabel("Account: ---")
        self.current_phone_label = QLabel("Phone: ---")
        self.current_status_label = QLabel("Status: Not Set")
        self.current_status_label.setStyleSheet("color: #FF9900;")
        
        current_layout.addWidget(self.current_name_label)
        current_layout.addWidget(self.current_phone_label)
        current_layout.addWidget(self.current_status_label)
        
        button_layout = QHBoxLayout()
        edit_btn = QPushButton("Edit")
        view_pwd_btn = QPushButton("View Details")
        edit_btn.clicked.connect(self._edit_current_account)
        view_pwd_btn.clicked.connect(self._view_password)
        button_layout.addWidget(edit_btn)
        button_layout.addWidget(view_pwd_btn)
        button_layout.addStretch()
        current_layout.addLayout(button_layout)
        
        current_group.setLayout(current_layout)
        layout.addWidget(current_group)
        
        # Accounts Table
        table_group = QGroupBox("All Saved Accounts")
        table_layout = QVBoxLayout()
        
        # Search bar
        search_layout = QHBoxLayout()
        search_label = QLabel("Search by name or phone:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter accounts...")
        self.search_input.textChanged.connect(self._filter_table)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        table_layout.addLayout(search_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["", "Name", "Phone", "Status", "Created", "Actions"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 150)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 120)
        self.table.setColumnWidth(5, 180)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        table_layout.addWidget(self.table)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)
        
        # Add button
        add_btn = QPushButton("+ Add New Account")
        add_btn.clicked.connect(self._add_account)
        layout.addWidget(add_btn)
        
        self.setLayout(layout)
    
    def load_accounts(self):
        """Load accounts from database"""
        try:
            # Clear search filter
            self.search_input.blockSignals(True)
            self.search_input.clear()
            self.search_input.blockSignals(False)
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT id, name, phone, is_active, created_at FROM accounts 
                       WHERE account_type = 'telegram'
                       ORDER BY created_at DESC"""
                )
                accounts = cursor.fetchall()
                
                # Update current account
                cursor.execute(
                    """SELECT name, phone FROM accounts 
                       WHERE account_type = 'telegram' AND is_active = 1 LIMIT 1"""
                )
                current = cursor.fetchone()
            
            if current:
                self.current_name_label.setText(f"Account: {current[0]}")
                self.current_phone_label.setText(f"Phone: {current[1]}")
                self.current_status_label.setText("Status: [OK] Active")
                self.current_status_label.setStyleSheet("color: #009900;")
            else:
                self.current_name_label.setText("Account: ---")
                self.current_phone_label.setText("Phone: ---")
                self.current_status_label.setText("Status: Not Set")
                self.current_status_label.setStyleSheet("color: #FF9900;")
            
            # Populate table
            self.table.setRowCount(len(accounts))
            for row, (acc_id, name, phone, is_active, created_at) in enumerate(accounts):
                # Radio button
                radio_item = QTableWidgetItem("●" if is_active else "○")
                radio_item.setData(Qt.UserRole, acc_id)
                radio_item.setTextAlignment(Qt.AlignCenter)
                
                # Name
                name_item = QTableWidgetItem(name)
                
                # Phone
                phone_item = QTableWidgetItem(phone)
                
                # Status
                status_item = QTableWidgetItem("Active" if is_active else "Inactive")
                status_item.setData(Qt.UserRole, acc_id)
                
                # Created
                created_item = QTableWidgetItem(created_at)
                
                # Actions buttons
                actions_widget = QWidget()
                actions_layout = QHBoxLayout()
                
                edit_btn = QPushButton("Edit")
                delete_btn = QPushButton("Delete")
                edit_btn.clicked.connect(lambda checked, aid=acc_id: self._edit_account(aid))
                delete_btn.clicked.connect(lambda checked, aid=acc_id: self._delete_account(aid))
                
                actions_layout.addWidget(edit_btn)
                actions_layout.addWidget(delete_btn)
                actions_layout.setContentsMargins(0, 0, 0, 0)
                actions_widget.setLayout(actions_layout)
                
                # Add to table
                self.table.setItem(row, 0, radio_item)
                self.table.setItem(row, 1, name_item)
                self.table.setItem(row, 2, phone_item)
                self.table.setItem(row, 3, status_item)
                self.table.setItem(row, 4, created_item)
                self.table.setCellWidget(row, 5, actions_widget)
                
                # Highlight active row
                if is_active:
                    for col in range(6):
                        item = self.table.item(row, col)
                        if item:
                            item.setBackground(QColor("#E3F2FD"))
                
                # Make radio clickable
                radio_item.setText("●" if is_active else "○")
            
            # Connect table item click for radio button selection
            self.table.itemClicked.connect(self._on_table_clicked)
        
        except Exception as e:
            print(f"Error loading accounts: {e}")
    
    def _on_table_clicked(self, item):
        """Handle table item click - for radio button selection"""
        if item.column() == 0:  # Radio column
            row = item.row()
            self._on_radio_clicked(row)
    
    def _on_radio_clicked(self, row: int):
        """Handle radio button click"""
        acc_id = self.table.item(row, 0).data(Qt.UserRole)
        self._set_account_active(acc_id)
    
    def _set_account_active(self, account_id: int):
        """Set account as active"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE accounts SET is_active = 0 WHERE account_type = 'telegram'")
                cursor.execute("UPDATE accounts SET is_active = 1 WHERE id = ?", (account_id,))
            self.load_accounts()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to set active account: {e}")
    
    def _filter_table(self, search_text: str):
        """Filter table rows by search text (name or phone)"""
        search_text = search_text.lower().strip()
        
        for row in range(self.table.rowCount()):
            # Get name and phone from columns 1 and 2
            name_item = self.table.item(row, 1)
            phone_item = self.table.item(row, 2)
            
            if name_item and phone_item:
                name = name_item.text().lower()
                phone = phone_item.text().lower()
                
                # Show row if search text matches name or phone
                if search_text in name or search_text in phone:
                    self.table.showRow(row)
                else:
                    self.table.hideRow(row)
            else:
                # Show row if no items found (safety)
                self.table.showRow(row)
    
    def _add_account(self):
        """Add new account"""
        dialog = AccountFormDialog(self, self.db)
        if dialog.exec_() == QDialog.Accepted:
            self.load_accounts()
    
    def _edit_account(self, account_id: int):
        """Edit existing account"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, phone, password FROM accounts WHERE id = ?", (account_id,))
                row = cursor.fetchone()
            
            if row:
                account_data = {
                    'id': row[0],
                    'name': row[1],
                    'phone': row[2],
                    'password': row[3],
                }
                dialog = AccountFormDialog(self, self.db, account_data)
                if dialog.exec_() == QDialog.Accepted:
                    self.load_accounts()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to edit account: {e}")
    
    def _delete_account(self, account_id: int):
        """Delete account and all related data (cascade delete)."""
        reply = QMessageBox.question(
            self, 
            "Confirm Delete", 
            "Delete this account and ALL associated data?\n\n"
            "This will permanently delete:\n"
            "• All conversations for this account\n"
            "• All messages in those conversations\n"
            "• All API keys for this account\n"
            "• All audit logs for this account\n\n"
            "This action CANNOT be undone!",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Get all conversation IDs for this account (for cascade delete)
                    cursor.execute(
                        "SELECT id FROM conversations WHERE account_id = ?",
                        (account_id,)
                    )
                    conversation_ids = [row[0] for row in cursor.fetchall()]
                    
                    # Delete messages for all conversations of this account
                    if conversation_ids:
                        placeholders = ','.join('?' * len(conversation_ids))
                        cursor.execute(
                            f"DELETE FROM messages WHERE conversation_id IN ({placeholders})",
                            conversation_ids
                        )
                    
                    # Delete conversations for this account
                    cursor.execute(
                        "DELETE FROM conversations WHERE account_id = ?",
                        (account_id,)
                    )
                    
                    # Delete API keys for this account
                    cursor.execute(
                        "DELETE FROM api_keys WHERE account_id = ?",
                        (account_id,)
                    )
                    
                    # Delete audit log entries for this account
                    try:
                        cursor.execute(
                            "DELETE FROM audit_log WHERE account_id = ?",
                            (account_id,)
                        )
                    except Exception:
                        pass  # Table may not exist yet
                    
                    # Finally delete the account itself
                    cursor.execute(
                        "DELETE FROM accounts WHERE id = ?",
                        (account_id,)
                    )
                    
                    conn.commit()
                
                QMessageBox.information(
                    self,
                    "Success",
                    "Account and all associated data deleted successfully."
                )
                self.load_accounts()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete account: {e}")
    
    def _edit_current_account(self):
        """Edit current account"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, phone, password FROM accounts WHERE is_active = 1 LIMIT 1"
                )
                row = cursor.fetchone()
            
            if row:
                self._edit_account(row[0])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to get current account: {e}")
    
    def _view_password(self):
        """View account password"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name, phone, password FROM accounts WHERE is_active = 1 LIMIT 1")
                row = cursor.fetchone()
            
            if row:
                name, phone, password = row
                msg = f"""
Telegram Account Info:

Account: {name}
Phone: {phone}
2FA Password: {"Set" if password else "Not Set"}

⚠ This information is sensitive. Don't share!
                """
                QMessageBox.information(self, "Account Details", msg)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to get account details: {e}")
    
    def _show_context_menu(self, position):
        """Show right-click context menu"""
        item = self.table.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        # Add context menu options here
        menu.exec_(self.table.mapToGlobal(position))
