"""Utility functions for GUI application."""

from typing import Any
from gui.config_manager import ConfigManager

def get_config_dict_list(manager: ConfigManager) -> list[dict[str, Any]]:
    """
    Get a list of config dictionaries from the ConfigManager.
    
    Args:
        manager (ConfigManager): The ConfigManager instance.
    
    Returns:
        list[dict[str, Any]]: A list of dictionaries representing the configs.
    """
    return [cfg.to_dict() for cfg in manager.configs]
