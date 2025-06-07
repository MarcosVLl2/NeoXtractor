"""
Temporary utility script for simulating PyInstaller environment during development.

This module sets up the environment to mimic a frozen (compiled) Python application
by modifying sys attributes and adjusting the Python path. This is useful for
testing application modules that have different behavior when running as a
PyInstaller executable versus running as a regular Python script.

Attributes set:
    sys.frozen: Set to True to simulate a frozen/compiled state
    sys._MEIPASS: Set to the parent directory path to simulate PyInstaller's
                  temporary extraction directory

The script also adds the parent directory to sys.path to enable importing
of application modules during development testing.
"""

import sys
import os

# Simulate frozen state
setattr(sys, 'frozen', True)
# Simulate PyInstaller _MEIPASS
setattr(sys, '_MEIPASS', os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

# Add parent directory to path for importing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
