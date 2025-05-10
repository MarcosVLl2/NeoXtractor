from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from gui.viewer_3d import ViewerWidget
from utils.config_manager import ConfigManager
from utils.console_handler import *
from utils.util import *
from converter import *
import os

from logger import logger

class FileSelector:
    @staticmethod
    def select_file():
        file_name, _ = QFileDialog.getOpenFileName(
            None, "Select File", "", "Mesh Files (*.mesh)"
        )
        return file_name

class MeshListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

    def keyPressEvent(self, event):
        """Handles key events for navigation in the mesh list."""
        if event.key() == Qt.Key_Down:
            selected_indexes = self.selectedIndexes()

            if selected_indexes:
                current_index = selected_indexes[0]
                next_index = self.model().index(current_index.row() + 1, 0)

                if next_index.isValid():
                    self.setCurrentIndex(next_index)  # Move selection down
                    self.itemActivated.emit(self.item(next_index.row()))  # Simulate double-click

        elif event.key() == Qt.Key_Up:
            selected_indexes = self.selectedIndexes()

            if selected_indexes:
                current_index = selected_indexes[0]
                prev_index = self.model().index(current_index.row() - 1, 0)

                if prev_index.isValid():
                    self.setCurrentIndex(prev_index)  # Move selection up
                    self.itemActivated.emit(self.item(prev_index.row()))  # Simulate double-click

        else:
            super().keyPressEvent(event)  # Handle other key events normally


def show_input_dialog(title, text):
    dialogue_response, dialogue_complete = QInputDialog.getText(
        None, title, text, QLineEdit.Normal, ""
    )
    return dialogue_response if dialogue_complete else ""


def create_mesh_viewer_tab(self):
    if hasattr(self, "window_mesh") and self.window_mesh is not None:
        return self.window_mesh  # Reuse existing instance

    print("Initializing mesh viewer tab...")

    # -----------------------------------
    # Mesh Viewer
    tab1 = QMainWindow(self)
    tab1.setGeometry(350, 150, 1400, 800)
    tab1.setWindowTitle("ModernGL Mesh Viewer")

    # Main Container
    central_widget = QWidget()
    tab1.setCentralWidget(central_widget)
    main_layout = QHBoxLayout(central_widget)

    # Left Side: File List Setup
    tab1.mesh_list_widget = MeshListWidget()  # Use the subclassed list view
    # tab1.mesh_list_widget = QListWidget()
    tab1.mesh_list_widget.setAcceptDrops(True)
    tab1.mesh_list_widget.setFixedWidth(400)
    tab1.mesh_list_widget.setToolTip("List of .mesh files in the loaded folder.")
    main_layout.addWidget(tab1.mesh_list_widget)

    # Define and attach signal handlers
    def on_mesh_item_clicked(item):
        """Handle single-click event for mesh items."""
        file_path = item.data(Qt.UserRole)
        on_mesh_item_double_clicked(item)
        logger.debug(f"Item clicked: {file_path}")


    def on_mesh_item_double_clicked(item):
        """Handle double-click event to load mesh into the viewer."""
        file_path = item.data(Qt.UserRole)
        if file_path and os.path.isfile(file_path):
            try:
                load_mesh(tab1, file_path)
                print(f"Mesh loaded: {file_path}")
                logger.debug(f"Mesh loaded: {file_path}")
            except Exception as e:
                logger.critical(tab1, "Error", f"Failed to load mesh file: {str(e)}")

    tab1.on_mesh_item_clicked = on_mesh_item_clicked
    tab1.on_mesh_item_double_clicked = on_mesh_item_double_clicked

    # Connect the signals to the handlers
    tab1.mesh_list_widget.itemPressed.connect(tab1.on_mesh_item_clicked)
    tab1.mesh_list_widget.itemDoubleClicked.connect(tab1.on_mesh_item_double_clicked)
    tab1.mesh_list_widget.itemActivated.connect(tab1.on_mesh_item_double_clicked) # process index using up and down arrow

    # Right Side: Viewer and Controls
    right_side = QVBoxLayout()
    
    # Viewer Widget
    tab1.viewer = ViewerWidget(tab1)  # Placeholder for Mesh Viewer
    tab1.viewer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    tab1.viewer.setMinimumSize(QSize(400, 400))
    right_side.addWidget(tab1.viewer)

    # Viewport Navigation Label
    navigation_label = QLabel(
        "Fly mode:  W: Forward  |  A: Left  |  S: Backward  |  D: Right  |  Shift+Key: Sprint  |  Ctrl+'1,3,7': Flip View  |  'F' Key: Focus Object"
    )
    navigation_label.setFixedHeight(20)
    right_side.addWidget(navigation_label)

    # Flip UV Checkbox
    tab1.flip_uv_checkbox = QCheckBox('Flip UVs on Save (V-axis)')
    tab1.flip_uv_checkbox.setChecked(False)
    right_side.addWidget(tab1.flip_uv_checkbox)

    # Default value if the scene isn't initialized yet
    default_zoom_speed = 1.0  # Default value if scene is None

    if tab1.viewer and tab1.viewer.scene and tab1.viewer.scene.camera:
        default_zoom_speed = tab1.viewer.scene.camera.zoom_speed

    # Zoom Speed Slider
    zoom_speed_label = QLabel(f"Camera Zoom Speed Control: {default_zoom_speed:.2f}")

    # Zoom Speed Slider
    zoom_speed_label = QLabel("Camera Zoom Speed Control:")
    zoom_speed_label.setFixedHeight(15)
    right_side.addWidget(zoom_speed_label)

    zoom_speed_slider = QSlider(Qt.Horizontal)
    zoom_speed_slider.setRange(1, 100)  # Range: 1 to 100
    zoom_speed_slider.setValue(20)  # Default speed
    zoom_speed_slider.setFixedWidth(300)
    right_side.addWidget(zoom_speed_slider)
    zoom_speed_slider.valueChanged.connect(lambda value: tab1.viewer.set_zoom_speed(value))

    def update_zoom_label(value):
        """Update the zoom speed label dynamically."""
        zoom_speed = value / 10.0  # Normalize zoom speed
        if tab1.viewer and tab1.viewer.scene and tab1.viewer.scene.camera:
            tab1.viewer.scene.camera.set_zoom_speed(zoom_speed)  # Ensure camera is initialized
        zoom_speed_label.setText(f"Camera Zoom Speed Control: {zoom_speed:.2f}")
    zoom_speed_slider.valueChanged.connect(update_zoom_label)

    # tab1.zoom_speed_slider.valueChanged.connect(update_zoom_label)

    # Add Right Side to Main Layout
    main_layout.addLayout(right_side)

    # Create Menus
    create_open_menu(tab1)
    create_save_menu(tab1)
    create_view_menu(tab1)

    return tab1


