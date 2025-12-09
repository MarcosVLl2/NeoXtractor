import io
from typing import Any, BinaryIO

import numpy as np

from core.binary_readers import read_float, read_uint16, read_uint32, read_uint8, read_half_float
from core.mesh_loader.types import BaseMeshParser, MeshData


class MeshParser5(BaseMeshParser):
    """Enhanced mesh parser with support for half-float formats and adaptive face reading."""
    
    def parse(self, data: bytes) -> MeshData:
        """Parse mesh using the enhanced parsing method."""
        model = {}
        
        f = io.BytesIO(data)
        
        raw_model = self._parse_mesh_enhanced(model, f)
        return self._standardize_mesh_data(raw_model)
    
    def _parse_mesh_enhanced(self, model: dict[str, Any], f: BinaryIO) -> dict[str, Any]:
        """Internal enhanced parsing implementation."""
        _magic_number = f.read(4)
        s_type = f.read(2)
        uk2 = f.read(2)
        
        model['bone_exist'] = read_uint32(f)
        model['mesh'] = []
        
        if model['bone_exist'] != 0 and model['bone_exist'] != 3:
            bone_count = read_uint16(f)
            self._validate_bone_count(bone_count)
            
            parent_nodes = []
            for _ in range(bone_count):
                parent_node = read_uint8(f)
                if parent_node == 255:
                    parent_node = -1
                parent_nodes.append(parent_node)
            model['bone_parent'] = parent_nodes
            
            bone_names = []
            for _ in range(bone_count):
                bone_name = f.read(32)
                try:
                    bone_name = bone_name.decode().replace('\0', '').replace(' ', '_')
                except UnicodeDecodeError:
                    bone_name = bone_name.decode(encoding='gbk').replace('\0', '').replace(' ', '_')
                bone_names.append(bone_name)
            model['bone_name'] = bone_names
            
            bone_extra_info = read_uint8(f)
            if bone_extra_info:
                for _ in range(bone_count):
                    f.read(28)
            
            model['bone_matrix'] = []
            for _ in range(bone_count):
                matrix = [read_float(f) for _ in range(16)]
                matrix = np.array(matrix).reshape(4, 4)
                model['bone_matrix'].append(matrix)
            
            if len(list(filter(lambda x: x == -1, parent_nodes))) > 1:
                num = len(model['bone_parent'])
                model['bone_parent'] = list(map(lambda x: num if x == -1 else x, model['bone_parent']))
                model['bone_parent'].append(-1)
                model['bone_name'].append('dummy_root')
                model['bone_matrix'].append(np.identity(4))
            
            _flag = read_uint8(f)
            if _flag != 0:
                raise ValueError(f"Unexpected _flag value {_flag} at position {f.tell()}")
        
        _offset = read_uint32(f)
        uv_layers = 0
        color_len = 0
        
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
            
            model['mesh'].append((mesh_vertex_count, mesh_face_count, uv_layers, color_len))
        
        vertex_count = read_uint32(f)
        face_count = read_uint32(f)
        
        self._validate_vertex_count(vertex_count)
        self._validate_face_count(face_count)
        
        model['position'] = []
        # vertex position
        for _ in range(vertex_count):
            if model['bone_exist'] < 2:
                x = read_float(f)
                y = read_float(f)
                z = read_float(f)
            else:
                x = read_half_float(f)
                y = read_half_float(f)
                z = read_half_float(f)
            model['position'].append((x, y, z))
        
        model['normal'] = []
        # vertex normal
        for _ in range(vertex_count):
            if model['bone_exist'] < 2:
                x = read_float(f)
                y = read_float(f)
                z = read_float(f)
            else:
                x = read_half_float(f)
                y = read_half_float(f)
                z = read_half_float(f)
            model['normal'].append((x, y, z))


        """
        if read_uint16(f) == 1:
            for _ in range(vertex_count):
                if model['bone_exist'] < 2:
                    x = read_float(f)
                    y = read_float(f)
                    z = read_float(f)
                else:
                    x = read_half_float(f)
                    y = read_half_float(f)
                    z = read_half_float(f)
        else:
            current_position = f.tell()
            f.seek(current_position - 2)
            
        #new normal, but i don't know how to add new normal-maps
        """
        # So just skip it
        # Skip
        if read_uint16(f) == 1:
            f.seek(vertex_count * 12, 1)

        # Face
        model['face'] = []
        face_start_position = f.tell()
        max_face = 0
        
        for _ in range(face_count):
            v1 = read_uint16(f)
            v2 = read_uint16(f)
            v3 = read_uint16(f)
            model['face'].append((v1, v2, v3))
            # if v3 - max_face < 16:
            #     max_face = max(max_face, v1, v2, v3)
            # else:
            #     # Retry with different alignment if needed
            #     model['face'] = []
            #     f.seek(face_start_position - 2)
            #     for _ in range(face_count):
            #         v1 = read_uint16(f)
            #         v2 = read_uint16(f)
            #         v3 = read_uint16(f)
            #         model['face'].append((v1, v2, v3))
            #     break
        
        model['uv'] = []
        # vertex uv
        for mesh_vertex_count, _, uv_layers, color_len in model['mesh']:
            if uv_layers > 0:
                for _ in range(mesh_vertex_count * (uv_layers - color_len)):
                    u = read_float(f)
                    v = read_float(f)
                    model['uv'].append((u, v))
                f.read(mesh_vertex_count * 8 * color_len)
            else:
                for _ in range(mesh_vertex_count):
                    model['uv'].append((0.0, 0.0))
        
        # vertex color
        for mesh_vertex_count, _, _, color_len in model['mesh']:
            f.read(mesh_vertex_count * 4 * color_len)
        
        if model['bone_exist'] != 0 and model['bone_exist'] != 3:
            model['vertex_bone'] = []
            for _ in range(vertex_count):
                vertex_bones = [read_uint8(f) for _ in range(4)]
                model['vertex_bone'].append(vertex_bones)
            
            model['vertex_weight'] = []
            for _ in range(vertex_count):
                vertex_weights = [read_float(f) for _ in range(4)]
                model['vertex_weight'].append(vertex_weights)
        
        return model