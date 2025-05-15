"""Provides MainWindow class."""

import os

from PySide6 import QtWidgets, QtGui

from gui.config_manager import ConfigManager
from gui.settings_manager import SettingsManager
from gui.utils.config import get_config_dict_list
from gui.windows.config_manager_window import ConfigManagerWindow
from utils import get_application_path

class MainWindow(QtWidgets.QMainWindow):
    """Main window class."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("NeoXtractor")

        first_run = not os.path.exists("settings.json")
        self.config_manager = ConfigManager()
        self.settings_manager = SettingsManager()

        # First run, setup default settings
        if first_run:
            self.config_manager.load_from_path(os.path.join(get_application_path(), "configs"))
            self.settings_manager.set("gameconfigs",
                                      get_config_dict_list(self.config_manager),
                                      True)
        else:
            self.config_manager.add_configs(self.settings_manager.get("gameconfigs", []))

        self.main_layout = QtWidgets.QHBoxLayout()

        def file_menu() -> QtWidgets.QMenu:
            menu = QtWidgets.QMenu(title="File")

            open_file = QtGui.QAction(
                self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirOpenIcon),
                "Open File",
                self
                )
            open_file.setStatusTip("Open a NPK file.")
            open_file.setShortcut("Ctrl+O")
            menu.addAction(open_file)

            menu.addSeparator()

            config_manager = QtGui.QAction(
                self.style().standardIcon(
                    QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView
                    ),
                "Config Manager",
                self
                )
            config_manager.setStatusTip("Open the Config Manager.")
            config_manager.setShortcut("Ctrl+M")

            def open_config_manager():
                dialog = ConfigManagerWindow(self.config_manager)
                dialog.exec()

            config_manager.triggered.connect(open_config_manager)

            menu.addAction(config_manager)

            return menu

        self.menuBar().addMenu(file_menu())
