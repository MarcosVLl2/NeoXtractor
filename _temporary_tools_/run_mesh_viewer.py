import sys
from PySide6 import QtWidgets

import _use_application_modules # pylint: disable=unused-import

from core.mesh_converter import FORMATS, convert_mesh
from gui.widgets.mesh_viewer import MeshViewer

viewer: MeshViewer

def save_as_format(target_format):
    """
    Save the current mesh in the specified format.
    
    Parameters:
    - target_format: The format to save the mesh as.
    """
    mesh = viewer.render_widget.mesh_data
    if mesh is None:
        QtWidgets.QMessageBox.warning(
            viewer,
            "No Mesh Loaded",
            "Please load a mesh file before saving."
        )
        return
    file_dialog = QtWidgets.QFileDialog()
    file_path, _ = file_dialog.getSaveFileName(
        None,
        f"Save Mesh as {target_format.NAME}",
        "",
        f"{target_format.NAME} Files (*{target_format.EXTENSION})"
    )
    if file_path:
        with open(file_path, "wb") as f:
            f.write(convert_mesh(mesh.raw_data, target_format))

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    wnd = QtWidgets.QWidget()

    layout = QtWidgets.QVBoxLayout(wnd)

    open_button = QtWidgets.QPushButton("Open Mesh File")
    layout.addWidget(open_button)

    def open_mesh_file():
        file_dialog = QtWidgets.QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            wnd,
            "Open Mesh File", 
            "", 
            "Mesh Files (*.mesh)"
        )
        if file_path:
            with open(file_path, "rb") as f:
                viewer.load_mesh(f.read())

    open_button.clicked.connect(open_mesh_file)

    msaa_combobox = QtWidgets.QComboBox()
    layout.addWidget(msaa_combobox)

    viewer = MeshViewer()
    viewer.render_widget.setApi(QtWidgets.QRhiWidget.Api.OpenGL)

    layout.addWidget(viewer)

    save_as_area = QtWidgets.QGridLayout()

    for i, fmt in enumerate(FORMATS):
        btn = QtWidgets.QPushButton(f"Save as {fmt.NAME}")
        btn.clicked.connect(lambda _, fmt=fmt: save_as_format(fmt))
        save_as_area.addWidget(btn, i // 2, i % 2)
    layout.addLayout(save_as_area)

    wnd.setWindowTitle(f"Mesh Viewer - {viewer.render_widget.api().name}")
    wnd.resize(800, 600)
    wnd.show()

    for sample_count in viewer.render_widget.rhi().supportedSampleCounts():
        if sample_count == 1:
            msaa_combobox.addItem("No MSAA", 1)
        else:
            msaa_combobox.addItem(f"{sample_count}x MSAA", sample_count)
    msaa_combobox.setCurrentIndex(0)
    def _set_msaa(value):
        viewer.render_widget.setSampleCount(value)
    msaa_combobox.currentIndexChanged.connect(lambda idx: _set_msaa(msaa_combobox.itemData(idx)))

    print(viewer.render_widget.api())
    sys.exit(app.exec())