def create_view_menu(tab1):
    view_menu = tab1.menuBar().addMenu("View")

    def add_menu_action(name, shortcut, callback, checkable=False, default_checked=False):
        action = QAction(name, tab1)
        action.setShortcut(shortcut)
        action.setCheckable(checkable)
        action.setChecked(default_checked)
        action.triggered.connect(callback)
        view_menu.addAction(action)

    add_menu_action("Show Bones", "Alt+B", lambda checked: tab1.viewer.toggle_bone_visibility(checked), True, True)
    add_menu_action("Wireframe Mode", "Alt+W", lambda checked: tab1.viewer.toggle_wireframe_mode(checked), True, False)
    add_menu_action("Show Normals", "Alt+N", lambda checked: tab1.viewer.toggle_normals_visibility(checked), True, False)
    add_menu_action("Enable Face Culling", "Alt+C", lambda checked: tab1.viewer.toggle_culling_mode(checked), True, False)

def create_save_menu(tab1):
    save_menu = tab1.menuBar().addMenu("Save")

    # def add_save_action(label, shortcut, callback):
    #     action = QAction(f"Save as {label}", tab1)
    #     action.setShortcut(shortcut)
    #     action.triggered.connect(callback)
    #     save_menu.addAction(action)

    # add_save_action("OBJ", "Ctrl+Shift+O", lambda: tab1.viewer.save_mesh_obj(tab1.flip_uv_checkbox.isChecked()))
    # add_save_action("SMD", "Ctrl+Shift+S", lambda: tab1.viewer.save_mesh_smd(tab1.flip_uv_checkbox.isChecked()))
    # add_save_action("ASCII", "Ctrl+Shift+A", lambda: tab1.viewer.save_mesh_ascii(tab1.flip_uv_checkbox.isChecked()))
    # add_save_action("PMX", "Ctrl+Shift+P", tab1.viewer.save_mesh_pmx)
    # add_save_action("IQE", "Ctrl+Shift+I", tab1.viewer.save_mesh_iqe)
    
    ischecked = tab1.flip_uv_checkbox.isChecked()

    save_actions = [
        ("FBX - Coming Soon", "Ctrl+Shift+F",
         lambda: QMessageBox.information(tab1, "Coming Soon", "FBX support is not implemented yet.")),
        ("GLTF2", "Ctrl+Shift+G", tab1.viewer.save_mesh_gltf),
        ("OBJ", "Ctrl+Shift+O", lambda: tab1.viewer.save_mesh_obj(ischecked)),
        ("SMD", "Ctrl+Shift+S", lambda: tab1.viewer.save_mesh_smd(ischecked)),
        ("ASCII", "Ctrl+Shift+A", lambda: tab1.viewer.save_mesh_ascii(ischecked)),
        ("PMX", "Ctrl+Shift+P", tab1.viewer.save_mesh_pmx),
        ("IQE", "Ctrl+Shift+I", tab1.viewer.save_mesh_iqe),
    ]

    for label, shortcut, func in save_actions:
        action = QAction(f"Save as {label}", tab1)
        action.setShortcut(shortcut)
        action.triggered.connect(func)
        save_menu.addAction(action)

