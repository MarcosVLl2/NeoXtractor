import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from utils.config_manager import ConfigManager
from utils.console_handler import *

class IconSplitterHandle(QSplitterHandle):
    """Custom Splitter Handle with an Icon."""
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)

        icon_path = os.path.join(os.path.dirname(__file__), "../icons/splitte.png")

        # Add a QLabel with an icon or text
        self.icon_label = QLabel(self)
        self.icon_label.setPixmap(QPixmap(icon_path))
        self.icon_label.setScaledContents(True)
        self.icon_label.setAlignment(Qt.AlignCenter)

        if os.path.exists(icon_path):
            self.icon_label.setPixmap(QPixmap(icon_path))
        else:
            self.icon_label.setText("|||")

        # Adjust size and position of the icon
        self.icon_label.setFixedSize(20, 20)
        self.icon_label.move(0, 0)

    def resizeEvent(self, event):
        """Ensure the icon stays centered when the splitter handle resizes."""
        super().resizeEvent(event)
        self.icon_label.move((self.width() - self.icon_label.width()) // 2,
                             (self.height() - self.icon_label.height()) // 2)

class IconSplitter(QSplitter):
    """Custom Splitter using the Icon Handle."""
    def createHandle(self):
        return IconSplitterHandle(self.orientation(), self)

def create_main_viewer_tab(self):
        self.config_manager = ConfigManager()
        self.output_folder = self.config_manager.get("output_folder", "")

        # ------------------------------------------------------------------------------------------------------------
        # Main Tab
        tab1 = QWidget()
        main_layout = QHBoxLayout(tab1)

        # Left side setup (Main)
        left_column_widget = QWidget()
        left_column = QVBoxLayout(left_column_widget)

        # Filter bar for QListWidget
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Search or filter items...")
        self.filter_input.textChanged.connect(self.filter_list_items)
        self.filter_input.setFixedWidth(200)
        self.filter_input.setToolTip("Type to filter the file list.")
        left_column.addWidget(self.filter_input)

        # File list setup
        self.file_list_widget = QListWidget()
        self.file_list_widget.itemPressed.connect(self.on_item_clicked)
        self.file_list_widget.installEventFilter(self)
        self.file_list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.file_list_widget.setToolTip("List of files in the loaded NPK.")
        left_column.addWidget(self.file_list_widget)
        # ------------------------------------------------------------------------------------------------------------

        # ------------------------------------------------------------------------------------------------------------
        # Right side setup (Main)
        right_column_widget = QWidget()
        right_column = QVBoxLayout(right_column_widget)

        # Output folder selection status bar
        self.output_folder_label = QLabel(f"Welcome!")
        self.output_folder_label.setFixedHeight(10)
        right_column.addWidget(self.output_folder_label)

        self.main_view_console_label = QLabel("    Log: ")
        self.main_view_console_label.setFixedHeight(20)
        self.main_view_console_label.alignment=Qt.AlignCenter
        right_column.addWidget(self.main_view_console_label)

        # Console output in the Main tab
        self.main_console = ConsoleWidget(self.console_handler)
        right_column.addWidget(self.main_console)
        
        horizontal_buttons_widget = QWidget()
        horizontal_buttons_layout = QHBoxLayout(horizontal_buttons_widget)
        horizontal_buttons_layout.alignment=Qt.AlignLeft
        self.read_all_files = QPushButton("Read all files")
        self.read_all_files.setFixedSize(100,30)
        self.read_all_files.pressed.connect(self.read_all_npk_data)
        self.read_all_files.setToolTip("Read all files from the loaded NPK.")
        horizontal_buttons_layout.addWidget(self.read_all_files)
        
        self.extract_all_files = QPushButton("Extract all files")
        self.extract_all_files.setFixedSize(100,30)
        self.extract_all_files.pressed.connect(self.extract_all_npk_data)
        horizontal_buttons_layout.addWidget(self.extract_all_files)
        horizontal_buttons_layout.addSpacerItem(QSpacerItem(1,1,QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))
        horizontal_buttons_widget.setLayout(horizontal_buttons_layout)
        right_column.addWidget(horizontal_buttons_widget)

        horizontal_buttons_layout.addSpacerItem(
            QSpacerItem(1, 1, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        )
        horizontal_buttons_widget.setLayout(horizontal_buttons_layout)
        right_column.addWidget(horizontal_buttons_widget)

        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Please choose a NPK file to process.")
        self.status_bar.setFixedHeight(15)
        right_column.addWidget(self.status_bar)

        # Add progress bar for read_all and extract_all npk data
        self.progress_bar = QProgressBar()
        self.progress_bar.setToolTip("Progress for file operations.")
        right_column.addWidget(self.progress_bar)
        # ------------------------------------------------------------------------------------------------------------

        # Splitter setup
        left_right_splitter = IconSplitter(Qt.Horizontal)
        left_right_splitter.addWidget(left_column_widget)
        left_right_splitter.addWidget(right_column_widget)
        left_right_splitter.setFixedWidth(50)

        # Set stretch factors for dynamic resizing
        left_right_splitter.setStretchFactor(0, 1)  # Left column resizes dynamically
        left_right_splitter.setStretchFactor(1, 2)  # Right column gets more space

        # Allow user resizing
        left_right_splitter.setCollapsible(0, False)
        left_right_splitter.setCollapsible(1, False)

        main_layout.addWidget(left_right_splitter)

        return tab1