"""Patch for archspec to fix FileNotFoundError."""

import os
import sys

from core.utils import get_application_path

if hasattr(sys, "_MEIPASS"):
    # Set correct path for archspec
    os.environ["ARCHSPEC_CPU_DIR"] = os.path.join(get_application_path(), "archspec", "json", "cpu")
