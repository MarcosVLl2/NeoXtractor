"""Dialog for creating a new game configuration."""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, 
                              QLineEdit, QDialogButtonBox,
                              QSpinBox)

from core.config import Config

class NewConfigDialog(QDialog):
    """Dialog for creating a new game configuration."""

    def __init__(self, parent=None):
        """Initialize the new config dialog.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Create New Config")
        self.setMinimumWidth(300)

        # Create layout
        self.main_layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()
        self.main_layout.addLayout(self.form_layout)

        # Config name field
        self.name_edit = QLineEdit()
        self.form_layout.addRow("Config Name:", self.name_edit)

        # Decryption key field
        self.key_edit = QSpinBox()
        self.key_edit.setMinimum(0)
        self.key_edit.setMaximum(999999)
        self.key_edit.setValue(0)  # Default value
        self.form_layout.addRow("Decryption Key (Use 0 for no key):", self.key_edit)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        def validate_and_accept():
            """Validate inputs before accepting the dialog."""
            if not self.name_edit.text().strip():
                self.name_edit.setStyleSheet("border: 1px solid red;")
                self.name_edit.setFocus()
                return
            self.accept()

        self.button_box.accepted.connect(validate_and_accept)

        self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)

    def get_config(self):
        """Get the created config.
        
        Returns:
            Config: The newly created config
        """
        config = Config()
        config.name = self.name_edit.text()

        decryption_key = self.key_edit.value()
        if decryption_key == 0:
            config.decryption_key = None
        else:
            config.decryption_key = decryption_key
        return config
