"""
Mesh Loader Module

A modular mesh loading system for parsing .mesh files using multiple parsing strategies.
Supports adaptive parsing with fallback mechanisms for robust file handling.
"""

from .parsers import (
    MeshData,
    StandardMeshParser,
    SimplifiedMeshParser,
    RobustMeshParser,
    AdaptiveMeshParser
)
from .exceptions import MeshParsingError

# Import the loader components after defining parsers
from .loader import MeshLoader

__all__ = [
    'MeshLoader',
    'MeshData',
    'StandardMeshParser',
    'SimplifiedMeshParser', 
    'RobustMeshParser',
    'AdaptiveMeshParser',
    'MeshParsingError'
]

__version__ = '1.0.0'
