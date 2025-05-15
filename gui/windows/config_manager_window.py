"""Config Manager Window for managing game configurations."""

import os
import json

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                               QListWidget, QPushButton, QFileDialog,
                               QMessageBox, QAbstractItemView)

from core.config import Config
from gui.config_manager import ConfigManager

class ConfigManagerWindow(QDialog):
    """Config Manager Dialog for managing game configurations."""

    def __init__(self, config_manager: ConfigManager, parent=None):
        """Initialize the config manager window.
        
        Args:
            config_manager: The config manager instance to use
            parent: Parent widget
        """
        super().__init__(parent)
        self.config_manager = config_manager

        self.setWindowTitle("Config Manager")
        self.setMinimumSize(500, 400)

        # Create layout
        self.main_layout = QHBoxLayout(self)

        # Left side - Config list
        self.config_list = QListWidget()
        # Enable multiple selection for delete/export operations
        self.config_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.main_layout.addWidget(self.config_list, 3)  # Give it 3 parts of the layout

        # Right side - Buttons
        self.button_layout = QVBoxLayout()
        self.main_layout.addLayout(self.button_layout, 1)  # Give it 1 part of the layout

        # Create buttons
        self.add_button = QPushButton("Add")
        self.delete_button = QPushButton("Delete")
        self.import_button = QPushButton("Import")
        self.export_button = QPushButton("Export")

        # Add buttons to layout with some spacing
        self.button_layout.addWidget(self.add_button)
        self.button_layout.addWidget(self.delete_button)
        self.button_layout.addSpacing(20)
        self.button_layout.addWidget(self.import_button)
        self.button_layout.addWidget(self.export_button)
        self.button_layout.addStretch()  # Push buttons to the top

        # Connect signals
        self.add_button.clicked.connect(self.add_config)
        self.delete_button.clicked.connect(self.delete_config)
        self.import_button.clicked.connect(self.import_config)
        self.export_button.clicked.connect(self.export_config)

        # Load configs into list
        self.refresh_config_list()

    def refresh_config_list(self):
        """Refresh the config list from the config manager."""
        self.config_list.clear()
        for config in self.config_manager.configs:
            self.config_list.addItem(config.name)

    def add_config(self):
        """Add a new config."""
        # This is a placeholder - in a real app, you'd show a dialog to create a new config
        try:
            # For demo purposes, create a simple config
            new_config = Config()
            new_config.name = f"NewConfig_{len(self.config_manager.configs) + 1}"
            new_config.decryption_key = 12345  # Sample key

            self.config_manager.add_config(new_config)
            self.refresh_config_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add config: {str(e)}")

    def delete_config(self):
        """Delete the selected configs."""
        selected_items = self.config_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select at least one config to delete.")
            return

        try:
            # Delete all selected configs
            for item in selected_items:
                config_name = item.text()
                self.config_manager.remove_config(config_name)

            self.refresh_config_list()

            # Show confirmation message
            if len(selected_items) == 1:
                QMessageBox.information(self, "Success", "Config deleted successfully.")
            else:
                QMessageBox.information(self, "Success",
                                        f"{len(selected_items)} configs deleted successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete config(s): {str(e)}")

    def import_config(self):
        """Import a config from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Config", "", "JSON Files (*.json)"
        )

        if not file_path:
            return  # User cancelled

        try:
            config = Config.from_file(file_path)
            self.config_manager.add_config(config)
            self.refresh_config_list()
            QMessageBox.information(self, "Success", f"Imported config: {config.name}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import config: {str(e)}")

    def export_config(self):
        """Export the selected config(s)."""
        selected_items = self.config_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select at least one config to export.")
            return

        selected_configs = []
        for item in selected_items:
            config_name = item.text()
            selected_configs.append(self.config_manager.get_config(config_name))

        if not selected_configs:
            QMessageBox.critical(self, "Error", "No matching configs found.")
            return

        if len(selected_configs) == 1:
            # Single config: Save to file
            config = selected_configs[0]
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Config", f"{config.name}.json", "JSON Files (*.json)"
            )

            if not file_path:
                return  # User cancelled

            try:
                with open(file_path, "w", encoding="utf-8") as config_file:
                    # Create a dictionary representing the config
                    config_dict = {
                        "name": config.name,
                        "decryption_key": config.decryption_key
                    }
                    json.dump(config_dict, config_file, indent=4)

                QMessageBox.information(self, "Success", f"Exported config to: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export config: {str(e)}")
        else:
            # Multiple configs: Save to directory
            dir_path = QFileDialog.getExistingDirectory(
                self, "Select Directory to Export Configs"
            )

            if not dir_path:
                return  # User cancelled

            try:
                successful_exports = 0
                for config in selected_configs:
                    file_path = os.path.join(dir_path, f"{config.name}.json")
                    with open(file_path, "w", encoding="utf-8") as config_file:
                        config_dict = {
                            "name": config.name,
                            "decryption_key": config.decryption_key
                        }
                        json.dump(config_dict, config_file, indent=4)
                    successful_exports += 1

                QMessageBox.information(
                    self, 
                    "Success", 
                    f"Exported {successful_exports} configs to: {dir_path}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export configs: {str(e)}")
