"""Mesh conversion utilities."""

from core.mesh_loader.parsers import MeshData

from .formats import (
    ascii as mesh_ascii,
    gltf,
    iqe,
    obj,
    pmx,
    smd
)

FORMATS = [mesh_ascii, gltf, iqe, obj, pmx, smd]

def convert_mesh(mesh: MeshData, target_format: type, **kwargs) -> bytes:
    """
    Convert mesh to the specified format.

    Parameters:
    - mesh: MeshData object containing bones, vertices, faces, etc.
    - target_format: The format class to convert the mesh to.
    - kwargs: Additional parameters for specific format conversions.

    Returns:
    - bytes: Converted mesh data in the specified format.
    """
    return target_format.convert(mesh, **kwargs)

__all__ = [
    'convert_mesh',
    'FORMATS',
    'mesh_ascii',
    'gltf',
    'iqe',
    'obj',
    'pmx',
    'smd'
]
