"""
Base parser class and specific mesh parser implementations.
"""

import io
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, BinaryIO, Optional, List, Tuple

import numpy as np

from core.binary_readers import read_uint32, read_uint16, read_uint8, read_float
from .exceptions import MeshParsingError


@dataclass
class MeshData:
    """
    Standardized mesh data structure containing all parsed mesh information.
    
    This dataclass provides a consistent interface for mesh data across all parsers,
    ensuring type safety and clear documentation of the expected data structure.
    """
    # Core mesh geometry
    position: List[Tuple[float, float, float]] = field(default_factory=list)
    normal: List[Tuple[float, float, float]] = field(default_factory=list)
    face: List[Tuple[int, int, int]] = field(default_factory=list)
    uv: List[Tuple[float, float]] = field(default_factory=list)
    
    # Bone/skeleton data
    bone_exist: int = 0
    bone_parent: List[int] = field(default_factory=list)
    bone_name: List[str] = field(default_factory=list)
    bone_matrix: List[np.ndarray] = field(default_factory=list)
    bone_count: int = 0
    
    # Vertex bone assignments
    vertex_bone: List[List[int]] = field(default_factory=list)
    vertex_weight: List[List[float]] = field(default_factory=list)
    
    # Mesh metadata
    mesh: List[Tuple[int, int, int, int]] = field(default_factory=list)
    mesh_version: int = 0
    
    # Additional optional data
    material_id: List[int] = field(default_factory=list)
    vertex_color: List[Tuple[float, float, float, float]] = field(default_factory=list)
    
    @property
    def vertex_count(self) -> int:
        """Get the number of vertices in the mesh."""
        return len(self.position)
    
    @property
    def face_count(self) -> int:
        """Get the number of faces in the mesh."""
        return len(self.face)
    
    @property
    def has_bones(self) -> bool:
        """Check if the mesh has bone data."""
        return self.bone_exist > 0 and len(self.bone_name) > 0
    
    @property
    def has_normals(self) -> bool:
        """Check if the mesh has normal data."""
        return len(self.normal) == len(self.position)
    
    @property
    def has_uvs(self) -> bool:
        """Check if the mesh has UV coordinate data."""
        return len(self.uv) == len(self.position)
    
    def validate(self) -> bool:
        """
        Validate the consistency of mesh data.
        
        Returns:
            True if the mesh data is consistent, False otherwise
        """
        vertex_count = self.vertex_count
        
        # Check that face indices are valid
        if self.face:
            max_index = max(max(face) for face in self.face)
            if max_index >= vertex_count:
                return False
        
        # Check bone data consistency
        if self.has_bones:
            if len(self.vertex_bone) != vertex_count or len(self.vertex_weight) != vertex_count:
                return False
            
            # Check bone indices are valid
            if self.vertex_bone:
                max_bone_index = max(max(bones) for bones in self.vertex_bone)
                if max_bone_index >= len(self.bone_name):
                    return False
        
        return True


