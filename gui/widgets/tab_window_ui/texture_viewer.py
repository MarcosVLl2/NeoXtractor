"""Code for viewer tab window customization."""

import os
from typing import cast, TYPE_CHECKING

from PySide6 import QtCore, QtWidgets

if TYPE_CHECKING:
    from gui.widgets.texture_viewer import TextureViewer
    from gui.windows.viewer_tab_window import ViewerTabWindow

SAVE_AS_FORMATS = {
    "PNG": "PNG Files (*.png)",
    "JPG": "JPEG Files (*.jpg *.jpeg)",
    "BMP": "BMP Files (*.bmp)"
}

def _save_as_format(viewer: 'TextureViewer', target_format: str, file_path: str):
    """
    Save the current texture in the specified format.
    
    Parameters:
    - target_format: The format to save the texture as.
    """
    image = viewer.processed_texture if viewer.processed_texture else viewer.texture
    if image is None:
        QtWidgets.QMessageBox.warning(
            viewer,
            "No Image Loaded",
            "Please load an image file before saving."
        )
        return
    if file_path:
        byte_array = QtCore.QByteArray()
        buffer = QtCore.QBuffer(byte_array)
        buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, cast(bytes, target_format))
        with open(file_path, "wb") as f:
            f.write(byte_array.data())

def _save_current_as_format(window: 'ViewerTabWindow', target_format: str, file_path: str | None = None):
    """
    Save the current image in the specified format.
    
    Parameters:
    - target_format: The format to save the image as.
    """
    viewer = cast('TextureViewer', window.tab_widget.currentWidget())
    if viewer is None:
        QtWidgets.QMessageBox.warning(
            window,
            "No File Opened",
            "Please open an image file before saving."
        )
        return
    if file_path is None:
        file_dialog = QtWidgets.QFileDialog()
        file_path, _ = file_dialog.getSaveFileName(
            None,
            f"Save Image as {target_format}",
            "",
            SAVE_AS_FORMATS[target_format]
        )
    if file_path:
        _save_as_format(viewer, target_format, file_path)
        QtWidgets.QMessageBox.information(
            window,
            "Save Successful",
            f"Image saved successfully as {target_format}."
        )

def _save_all_as_format(window: 'ViewerTabWindow', target_format: str):
    """
    Save all images in the current tab window in the specified format.
    
    Parameters:
    - target_format: The format to save the images as.
    """
    file_count = window.tab_widget.count()
    if file_count == 0:
        QtWidgets.QMessageBox.warning(
            window,
            "No Files Opened",
            "Please open image files before saving all."
        )
        return
    folder_dialog = QtWidgets.QFileDialog()
    save_directory = folder_dialog.getExistingDirectory(
        window,
        "Select Directory to Save All Images"
    )
    if not save_directory:
        return
    for i in range(file_count):
        viewer = cast('TextureViewer', window.tab_widget.widget(i))
        if viewer is None or viewer.texture is None:
            continue
        file_path = os.path.join(
            save_directory,
            f"{os.path.splitext(window.tab_widget.tabText(i))[0]}.{target_format.lower()}"
        )
        _save_as_format(viewer, target_format, file_path)
    QtWidgets.QMessageBox.information(
        window,
        "Save All Successful",
        f"All images saved successfully as {target_format}."
    )

def setup_texture_viewer_tab_window(tab_window: 'ViewerTabWindow'):
    """Setup the texture viewer tab window."""

    save_as_menu = tab_window.menuBar().addMenu("Save As")

    for name in SAVE_AS_FORMATS:
        action = save_as_menu.addAction(name)
        action.triggered.connect(lambda _, fmt=name: _save_current_as_format(tab_window, fmt))

    save_all_as_menu = tab_window.menuBar().addMenu("Save All As")
    for name in SAVE_AS_FORMATS:
        action = save_all_as_menu.addAction(name)
        action.triggered.connect(lambda _, fmt=name: _save_all_as_format(tab_window, fmt))
