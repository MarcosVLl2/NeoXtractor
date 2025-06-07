"""Renders a colorful triangle using Qt's RHI API."""

import ctypes
import sys
import os
from typing import cast

from PySide6 import QtGui, QtWidgets

PROJECT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))

VERTEX_DATA = [
    # Vertex position  Colors
       0.0,   0.5,     1.0, 0.0, 0.0,
      -0.5,  -0.5,     0.0, 1.0, 0.0,
       0.5,  -0.5,     0.0, 0.0, 1.0,
]

class ColorTriangleWidget(QtWidgets.QRhiWidget):
    """
    A QRhiWidget that renders a rotating triangle with colors.
    This widget utilizes Qt's RHI (Rendering Hardware Interface) to render a 3D triangle
    with vertex colors. It sets up the necessary graphics pipeline, buffers, and shader
    resource bindings to perform hardware-accelerated rendering.
    The triangle rotates continuously around the Y axis.
    Requirements:
    - Shader files "color.vert.qsb" and "color.frag.qsb" must be available in "data/shaders" 
    Methods:
            initialize(cb): Sets up the rendering resources when the RHI context is ready
            render(cb): Performs the actual rendering of the triangle each frame
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)

        self._rhi: QtGui.QRhi | None = None
        self._pipeline: QtGui.QRhiGraphicsPipeline | None = None
        self._vbuf: QtGui.QRhiBuffer | None = None
        self._ubuf: QtGui.QRhiBuffer | None = None
        self._srb: QtGui.QRhiShaderResourceBindings | None = None
        self._view_proj: QtGui.QMatrix4x4 | None = None

    def initialize(self, cb: QtGui.QRhiCommandBuffer):
        if self._rhi != self.rhi() or self._rhi is None: # type hint
            self._pipeline = None
            self._rhi = self.rhi()

        if self._pipeline is None:
            self._vbuf = self._rhi.newBuffer(QtGui.QRhiBuffer.Type.Immutable,
                                             QtGui.QRhiBuffer.UsageFlag.VertexBuffer,
                                             ctypes.sizeof(ctypes.c_float) * len(VERTEX_DATA)
                                             )
            self._vbuf.create()

            self._ubuf = self._rhi.newBuffer(QtGui.QRhiBuffer.Type.Dynamic,
                                             QtGui.QRhiBuffer.UsageFlag.UniformBuffer,
                                             80
                                             )
            self._ubuf.create()

            self._srb = self._rhi.newShaderResourceBindings()
            self._srb.setBindings([
                QtGui.QRhiShaderResourceBinding.uniformBuffer(0,
                                                              QtGui.QRhiShaderResourceBinding.StageFlag.VertexStage |
                                                              QtGui.QRhiShaderResourceBinding.StageFlag.FragmentStage,
                                                              self._ubuf),
            ])
            self._srb.create()

            self._pipeline = self._rhi.newGraphicsPipeline()
            with open(os.path.join(PROJECT_DIR, "data", "shaders", "color.vert.qsb"), "rb") as f:
                vsrc = f.read()
                vsrc = QtGui.QShader.fromSerialized(vsrc)
                with open(os.path.join(PROJECT_DIR, "data", "shaders", "color.frag.qsb"), "rb") as f:
                    fsrc = f.read()
                    fsrc = QtGui.QShader.fromSerialized(fsrc)

                    self._pipeline.setShaderStages([
                        QtGui.QRhiShaderStage(QtGui.QRhiShaderStage.Type.Vertex, vsrc),
                        QtGui.QRhiShaderStage(QtGui.QRhiShaderStage.Type.Fragment, fsrc)
                    ])
            input_layout = QtGui.QRhiVertexInputLayout()
            input_layout.setBindings([
                QtGui.QRhiVertexInputBinding(5 * ctypes.sizeof(ctypes.c_float)),
            ])
            input_layout.setAttributes([
                QtGui.QRhiVertexInputAttribute(0, 0, QtGui.QRhiVertexInputAttribute.Format.Float2, 0),
                QtGui.QRhiVertexInputAttribute(0, 1, QtGui.QRhiVertexInputAttribute.Format.Float3,
                                               2 * ctypes.sizeof(ctypes.c_float)
                                               ),
            ])
            self._pipeline.setVertexInputLayout(input_layout)
            self._pipeline.setShaderResourceBindings(self._srb)
            self._pipeline.setRenderPassDescriptor(self.renderTarget().renderPassDescriptor())
            self._pipeline.create()

            resource_updates = self._rhi.nextResourceUpdateBatch()
            arr = (ctypes.c_float * len(VERTEX_DATA))(*VERTEX_DATA)
            resource_updates.uploadStaticBuffer(self._vbuf, cast(int, arr))
            cb.resourceUpdate(resource_updates)

        output_size = self.renderTarget().pixelSize()
        self._view_proj = self._rhi.clipSpaceCorrMatrix()
        self._view_proj.perspective(45, output_size.width() / output_size.height(), 0.01, 1000)
        self._view_proj.translate(0, 0, -4)

    def render(self, cb: QtGui.QRhiCommandBuffer):
        if self._rhi is None or self._view_proj is None or self._ubuf is None or self._pipeline is None:
            return

        resource_updates = self._rhi.nextResourceUpdateBatch()
        self._view_proj.rotate(1.5, 0, 1, 0)
        vp_data = self._view_proj.data()
        ubuf_data = list(vp_data) + [1] # MVP and Opacity data
        arr = (ctypes.c_float * len(ubuf_data))(*ubuf_data)
        resource_updates.updateDynamicBuffer(self._ubuf, 0, ctypes.sizeof(arr), cast(int, arr))

        clr = QtGui.QColor.fromRgbF(0.4, 0.7, 0.0, 1.0)
        cb.beginPass(self.renderTarget(), clr, QtGui.QRhiDepthStencilClearValue(1, 0), resource_updates)

        cb.setGraphicsPipeline(self._pipeline)
        cb.setViewport(QtGui.QRhiViewport(0, 0, self.renderTarget().pixelSize().width(),
                                          self.renderTarget().pixelSize().height()))
        cb.setShaderResources()
        cb.setVertexInput(0, [(self._vbuf, 0)])
        cb.draw(3)

        cb.endPass()

        self.update()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    wnd = QtWidgets.QWidget()
    
    layout = QtWidgets.QVBoxLayout(wnd)

    viewer = ColorTriangleWidget()
    viewer.setApi(QtWidgets.QRhiWidget.Api.Vulkan)

    layout.addWidget(viewer)

    wnd.setWindowTitle(f"RHI Test - {viewer.api().name}")
    wnd.resize(800, 600)
    wnd.show()

    print(viewer.api())
    sys.exit(app.exec())
