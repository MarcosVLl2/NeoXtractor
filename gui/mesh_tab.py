from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from gui.viewer_3d import ViewerWidget
from utils.config_manager import ConfigManager
from utils.console_handler import *
from utils.util import *

class FileSelector:
    @staticmethod
    def select_file():
        file_name, _ = QFileDialog.getOpenFileName(
            None, "Select File", "", "Mesh Files (*.mesh)"
        )
        return file_name

def show_input_dialog(title, text):
    dialogue_response, dialogue_complete = QInputDialog.getText(
        None, title, text, QLineEdit.Normal, ""
    )
    return dialogue_response if dialogue_complete else ""

def create_mesh_viewer_tab(self):
        # -----------------------------------
        # Main Tab/ Mesh Viewer
        tab1 = QMainWindow()
        tab1.setGeometry(350,150,1000,800)
        tab1.setWindowTitle("ModernGL Mesh Viewer")
        tab1.closeEvent = on_closing_mesh_view

        _main = QWidget()
        tab1_layout = QVBoxLayout()
        
        full_widget = QWidget()
        full_layout = QVBoxLayout(full_widget)
        right_widget = QWidget()
        right_side = QVBoxLayout(right_widget)
        left_widget = QWidget()
        left_side = QVBoxLayout(left_widget)

        tab1.viewer = ViewerWidget(tab1)  # Placeholder for Mesh viewer
        tab1.viewer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        tab1.viewer.setMinimumSize(QSize(400,400))
        tab1.viewer.update_aspect_ratio()
        right_side.addWidget(tab1.viewer)
        
        # Viewport Navigation
        tab1.navigate_label = QLabel(
            "Key 7: Top View  |  Key 3: Right View  |  Key 1: Front View  |  Ctrl+Key: Flip View  |  Middle: Dolly  |  Letf: Pan  |  Right: Orbit  |  'F' Key: Focus on Object"
        )
        # tab1.navigate_label.setWordWrap(True)
        tab1.navigate_label.setFixedHeight(20)
        left_side.addWidget(tab1.navigate_label)

        # Flip UV checkbox
        tab1.flip_uv_checkbox = QCheckBox('Flip UVs V-axis on Save')
        left_side.addWidget(tab1.flip_uv_checkbox)

        # Zoom slider
        tab1.zoom_speed_label = QLabel("Camera Zoom Speed Control:")
        tab1.zoom_speed_slider = QSlider(Qt.Horizontal)
        tab1.zoom_speed_slider.setMinimum(1)
        tab1.zoom_speed_slider.setMaximum(200)
        tab1.zoom_speed_slider.setValue(100)
        tab1.zoom_speed_slider.setFixedWidth(400)
        tab1.zoom_speed_slider.valueChanged.connect(lambda: update_zoom_speed(tab1))

        tab1.zoom_speed_label.setFixedHeight(15)
        tab1.zoom_speed_slider.setRange(1, 100)  # Convert from 0.01 to 1.0
        tab1.zoom_speed_slider.setValue(20)  # Set default zoom speed to 0.2

        full_layout.addWidget(right_widget)
        full_layout.addWidget(left_widget)
        tab1_layout.addWidget(full_widget)
        tab1_layout.addWidget(tab1.zoom_speed_label)
        tab1_layout.addWidget(tab1.zoom_speed_slider)
        _main.setLayout(tab1_layout)
        tab1.setCentralWidget(_main)
        
        # Add menus
        create_open_menu(tab1)
        create_view_menu(tab1)
        create_save_menu(tab1)

        # Attach load_mesh method
        setattr(tab1, "load_mesh", lambda file_path: load_mesh(tab1, file_path))
        
        return tab1

def on_closing_mesh_view(event):
    dialogbox = QDialog()
    dialogbox.setWindowTitle("ModernGL Mesh Viewer")

    # Layout and Widgets
    layout = QVBoxLayout()

    # Message Label
    label = QLabel("Are you sure you want to close the Mesh Viewer?\nIf you close it now, you wont be able to use it again until you restart the app.", )
    layout.addWidget(label, alignment=Qt.AlignCenter)  # Align the message to the center

    button_layout = QHBoxLayout()
    close_button = QPushButton("Close Anyway")
    close_button.clicked.connect(dialogbox.accept)
    button_layout.addWidget(close_button)

    cancel_button = QPushButton("Leave Open")
    cancel_button.clicked.connect(dialogbox.reject)
    button_layout.addWidget(cancel_button)

    layout.addLayout(button_layout)
    dialogbox.setLayout(layout)

    if dialogbox.exec_() == QDialog.Accepted:
        event.accept()
    else:
        event.ignore()

