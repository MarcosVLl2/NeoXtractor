import io
from typing import Any, BinaryIO

import numpy as np

from core.binary_readers import read_float, read_uint8, read_uint16, read_uint32
from core.mesh_loader.types import BaseMeshParser, MeshData


class MeshParser3(BaseMeshParser):
    """Robust mesh parser with enhanced error handling and byte-level validation."""

    def parse(self, data: bytes) -> MeshData:
        """Parse mesh using the robust parsing method."""
        model = {}

        f = io.BytesIO(data)

        raw_model = self._parser_mesh_bytes(model, f)
        return self._standardize_mesh_data(raw_model)

    def _parser_mesh_bytes(self, model: dict[str, Any], f: BinaryIO) -> dict[str, Any]:
        """Internal robust parsing implementation."""
        _magic_number = f.read(8)

        # Read mesh version
        current_pos = f.tell()
        f.seek(4)
        model["mesh_version"] = read_uint8(f)

        f.seek(12)
        model["bone_count"] = read_uint8(f)
        f.seek(current_pos)  # Reset to position after magic number

        model["has_bones"] = read_uint32(f)
        model["mesh"] = {}

        if model["has_bones"]:
            if model["has_bones"] > 1:
                count = read_uint8(f)
                f.read(2)
                f.read(count * 4)
            bone_count = read_uint16(f)
            self._validate_bone_count(bone_count)
            parent_nodes = []
            for _ in range(bone_count):
                parent_node = read_uint8(f)
                if parent_node == 255:
                    parent_node = -1
                parent_nodes.append(parent_node)
            model["bone_parent"] = parent_nodes

            bone_names = []
            for _ in range(bone_count):
                bone_name = f.read(32)
                bone_name = bone_name.decode().replace("\0", "").replace(" ", "_")
                bone_names.append(bone_name)
            model["bone_name"] = bone_names

            bone_extra_info = read_uint8(f)
            if bone_extra_info:
                for _ in range(bone_count):
                    f.read(28)

            model["bone_matrix"] = []
            for _ in range(bone_count):
                matrix = [read_float(f) for _ in range(16)]
                matrix = np.array(matrix).reshape(4, 4)
                model["bone_matrix"].append(matrix)

            if len(list(filter(lambda x: x == -1, parent_nodes))) > 1:
                num = len(model["bone_parent"])
                model["bone_parent"] = list(
                    map(lambda x: num if x == -1 else x, model["bone_parent"])
                )
                model["bone_parent"].append(-1)
                model["bone_name"].append("dummy_root")
                model["bone_matrix"].append(np.identity(4))

            _flag = read_uint8(f)
            if _flag != 0:
                raise ValueError(
                    f"Unexpected _flag value {_flag} at position {f.tell()}"
                )

        _offset = read_uint32(f)
        model["mesh"]["data"] = []
        while True:
            flag = read_uint16(f)
            if flag == 1:
                break
            f.seek(-2, 1)
            mesh_vertex_count = read_uint32(f)
            mesh_face_count = read_uint32(f)
            uv_layers = read_uint8(f)
            color_len = read_uint8(f)

            self._validate_vertex_count(mesh_vertex_count)
            self._validate_face_count(mesh_face_count)

            model["mesh"]["data"].append(
                (mesh_vertex_count, mesh_face_count, uv_layers, color_len)
            )

        vertex_count = read_uint32(f)
        face_count = read_uint32(f)

        self._validate_vertex_count(vertex_count)
        self._validate_face_count(face_count)

        model["mesh"]["position"] = []
        # vertex position
        for _ in range(vertex_count):
            x = read_float(f)
            y = read_float(f)
            z = read_float(f)
            model["mesh"]["position"].append((x, y, z))

        model["mesh"]["normal"] = []
        # vertex normal
        for _ in range(vertex_count):
            x = read_float(f)
            y = read_float(f)
            z = read_float(f)
            model["mesh"]["normal"].append((x, y, z))

        _flag = read_uint16(f)
        if _flag:
            f.seek(vertex_count * 12, 1)

        model["mesh"]["face"] = []
        # face index table
        for _ in range(face_count):
            v1 = read_uint16(f)
            v2 = read_uint16(f)
            v3 = read_uint16(f)
            model["mesh"]["face"].append((v1, v2, v3))

        model["mesh"]["uv"] = []
        # vertex uv
        for mesh_vertex_count, _, uv_layers, _ in model["mesh"]["data"]:
            if uv_layers > 0:
                for _ in range(mesh_vertex_count):
                    u = read_float(f)
                    v = read_float(f)
                    model["mesh"]["uv"].append((u, v))
                f.read(mesh_vertex_count * 8 * (uv_layers - 1))
            else:
                for _ in range(mesh_vertex_count):
                    u = 0.0
                    v = 0.0
                    model["mesh"]["uv"].append((u, v))

        # vertex color
        for mesh_vertex_count, _, _, color_len in model["mesh"]["data"]:
            f.read(mesh_vertex_count * 4 * color_len)

        if model["has_bones"]:
            model["vertex_bone"] = []
            for _ in range(vertex_count):
                vertex_bones = [read_uint8(f) for _ in range(4)]
                model["vertex_bone"].append(vertex_bones)

            model["vertex_weight"] = []
            for _ in range(vertex_count):
                vertex_weights = [read_float(f) for _ in range(4)]
                model["vertex_weight"].append(vertex_weights)

        return model
