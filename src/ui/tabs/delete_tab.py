"""
Delete Bot Tab - removes all bot data and files, then exits the application.
"""

import logging
import shutil
import sys
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox,
    QPushButton, QHBoxLayout, QMessageBox, QInputDialog
)
from src.database import DatabaseManager
from src.config import ConfigManager

logger = logging.getLogger(__name__)


class DeleteBotTab(QWidget):
    """Deletes all bot data and files, then closes the application."""

    def __init__(self, db: DatabaseManager, config: ConfigManager):
        super().__init__()
        self.db = db
        self.config = config
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()

        warning = QLabel("DELETE BOT — POINT OF NO RETURN")
        warning.setStyleSheet(
            "font-weight: bold; color: #FFFFFF; background-color: #CC0000; padding: 10px;"
        )
        layout.addWidget(warning)

        info = QLabel(
            "The following files will be permanently deleted:\n\n"
            "  • Database (telegrambot.db)\n"
            "  • Configuration (config/config.json)\n"
            "  • Session files (pyrogram_sessions/)\n"
            "  • Log files (logs/)\n"
            "  • Backups (backups/)\n\n"
            "The application will close after deletion.\n"
            "This cannot be undone."
        )
        layout.addWidget(info)

        self.confirm1 = QCheckBox("I understand this will delete all data and files")
        self.confirm2 = QCheckBox("I accept that this action cannot be reversed")
        layout.addWidget(self.confirm1)
        layout.addWidget(self.confirm2)

        button_layout = QHBoxLayout()
        self.delete_btn = QPushButton("Delete Everything and Exit")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete)

        cancel_btn = QPushButton("No, Take Me Back")
        cancel_btn.clicked.connect(self._cancel)

        def update_btn():
            self.delete_btn.setEnabled(self.confirm1.isChecked() and self.confirm2.isChecked())

        self.confirm1.stateChanged.connect(update_btn)
        self.confirm2.stateChanged.connect(update_btn)

        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        layout.addStretch()
        self.setLayout(layout)

    def _cancel(self):
        self.confirm1.setChecked(False)
        self.confirm2.setChecked(False)

    def _delete(self):
        # Require the user to type DELETE to confirm
        text, ok = QInputDialog.getText(
            self,
            "Final Confirmation",
            'Type DELETE (all caps) to confirm:',
        )
        if not ok or text.strip() != "DELETE":
            QMessageBox.information(self, "Cancelled", "Deletion cancelled.")
            return

        errors = []

        def remove(path: Path):
            try:
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
            except Exception as e:
                errors.append(f"{path}: {e}")

        # Close DB connection before deleting the file
        try:
            self.db.connection = None
        except Exception:
            pass

        targets = [
            Path("telegrambot.db"),
            Path("config/config.json"),
            Path("pyrogram_sessions"),
            Path("logs"),
            Path("backups"),
        ]
        for target in targets:
            remove(target)

        if errors:
            logger.error(f"Deletion completed with errors: {errors}")
            QMessageBox.warning(
                self,
                "Deletion Completed with Errors",
                "Some files could not be deleted:\n\n" + "\n".join(errors) +
                "\n\nThe application will now close.",
            )
        else:
            logger.info("Bot deletion completed — exiting")
            QMessageBox.information(
                self, "Deleted", "All files have been deleted. The application will now close."
            )

        sys.exit(0)
