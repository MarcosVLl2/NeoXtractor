import io
from typing import Any, BinaryIO, Iterable

import numpy as np

from core.binary_readers import (
    read_float,
    read_half_float,
    read_uint8,
    read_uint16,
    read_uint32,
)
from core.logger import get_logger
from core.mesh_loader.types import BaseMeshParser, MeshData


def get_file_compatibility_chart(
    version: int, size: int, repeated_entry: int, bones: int, vertexes: int, faces: int
) -> Any:
    if bones == 0:
        comparing = size - 12
    else:
        comparing = 0

    return None


class MeshParser0(BaseMeshParser):
    """Standard mesh parser for typical mesh formats with bone hierarchies."""

    def parse(self, data: bytes) -> MeshData:
        """Parse mesh."""

        f = io.BytesIO(data)

        raw_model = self._parse_mesh_testing(f)
        return self._standardize_mesh_data(raw_model)

    def _parse_mesh_testing(self, f: BinaryIO) -> dict[str, Iterable[Any] | int]:
        """TEORIA: Hacer como NPK y usar un algoritmo de deteccion de tamaño, ajustar acorde (como base)"""
        """AJUSTAR PARA ESE VALOR OPCIONAL: Tamaños validos (66 bytes x face etc...) y por version"""

        model: dict[str, Iterable[Any] | int] = {}
        model["mesh"] = {}
        model["mesh"]["extra"] = []
        parent_nodes: list[int] = []
        MAX_PARENT_NODE = 255

        pattern_reader = read_uint8
        vertex_position_reader = read_float

        f.seek(-14, 2)
        offset = read_uint32(f)
        f.seek(offset)

        while True:
            vertex_count = read_uint32(f)
            face_count = read_uint32(f)
            uv_layers = read_uint8(f)
            is_16bits = read_uint8(f)
            color_len = read_uint8(f)
            must_be_zero = read_uint8(f)
            if color_len == 1 and must_be_zero == 0:
                vertex_count = read_uint32(f)
                face_count = read_uint32(f)
                offset = f.tell()
                break
            else:
                model["mesh"]["extra"].append(
                    (vertex_count, face_count, uv_layers, is_16bits)
                )
                f.seek(-2, 1)

        if is_16bits:
            MAX_PARENT_NODE = 65535
            pattern_reader = read_uint16
            vertex_position_reader = read_float

        f.seek(0)

        _magic_number = read_uint32(f)
        model["mesh_version"] = read_uint16(f)
        read_uint16(f)  # always_0x0500
        model["has_bones"] = read_uint16(f)
        read_uint16(f)  # always_0x0000
        get_logger().info(
            f"MESH: Version {model['mesh_version']} | Bones: {'No' if model['has_bones'] == 0 else model['has_bones']}"
        )

        if model["has_bones"] and pattern_reader is not None:
            model["bone_count"] = bone_count = read_uint16(f)
            self._validate_bone_count(bone_count)

            for _ in range(bone_count):
                parent_node: int = pattern_reader(f)
                if parent_node == MAX_PARENT_NODE:
                    parent_node = -1
                parent_nodes.append(parent_node)
            model["bone_parent"] = parent_nodes

            bone_names: list[str] = []
            for _ in range(bone_count):
                bone_name = f.read(32)
                bone_name = bone_name.decode().replace("\0", "").replace(" ", "_")
                bone_names.append(bone_name)
            model["bone_name"] = bone_names

            bone_extra_info = read_uint8(f)
            if bone_extra_info:
                f.seek(28 * bone_count, 1)

            model["bone_matrix"] = []
            for _ in range(bone_count):
                matrix = [read_float(f) for _ in range(16)]
                matrix = np.array(matrix).reshape(4, 4)
                model["bone_matrix"].append(matrix)

            # creates a new "dummy_root" as a default bone for the rest of the starters to link to
            if parent_nodes.count(-1) > 1:
                num = len(model["bone_parent"])
                model["bone_parent"] = list(
                    map(lambda x: num if x == -1 else x, model["bone_parent"])
                )
                model["bone_parent"].append(-1)
                model["bone_name"].append("dummy_root")
                model["bone_matrix"].append(np.identity(4))

            flag1 = read_uint8(f)
            if flag1 != 0:
                raise ValueError(
                    f"Unexpected _flag value {flag1} at position {hex(f.tell() - 1)}"
                )

        f.seek(offset)

        model["mesh"]["data"] = []
        model["mesh"]["data"].append(
            (
                vertex_count,
                face_count,
                uv_layers,
                color_len,
            )
        )
        get_logger().info(
            f"MESH: Vertexes {vertex_count} | FACES: {face_count} | UV_LAYERS: {'No' if uv_layers == 0 else uv_layers}"
        )

        get_logger().info(
            f"MESH: Geometry Precision {'Half (2 bytes)' if is_16bits else 'Float (4 bytes)'}"
        )

        model["mesh"]["position"] = []
        # vertex position
        for _ in range(vertex_count):
            x = vertex_position_reader(f)
            y = vertex_position_reader(f)
            z = vertex_position_reader(f)
            model["mesh"]["position"].append((x, y, z))

        model["mesh"]["normal"] = []
        # vertex normal
        for _ in range(vertex_count):
            x = vertex_position_reader(f)
            y = vertex_position_reader(f)
            z = vertex_position_reader(f)
            model["mesh"]["normal"].append((x, y, z))

        _flag = read_uint16(f)

        if _flag == 1:
            step = 12
            f.seek(vertex_count * step, 1)

        # data divisions: vertex_count * 8
        #

        model["mesh"]["face"] = []
        # face index table
        for _ in range(face_count):
            v1 = read_uint16(f)
            v2 = read_uint16(f)
            v3 = read_uint16(f)
            model["mesh"]["face"].append((v1, v2, v3))

        model["mesh"]["uv"] = []
        if uv_layers:
            for _ in range(vertex_count):
                model["mesh"]["uv"].append((read_float(f), read_float(f)))
        else:
            for _ in range(vertex_count):
                model["mesh"]["uv"].append((0.0, 0.0))

        if model["has_bones"]:
            # f.seek(vertex_count * 4, 1)

            model["vertex_bone"] = []
            for _ in range(vertex_count):
                model["vertex_bone"].append([read_uint8(f) for _ in range(4)])

            model["vertex_weight"] = []
            for _ in range(vertex_count):
                model["vertex_weight"].append([read_float(f) for _ in range(4)])

        return model
