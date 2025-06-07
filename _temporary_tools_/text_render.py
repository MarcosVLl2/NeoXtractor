"""Render text"""

import ctypes
import sys
import os
import random
from dataclasses import dataclass
from typing import cast

from PySide6 import QtGui, QtWidgets, QtCore
from PIL import Image, ImageDraw, ImageFont

PROJECT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))

@dataclass
class Character:
    """
    Represents a character in a font atlas with texture coordinates and metrics.
    A Character object stores the necessary information to render a single character
    from a font texture atlas, including its position in the texture, dimensions,
    and vertical positioning information.
    Args:
        tex_coords (tuple[int | float, int | float, int | float, int | float]): 
            Texture coordinates in the format (x1, y1, x2, y2) defining the 
            character's position in the texture atlas.
        size (tuple[int | float, int]): 
            The width and height of the character in pixels as (width, height).
        ascent (int): 
            The ascent value representing the distance from the baseline to the 
            top of the character, used for proper vertical alignment.
    Attributes:
        tex_coords: Texture coordinates for the character in the atlas.
        size: Dimensions of the character.
        ascent: Vertical offset from baseline to character top.
    """

    def __init__(self,
                 tex_coords: tuple[int | float, int | float, int | float, int | float],
                 size: tuple[int | float, int],
                 ascent: int):
        self.tex_coords = tex_coords
        self.size = size
        self.ascent = ascent

