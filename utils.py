"""Shared utility functions for the application."""

import os
import sys

def get_application_path():
    """
    Returns the base path of the application, works both in development
    and when packaged with PyInstaller.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller creates a temporary folder and stores path in _MEIPASS
        application_path = getattr(sys, '_MEIPASS')
    else:
        # Get the directory of the main script when running normally
        application_path = os.path.dirname(os.path.abspath(sys.argv[0]))

    return application_path
