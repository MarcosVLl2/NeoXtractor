import sys, os, io, time, json, signal
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from gui.qt_theme import qt_theme

from utils.config_manager import ConfigManager
from utils.console_handler import *
from utils.util import *
from utils.extractor_utils import read_index, read_entry, determine_info_size
# from utils import FileListModel

from gui.main_window import * # create_main_viewer_tab(self)
from gui.mesh_tab import * # create_mesh_viewer_tab(self)
from gui.extraction_tab import ExtractionViewer
from gui.viewer_3d import ViewerWidget
from gui.texture_viewer import TextureViewer
from gui.plain_text_viewer import *
from gui.raw_hex_viewer import HexViewerApp
from gui.popups import AboutPopup

# from bin.read_nxfn import NxfnResultViewer
from converter import * # saveobj, savesmd, saveascii, savepmx, saveiqe, parse_mesh_original, parse_mesh_helper, parse_mesh_adaptive
from qframelesswindow import FramelessWindow
from functools import partial
from logger import logger


def custom_logging_handler(mode, context, message):
    with open("logfile.txt", "a") as log_file:
        if mode == QtDebugMsg:
            log_file.write(f"DEBUG: {message}\n")
        elif mode == QtInfoMsg:
            log_file.write(f"INFO: {message}\n")
        elif mode == QtWarningMsg:
            log_file.write(f"WARNING: {message}\n")
        elif mode == QtCriticalMsg:
            log_file.write(f"CRITICAL: {message}\n")
        elif mode == QtFatalMsg:
            log_file.write(f"FATAL: {message}\n")