class BaseMeshParser(ABC):
    """Abstract base class for mesh parsers."""
    
    @abstractmethod
    def parse(self, data: bytes, file_obj: Optional[BinaryIO] = None) -> MeshData:
        """
        Parse mesh data.
        
        Args:
            data: Raw mesh data as bytes
            file_obj: Optional file-like object for reading
            
        Returns:
            MeshData object containing parsed mesh data
            
        Raises:
            MeshParsingError: If parsing fails
        """
        raise NotImplementedError
    
    def _standardize_mesh_data(self, model: Dict[str, Any]) -> MeshData:
        """
        Convert raw parsed data to standardized MeshData object.
        
        Args:
            model: Raw parsed mesh data dictionary
            
        Returns:
            Standardized MeshData object with unified field names and structure
        """
        # Create MeshData with unified field mapping
        mesh_data = MeshData(
            # Core mesh data
            position=model.get('position', []),
            normal=model.get('normal', []),
            face=model.get('face', []),
            uv=model.get('uv', []),
            
            # Bone data
            bone_exist=model.get('bone_exist', 0),
            bone_parent=model.get('bone_parent', []),
            bone_name=model.get('bone_name', []),
            bone_matrix=model.get('bone_original_matrix', model.get('bone_matrix', [])),
            bone_count=model.get('bone_count', 0),
            
            # Vertex bone assignments - unify different field names
            vertex_bone=model.get('vertex_joint', model.get('vertex_bone', [])),
            vertex_weight=model.get('vertex_joint_weight', model.get('vertex_weight', [])),
            
            # Mesh metadata
            mesh=model.get('mesh', []),
            mesh_version=model.get('mesh_version', 0),
            
            # Additional fields if present
            material_id=model.get('material_id', []),
            vertex_color=model.get('vertex_color', []),
        )
        
        # Ensure consistent bone naming
        if mesh_data.bone_name:
            mesh_data.bone_name = [
                name.replace('\0', '').replace(' ', '_').strip() 
                for name in mesh_data.bone_name
            ]
        
        # Ensure consistent data types for vertex counts
        if mesh_data.position:
            vertex_count = len(mesh_data.position)
            
            # Pad missing normals with zero vectors
            if len(mesh_data.normal) < vertex_count:
                mesh_data.normal.extend([(0.0, 0.0, 0.0)] * (vertex_count - len(mesh_data.normal)))
            
            # Pad missing UV coordinates with zero vectors
            if len(mesh_data.uv) < vertex_count:
                mesh_data.uv.extend([(0.0, 0.0)] * (vertex_count - len(mesh_data.uv)))
            
            # Pad missing bone assignments
            if mesh_data.bone_exist and len(mesh_data.vertex_bone) < vertex_count:
                mesh_data.vertex_bone.extend([[0, 0, 0, 0]] * (vertex_count - len(mesh_data.vertex_bone)))
                
            # Pad missing bone weights
            if mesh_data.bone_exist and len(mesh_data.vertex_weight) < vertex_count:
                mesh_data.vertex_weight.extend([[1.0, 0.0, 0.0, 0.0]] * (vertex_count - len(mesh_data.vertex_weight)))
        
        return mesh_data


class StandardMeshParser(BaseMeshParser):
    """Standard mesh parser for typical mesh formats with bone hierarchies."""
    
    def parse(self, data: bytes, file_obj: Optional[BinaryIO] = None) -> MeshData:
        """Parse mesh using the standard parsing method."""
        model = {}
        
        if file_obj is None:
            file_obj = io.BytesIO(data)
        
        raw_model = self._parse_mesh_original(model, file_obj)
        return self._standardize_mesh_data(raw_model)
    
    def _parse_mesh_original(self, model: Dict[str, Any], f: BinaryIO) -> Dict[str, Any]:
        """Internal standard parsing implementation."""
        _magic_number = f.read(8)

        # Read mesh version
        current_pos = f.tell()
        f.seek(4)
        model['mesh_version'] = read_uint8(f)

        f.seek(12)
        model['bone_count'] = read_uint8(f)
        f.seek(current_pos)  # Reset to position after magic number

        model['bone_exist'] = read_uint32(f)
        model['mesh'] = []
        parent_nodes = []

        if model['bone_exist']:
            if model['bone_exist'] > 1:
                count = read_uint8(f)
                f.read(2)
                f.read(count * 4)
            bone_count = read_uint16(f)
            for _ in range(bone_count):
                parent_node = read_uint16(f)
                if parent_node == 65535:
                    parent_node = -1
                parent_nodes.append(parent_node)
            model['bone_parent'] = parent_nodes

            bone_names = []
            for _ in range(bone_count):
                bone_name = f.read(32)
                bone_name = bone_name.decode().replace('\0', '').replace(' ', '_')
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
        while True:
            flag = read_uint16(f)
            if flag == 1:
                break
            f.seek(-2, 1)
            mesh_vertex_count = read_uint32(f)
            mesh_face_count = read_uint32(f)
            _flag = read_uint8(f)
            color_len = read_uint8(f)

            model['mesh'].append((mesh_vertex_count, mesh_face_count, _flag, color_len))

        vertex_count = read_uint32(f)
        face_count = read_uint32(f)

        model['position'] = []
        # vertex position
        for _ in range(vertex_count):
            x = read_float(f)
            y = read_float(f)
            z = read_float(f)
            model['position'].append((x, y, z))

        model['normal'] = []
        # vertex normal
        for _ in range(vertex_count):
            x = read_float(f)
            y = read_float(f)
            z = read_float(f)
            model['normal'].append((x, y, z))

        _flag = read_uint16(f)
        if _flag:
            f.seek(vertex_count * 12, 1)

        model['face'] = []
        # face index table
        for _ in range(face_count):
            v1 = read_uint16(f)
            v2 = read_uint16(f)
            v3 = read_uint16(f)
            model['face'].append((v1, v2, v3))

        model['uv'] = []
        # vertex uv
        for mesh_vertex_count, _, uv_layers, _ in model['mesh']:
            if uv_layers > 0:
                for _ in range(mesh_vertex_count):
                    u = read_float(f)
                    v = read_float(f)
                    model['uv'].append((u, v))
                f.read(mesh_vertex_count * 8 * (uv_layers - 1))
            else:
                for _ in range(mesh_vertex_count):
                    u = 0.0
                    v = 0.0
                    model['uv'].append((u, v))        # vertex color
        for mesh_vertex_count, _, _, color_len in model['mesh']:
            f.read(mesh_vertex_count * 4 * color_len)

        if model['bone_exist']:
            model['vertex_bone'] = []
            for _ in range(vertex_count):
                vertex_bones = [read_uint16(f) for _ in range(4)]
                model['vertex_bone'].append(vertex_bones)

            model['vertex_weight'] = []
            for _ in range(vertex_count):
                vertex_weights = [read_float(f) for _ in range(4)]
                model['vertex_weight'].append(vertex_weights)

        return model


