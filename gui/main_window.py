import os, json
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from utils.config_manager import ConfigManager

from utils.console_handler import *
from logger import logger

config_manager = ConfigManager() # Fetch Outputfolder from config manager
output_folder = config_manager.get("output_folder", "")
project_folder = config_manager.get("project_folder", "")
g_config = config_manager.get("game_config", "")
npk_type = config_manager.get("npk_type", 0)
decryption_key = config_manager.get("decryption_key", 0)
aes_key = config_manager.get("aes_key", 0)
index_size = config_manager.get("index_size", 0)

class IconSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.icon_label = QLabel(self)
        self.icon_label.setScaledContents(True)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedSize(80, 80)
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.icon_label.move((self.width() - self.icon_label.width()) // 2,
                             (self.height() - self.icon_label.height()) // 2)

class IconSplitter(QSplitter):
    def createHandle(self):
        return IconSplitterHandle(self.orientation(), self)


def create_main_viewer_tab(self):
    tab1 = QWidget()
    main_layout = QHBoxLayout(tab1)

    # Right side setup (Main)
    left_column_widget = QWidget()
    left_column = QVBoxLayout(left_column_widget)

    self.create_file_menu()
    self.create_help_menu()
    self.create_edit_menu()
    self.create_extraction_menu()
    self.create_tools_menu()
  
    self.list = QListView()
    self.list.doubleClicked.connect(self.on_item_double_clicked)
    self.list.clicked.connect(self.on_item_double_clicked)
    self.list_model = QStandardItemModel(self)
    self.list.setModel(self.list_model)

    # self.list.installEventFilter(self)

    # Status bar
    self.status_bar2 = QStatusBar()
    self.status_bar2.showMessage(f"Game Config: {g_config}")

    self.filter_input = QLineEdit(self)
    self.filter_input.setPlaceholderText("Search...")
    self.filter_input.textChanged.connect(self.filter_list_items)

    self.filter_combobox = QComboBox(self)
    self.filter_combobox.setEditable(False)
    # self.filter_combobox.lineEdit().setPlaceholderText("Search...")
    combo_items = ["ALL", "MESH", "TEXTURE", "CHARACTER", "SKIN", "TEXT FORMAT"]
    self.filter_combobox.addItems(combo_items)
    self.filter_combobox.currentIndexChanged.connect(self.filter_list_items)

    # Filtered mesh Checkbox
    self.filtered_mesh_checkbox = QCheckBox("Load 'biped head' mesh")
    self.filtered_mesh_checkbox.setChecked(False)

    # Status bar
    self.status_bar = QStatusBar()
    self.status_bar.showMessage("Please choose a file to process.")

    self.progress_bar = QProgressBar()

    # Horizontal buttons
    horizontal_buttons_widget = QWidget()
    horizontal_buttons_layout = QHBoxLayout(horizontal_buttons_widget)

    self.set_output_button = QPushButton("SET OUTPUT")
    self.set_output_button.setFixedSize(100, 30)
    self.set_output_button.pressed.connect(self.set_output)

    self.extract_all_files = QPushButton("UNPACK NPK")
    self.extract_all_files.setFixedSize(100, 30)
    self.extract_all_files.pressed.connect(self.extract_processed_npk_data)

    left_column.addWidget(self.status_bar2)
    left_column.addWidget(self.filter_input)
    left_column.addWidget(self.filter_combobox)
    left_column.addWidget(self.filtered_mesh_checkbox)
    left_column.addWidget(self.list)
    left_column.addWidget(self.status_bar)
    left_column.addWidget(self.progress_bar)
    left_column.addWidget(horizontal_buttons_widget)

    horizontal_buttons_layout.addStretch()
    horizontal_buttons_layout.addWidget(self.set_output_button)
    horizontal_buttons_layout.addWidget(self.extract_all_files)
    horizontal_buttons_layout.addStretch()

    main_layout.addWidget(left_column_widget)

    # ------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------
    # Right side setup (Main)
    right_column_widget = QWidget()
    right_column = QVBoxLayout(right_column_widget)

    self.main_console = ConsoleWidget(self.console_handler)
    right_column.addWidget(self.main_console)

    main_layout.addWidget(right_column_widget)

    return tab1
    # ------------------------------------------------------------------------------------------------------------

def load_data_into_list(self, external_data, json_file):
    try:
        # Load the JSON file
        if not os.path.exists(json_file):
            print(f"JSON file {json_file} not found. Aborting load.")
            logger.debug(f"JSON file {json_file} not found. Aborting load.")
            return

        with open(json_file, 'r') as file:
            data = json.load(file)
            hash_mapping = data.get("characters", {})  # Get hash-to-filename mapping
            print(f"Loaded JSON: {hash_mapping}")
            logger.debug(f"Loaded JSON: {hash_mapping}")

        # Clear the existing model data
        self.list_model.clear()

        # Populate the model with updated data
        for i, entry in enumerate(external_data):
            # Get the name from hash_mapping or use entry as a fallback
            display_name = hash_mapping.get(entry, entry)
            item = QStandardItem(display_name)
            item.setData(entry, Qt.UserRole)  # Store the index in UserRole
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Prevent edit
            item.setIcon(QIcon.fromTheme("document"))  # Optional: Add an icon
            self.list_model.appendRow(item)

        self.list.setModel(self.list_model)

        print("List model updated successfully.")
        logger.debug("List model updated successfully.")

    except Exception as e:
        self.status_bar.showMessage(f"Error loading data into list: {str(e)}")
        print(f"Error details: {str(e)}")
        logger.debug(f"Error details: {str(e)}")

