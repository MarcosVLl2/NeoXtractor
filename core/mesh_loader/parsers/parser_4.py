import io
import struct
from typing import Any, BinaryIO, Optional

import numpy as np

from core.binary_readers import read_float, read_uint8, read_uint16, read_uint32
from core.mesh_loader.exceptions import MeshParsingError
from core.mesh_loader.types import (
    MAX_FACE_COUNT,
    MAX_VERTEX_COUNT,
    BaseMeshParser,
    MeshData,
)


class MeshParser4(BaseMeshParser):
    """Adaptive mesh parser that dynamically finds valid mesh offsets for corrupted or variable format files."""

    def parse(self, data: bytes) -> MeshData:
        """Parse mesh using the adaptive parsing method."""
        model = {}

        f = io.BytesIO(data)

        raw_model = self._parse_mesh_dynamic(model, f)
        return self._standardize_mesh_data(raw_model)

    def _find_valid_mesh_offset(self, f: BinaryIO) -> Optional[int]:
        """Scans for a valid mesh offset based on expected patterns."""
        file_size = f.seek(0, 2)  # Get file size
        f.seek(0)  # Reset position
        for offset in range(0, file_size - 8):  # Avoid EOF errors
            f.seek(offset)
            try:
                vertex_count = read_uint32(f)
                face_count = read_uint32(f)
                if (
                    10 < vertex_count < MAX_VERTEX_COUNT
                    and 10 < face_count < MAX_FACE_COUNT
                ):
                    return offset
            except struct.error:
                continue
        return None  # No valid offset found

    def _parse_mesh_dynamic(self, model: dict[str, Any], f: BinaryIO) -> dict[str, Any]:
        """Parses a .mesh file, dynamically finding the correct mesh offset."""
        _magic_number = f.read(8)

        # Read mesh version
        current_pos = f.tell()
        f.seek(4)
        model["mesh_version"] = read_uint8(f)

        f.seek(12)
        model["bone_count"] = read_uint8(f)
        f.seek(current_pos)  # Reset to position after magic number

        model["bone_exist"] = read_uint32(f)
        model["mesh"] = []

        if model["bone_exist"]:
            if model["bone_exist"] > 1:
                count = read_uint8(f)
                f.read(2)
                f.read(count * 4)
            bone_count = read_uint16(f)
            self._validate_bone_count(bone_count)
            model["bone_parent"] = [read_uint16(f) for _ in range(bone_count)]
            model["bone_name"] = [
                f.read(32).decode(errors="ignore").strip("\0").replace(" ", "_")
                for _ in range(bone_count)
            ]
            bone_extra_info = read_uint8(f)
            if bone_extra_info:
                for _ in range(bone_count):
                    f.read(28)
            model["bone_matrix"] = [
                np.array([read_float(f) for _ in range(16)]).reshape(4, 4)
                for _ in range(bone_count)
            ]

        # Find correct mesh offset
        mesh_offset = self._find_valid_mesh_offset(f)
        if mesh_offset is None:
            raise MeshParsingError("Could not find valid mesh offset")
        f.seek(mesh_offset)

        vertex_count = read_uint32(f)
        face_count = read_uint32(f)

        self._validate_vertex_count(vertex_count)
        self._validate_face_count(face_count)

        model["position"] = [
            (read_float(f), read_float(f), read_float(f)) for _ in range(vertex_count)
        ]
        model["normal"] = [
            (read_float(f), read_float(f), read_float(f)) for _ in range(vertex_count)
        ]

        _flag = read_uint16(f)
        if _flag:
            f.seek(vertex_count * 12, 1)

        model["face"] = [
            (read_uint16(f), read_uint16(f), read_uint16(f)) for _ in range(face_count)
        ]

        model["uv"] = []
        for mesh_vertex_count, _, uv_layers, _ in model["mesh"]:
            if uv_layers > 0:
                for _ in range(mesh_vertex_count):
                    u = read_float(f)
                    v = read_float(f)
                    model["uv"].append((u, v))
                f.read(mesh_vertex_count * 8 * (uv_layers - 1))
            else:
                for _ in range(mesh_vertex_count):
                    model["uv"].append((0.0, 0.0))

        for mesh_vertex_count, _, _, color_len in model["mesh"]:
            f.read(mesh_vertex_count * 4 * color_len)

        if model["bone_exist"]:
            model["vertex_bone"] = [
                [read_uint8(f) for _ in range(4)] for _ in range(vertex_count)
            ]
            model["vertex_weight"] = [
                [read_float(f) for _ in range(4)] for _ in range(vertex_count)
            ]

        return model