class SimplifiedMeshParser(BaseMeshParser):
    """Simplified mesh parser for alternative mesh formats with streamlined bone processing."""
    
    def parse(self, data: bytes, file_obj: Optional[BinaryIO] = None) -> MeshData:
        """Parse mesh using the simplified parsing method."""
        if isinstance(data, bytes):
            raw_model = self._parse_mesh_helper(data)
        else:
            # data is assumed to be a file path
            with open(data, 'rb') as f:
                file_content = f.read()
            raw_model = self._parse_mesh_helper(file_content)
        return self._standardize_mesh_data(raw_model)
    
    def _parse_mesh_helper(self, path: bytes) -> Dict[str, Any]:
        """Internal simplified parsing implementation."""
        model = {}
        with io.BytesIO(path) as f:
            _magic_number = f.read(8)

            # Read mesh version
            current_pos = f.tell()
            f.seek(4)
            model['mesh_version'] = read_uint8(f)

            f.seek(12)
            model['bone_count'] = read_uint8(f)
            f.seek(current_pos)  # Reset to position after magic number

            model['bone_exist'] = read_uint32(f)
            model['mesh'] = []

            if model['bone_exist']:
                if model['bone_exist'] == 1 or model['bone_exist'] == 4:
                    count = read_uint8(f)
                    f.read(2)
                    f.read(count * 4)
                bone_count = read_uint16(f)
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
                    bone_name = bone_name.decode().replace('\0', '').replace(' ', '_')
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
                assert _flag == 0

            _offset = read_uint32(f)
            while True:
                flag = read_uint16(f)
                if flag == 1:
                    break
                f.seek(-2, 1)
                mesh_vertex_count = read_uint32(f)
                mesh_face_count = read_uint32(f)
                uv_layers = read_uint8(f)
                color_len = read_uint8(f)

                model['mesh'].append((mesh_vertex_count, mesh_face_count, uv_layers, color_len))

            vertex_count = read_uint32(f)
            face_count = read_uint32(f)

            model['position'] = []
            # vertex position
            for _ in range(vertex_count):
                x = read_float(f)
                y = read_float(f)
                z = read_float(f)
                model['position'].append((x, y, z))

            model['normal'] = []
            # vertex normal
            for _ in range(vertex_count):
                x = read_float(f)
                y = read_float(f)
                z = read_float(f)
                model['normal'].append((x, y, z))

            _flag = read_uint16(f)
            if _flag:
                f.seek(vertex_count * 12, 1)

            model['face'] = []
            # face index table
            for _ in range(face_count):
                v1 = read_uint16(f)
                v2 = read_uint16(f)
                v3 = read_uint16(f)
                model['face'].append((v1, v2, v3))

            model['uv'] = []
            # vertex uv
            for mesh_vertex_count, _, uv_layers, _ in model['mesh']:
                if uv_layers > 0:
                    for _ in range(mesh_vertex_count):
                        u = read_float(f)
                        v = read_float(f)
                        model['uv'].append((u, v))
                    f.read(mesh_vertex_count * 8 * (uv_layers - 1))
                else:
                    for _ in range(mesh_vertex_count):
                        u = 0.0
                        v = 0.0
                        model['uv'].append((u, v))

            # vertex color
            for mesh_vertex_count, _, _, color_len in model['mesh']:
                f.read(mesh_vertex_count * 4 * color_len)

            if model['bone_exist']:
                model['vertex_bone'] = []
                for _ in range(vertex_count):
                    vertex_bones = [read_uint8(f) for _ in range(4)]
                    model['vertex_bone'].append(vertex_bones)

                model['vertex_weight'] = []
                for _ in range(vertex_count):
                    vertex_weights = [read_float(f) for _ in range(4)]
                    model['vertex_weight'].append(vertex_weights)

        return model


