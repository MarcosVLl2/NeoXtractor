"""Types for Mesh Loader"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np

MAX_VERTEX_COUNT = 500000
MAX_FACE_COUNT = 250000
MAX_BONE_COUNT = 2000


@dataclass
class MeshData:
    """
    Standardized mesh data structure containing all parsed mesh information.

    This dataclass provides a consistent interface for mesh data across all parsers,
    ensuring type safety and clear documentation of the expected data structure.
    """

    # Metadata
    version: int

    # Core mesh geometry
    position: list[tuple[float, float, float]] = field(default_factory=list)
    normal: list[tuple[float, float, float]] = field(default_factory=list)
    face: list[tuple[int, int, int]] = field(default_factory=list)
    uv: list[tuple[float, float]] = field(default_factory=list)

    # Bone/skeleton data
    bone_exist: int = 0
    bone_parent: list[int] = field(default_factory=list)
    bone_name: list[str] = field(default_factory=list)
    bone_matrix: list[np.ndarray] = field(default_factory=list)
    bone_count: int = 0

    # Vertex bone assignments
    vertex_bone: list[list[int]] = field(default_factory=list)
    vertex_weight: list[list[float]] = field(default_factory=list)

    # Mesh metadata
    mesh: list[tuple[int, int, int, int]] = field(default_factory=list)
    mesh_version: int = 0

    # Additional optional data
    material_id: list[int] = field(default_factory=list)
    vertex_color: list[tuple[float, float, float, float]] = field(default_factory=list)

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
            if (
                len(self.vertex_bone) != vertex_count
                or len(self.vertex_weight) != vertex_count
            ):
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
    def parse(self, data: bytes) -> MeshData:
        """
        Parse mesh data.

        Args:
            data: Raw mesh data as bytes

        Returns:
            MeshData object containing parsed mesh data

        Raises:
            MeshParsingError: If parsing fails
        """
        raise NotImplementedError

    def _standardize_mesh_data(self, model: dict[str, Any]) -> MeshData:
        """
        Convert raw parsed data to standardized MeshData object.

        Args:
            model: Raw parsed mesh data dictionary

        Returns:
            Standardized MeshData object with unified field names and structure
        """
        # Create MeshData with unified field mapping
        mesh_data = MeshData(
            # Metadata
            version=model.get("mesh_version", 0),
            # Core mesh data
            position=model.get("position", []),
            normal=model.get("normal", []),
            face=model.get("face", []),
            uv=model.get("uv", []),
            # Bone data
            bone_exist=model.get("bone_exist", 0),
            bone_parent=model.get("bone_parent", []),
            bone_name=model.get("bone_name", []),
            bone_matrix=model.get("bone_original_matrix", model.get("bone_matrix", [])),
            bone_count=model.get("bone_count", 0),
            # Vertex bone assignments - unify different field names
            vertex_bone=model.get("vertex_joint", model.get("vertex_bone", [])),
            vertex_weight=model.get(
                "vertex_joint_weight", model.get("vertex_weight", [])
            ),
            # Mesh metadata
            mesh=model.get("mesh", []),
            mesh_version=model.get("mesh_version", 0),
            # Additional fields if present
            material_id=model.get("material_id", []),
            vertex_color=model.get("vertex_color", []),
        )

        # Ensure consistent bone naming
        if mesh_data.bone_name:
            mesh_data.bone_name = [
                name.replace("\0", "").replace(" ", "_").strip()
                for name in mesh_data.bone_name
            ]

        # Ensure consistent data types for vertex counts
        if mesh_data.position:
            vertex_count = len(mesh_data.position)

            # Pad missing normals with zero vectors
            if len(mesh_data.normal) < vertex_count:
                mesh_data.normal.extend(
                    [(0.0, 0.0, 0.0)] * (vertex_count - len(mesh_data.normal))
                )

            # Pad missing UV coordinates with zero vectors
            if len(mesh_data.uv) < vertex_count:
                mesh_data.uv.extend([(0.0, 0.0)] * (vertex_count - len(mesh_data.uv)))

            # Pad missing bone assignments
            if mesh_data.bone_exist and len(mesh_data.vertex_bone) < vertex_count:
                mesh_data.vertex_bone.extend(
                    [[0, 0, 0, 0]] * (vertex_count - len(mesh_data.vertex_bone))
                )

            # Pad missing bone weights
            if mesh_data.bone_exist and len(mesh_data.vertex_weight) < vertex_count:
                mesh_data.vertex_weight.extend(
                    [[1.0, 0.0, 0.0, 0.0]]
                    * (vertex_count - len(mesh_data.vertex_weight))
                )

        return mesh_data

    def _validate_vertex_count(self, vertex_count: int) -> None:
        """
        Validate vertex count against maximum limits.

        Args:
            vertex_count: Number of vertices in the mesh

        Raises:
            ValueError: If vertex count exceeds maximum limit
        """
        if vertex_count == 0:
            raise ValueError("Vertex count cannot be zero")
        if vertex_count > MAX_VERTEX_COUNT:
            raise ValueError(
                f"Vertex count {vertex_count} exceeds maximum limit of {MAX_VERTEX_COUNT}"
            )

    def _validate_face_count(self, face_count: int) -> None:
        """
        Validate face count against maximum limits.

        Args:
            face_count: Number of faces in the mesh

        Raises:
            ValueError: If face count exceeds maximum limit
        """
        if face_count == 0:
            raise ValueError("Face count cannot be zero")
        if face_count > MAX_FACE_COUNT:
            raise ValueError(
                f"Face count {face_count} exceeds maximum limit of {MAX_FACE_COUNT}"
            )

    def _validate_bone_count(self, bone_count: int) -> None:
        """
        Validate bone count against maximum limits.

        Args:
            bone_count: Number of bones in the mesh

        Raises:
            ValueError: If bone count exceeds maximum limit
        """
        if bone_count > MAX_BONE_COUNT:
            raise ValueError(
                f"Bone count {bone_count} exceeds maximum limit of {MAX_BONE_COUNT}"
            )