def create_open_menu(tab1):
    open_menu = tab1.menuBar().addMenu("Open")
    open_action = QAction("Open file (.mesh)", tab1)
    open_action.setShortcut("Ctrl+O")
    open_action.triggered.connect(lambda: openFile(tab1))
    open_menu.addAction(open_action)

    # Open folder and filter .mesh files
    open_folder_action = QAction("Open Folder (Filter .mesh)", tab1)
    open_folder_action.setShortcut("Ctrl+Shift+O")
    open_folder_action.triggered.connect(lambda: openFolder(tab1))
    open_menu.addAction(open_folder_action)


def update_zoom_speed(tab1):
    if hasattr(tab1.viewer.scene, "camera"):
        zoom_speed = tab1.zoom_speed_slider.value() / 30.0
        tab1.viewer.scene.camera.zoom_speed = zoom_speed
        tab1.statusBar().showMessage(f"Zoom Speed: {zoom_speed:.1f}")
    else:
        tab1.statusBar().showMessage("No camera available to adjust zoom speed.")


def openFile(tab1):
    file_name = FileSelector.select_file()
    if not file_name:
        return
    
    tab1.viewer.filename = os.path.realpath(os.path.basename(file_name)) # Filename for open mesh
    tab1.viewer.mesh_version = os.path.realpath(file_name)

    try:
        # Try to read the file as a string
        with open(file_name, 'r', encoding='utf-8') as f:
            file_content = f.read()
        print("File successfully read as string.")
        logger.debug("File successfully read as string within the Mesh Window List View.")
    except Exception as e:
        print(f"Failed to read as string: {e}")
        logger.debug(f"Failed to read as string: {e}")
        try:
            # If reading as a string fails, try reading as bytes
            with open(file_name, 'rb') as f:
                file_content = f.read()
            print("File successfully read as bytes.")
            logger.debug("File successfully read as bytes within the Mesh Window List View.")
        except Exception as e:
            print(f"Failed to read as bytes: {e}")
            logger.debug(f"Failed to read as bytes: {e}")
            return

    # Pass the file content to the mesh loader function
    load_mesh(tab1, file_content)
    if file_name:
        load_mesh(tab1, file_name)

def openFolder(tab1):
    """Open a folder, filter .mesh files, and display them in mesh_list_widget."""
    folder_path = QFileDialog.getExistingDirectory(None, "Select Folder")

    if not folder_path:
        return

    tab1.mesh_list_widget.clear()  # Clear the list before adding new items

    mesh_files = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.mesh'):
                mesh_files.append(os.path.join(root, file))

    if not mesh_files:
        QMessageBox.information(tab1, "No Mesh Files", "No .mesh files found in the selected folder.")
        return

    for mesh_file in mesh_files:
        item = QListWidgetItem(os.path.basename(mesh_file))  # Show only the file name
        item.setData(Qt.UserRole, mesh_file)  # Store the full file path in UserRole
        tab1.mesh_list_widget.addItem(item)

    QMessageBox.information(tab1, "Success", f"Loaded {len(mesh_files)} .mesh files.")
    logger.info(tab1, "Success", f"Loaded {len(mesh_files)} .mesh files.")

def load_mesh(tab1, file_path):
    try:
        # Attempt to parse the mesh directly from the file path
        mesh = mesh_from_path(file_path)
        if mesh:
            tab1.viewer.load_mesh(mesh, file_path)
            tab1.viewer.filename = os.path.basename(file_path) # Filename to mesh viewer
            tab1.viewer.filepath = os.path.abspath(file_path) # Filepath to mesh viewer

            return

        # If neither type could be loaded, show an error
        print(tab1, "Error", "Failed to parse the mesh file. Unsupported format.")
        logger.warning("Failed to parse the mesh file. Unsupported format.")
    except FileNotFoundError:
        print(tab1, "File Not Found", "The selected file could not be found.")
        logger.debug("File Not Found", "The selected file could not be found.")
    except Exception as e:
        print(tab1, "Error", f"Failed to load mesh file: {e} \n File Path: {file_path}")
        logger.critical("Error", f"Failed to load mesh file: {e} \n File Path: {file_path}")