class RobustMeshParser(BaseMeshParser):
    """Robust mesh parser with enhanced error handling and byte-level validation."""
    
    def parse(self, data: bytes, file_obj: Optional[BinaryIO] = None) -> MeshData:
        """Parse mesh using the robust parsing method."""
        model = {}
        
        if file_obj is None:
            file_obj = io.BytesIO(data)
            
        raw_model = self._parser_mesh_bytes(model, file_obj)
        return self._standardize_mesh_data(raw_model)
    
    def _parser_mesh_bytes(self, model: Dict[str, Any], f: BinaryIO) -> Dict[str, Any]:
        """Internal robust parsing implementation."""
        _magic_number = f.read(8)

        # Read mesh version
        current_pos = f.tell()
        f.seek(4)
        model['mesh_version'] = read_uint8(f)

        f.seek(12)
        model['bone_count'] = read_uint8(f)
        f.seek(current_pos)  # Reset to position after magic number

        model['bone_exist'] = read_uint32(f)
        model['mesh'] = []

        if model['bone_exist']:
            if model['bone_exist'] > 1:
                count = read_uint8(f)
                f.read(2)
                f.read(count * 4)
            bone_count = read_uint16(f)
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
                bone_name = bone_name.decode().replace('\0', '').replace(' ', '_')
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
        while True:
            flag = read_uint16(f)
            if flag == 1:
                break
            f.seek(-2, 1)
            mesh_vertex_count = read_uint32(f)
            mesh_face_count = read_uint32(f)
            uv_layers = read_uint8(f)
            color_len = read_uint8(f)

            model['mesh'].append((mesh_vertex_count, mesh_face_count, uv_layers, color_len))

        vertex_count = read_uint32(f)
        face_count = read_uint32(f)

        model['position'] = []
        # vertex position
        for _ in range(vertex_count):
            x = read_float(f)
            y = read_float(f)
            z = read_float(f)
            model['position'].append((x, y, z))

        model['normal'] = []
        # vertex normal
        for _ in range(vertex_count):
            x = read_float(f)
            y = read_float(f)
            z = read_float(f)
            model['normal'].append((x, y, z))

        _flag = read_uint16(f)
        if _flag:
            f.seek(vertex_count * 12, 1)

        model['face'] = []
        # face index table
        for _ in range(face_count):
            v1 = read_uint16(f)
            v2 = read_uint16(f)
            v3 = read_uint16(f)
            model['face'].append((v1, v2, v3))

        model['uv'] = []
        # vertex uv
        for mesh_vertex_count, _, uv_layers, _ in model['mesh']:
            if uv_layers > 0:
                for _ in range(mesh_vertex_count):
                    u = read_float(f)
                    v = read_float(f)
                    model['uv'].append((u, v))
                f.read(mesh_vertex_count * 8 * (uv_layers - 1))
            else:
                for _ in range(mesh_vertex_count):
                    u = 0.0
                    v = 0.0
                    model['uv'].append((u, v))

        # vertex color
        for mesh_vertex_count, _, _, color_len in model['mesh']:
            f.read(mesh_vertex_count * 4 * color_len)

        if model['bone_exist']:
            model['vertex_bone'] = []
            for _ in range(vertex_count):
                vertex_bones = [read_uint8(f) for _ in range(4)]
                model['vertex_bone'].append(vertex_bones)

            model['vertex_weight'] = []
            for _ in range(vertex_count):
                vertex_weights = [read_float(f) for _ in range(4)]
                model['vertex_weight'].append(vertex_weights)

        return model