qInstallMessageHandler(custom_logging_handler)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('NeoXtractor')
        self.setGeometry(150, 50, 1600, 950)
        self.npkentries = dict()

        self.config_manager = ConfigManager() # Fetch Outputfolder from config manager
        self.decryption_key = self.config_manager.get("decryption_key", 0)
        self.output_folder = self.config_manager.get("output_folder", "")
        self.project_folder = self.config_manager.get("project_folder", "")
        self.aes_key = self.config_manager.get("aes_key", 0)
        self.index_size = self.config_manager.get("index_size", 0)
        self.npk_type = self.config_manager.get("npk_type", 0)

        self.update_config_data("./configs/IDV_config.json", "Data", "npk_type", 1) # update config entry (Testing)

        # Initialize the console output handler
        self.console_handler = ConsoleOutputHandler()
        redirect_output(self.console_handler)  # Redirect stdout and stderr

        self.main_console = ConsoleWidget(self.console_handler)
        self.console_handler.add_console(self.main_console.console_output)

        # Allowed extensions for respective window implementation
        self.allowed_texture_exts = ["bmp", "gif", "jpg", "jpeg", "png", "pbm", "pgm", "ppm", "xbm", "xpm", "tga", "ico", "tiff", "dds", "pvr","astc", "ktx", "cbk"]
        self.allowed_mesh_exts = [".mesh"]
        self.allowed_text_exts = [".mtl", ".json", ".xml", ".trackgroup", ".nfx", ".h",
                                 ".shader", ".animation"]  # Only for double-clicking, context menu will still work for other formats

        # Initialize the rest of the UI
        self.initUI()

    def log_message(self):
        print("This is a print statement")
        qInstallMessageHandler(lambda mode, context, message: None) # Disable default output
        raise ValueError("This is an exception logged to file.") 

    def eventFilter(self, source, event):
        # Handle Right-Click Context Menu
        if event.type() == QEvent.ContextMenu and source is self.list:
            index = self.list.indexAt(event.pos())
            if not index.isValid():
                logger.warning("No item under cursor.")
                return True

            # Retrieve associated file index
            file_index = self.list.model().data(index, Qt.UserRole)
            if file_index is None or file_index not in self.npkentries:
                logger.debug("No valid file index associated with the item.")
                return True

            # Create Context Menu
            list_context_menu = QMenu(self)
            showdata_action = QAction("Show Data", self)
            showdata_action.triggered.connect(lambda: self.show_data(file_index))
            export_action = QAction("Export File", self)
            export_action.triggered.connect(lambda: self.extract_file())
            hex_action = QAction("Hex Viewer", self)
            hex_action.triggered.connect(lambda: self.show_hex_data())
            text_action = QAction("Plaintext Viewer", self)
            text_action.triggered.connect(lambda: self.show_text())
            texture_action = QAction("Texture Viewer", self)
            texture_action.triggered.connect(lambda: self.show_texture())
            mesh_action = QAction("Mesh Viewer", self)
            mesh_action.triggered.connect(lambda: self.show_mesh())

            # Add actions to the menu
            list_context_menu.addAction(showdata_action)
            list_context_menu.addAction(export_action)
            list_context_menu.addAction(hex_action)
            list_context_menu.addAction(text_action)
            list_context_menu.addAction(texture_action)
            list_context_menu.addAction(mesh_action)

            list_context_menu.exec_(event.globalPos())
            return True  # Block further processing

        # Handle Down Arrow Key and Skip Hidden Items
        elif event.type() == QEvent.KeyPress and event.key() == Qt.Key_Down and source is self.list:
            selected_indexes = self.list.selectionModel().selectedIndexes()
            if not selected_indexes:
                return True  # No selection, stop processing

            current_index = selected_indexes[0]
            row_count = self.list.model().rowCount()

            # Find the next **visible** row
            next_row = current_index.row() + 1
            while next_row < row_count and self.list.isRowHidden(next_row):
                next_row += 1  # Skip hidden rows

            next_index = self.list.model().index(next_row, 0)

            if next_index.isValid():
                self.list.setCurrentIndex(next_index)  # Move selection down
                self.on_item_double_clicked(next_index)  # Simulate double-click

            return True  # Block default behavior
        return super().eventFilter(source, event)

    def initUI(self):

        # Main widget and layout for the window
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)  # Horizontal layout to hold the main splitter

        # Define all the Windows that can be opened
        self.main_exploring = create_main_viewer_tab(self)
        self.window_mesh = create_mesh_viewer_tab(self)

        self.list.installEventFilter(self)

        # Add widgets to the main layout
        main_layout.addWidget(self.main_exploring)

        # Connect double-click signal
        self.list.clicked.connect(self.on_item_clicked)
        self.list.doubleClicked.connect(self.on_item_double_clicked)

        # Set up master status bar
        self.mstatus_bar = self.statusBar()
        self.mstatus_bar.showMessage("Ready")


    # Context Menu Options
    def show_data(self, file_index):
        """Displays metadata about the selected NPK entry."""
        try:
            selected_indexes = self.list.selectionModel().selectedIndexes()
            if not selected_indexes:
                print("No valid selection.")
                logger.warning("No valid selection for Show Data.")
                return

            index = selected_indexes[0]
            selected_file_index = self.list.model().data(index, Qt.UserRole)

            file = self.npkentries.get(selected_file_index)
            if not file:
                print(f"Selected entry {selected_file_index} not found.")
                logger.debug(f"Selected entry {selected_file_index} not found.")
                return

            dialog = QDialog(self)
            dialog.setWindowTitle("NPK Data")
            dialog.setFixedSize(600, 400)

            main_layout = QHBoxLayout()

            # Left side labels
            labels = [
                "SIGN:", "NPK OFFSET:", "DATA LENGTH:", "ORIGINAL DATA LENGTH:",
                "COMPRESSED CRC:", "ORIGINAL CRC:", "COMPRESSION FLAG:", "FILE FLAG:"
            ]

            if file.file_structure:
                labels.append("FILE STRUCTURE:")
            labels.append("EXTENSION:")

            left_layout = QVBoxLayout()
            for label in labels:
                left_layout.addWidget(QLabel(label))

            # Right side values
            right_layout = QVBoxLayout()
            right_layout.addWidget(QLabel(hex(file.file_sign)))
            right_layout.addWidget(QLabel(hex(file.file_offset)))
            right_layout.addWidget(QLabel(str(file.file_length)))
            right_layout.addWidget(QLabel(str(file.file_original_length)))
            right_layout.addWidget(QLabel(str(file.zcrc)))
            right_layout.addWidget(QLabel(str(file.crc)))
            right_layout.addWidget(QLabel(str(file.zflag)))
            right_layout.addWidget(QLabel(str(file.fileflag)))

            if file.file_structure:
                right_layout.addWidget(QLabel(file.file_structure.decode("utf-8")))
            right_layout.addWidget(QLabel(file.ext))

            # Create Splitter
            splitter = QSplitter(Qt.Horizontal)
            left_widget = QWidget()
            left_widget.setLayout(left_layout)
            right_widget = QWidget()
            right_widget.setLayout(right_layout)

            splitter.addWidget(left_widget)
            splitter.addWidget(right_widget)

            # Add to layout
            main_layout.addWidget(splitter)
            dialog.setLayout(main_layout)

            dialog.exec_()

        except Exception as e:
            print(f"Error displaying data: {e}")
            logger.critical(f"Error displaying data: {e}")
            QMessageBox.critical(self, "Error", f"Could not display file data:\n{e}")

    def show_hex_data(self):
        self.window_hex = HexViewerApp(self.npkentries[self.selectednpkentry].data)
        self.window_hex.show()
        self.window_hex.raise_()

    def show_text(self):
        self.window_text = create_text_tab(self)
        self.window_text.show()
        self.window_text.raise_()

    def show_mesh(self):
        """Displays the selected mesh in the Mesh Viewer."""

        print(f"DEBUG: Selected Mesh - {self.window_mesh.viewer.filename}")

        if not hasattr(self.window_mesh, "viewer") or self.window_mesh.viewer is None:
            print("Mesh viewer is not initialized.")
            return
    
        if not hasattr(self.window_mesh.viewer, "scene") or self.window_mesh.viewer.scene is None:
            print("Mesh viewer is not ready, waiting for initialization.")
            self.window_mesh.viewer.on_init = lambda : self.show_mesh()
            self.window_mesh.show()
            return

        # Get all selected indexes from the QListView
        selected_indexes = self.list.selectionModel().selectedIndexes()
        if not selected_indexes:
            print("No file selected for mesh viewing.")
            logger.warning("No file selected for mesh viewing.")
            return

        for source_index in selected_indexes:
            # Retrieve the corresponding file index from the selected item
            file_index = self.list.model().data(source_index, Qt.UserRole)

            if file_index is None or not (0 <= file_index < len(self.npkentries)):
                print("Invalid file index for mesh viewing.")
                logger.debug("Invalid file index for mesh viewing.")
                continue

            # Get the NPK entry data
            npk_entry = self.npkentries.get(file_index)
            if not npk_entry or not any(npk_entry.updated_name.lower().endswith(ext) for ext in self.allowed_mesh_exts):
                print(f"'{npk_entry.updated_name}' is not a valid mesh file.")
                logger.debug(f"'{npk_entry.updated_name}' is not a valid mesh file.")
                continue
            
            try:
                # Parse the mesh data
                mesh = mesh_from_path(npk_entry.data)
                if not mesh:
                    raise ValueError("Failed to parse the mesh file.")

                # Load the mesh into the viewer
                self.window_mesh.viewer.load_mesh(mesh, self.get_savefile_location())
                self.window_mesh.viewer.focus_on_selected_object()
                self.window_mesh.viewer.update_aspect_ratio()

                # Ensure the mesh viewer window is displayed and raised
                self.update()
                self.window_mesh.show()
                self.window_mesh.raise_()

            except Exception as e:
                logger.critical(f"An error occurred while loading the mesh '{npk_entry.updated_name}': {str(e)}")

            # Focus on the loaded mesh and update the viewer
            self.window_mesh.viewer.focus_on_selected_object()
            self.window_mesh.viewer.update_aspect_ratio()
            self.update()

            # Bring the viewer to the front
            # self.window_mesh.raise_()

    def show_texture(self):
        """Displays the selected texture file in the TextureViewer window."""
        selected_indexes = self.list.selectionModel().selectedIndexes()
        if not selected_indexes:
            print("No file selected for texture viewing.")
            logger.warning("No file selected for texture viewing.")
            return

        source_index = selected_indexes[0]
        file_index = self.list.model().data(source_index, Qt.UserRole)

        if file_index is None or not (0 <= file_index < len(self.npkentries)):
            print("Invalid file index for texture viewing.")
            logger.warning("Invalid file index for texture viewing.")
            return

        npk_entry = self.npkentries.get(file_index)
        if not npk_entry or not any(npk_entry.updated_name.lower().endswith(ext) for ext in self.allowed_texture_exts):
            print(f"'{npk_entry.updated_name}' is not a valid texture file.")
            logger.debug(f"'{npk_entry.updated_name}' is not a valid texture file.")
            return

        try:
            # If the texture viewer doesn't exist, create it
            if not hasattr(self, "window_texture") or self.window_texture is None:
                self.window_texture = TextureViewer(npk_entry, parent=self)
            
            # Update the existing viewer with the new texture
            self.window_texture.show()
            self.window_texture.raise_()
            self.window_texture.displayImage(npk_entry)
        except Exception as e:
            logger.critical(f"An error occurred at location {e.__traceback__.tb_frame.f_code.co_name}; line {e.__traceback__.tb_lineno} while loading the texture: {str(e)}")


    # Main Toolbar
    # ----------------------------------------------------------------------------------------------------------
    def create_file_menu(self):
        # File Menu Button
        file_menu = self.menuBar().addMenu("File")

        # Choose New Config action
        new_config_action = QAction(self.style().standardIcon(QStyle.SP_FileIcon), "Choose New Config", self)
        new_config_action.setStatusTip("Select a new configuration file.")
        new_config_action.triggered.connect(partial(self.npk_config_data, force_new_file=True))
        file_menu.addAction(new_config_action)

        # Load Last Config action
        last_config_action = QAction(self.style().standardIcon(QStyle.SP_DialogSaveButton), "Load Last Config", self)
        last_config_action.setStatusTip("Load the last used configuration.")
        last_config_action.triggered.connect(partial(self.npk_config_data, force_new_file=False))
        file_menu.addAction(last_config_action)

        open_folder_action = QAction(self.style().standardIcon(QStyle.SP_DirOpenIcon), "Open File", self)
        open_folder_action.setStatusTip("Choose File")
        open_folder_action.setShortcut("Ctrl+O")
        open_folder_action.triggered.connect(partial(self.load_npk, "./utils/filename.json"))
        file_menu.addAction(open_folder_action)

    def create_help_menu(self):
        # About Menu Button
        about_menu = self.menuBar().addMenu("Help *")

        d_crypt_action = QAction(self.style().standardIcon(QStyle.SP_VistaShield), "D-Key", self)
        d_crypt_action.setShortcut('Ctrl+D')
        d_crypt_action.setStatusTip("Open an decryction popup window")
        d_crypt_action.triggered.connect(self.show_decrypt)
        about_menu.addAction(d_crypt_action)

        about_action = QAction(self.style().standardIcon(QStyle.SP_VistaShield), "About", self)
        about_action.setShortcut('Ctrl+H')
        about_action.setStatusTip("Open an about popup window")
        about_action.triggered.connect(self.show_about)
        about_menu.addAction(about_action)

    def create_edit_menu(self):
        # Settings Menu Button
        settings_menu = self.menuBar().addMenu("Edit *")

        settings_action = QAction(self.style().standardIcon(QStyle.SP_VistaShield), "Preferences", self)
        settings_action.setShortcut('Ctrl+,')
        settings_action.setStatusTip("Open an about popup window")
        settings_action.triggered.connect(self.show_settings)
        settings_menu.addAction(settings_action)
    
    def create_extraction_menu(self):
        """Creates the batch extraction menu."""
        # Create extraction window instance
        self.extraction_window = ExtractionViewer(self)

        # Create the menu
        extraction_menu = self.menuBar().addMenu("Batch *")

        # Create extraction action
        extraction_action = QAction(self.style().standardIcon(QStyle.SP_VistaShield), "Extract NPK", self)
        extraction_action.setShortcut('Ctrl+,')
        extraction_action.setStatusTip("Open an extraction popup window")
        extraction_action.triggered.connect(self.show_extraction_window)  # Connect to a function
        extraction_menu.addAction(extraction_action)

    def show_extraction_window(self):
        """Displays the extraction window when triggered."""
        self.extraction_window.show()
        self.extraction_window.raise_()

    def create_tools_menu(self):
        tools_menu = self.menuBar().addMenu("Tools")

        mesh_viewer_action = QAction("Mesh Viewer", self)
        mesh_viewer_action.setStatusTip("Open Mesh Viewer")
        mesh_viewer_action.triggered.connect(self.show_mesh_viewer_window)
        tools_menu.addAction(mesh_viewer_action)

    def show_mesh_viewer_window(self):
        self.window_mesh.show()
        self.window_mesh.raise_()

    def show_decrypt(self):
        """Show the decryption popup window."""
        self.statusBar().showMessage("D-Key...")

        # Load message from a text file
        try:
            with open("info/decryption_manager_info.txt", 'r') as file:
                message = file.read()
        except FileNotFoundError:
            message = "Error: Message file not found."
        # Initialize the decryption window with the loaded message
        result, ok = QInputDialog().getInt(None, "Decryption Key", message, self.decryption_key, -1000,1000, 10)
        if ok:
            # Retrieve input text if the dialog was accepted
            self.decryption_key = result  # Store the input for future use
            self.config_manager.set("decryption_key", result)
            print(f"Decryption Key Entered: {self.decryption_key}")
            logger.debug(f"Decryption Key Entered: {self.decryption_key}")
        self.statusBar().showMessage(f"Decryption key set to {result}")

    def show_about(self):
        """Show the about popup window."""
        self.statusBar().showMessage("Preferences...")
        # Load message from a text file
        try:
            with open("info/about_info.txt", 'r') as file:
                message = file.read()
        except FileNotFoundError:
            message = "Error: Message file not found."

        # Initialize the popup with the loaded message
        popup = AboutPopup(message)
        popup.exec_()

    def show_settings(self):
        """Show the settings window.""" # Edit Tab
        self.statusBar().showMessage("Preferences...")
        # Load message from a text file
        try:
            with open("info/about_info.txt", 'r') as file:
                message = file.read()
        except FileNotFoundError:
            message = "Error: Message file not found."

        # Initialize the popup with the loaded message
        popup = AboutPopup(message)
        popup.exec_()


    # Functionality
    # ----------------------------------------------------------------------------------------------------------
    def get_savefile_location(self):
        try:
            # Get the currently selected indexes
            selected_indexes = self.list.selectionModel().selectedIndexes()
            
            if not selected_indexes:
                logger.warning("No valid NPK entry selected.")
                return None

            # Dynamically get the selected file index (from selection)
            selected_index = selected_indexes[0]
            file_index = self.list.model().data(selected_index, Qt.UserRole)

            if file_index not in self.npkentries:
                logger.warning(f"No valid file index ({file_index}) found in npkentries.")
                return None

            currnpk = self.npkentries[file_index]

            # Construct the output path dynamically based on the NPK entry attributes
            base_path = os.path.join(self.output_folder, os.path.basename(self.npk.path))

            if currnpk.file_structure:
                filestructure = currnpk.file_structure.decode("utf-8").replace("\\", "/")
                folder_path = os.path.join(base_path, os.path.dirname(filestructure))
                os.makedirs(folder_path, exist_ok=True)
                file_path = os.path.join(folder_path, os.path.basename(filestructure))
            else:
                # Fallback if file_structure is empty
                os.makedirs(base_path, exist_ok=True)
                file_path = os.path.join(base_path, f"{hex(currnpk.file_sign)}.{currnpk.ext}")

            logger.info(f"Generated file path: {file_path}")
            return file_path

        except Exception as e:
            logger.critical(f"Error generating save file location: {e}")
            return None

    def set_output(self):
        file_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if file_path:
            # self.output_folder = self.config_manager.set(f"output_folder", f"{os.path.basename(file_path)}")
            self.output_folder = self.config_manager.set(f"output_folder", f"{file_path}")
            self.status_bar.showMessage(f'Output Folder: {file_path}.')
            logger.info(f'Output Folder: {file_path}.')
        return self.output_folder

    def extract_file(self):
        """Extract the currently selected NPK entry to a user-specified location."""

        # Ensure a file is selected
        selected_indexes = self.list.selectionModel().selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "Extraction Error", "No file selected for extraction.")
            logger.warning("No file selected for extraction.")
            return

        selected_index = selected_indexes[0]
        file_index = self.list.model().data(selected_index, Qt.UserRole)

        if file_index is None or file_index not in self.npkentries:
            QMessageBox.warning(self, "Extraction Error", "Invalid NPK entry selected.")
            logger.warning("Invalid NPK entry selected.")
            return

        npk_entry = self.npkentries[file_index]

        # Ensure there is data to extract
        if not npk_entry.data or npk_entry.file_original_length == 0:
            QMessageBox.warning(self, "Extraction Error", f"The selected file '{npk_entry.updated_name}' is empty.")
            logger.warning(f"Skipping extraction: {npk_entry.updated_name} (empty file).")
            return

        # Get save file location with default name
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save File As", npk_entry.updated_name, "All Files (*.*)"
        )
        if not save_path:
            self.status_bar.showMessage("Extraction canceled.")
            return

        # Write file to disk
        try:
            with open(save_path, "wb") as f:
                f.write(npk_entry.data)

            self.status_bar.showMessage(f"File extracted: {save_path}")
            QMessageBox.information(self, "Extraction Complete", f"Successfully extracted:\n{save_path}")
            logger.info(f"Extracted file: {save_path}")

        except Exception as e:
            QMessageBox.critical(self, "Extraction Failed", f"An error occurred:\n{str(e)}")
            logger.critical(f"Error extracting {npk_entry.updated_name}: {e}")


    def npk_config_data(self, config_file=None, force_new_file=False):
        """Load configuration data from a JSON file and save the last used config path."""
        # Check if a saved config path exists

        config_path_storage = "./utils/last_config.json"

        # Load last used config if available
        if not force_new_file and not config_file and os.path.exists(config_path_storage):
            try:
                with open(config_path_storage, "r") as storage_file:
                    saved_path = json.load(storage_file).get("last_used_config", None)
                    if saved_path and os.path.exists(saved_path):
                        config_file = saved_path
            except Exception as e:
                print(f"Error loading saved config path: {e}")
                logger.warning(f"Error loading saved config path: {e}")

        # If no valid config, ask user
        if not config_file or force_new_file:
            self.status_bar.showMessage('Choosing config file...')
            file_path = QFileDialog.getOpenFileName(self, "Choose file", filter="NPK Config (*.json)")[0]
            if not file_path:  # User canceled file dialog
                print("Config selection canceled.")
                return
            config_file = file_path

        # Validate config file extension
        if not config_file.endswith(".json"):
            print("Invalid File", "Please select a valid JSON configuration file.")
            logger.warning("Invalid File selected for NPK Config.")
            return
        
        try:
            # Load the JSON file
            with open(config_file, "r") as file:
                data = json.load(file)
                mapping = data.get("Data", {})

                # Debugging - Print mapping
                print(f"Mapping Loaded: {mapping}")

                # Retrieve specific configuration values
                game_config = mapping.get("game_config")
                npk_type = int(mapping.get("npk_type", 0)) # Ensure it's an integer
                decryption_key = int(mapping.get("decryption_key", 0))
                aes_key = int(mapping.get("aes_key", 0))
                index_size = int(mapping.get("index_size", 0))

                # Debugging - Print values
                print(f"Config Values Loaded: {game_config}, {npk_type}, {decryption_key}, {aes_key}, {index_size}")
                logger.debug(f"Config Values Loaded: {game_config}, {npk_type}, {decryption_key}, {aes_key}, {index_size}")

                #Update application state
                self.game_config = game_config
                self.npk_type = npk_type
                self.decryption_key = decryption_key
                self.aes_key = aes_key
                self.index_size = index_size
                self.compblks2png = compblks2png

                # Save the last used config path
                with open(config_path_storage, "w") as storage_file:
                    json.dump({"last_used_config": config_file}, storage_file)
                # print(f"Saved last used config path: {config_file}")
                logger.info(f"Saved last used config path: {config_file}")
                    
            # Update Config Manager
            if hasattr(self, "config_manager") and self.config_manager is not None:
                self.config_manager.set("game_config", game_config)
                self.config_manager.set("npk_type", npk_type)
                self.config_manager.set("decryption_key", decryption_key)
                self.config_manager.set("aes_key", aes_key)
                self.config_manager.set("index_size", index_size)
                self.config_manager.set("compblks2png", )
            else:
                print("ERROR: config_manager is not initialized!")
                logger.critical("ERROR: config_manager is not initialized!")
        
            self.status_bar2.showMessage(f"Game Config: {game_config}")

        except Exception as e:
            print(f"Error loading Config file: {e}")
            logger.critical(f"Error loading Config file: {e}")

    def update_config_data(self, json_file_path, outer_key, inner_key, value):
        """Update a nested JSON file structure."""
        # Check if the file exists
        if not os.path.exists(json_file_path):
            print(f"File {json_file_path} does not exist. Creating a new one.")
            logger.warning(f"File {json_file_path} does not exist. Creating a new one.")
            data = {outer_key: {}}  # Create a nested structure if the file doesn't exist
        else:
            # Read the existing JSON data
            try:
                with open(json_file_path, "r") as file:
                    data = json.load(file)
            except json.JSONDecodeError:
                print(f"File {json_file_path} contains invalid JSON. Starting with an empty dictionary.")
                logger.warning(f"File {json_file_path} contains invalid JSON. Starting with an empty dictionary.")
                data = {outer_key: {}}

        # Ensure the outer key exists
        if outer_key not in data:
            data[outer_key] = {}

        # Update the nested dictionary
        data[outer_key][inner_key] = value

        # Write the updated data back to the file
        with open(json_file_path, "w") as file:
            json.dump(data, file, indent=4)

        print(f"Updated {json_file_path}: Set {outer_key}.{inner_key} to {value}")
        logger.info(f"Updated {json_file_path}: Set {outer_key}.{inner_key} to {value}")


    def load_npk(self, json_file):
        """Load an NPK file and populate the list."""
        self.clear_npk_data()
        self.status_bar.showMessage('Selecting file...')

        file_path, _ = QFileDialog.getOpenFileName(self, "Open file", filter="NPK Files (*.npk)")
        if not file_path or not file_path.endswith(".npk"):
            self.status_bar.showMessage("Select NPK to extract!")
            return

        self.status_bar.showMessage(f'Loading NPK: {file_path}')
        # print("Path is: {}".format(file_path))

        # Read NPK File
        self.npk_file = io.BytesIO(open(file_path, 'rb').read())
        if read_index(self, file_path) == -1:
            self.status_bar.showMessage("Failed to read NPK index!")
            return

        # Populate List Model
        self.list_model.clear()
        currfile = 0
        for file in self.npk.index_table:
            filename = file[6].decode("utf-8") if file[6] else hex(file[0])

            widgetitem = QStandardItem(filename)
            widgetitem.setData(currfile, Qt.UserRole)  # Store file index as Qt.UserRole
            widgetitem.setIcon(self.style().standardIcon(QStyle.SP_DialogNoButton))

            self.list_model.appendRow(widgetitem)
            currfile += 1
            self.progress_bar.setValue((currfile + 1) * 100 // len(self.npk.index_table))  # Update progress bar

        self.status_bar.showMessage(f'Loading NPK: {file_path}')
        self.read_all_npk_data(json_file)  # Call the existing read_all_npk_data

        info_size = determine_info_size(self)
        logger.debug(f"Info Size: {info_size}")

        if self.list_model.rowCount() > 0:
            self.list.setCurrentIndex(self.list_model.index(0, 0))  # Auto-select first item

    def read_all_npk_data(self, json_file):
        """Read all entries from the NPK file and update the list with filenames."""
        if not hasattr(self, "npk"):
            QMessageBox.information(self, "Open NPK!", "You must open an NPK file first!")
            logger.info("Open NPK!", "You must open an NPK file first!")
            return

        # Ensure list view has a model
        model = self.list.model()
        if model is None:
            print("No list-model set for the list view.")
            logger.critical("No list-model set for the list view.")
            return

        # Load JSON file for filename mapping
        hash_mapping = {}
        try:
            with open(json_file, "r", encoding="utf-8") as file:
                data = json.load(file)
                hash_mapping = data.get("characters", {})
                ViewerWidget.json_mapping = hash_mapping  # Store mapping globally
        except Exception as e:
            print(f"Error loading JSON file: {e}")
            logger.debug(f"Error loading JSON file: {e}")

        # Iterate through the model's rows
        for x in range(model.rowCount()):
            try:
                item = model.item(x)
                if not item:
                    continue

                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Disable editing
                fileindex = item.data(Qt.UserRole)  # Retrieve file index

                if fileindex is None or not (0 <= fileindex < len(self.npk.index_table)):
                    continue  # Skip invalid indices

                # Read entry from NPK
                npkentry = read_entry(self, fileindex)
                self.progress_bar.setValue((x + 1) * 100 // len(self.npk.index_table))  # Update progress bar

                if npkentry.file_original_length == 0:
                    print(f"Index {fileindex} is empty")
                    logger.debug(f"Index {fileindex} is empty")
                    continue

                # Update filename
                original_filename = item.text()
                updated_filename = hash_mapping.get(original_filename, original_filename)
                if not npkentry.file_structure:
                    updated_filename += f".{npkentry.ext or 'bin'}"

                item.setText(updated_filename)
                npkentry.updated_name = updated_filename  # Store updated name in npkentry
                self.npkentries[fileindex] = npkentry

                # Set success icon
                if self.style():
                    item.setIcon(self.style().standardIcon(QStyle.SP_DialogYesButton))
                else:
                    item.setIcon(QIcon())  # Fallback if no style is available

            except Exception as e:
                print(f"Failed to process entry at row {x}: {e}")
                logger.debug(f"Failed to process entry at row {x}: {e}")
                if item and self.style():
                    item.setIcon(self.style().standardIcon(QStyle.SP_DialogNoButton))  # Failure icon

    def extract_processed_npk_data(self):
        """Extract all processed NPK entries into an output folder."""
        
        if not hasattr(self, "npkentries") or not self.npkentries:
            QMessageBox.warning(self, "Extraction Error", "No NPK data loaded. Load an NPK first!")
            return
        
        # Get output directory from config manager
        # output_dir = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        output_dir = self.config_manager.get("output_folder", "")

        if not output_dir:
            self.status_bar.showMessage("Extraction canceled.")
            return
        
        extracted_files = 0
        total_files = len(self.npkentries)

        # Extract each file
        for file_index, npkentry in self.npkentries.items():
            try:
                if npkentry.file_original_length == 0:
                    print(f"Skipping empty file: {npkentry.updated_name}")
                    logger.debug(f"Skipping empty file: {npkentry.updated_name}")
                    continue

                # Generate output path
                output_file_path = os.path.join(output_dir, npkentry.updated_name)

                # Write extracted file
                with open(output_file_path, "wb") as f:
                    f.write(npkentry.data)
                    self.status_bar.showMessage(f"Extracting: {npkentry}.")

                print(f"Extracted: {output_file_path}")
                logger.info(f"Extracted: {output_file_path}")
                extracted_files += 1

                # Update progress bar
                self.progress_bar.setValue((extracted_files * 100) // total_files)

            except Exception as e:
                print(f"Failed to extract {npkentry.updated_name}: {e}")
                logger.critical(f"Failed to extract {npkentry.updated_name}: {e}")

        # Show completion message
        if extracted_files > 0:
            self.status_bar.showMessage(f"Extraction complete! {extracted_files} files saved to {output_dir}")
            QMessageBox.information(self, "Extraction Complete", f"Successfully extracted {extracted_files} files.")
        else:
            self.status_bar.showMessage("No valid files were extracted.")
            QMessageBox.warning(self, "Extraction Warning", "No valid files found to extract.")


    def extract_selected_npk_data(self):
        if hasattr(self, "npk"):
            for index in self.npkentries:
                currnpk = self.npkentries[index]
                path = f"{self.output_folder}" + "/" + os.path.basename(f"{self.npk.path}") + "/"
                if not currnpk.file_structure:
                    os.makedirs(path, exist_ok=True)
                    path = path + hex(currnpk.file_sign) + "." + currnpk.ext
                else:
                    filestructure = currnpk.file_structure.decode("utf-8").replace("\\", "/")
                    path = path + os.path.dirname(filestructure)
                    os.makedirs(path, exist_ok=True)
                    path = path + "/" + os.path.basename(filestructure)

                with open(path, "wb") as f:
                    f.write(currnpk.data)
                try:
                    with open(path, "wb") as f:
                        f.write(currnpk.data)

                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")
            QMessageBox.information(self, "Finished!", f"Saved {len(self.npkentries)} files to \"{self.output_folder}\" folder")
        else:
            QMessageBox.information(self, "Open NPK first", "You must open an NPK file before extracting it!")

    def extract_loaded_Textures(self):
        if hasattr(self, "npk"):
            # allowed_extensions = {".dds", ".png"}  # Define allowed texture extensions
            saved_count = 0 

            # Iterate through all items in the file list widget
            for i in range(self.file_list_widget.count()):
                item = self.file_list_widget.item(i)
                
                # Retrieve the corresponding npk entry using the item's data
                index = item.data(3)
                currnpk = self.npkentries.get(index)

                if not currnpk:
                    continue

                if currnpk.ext.lower() not in self.allowed_texture_exts:
                    continue

                # Build the output path
                base_path = os.path.join(self.output_folder, os.path.basename(self.npk.path))
                if not currnpk.file_structure:
                    os.makedirs(base_path, exist_ok=True)
                    output_path = os.path.join(base_path, f"{hex(currnpk.file_sign)}.{currnpk.ext}")
                else:
                    filestructure = currnpk.file_structure.decode("utf-8").replace("\\", "/")
                    output_dir = os.path.join(base_path, os.path.dirname(filestructure))
                    os.makedirs(output_dir, exist_ok=True)
                    output_path = os.path.join(output_dir, os.path.basename(filestructure))

                # Save the file and handle errors
                try:
                    with open(output_path, "wb") as f:
                        f.write(currnpk.data)
                    saved_count += 1
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")

            # Show a final message indicating the number of saved files
            if saved_count > 0:
                QMessageBox.information(self, "Finished!", f"Saved {saved_count} texture files to \"{self.output_folder}\" folder")
            else:
                print(self, "No Files Saved", "No valid texture files were saved.")
        else:
            QMessageBox.information(self, "Open NPK first", "You must open an NPK file before extracting it!")

    def clear_npk_data(self):
        self.filter_input.clear()
        self.selectednpkentry = 0
        self.npkentries.clear()
        if hasattr(self, "npk"):
            self.npk.clear()
        self.npkentry = None


    def on_item_clicked(self, item):
        """Handles single-click events in the list view."""
        
        # Get the model from the QListView
        model = self.list.model()
        if not model:
            print("ERROR: Model is None.")
            return

        # Retrieve the index stored in UserRole
        index = item.data(Qt.UserRole)  # Stored file index

        # Ensure index is valid
        if index is None or not (0 <= index < len(self.npkentries)):
            print(f"Invalid item index: {index}")
            logger.warning(f"Invalid item index: {index}")
            return

        # Check if the entry is already loaded
        if index not in self.npkentries:
            npkentry = read_entry(self, index)

            if npkentry.file_original_length == 0:
                print(f"This index {index} is empty.")
                return

            # Update item text with file extension if missing
            if not bool(item.data(4)) and not npkentry.file_structure:
                item.setText(item.text() + f".{npkentry.ext}")

            # Mark item as updated
            item.setData(4, True)
            item.setIcon(self.style().standardIcon(QStyle.SP_DialogYesButton))

            # Store entry in npkentries
            self.npkentries[index] = npkentry

        # Update selected entry reference
        self.selectednpkentry = index

        # Print selected item for debugging
        selected_item = self.npkentries.get(index, None)
        if selected_item:
            print(f"Selected item index: {index}, Data: {selected_item}")

    def on_item_double_clicked(self, index):
        """Handles double-click events to open the appropriate viewer."""
        
        # Ensure the index is valid
        if not index.isValid():
            print("Invalid index.")
            logger.warning("Invalid index.")
            return

        # Retrieve file index stored in UserRole
        file_index = self.list.model().data(index, Qt.UserRole)
        if file_index is None or not (0 <= file_index < len(self.npkentries)):
            print("No file index data associated.")
            logger.warning("No file index data associated.")
            return

        # Retrieve the corresponding NPK entry
        npk_entry = self.npkentries.get(file_index)
        if not npk_entry:
            print(f"No entry found for index {file_index}.")
            logger.debug(f"No entry found for index {file_index}.")
            return

        # Determine file type and open the correct viewer
        filename_lower = npk_entry.updated_name.lower()

        if filename_lower.endswith(tuple(self.allowed_mesh_exts)):
            self.show_mesh()
            self.window_mesh.viewer.filename = npk_entry.updated_name
            self.window_mesh.viewer.filepath = self.list.model().data(index, Qt.UserRole)  # Ensure correct path

            # Check if scene exist befor calling focus selected object
            if hasattr(self.window_mesh.viewer, "scene") and self.window_mesh.viewer.scene is not None:
                self.window_mesh.viewer.focus_on_selected_object()
            else:
                print("Scene is not ready. Delaying focus...")
                QTimer.singleShot(200, self.window_mesh.viewer.focus_on_selected_object)
        elif filename_lower.endswith(tuple(self.allowed_texture_exts)):
            self.show_texture()
        elif filename_lower.endswith(tuple(self.allowed_text_exts)):
            self.show_text()
        else:
            print(f"Unsupported file type: {npk_entry.updated_name}")
            logger.debug(f"Unsupported file type: {npk_entry.updated_name}")


    def on_selection_changed(self):
        selected_indexes = self.list.selectionModel().selectedIndexes()
        for proxy_index in selected_indexes:
            source_index = self.proxy_model.mapToSource(proxy_index)
            if not source_index.isValid():
                continue

            file_index = self.list_model.data(source_index, Qt.ItemDataRole.UserRole)
            if file_index:
                print(f"Selected: {file_index['name']} (Index: {file_index['index']})")
                logger.debug(f"Selected: {file_index['name']} (Index: {file_index['index']})")

    def filter_list_items(self):
        """Filter QListView items based on user input from QLineEdit and QComboBox."""
        model = self.list.model()
        if model is None:
            logger.warning("No list-model set for filtering.")
            return

        search_string = self.filter_input.text().strip().lower()  # Get text input
        category = self.filter_combobox.currentText()  # Get selected category

        for row in range(model.rowCount()):
            item = model.item(row)
            file_index = item.data(Qt.UserRole)

            if file_index is None or file_index not in self.npkentries:
                self.list.setRowHidden(row, True)
                continue

            npk_entry = self.npkentries[file_index]

            # file_path = os.path.join(self.output_folder, npk_entry.updated_name)
            # file_path = os.path.join(self.npkentries, npk_entry.updated_name)

            # Apply text filtering
            text_match = not search_string or search_string in npk_entry.updated_name.lower()

            # Apply category filtering
            category_match = False
            if category == "ALL":
                category_match = True
            elif category == "MESH" and npk_entry.updated_name.lower().endswith(tuple(self.allowed_mesh_exts)):
                category_match = True
            elif category == "TEXTURE" and npk_entry.updated_name.lower().endswith(tuple(self.allowed_texture_exts)):
                category_match = True
            elif category == "CHARACTER" and "character" in npk_entry.updated_name.lower():
                category_match = True
            elif category == "SKIN" and "skin" in npk_entry.updated_name.lower():
                category_match = True
            elif category == "TEXT FORMAT" and npk_entry.updated_name.lower().endswith(tuple(self.allowed_text_exts)):
                category_match = True
            
            # If filtering for MESH, apply additional ransack filtering (from filepath)
            # if category == "MESH" and category_match:
            #     if not self.ransack_agent(file_path, "biped head"):
            #         category_match = False

            # If filtering for MESH and checkbox is enabled, apply additional ransack filtering (in-memory scan)
            if self.filtered_mesh_checkbox.isChecked():
                if category == "MESH" and category_match:
                    # self.list_model.beginResetModel()
                    if not self.ransack_agent(npk_entry.data, "biped head"):  # Scan in-memory data
                        category_match = False
                    # self.list_model.endResetModel()

            # Hide or show based on filtering
            self.list.setRowHidden(row, not (text_match and category_match))

    # For file path
    # def ransack_agent(self, file_path, search_string):
    #     """Check if the given search_string is present in the specified file."""
    #     try:
    #         with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
    #             return search_string in file.read()
    #     except Exception as e:
    #         logger.warning(f"Error reading {file_path}: {e}")
    #         return False

    def ransack_agent(self, data, search_string):
        """Check if the given search_string is present in the in-memory NPK entry data."""
        try:
            if isinstance(data, bytes):  # Convert binary data to string for searching
                data = data.decode('utf-8', errors='ignore')

            return search_string in data.lower()
        except Exception as e:
            logger.warning(f"Error scanning in-memory data: {e}")
            return False

    def append_console_output(self, text: str):
            """Appends text to the console output."""
            if hasattr(self.console_handler, 'text_output'):
                self.console_handler.text_output.emit(text)
            else:
                print("Console handler is not properly initialized.")

def main():
    app = QApplication(sys.argv)
    app.setPalette(qt_theme.palettes()["dark"]) # Set the dark palette
    app.setStyleSheet(qt_theme.style_modern()) # Apply the dark theme stylesheet
    signal.signal(signal.SIGINT, lambda *a: app.quit())
    main_window = MainWindow()
    main_window.show()
    logger.info("Application started")
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