def update_zoom_speed(tab1):
    if hasattr(tab1.viewer.scene, "camera"):
        zoom_speed = tab1.zoom_speed_slider.value() / 10.0
        tab1.viewer.scene.camera.zoom_speed = zoom_speed
        tab1.statusBar().showMessage(f"Zoom Speed: {zoom_speed:.1f}")
    else:
        tab1.statusBar().showMessage("No camera available to adjust zoom speed.")

def create_view_menu(tab1):
    # View Menu Button
    view_menu = tab1.menuBar().addMenu("View")

    # Create the checkable action for "Show Bones"
    show_bones_action = QAction("Show Bones", tab1)
    show_bones_action.setShortcut('Alt+B')
    show_bones_action.setCheckable(True)
    show_bones_action.setChecked(True)
    show_bones_action.triggered.connect(lambda checked: tab1.viewer.toggle_bone_visibility(checked))
    view_menu.addAction(show_bones_action)

    # Create the checkable action for "Show Wireframe"
    show_wireframe_action = QAction("Wireframe Mode", tab1)
    show_wireframe_action.setShortcut('Alt+W')
    show_wireframe_action.setCheckable(True)
    show_wireframe_action.setChecked(False)
    show_wireframe_action.triggered.connect(lambda checked: tab1.viewer.toggle_wireframe_mode(checked))
    view_menu.addAction(show_wireframe_action)

    # Create the checkable action for "Show Normals"
    show_norm_action = QAction("Show Normals", tab1)
    show_norm_action.setShortcut('Alt+N')
    show_norm_action.setCheckable(True)
    show_norm_action.setChecked(False)
    show_norm_action.triggered.connect(lambda checked: tab1.viewer.toggle_normals_visibility(checked))
    view_menu.addAction(show_norm_action)
    
def create_save_menu(tab1):
    save_menu = tab1.menuBar().addMenu("Save")

    save_actions = [
        ("Save as FBX - Coming Soon", "Ctrl+Shift+F", lambda: QMessageBox.information(tab1, "Coming Soon", "FBX support is not implemented yet.")),
        ("Save as GLTF2", "Ctrl+Shift+G", tab1.viewer.save_mesh_gltf),
        ("Save as OBJ", "Ctrl+Shift+O", tab1.viewer.save_mesh_obj),
        ("Save as SMD", "Ctrl+Shift+S", tab1.viewer.save_mesh_smd),
        ("Save as ASCII", "Ctrl+Shift+A", tab1.viewer.save_mesh_ascii),
        ("Save as PMX", "Ctrl+Shift+P", tab1.viewer.save_mesh_pmx),
        ("Save as IQE", "Ctrl+Shift+I", tab1.viewer.save_mesh_iqe),
    ]

    for label, shortcut, func in save_actions:
        action = QAction(label, tab1)
        action.setShortcut(shortcut)
        action.triggered.connect(func)
        save_menu.addAction(action)

def create_open_menu(tab1):
    open_menu = tab1.menuBar().addMenu("Open")
    open_action = QAction("Open (.mesh) file", tab1)
    open_action.setShortcut("Ctrl+O")
    open_action.triggered.connect(lambda: openFile(tab1))
    open_menu.addAction(open_action)

def openFile(tab1):
    file_name = FileSelector.select_file()
    if file_name:
        tab1.load_mesh(file_name)

def load_mesh(tab1, file_path):
    try:
        # Open file in binary mode
        with open(file_path, "rb") as file:
            mesh_data = file.read()  # Read binary data

        # Parse mesh data
        mesh = mesh_from_path(mesh_data)
        if mesh:
            tab1.viewer.load_mesh(mesh, file_path)
        else:
            QMessageBox.warning(tab1, "Error", "Failed to parse the mesh file.")
    except FileNotFoundError:
        QMessageBox.warning(tab1, "File Not Found", "The selected file could not be found.")
    except Exception as e:
        QMessageBox.critical(tab1, "Error", f"Failed to load mesh file: {e}")