class TextRenderWidget(QtWidgets.QRhiWidget):
    """
    A Qt widget that renders text using the Qt RHI (Rendering Hardware Interface) API.
    This widget creates a custom text rendering system using OpenGL/Vulkan/Direct3D through Qt's RHI.
    It generates a font atlas texture containing ASCII characters (32-127) and renders text by
    creating quads for each character with appropriate texture coordinates.
    Key Features:
    - Font atlas generation from TrueType fonts or system default
    - Hardware-accelerated text rendering with proper alpha blending
    - Dynamic vertex buffer updates for real-time text changes
    - Orthographic projection setup for 2D text positioning
    - Baseline-aligned character positioning
    The widget automatically handles:
    - Font loading (tries Roboto-Regular.ttf, falls back to default)
    - Texture atlas creation and GPU upload
    - Shader pipeline setup with vertex and fragment shaders
    - Dynamic text positioning and scaling
    - Real-time updates with automatic refresh
    Attributes:
        _rhi: Qt RHI instance for graphics operations
        _pipeline: Graphics pipeline for text rendering
        _vbuf: Dynamic vertex buffer for character quads
        _ibuf: Static index buffer for quad rendering
        _ubuf: Uniform buffer for projection matrix and color
        _srb: Shader resource bindings for textures and uniforms
        _char_data: Dictionary mapping characters to texture coordinates and metrics
        _image: QImage containing the generated font atlas
    Example:
        widget = TextRenderWidget()
        # Text is automatically rendered with current timestamp
        # Override render() method to customize text content and positioning
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)

        self._rhi: QtGui.QRhi | None = None
        self._pipeline: QtGui.QRhiGraphicsPipeline | None = None
        self._vbuf: QtGui.QRhiBuffer | None = None
        self._ibuf: QtGui.QRhiBuffer | None = None
        self._ubuf: QtGui.QRhiBuffer | None = None
        self._srb: QtGui.QRhiShaderResourceBindings | None = None

        self._clr_r = random.random()
        self._clr_r_dir = 1
        self._clr_g = random.random()
        self._clr_g_dir = 1
        self._clr_b = random.random()
        self._clr_b_dir = 1

        self._create_atlas_texture(32)

    def _create_atlas_texture(self, font_size: int):
        atlas_size = 512
        atlas = Image.new('L', (atlas_size, atlas_size), 0)
        atlas_draw = ImageDraw.Draw(atlas)

        font: ImageFont.FreeTypeFont | ImageFont.ImageFont
        try:
            font = ImageFont.truetype(os.path.join(PROJECT_DIR, "data", "fonts", "Roboto-Regular.ttf"), font_size)
        except OSError:
            print("Failed to load font, falling back to default")
            font = ImageFont.load_default()
            if not isinstance(font, ImageFont.FreeTypeFont):
                raise TypeError("Default font is not a FreeTypeFont")

        # Create character map
        self._char_data: dict[str, Character] = {}
        cursor_x, cursor_y = 0, 0
        max_height = 0

        ascent, descent = font.getmetrics()
        total_height = ascent + descent

        for char_code in range(32, 128):
            char = chr(char_code)
            bbox = font.getbbox(char)
            char_width = bbox[2] - bbox[0]
            char_height = bbox[3] - bbox[1]

            if cursor_x + char_width >= atlas_size:
                cursor_x = 0
                cursor_y += total_height + 2
                max_height = 0

            if char_height > max_height:
                max_height = char_height

            # Draw character aligned to the baseline
            atlas_draw.text((cursor_x, cursor_y + ascent), char, font=font, fill=255, anchor="ls")

            self._char_data[char] = Character(
                (
                    cursor_x / atlas_size,
                    cursor_y / atlas_size,
                    (cursor_x + char_width) / atlas_size,
                    (cursor_y + total_height) / atlas_size
                ),
                (char_width, total_height),
                ascent
            )

            cursor_x += char_width + 2

        print(f"Font atlas created with {len(self._char_data)} characters")

        # Convert to QImage with proper format and stride
        self._image = QtGui.QImage(atlas.tobytes(), atlas.size[0], atlas.size[1],
                                  atlas.size[0], QtGui.QImage.Format.Format_Grayscale8)

    def initialize(self, cb: QtGui.QRhiCommandBuffer):
        if self._rhi != self.rhi() or self._rhi is None: # type hint
            self._pipeline = None
            self._rhi = self.rhi()

        if self._pipeline is None:
            resource_updates = self._rhi.nextResourceUpdateBatch()

            # Create texture from atlas
            texture = self._rhi.newTexture(QtGui.QRhiTexture.Format.R8, self._image.size())
            texture.create()
            resource_updates.uploadTexture(texture, self._image)

            # Create vertex buffer for dynamic geometry
            self._vbuf = self._rhi.newBuffer(QtGui.QRhiBuffer.Type.Dynamic,
                                        QtGui.QRhiBuffer.UsageFlag.VertexBuffer,
                                        4096 * 4 * 4)  # Enough space for many characters
            self._vbuf.create()

            # Create index buffer for rendering quads (0,1,2, 0,2,3)
            self._ibuf = self._rhi.newBuffer(QtGui.QRhiBuffer.Type.Immutable,
                                        QtGui.QRhiBuffer.UsageFlag.IndexBuffer,
                                        1024 * 6 * 2)  # 6 indices per quad (uint16), 1024 quads max
            self._ibuf.create()

            # Fill index buffer with quad indices pattern (0,1,2, 0,2,3, ...)
            indices = []
            for i in range(1024):
                base = i * 4
                indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])

            index_data = (ctypes.c_uint16 * len(indices))(*indices)
            resource_updates.uploadStaticBuffer(self._ibuf, cast(int, index_data))

            # Create uniform buffer for projection matrix and text color
            self._ubuf = self._rhi.newBuffer(QtGui.QRhiBuffer.Type.Dynamic,
                                        QtGui.QRhiBuffer.UsageFlag.UniformBuffer,
                                        64)  # Matrix (64 bytes)
            self._ubuf.create()

            sampler = self._rhi.newSampler(QtGui.QRhiSampler.Filter.Nearest,
                                        QtGui.QRhiSampler.Filter.Nearest,
                                        QtGui.QRhiSampler.Filter.None_,
                                        QtGui.QRhiSampler.AddressMode.ClampToEdge,
                                        QtGui.QRhiSampler.AddressMode.ClampToEdge)
            sampler.create()

            # Create shader resource bindings
            self._srb = self._rhi.newShaderResourceBindings()
            self._srb.setBindings([
                QtGui.QRhiShaderResourceBinding.uniformBuffer(0, QtGui.QRhiShaderResourceBinding.StageFlag.VertexStage |
                                                        QtGui.QRhiShaderResourceBinding.StageFlag.FragmentStage,
                                                        self._ubuf),
                QtGui.QRhiShaderResourceBinding.sampledTexture(1,
                                                        QtGui.QRhiShaderResourceBinding.StageFlag.FragmentStage,
                                                        texture, sampler)
            ])
            self._srb.create()

            # Create graphics pipeline
            self._pipeline = self._rhi.newGraphicsPipeline()

            with open(os.path.join(PROJECT_DIR, "data", "shaders", "text.vert.qsb"), "rb") as f:
                vsrc = f.read()
                vsrc = QtGui.QShader.fromSerialized(vsrc)
                with open(os.path.join(PROJECT_DIR, "data", "shaders", "text.frag.qsb"), "rb") as f:
                    fsrc = f.read()
                    fsrc = QtGui.QShader.fromSerialized(fsrc)

                    self._pipeline.setShaderStages([
                        QtGui.QRhiShaderStage(QtGui.QRhiShaderStage.Type.Vertex, vsrc),
                        QtGui.QRhiShaderStage(QtGui.QRhiShaderStage.Type.Fragment, fsrc)
                    ])

            # Set up vertex input layout
            input_layout = QtGui.QRhiVertexInputLayout()
            input_layout.setBindings([
                QtGui.QRhiVertexInputBinding(8 * ctypes.sizeof(ctypes.c_float))
                # 8 floats per vertex (pos.xy + tex.uv + color.rgba)
            ])
            input_layout.setAttributes([
                QtGui.QRhiVertexInputAttribute(0, 0, QtGui.QRhiVertexInputAttribute.Format.Float2, 0),
                QtGui.QRhiVertexInputAttribute(0, 1, QtGui.QRhiVertexInputAttribute.Format.Float2,
                                               2 * ctypes.sizeof(ctypes.c_float)),
                QtGui.QRhiVertexInputAttribute(0, 2, QtGui.QRhiVertexInputAttribute.Format.Float4,
                                               4 * ctypes.sizeof(ctypes.c_float))
            ])

            self._pipeline.setVertexInputLayout(input_layout)
            self._pipeline.setShaderResourceBindings(self._srb)
            self._pipeline.setRenderPassDescriptor(self.renderTarget().renderPassDescriptor())

            # Set up blending for text rendering
            target_blend = QtGui.QRhiGraphicsPipeline.TargetBlend()
            # TargetBlend is not currently typed
            target_blend.enable = True # type: ignore
            target_blend.srcColor = QtGui.QRhiGraphicsPipeline.BlendFactor.SrcAlpha # type: ignore
            target_blend.dstColor = QtGui.QRhiGraphicsPipeline.BlendFactor.OneMinusSrcAlpha # type: ignore
            target_blend.srcAlpha = QtGui.QRhiGraphicsPipeline.BlendFactor.One # type: ignore
            target_blend.dstAlpha = QtGui.QRhiGraphicsPipeline.BlendFactor.OneMinusSrcAlpha # type: ignore

            self._pipeline.setTargetBlends([target_blend])

            # Create the pipeline
            self._pipeline.create()

            cb.resourceUpdate(resource_updates)

    def render(self, cb: QtGui.QRhiCommandBuffer):
        if self._rhi is None or self._vbuf is None or self._ubuf is None or self._pipeline is None:
            return

        projection = QtGui.QMatrix4x4()
        projection.ortho(0, self.renderTarget().pixelSize().width(), self.renderTarget().pixelSize().height(),
                         0, -1.0, 1.0)

        # Convert matrix and color to array
        matrix_data = projection.data()

        uniform_array = (ctypes.c_float * len(matrix_data))(*matrix_data)

        resource_updates = self._rhi.nextResourceUpdateBatch()
        resource_updates.updateDynamicBuffer(self._ubuf, 0, ctypes.sizeof(uniform_array),
                                           cast(int, uniform_array))

        scale = 1
        x, y = 10, self.renderTarget().pixelSize().height() - 32
        text = "Hello World! Current time: " + QtCore.QDateTime.currentDateTime().toString("hh:mm:ss")

        self._clr_r += (0.012 + 0.02) * random.random() * self._clr_g_dir
        if self._clr_r > 1.0 or self._clr_r < 0.0:
            self._clr_r_dir *= -1
        self._clr_r = max(0.0, min(1.0, self._clr_r))
        self._clr_g += (0.009 + 0.001) * random.random() * self._clr_g_dir
        if self._clr_g > 1.0 or self._clr_g < 0.0:
            self._clr_g_dir *= -1
        self._clr_g = max(0.0, min(1.0, self._clr_g))
        self._clr_b += (0.01 + 0.002) * random.random() * self._clr_b_dir
        if self._clr_b > 1.0 or self._clr_b < 0.0:
            self._clr_b_dir *= -1
        self._clr_b = max(0.0, min(1.0, self._clr_b))
        color_data = [self._clr_r, self._clr_g, self._clr_b, 1.0]

        # Generate vertices for text
        vertices = []
        char_count = 0
        cursor_x = x

        for char in text:
            if char not in self._char_data:
                print(f"Character '{char}' not found in atlas")
                continue

            char_info = self._char_data[char]
            w, h = char_info.size
            w, h = w * scale, h * scale
            tex_coords = char_info.tex_coords

            # Position character relative to baseline
            char_y = y - (char_info.ascent * scale)

            # Add quad vertices (position + texcoord for each vertex)
            quad = [
                # Bottom-left
                cursor_x, char_y + h, tex_coords[0], tex_coords[1]
            ] + color_data + [
                # Top-left
                cursor_x, char_y, tex_coords[0], tex_coords[3]
            ] + color_data + [
                # Top-right
                cursor_x + w, char_y, tex_coords[2], tex_coords[3]
            ] + color_data + [
                # Bottom-right
                cursor_x + w, char_y + h, tex_coords[2], tex_coords[1]
            ] + color_data
            vertices.extend(quad)
            cursor_x += w
            char_count += 1

        # Skip if no valid characters
        if char_count == 0:
            return

        # Convert vertices to array
        vertex_array = (ctypes.c_float * len(vertices))(*vertices)

        # Update vertex buffer
        resource_updates.updateDynamicBuffer(self._vbuf, 0, ctypes.sizeof(vertex_array),
                                          cast(int, vertex_array))

        clr = QtGui.QColor.fromRgbF(0, 0, 0, 1.0)
        cb.beginPass(self.renderTarget(), clr, QtGui.QRhiDepthStencilClearValue(1, 0), resource_updates)

        # Set up render pass (continue existing pass)
        cb.setGraphicsPipeline(self._pipeline)
        cb.setViewport(QtGui.QRhiViewport(0, 0, self.renderTarget().pixelSize().width(),
                                          self.renderTarget().pixelSize().height()))
        cb.setShaderResources()

        if self._vbuf is not None and self._ibuf is not None:
            cb.setVertexInput(0, [(self._vbuf, 0)], self._ibuf, 0, QtGui.QRhiCommandBuffer.IndexFormat.IndexUInt16)

            # Draw text (6 indices per quad)
            cb.drawIndexed(char_count * 6, 1, 0)

        cb.endPass()

        self.update()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    wnd = QtWidgets.QWidget()

    layout = QtWidgets.QVBoxLayout(wnd)

    viewer = TextRenderWidget()
    viewer.setApi(QtWidgets.QRhiWidget.Api.Vulkan)

    layout.addWidget(viewer)

    wnd.setWindowTitle(f"Text Render - {viewer.api().name}")
    wnd.resize(800, 600)
    wnd.show()

    print(viewer.api())
    sys.exit(app.exec())
