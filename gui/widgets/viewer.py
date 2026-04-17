"""Base viewer classes for file preview."""

from typing import Optional

from PySide6 import QtWidgets

from core.file import IFile


class Viewer(QtWidgets.QWidget):
    """Base class for all file viewers."""
    
    name: str = "Base Viewer"
    accepted_extensions: list[str] = []
    allow_unsupported_extensions: bool = False
    
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
    
    def set_file(self, file: IFile):
        """Load and display a file.
        
        Args:
            file: The file to display
            
        Raises:
            ValueError: If the file cannot be displayed
        """
        raise NotImplementedError("Subclasses must implement set_file()")
    
    def unload_file(self):
        """Unload the current file and free resources."""
        pass


class ICustomTabWindow:
    """Interface for viewers that need custom tab window setup."""
    
    @staticmethod
    def setup_tab_window(window: QtWidgets.QMainWindow):
        """Setup custom tab window features.
        
        Args:
            window: The tab window to setup
            
        Raises:
            NotImplementedError: If subclass doesn't implement this method
        """
        raise NotImplementedError("Subclasses must implement setup_tab_window()")