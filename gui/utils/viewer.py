"""Viewer utility functions for viewers."""

from typing import Type
from PySide6 import QtWidgets

from core.npk.types import NPKEntry
from gui.widgets.code_editor import CodeEditor
from gui.widgets.hex_viewer import HexViewer
from gui.widgets.mesh_viewer.viewer_widget import MeshViewer
from gui.widgets.texture_viewer import TextureViewer

ALL_VIEWERS = (HexViewer, CodeEditor, TextureViewer, MeshViewer)

def find_best_viewer(extension: str, is_text = False) -> Type[QtWidgets.QWidget]:
    """
    Finds and selects the most appropriate previewer widget for the given NPK entry.
    This method iterates through available previewers and selects one based on the file extension
    of the NPK entry. If a previewer declares compatibility with the entry's extension through
    its 'accepted_extensions' attribute, that previewer is selected. If no specialized previewer
    is found, it defaults to a code editor for text files or a hex viewer for binary files.
    Args:
        extesnion (str): The file extension to find a previewer for
        is_text (bool): Whether the file is a text file or not
    Returns:
        Type[QtWidgets.QWidget]: The class of the selected previewer widget
    """

    for previewer in ALL_VIEWERS:
        if hasattr(previewer, "accepted_extensions"):
            if extension in getattr(previewer, "accepted_extensions"):
                return previewer

    return CodeEditor if is_text else HexViewer

def set_data_for_viewer(viewer: QtWidgets.QWidget, data: bytes | None, extension: str = "dat"):
    """
    Set the data for the viewer.
    
    :param viewer: The viewer to set the data for.
    :param data: The data to set.
    :param extension: The file extension of the data.
    """
    if isinstance(viewer, HexViewer):
        viewer.setData(bytearray(data) if data is not None else bytearray())
    elif isinstance(viewer, CodeEditor):
        if data is None:
            viewer.set_content("")
        else:
            viewer.set_content(data.decode("utf-8", errors="replace"), extension)
    elif isinstance(viewer, TextureViewer):
        if data is None:
            viewer.clear()
        else:
            # Raises ValueError if the image is not supported
            viewer.set_texture(data, extension)
    elif isinstance(viewer, MeshViewer):
        if data is None:
            viewer.unload_mesh()
        else:
            viewer.load_mesh(data)

def set_entry_for_viewer(viewer: QtWidgets.QWidget, data: NPKEntry | None):
    """
    Set the data for the viewer.
    
    :param viewer: The viewer to set the data for.
    :param data: The NPK entry data to set.
    """
    set_data_for_viewer(viewer, data.data if data is not None else None, \
                         data.extension if data is not None else "dat")

def get_viewer_display_name(viewer: QtWidgets.QWidget | type) -> str:
    """
    Get the display name for the viewer.
    
    :param viewer: The viewer to get the display name for.
    :return: The display name of the viewer.
    """
    if hasattr(viewer, "name"):
        return getattr(viewer, "name")
    return viewer.__class__.__name__
