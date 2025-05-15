import json
import os
from typing import Any

class SettingsManager:
    """
    A manager for application settings that handles loading, saving, and accessing
    configuration values.
    This class provides functionality to manage application settings through a JSON file.
    Settings can be accessed and modified using dot notation for nested configurations.
    Attributes:
        settings (dict): Dictionary containing the application settings.
    Args:
        path (str, optional): Path to the JSON configuration file. Defaults to "settings.json".
    Examples:
        >>> settings = SettingsManager("app_settings.json")
        >>> settings.load_config()  # Load existing settings or initialize empty
        >>> theme = settings.get("appearance.theme", "light")  # Get with default
        >>> settings.set("appearance.theme", "dark")  # Set nested value
        >>> settings.save_config()  # Save changes to file
    Notes:
        - The class handles common file operation errors and provides fallbacks.
        - Settings are stored in a nested dictionary structure.
        - Accessing non-existent settings with get() returns the provided default value.
        - Setting values with dot notation automatically creates necessary nested structures.
    """
    settings: dict[str, Any] = {}

    def __init__(self, path: str = "settings.json"):
        self._path = path
        self.load_config()

    @property
    def path(self):
        """Get the path to the config file."""
        return self._path

    def load_config(self):
        """Load settings from the config file."""
        try:
            if os.path.exists(self._path):
                with open(self._path, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
            else:
                self.settings = {}
            return True
        except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
            print(f"Error loading config: {e}")
            self.settings = {}
            return False

    def save_config(self):
        """Save current settings to the config file."""
        try:
            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4)
            return True
        except (FileNotFoundError, PermissionError, OSError) as e:
            print(f"Error saving config: {e}")
            return False

    def get(self, key: str, default: Any = None, save = False) -> Any:
        """
        Get a value from settings using dot notation.
        
        Example: 
            settings.get("appearance.theme")
        """
        parts = key.split('.')
        current = self.settings

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        
        if save:
            self.save_config()

        return current

    def set(self, key: str, value: Any, save = False) -> None:
        """
        Set a value in settings using dot notation.
        
        Example:
            settings.set("appearance.theme", "dark")
        """
        parts = key.split('.')
        current = self.settings

        # Navigate the dictionary structure
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]

        # Set the value at the final level
        current[parts[-1]] = value

        if save:
            self.save_config()
