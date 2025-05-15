"""NeoXtractor entrypoint"""

import sys
from PySide6 import QtWidgets

from gui.windows.main_window import MainWindow

def run_gui():
    """Run NeoXtractor as a GUI application."""
    app = QtWidgets.QApplication(sys.argv)

    main_window = MainWindow()
    main_window.resize(1600, 900)
    main_window.show()

    sys.exit(app.exec())

def run_cli():
    """Run NeoXtractor as a CLI application."""
    raise NotImplementedError("CLI mode is not implemented yet.")

if __name__ == "__main__":
    run_gui()