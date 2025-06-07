"""Theme management system for NeoXtractor."""

import os
import re
import json
from typing import Optional, Dict, Any, cast
from PySide6 import QtCore, QtWidgets
from core.logger import get_logger
from core.utils import get_application_path


class ThemeManager(QtCore.QObject):
    """Central theme manager for the application."""

    theme_changed = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self._current_theme: str | None = None  # None = system theme
        self._app = cast(QtWidgets.QApplication, QtWidgets.QApplication.instance())
        self._logger = get_logger()

        # Path to themes directory
        self._themes_path = os.path.join(get_application_path(), "data", "themes")

        # Cache for loaded themes
        self._theme_cache: Dict[str, Dict[str, Any]] = {}

        # Load theme definitions
        self._load_theme_definitions()

    def get_current_theme(self) -> str | None:
        """Get the currently active theme."""
        return self._current_theme

    def set_theme(self, theme: str | None) -> None:
        """Set the application theme.
        
        Args:
            theme: Theme name or None for system theme
        """
        if theme == self._current_theme:
            return

        theme_name = theme if theme is not None else "system"
        self._logger.info("Switching theme to: %s", theme_name)
        self._current_theme = theme

        if theme is None:
            self._apply_system_theme()
        else:
            self._apply_custom_theme(theme)

        self.theme_changed.emit(theme_name)

    def _load_theme_definitions(self) -> None:
        """Load theme definitions from theme files."""
        if not os.path.exists(self._themes_path):
            self._logger.warning("Themes directory not found: %s", self._themes_path)
            return

        # Discover themes by scanning the themes directory
        try:
            for item in os.listdir(self._themes_path):
                theme_dir = os.path.join(self._themes_path, item)
                if os.path.isdir(theme_dir):
                    try:
                        self._load_theme_from_directory(item, theme_dir)
                    except Exception as e:
                        self._logger.error("Failed to load theme %s: %s", item, e)
        except OSError as e:
            self._logger.error("Error reading themes directory: %s", e)
            return

        self._logger.info("Loaded %d themes from files", len(self._theme_cache))

    def _load_theme_from_directory(self, theme_name: str, theme_dir: str) -> None:
        """Load a theme from its directory."""
        def_file = os.path.join(theme_dir, "definition.json")
        style_file = os.path.join(theme_dir, "style.qss")

        if not os.path.exists(def_file):
            raise FileNotFoundError(f"Definition file not found: {def_file}")

        if not os.path.exists(style_file):
            raise FileNotFoundError(f"Style file not found: {style_file}")

        # Load definition
        with open(def_file, 'r', encoding='utf-8') as f:
            definition = json.load(f)

        # Load stylesheet template
        with open(style_file, 'r', encoding='utf-8') as f:
            style_template = f.read()

        # Extract theme metadata
        theme_info = {
            'name': definition.get('name', theme_name),
            'base': definition.get('base', 'custom'),
            'description': definition.get('description', ''),
            'colors': definition.get('colors', {}),
            'style_template': style_template
        }

        self._theme_cache[theme_name] = theme_info

        self._logger.debug("Loaded theme: %s - %s (%s)", theme_name, theme_info['name'], theme_info['base'])

    def _apply_system_theme(self) -> None:
        """Apply system theme by resetting to default style."""
        if self._app and isinstance(self._app, QtWidgets.QApplication):
            self._app.setStyleSheet("")
            # Let Qt use the system's default style

    def _apply_custom_theme(self, theme: str) -> None:
        """Apply a custom theme using stylesheets."""
        if not self._app or not isinstance(self._app, QtWidgets.QApplication):
            return

        theme_data = self._theme_cache.get(theme)
        if not theme_data:
            self._logger.warning("No theme data found for theme: %s", theme)
            return

        colors = theme_data.get('colors', {})
        style_template = theme_data.get('style_template', '')

        if not colors or not style_template:
            self._logger.warning("Incomplete theme data for theme: %s", theme)
            return

        stylesheet = self._generate_stylesheet_from_template(style_template, colors)
        self._app.setStyleSheet(stylesheet)

    def _generate_stylesheet_from_template(self, template: str, colors: Dict[str, Any]) -> str:
        """Generate Qt stylesheet from template and colors."""
        try:
            # Flatten the color structure for template substitution
            flattened_colors = {}

            if 'palette' in colors:
                flattened_colors.update(colors['palette'])

            # Add custom colors with prefixed keys for specific use cases
            if 'custom' in colors:
                for category, category_colors in colors['custom'].items():
                    if isinstance(category_colors, dict):
                        for key, value in category_colors.items():
                            flattened_colors[f"{category}_{key}"] = value

            # Also add the raw colors if they're already flattened
            if all(isinstance(v, str) for v in colors.values()):
                flattened_colors.update(colors)

            # Replace @variable syntax with actual color values
            # Sort by length (descending) to replace longer variable names first
            # This prevents partial matches (e.g., @disabled matching inside @text_disabled)
            result = template
            sorted_colors = sorted(flattened_colors.items(), key=lambda x: len(x[0]), reverse=True)

            for color_name, color_value in sorted_colors:
                # Use word boundaries to ensure exact matches only
                pattern = r'@' + re.escape(color_name) + r'(?![a-zA-Z0-9_])'
                result = re.sub(pattern, color_value, result)

            return result

        except Exception as e:
            self._logger.error("Error generating stylesheet: %s", e)
            return ""

    def _get_fallback_color(self, missing_key: str) -> str:
        """Get a reasonable fallback color for missing theme keys."""
        # Common fallbacks based on key name patterns
        fallback_map = {
            'background': '#ffffff',
            'surface': '#f8f9fa',
            'primary': '#1976d2',
            'secondary': '#424242',
            'text': '#212121',
            'border': '#e0e0e0',
            'hover': '#f5f5f5',
            'selected': '#e3f2fd',
            'error': '#d32f2f',
            'warning': '#f57c00',
            'success': '#388e3c',
            'info': '#1976d2'
        }

        # Try exact match first
        if missing_key in fallback_map:
            return fallback_map[missing_key]

        # Try partial matches
        for key, color in fallback_map.items():
            if key in missing_key.lower():
                return color

        # Default fallback
        return '#000000'

    def get_color(self, color_path: str) -> str:
        """Get a color value from the current theme.
        
        Args:
            color_path: Dot-separated path to the color (e.g., 'palette.primary' or 'custom.editor.background')
        
        Returns:
            The color hex value or system theme fallback
        """
        # For system theme, return hardcoded values
        if self._current_theme is None:
            return self._get_system_color(color_path)

        theme_data = self._theme_cache.get(self._current_theme)
        if not theme_data:
            return self._get_system_color(color_path)

        colors = theme_data.get('colors', {})

        # Handle dot-separated paths
        parts = color_path.split('.')
        current = colors

        try:
            for part in parts:
                current = current[part]
            return str(current) if current else self._get_system_color(color_path)
        except (KeyError, TypeError):
            # Fallback: try simple key lookup for backward compatibility
            return colors.get(color_path, self._get_system_color(color_path))

    def _get_system_color(self, color_path: str) -> str:
        """Get hardcoded color values for system theme."""
        system_colors = {
            # Palette colors with dot notation
            'palette.background': '#ffffff',
            'palette.surface': '#f8f9fa',
            'palette.surface_variant': '#e9ecef',
            'palette.primary': '#1976d2',
            'palette.primary_variant': '#1565c0',
            'palette.secondary': '#424242',
            'palette.accent': '#ff5722',
            'palette.text': '#212121',
            'palette.text_secondary': '#757575',
            'palette.text_disabled': '#bdbdbd',
            'palette.border': '#e0e0e0',
            'palette.border_focus': '#1976d2',
            'palette.hover': '#f5f5f5',
            'palette.selected': '#e3f2fd',
            'palette.pressed': '#bbdefb',
            'palette.disabled': '#f5f5f5',
            'palette.error': '#d32f2f',
            'palette.warning': '#f57c00',
            'palette.success': '#388e3c',
            'palette.info': '#1976d2',

            # Legacy flat colors for backward compatibility
            'background': '#ffffff',
            'surface': '#f8f9fa',
            'primary': '#1976d2',
            'secondary': '#424242',
            'text': '#212121',
            'text_secondary': '#757575',
            'border': '#e0e0e0',
            'hover': '#f5f5f5',
            'selected': '#e3f2fd'
        }
        return system_colors.get(color_path, '#000000')

    def get_palette_colors(self) -> Dict[str, str]:
        """Get all palette colors from current theme."""
        if self._current_theme is None:
            # Return system theme colors
            return {
                'background': '#ffffff',
                'surface': '#f8f9fa',
                'surface_variant': '#e9ecef',
                'primary': '#1976d2',
                'primary_variant': '#1565c0',
                'secondary': '#424242',
                'accent': '#ff5722',
                'text': '#212121',
                'text_secondary': '#757575',
                'text_disabled': '#bdbdbd',
                'border': '#e0e0e0',
                'border_focus': '#1976d2',
                'hover': '#f5f5f5',
                'selected': '#e3f2fd',
                'pressed': '#bbdefb',
                'disabled': '#f5f5f5',
                'error': '#d32f2f',
                'warning': '#f57c00',
                'success': '#388e3c',
                'info': '#1976d2'
            }

        theme_data = self._theme_cache.get(self._current_theme)
        if not theme_data:
            return {}

        colors = theme_data.get('colors', {})
        return colors.get('palette', {})

    def get_custom_colors(self, category: str) -> Dict[str, str]:
        """Get custom colors for a specific category.
        
        Args:
            category: The category name (e.g., 'editor', 'syntax', 'hex')
        
        Returns:
            Dictionary of color names to hex values
        """
        if self._current_theme is None:
            # System theme has no custom colors
            return {}

        theme_data = self._theme_cache.get(self._current_theme)
        if not theme_data:
            return {}

        colors = theme_data.get('colors', {})
        custom = colors.get('custom', {})
        return custom.get(category, {})

    def get_available_themes(self) -> Dict[str, Dict[str, str]]:
        """Get information about all available themes.
        
        Returns:
            Dictionary mapping theme names to their metadata
        """
        themes = {}
        for theme_name, theme_data in self._theme_cache.items():
            themes[theme_name] = {
                'name': theme_data.get('name', theme_name),
                'description': theme_data.get('description', ''),
                'base': theme_data.get('base', 'custom')
            }
        return themes

    def get_theme_info(self, theme_name: str) -> Dict[str, str]:
        """Get metadata for a specific theme.
        
        Args:
            theme_name: The theme identifier
            
        Returns:
            Dictionary with theme metadata or empty dict if not found
        """
        theme_data = self._theme_cache.get(theme_name)
        if not theme_data:
            return {}

        return {
            'name': theme_data.get('name', theme_name),
            'description': theme_data.get('description', ''),
            'base': theme_data.get('base', 'custom')
        }

    @staticmethod
    def instance() -> 'ThemeManager':
        """Get the global theme manager instance."""
        app = QtWidgets.QApplication.instance()
        if not app:
            raise RuntimeError("No QApplication instance found")

        theme_manager = app.property("theme_manager")
        if not theme_manager:
            theme_manager = ThemeManager()
            app.setProperty("theme_manager", theme_manager)

        return theme_manager