class AdaptiveMeshParser(BaseMeshParser):
    """Adaptive mesh parser that dynamically finds valid mesh offsets for corrupted or variable format files."""
    
    def parse(self, data: bytes, file_obj: Optional[BinaryIO] = None) -> MeshData:
        """Parse mesh using the adaptive parsing method."""
        model = {}
        
        if file_obj is None:
            file_obj = io.BytesIO(data)
            
        raw_model = self._parse_mesh_dynamic(model, file_obj)
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
                if 10 < vertex_count < 1000000 and 10 < face_count < 1000000:
                    return offset
            except struct.error:
                continue
        return None  # No valid offset found
    
    def _parse_mesh_dynamic(self, model: Dict[str, Any], f: BinaryIO) -> Dict[str, Any]:
        """Parses a .mesh file, dynamically finding the correct mesh offset."""
        _magic_number = f.read(8)

        # Read mesh version
        current_pos = f.tell()
        f.seek(4)
        model['mesh_version'] = read_uint8(f)

        f.seek(12)
        model['bone_count'] = read_uint8(f)
        f.seek(current_pos)  # Reset to position after magic number

        model['bone_exist'] = read_uint32(f)
        model['mesh'] = []

        if model['bone_exist']:
            if model['bone_exist'] > 1:
                count = read_uint8(f)
                f.read(2)
                f.read(count * 4)
            bone_count = read_uint16(f)
            model['bone_parent'] = [read_uint16(f) for _ in range(bone_count)]
            model['bone_name'] = [f.read(32).decode(errors="ignore").strip("\0").replace(" ", "_") for _ in range(bone_count)]
            bone_extra_info = read_uint8(f)
            if bone_extra_info:
                for _ in range(bone_count):
                    f.read(28)
            model['bone_matrix'] = [np.array([read_float(f) for _ in range(16)]).reshape(4, 4) for _ in range(bone_count)]

        # Find correct mesh offset
        mesh_offset = self._find_valid_mesh_offset(f)
        if mesh_offset is None:
            raise MeshParsingError("Could not find valid mesh offset")
        f.seek(mesh_offset)

        vertex_count = read_uint32(f)
        face_count = read_uint32(f)

        model['position'] = [(read_float(f), read_float(f), read_float(f)) for _ in range(vertex_count)]
        model['normal'] = [(read_float(f), read_float(f), read_float(f)) for _ in range(vertex_count)]

        _flag = read_uint16(f)
        if _flag:
            f.seek(vertex_count * 12, 1)

        model['face'] = [(read_uint16(f), read_uint16(f), read_uint16(f)) for _ in range(face_count)]

        model['uv'] = []
        for mesh_vertex_count, _, uv_layers, _ in model['mesh']:
            if uv_layers > 0:
                for _ in range(mesh_vertex_count):
                    u = read_float(f)
                    v = read_float(f)
                    model['uv'].append((u, v))
                f.read(mesh_vertex_count * 8 * (uv_layers - 1))
            else:
                for _ in range(mesh_vertex_count):
                    model['uv'].append((0.0, 0.0))

        for mesh_vertex_count, _, _, color_len in model['mesh']:
            f.read(mesh_vertex_count * 4 * color_len)

        if model['bone_exist']:
            model['vertex_bone'] = [[read_uint8(f) for _ in range(4)] for _ in range(vertex_count)]
            model['vertex_weight'] = [[read_float(f) for _ in range(4)] for _ in range(vertex_count)]
        
        return model
