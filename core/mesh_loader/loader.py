"""
Main mesh loader class that provides adaptive parsing functionality.
"""

import io
from typing import Union, Optional, List
from pathlib import Path

from core.logger import get_logger

from .parsers import (
    MeshData,
    BaseMeshParser,
    StandardMeshParser,
    SimplifiedMeshParser,
    RobustMeshParser,
    AdaptiveMeshParser
)

class MeshLoader:
    """
    Main mesh loader class that provides adaptive parsing with fallback mechanisms.
    
    This class attempts to parse mesh files using multiple parsing strategies,
    falling back to alternative methods if the primary method fails.
    """

    def __init__(self):
        """
        Initialize the mesh loader.
        
        Args:
            logger: Optional logger instance for debugging and error reporting
        """
        self._parsers = self._initialize_parsers()

    def _initialize_parsers(self) -> List[BaseMeshParser]:
        """Initialize the list of available parsers in order of preference."""
        return [
            StandardMeshParser(),
            SimplifiedMeshParser(),
            RobustMeshParser(),
            AdaptiveMeshParser()
        ]

    def load_from_bytes(self, data: bytes) -> Optional[MeshData]:
        """
        Load mesh data from raw bytes using adaptive parsing.
        
        Args:
            data: Raw mesh data as bytes
            
        Returns:
            MeshData object containing parsed mesh data, or None if all parsers fail
        """
        get_logger().debug("Parsing mesh data from bytes")

        # Try parsing with bytes data
        for _i, parser in enumerate(self._parsers):
            parser_name = parser.__class__.__name__
            try:
                get_logger().debug("Attempting %s (bytes)", parser_name)

                with io.BytesIO(data) as f:
                    model = parser.parse(data, f)

                get_logger().info("Successfully parsed using %s (bytes)", parser_name)
                return model

            except Exception as e:
                get_logger().warning("%s (bytes) failed: %s", parser_name, e)

        get_logger().error("All byte-based parsing methods failed")
        return None

    def load_from_file(self, file_path: Union[str, Path]) -> Optional[MeshData]:
        """
        Load mesh data from a file using adaptive parsing.
        
        Args:
            file_path: Path to the mesh file
            
        Returns:
            MeshData object containing parsed mesh data, or None if all parsers fail
        """
        file_path = Path(file_path)

        if not file_path.exists():
            get_logger().error("File not found: %s", file_path)
            return None

        get_logger().debug("Starting adaptive parsing from file: %s", file_path)

        try:
            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # First try parsing as bytes
            result = self.load_from_bytes(file_content)
            if result is not None:
                return result

            # Try parsing with file path (for parsers that need file access)
            for parser in self._parsers:
                parser_name = parser.__class__.__name__
                try:
                    get_logger().debug("Attempting %s (file path)", parser_name)

                    with open(file_path, 'rb') as f:
                        model = parser.parse(file_content, f)

                    get_logger().info("Successfully parsed using %s (file path)", parser_name)
                    return model

                except Exception as e:
                    get_logger().warning("%s (file path) failed: %s", parser_name, e)

        except Exception as e:
            get_logger().error("Error reading file %s: %s", file_path, e)

        get_logger().error("All parsing methods failed")
        return None

    def get_parser_info(self) -> List[str]:
        """
        Get information about available parsers.
        
        Returns:
            List of parser class names
        """
        return [parser.__class__.__name__ for parser in self._parsers]

    def add_parser(self, parser: BaseMeshParser, position: Optional[int] = None):
        """
        Add a custom parser to the loader.
        
        Args:
            parser: Parser instance to add
            position: Optional position to insert the parser (default: append)
        """
        if not isinstance(parser, BaseMeshParser):
            raise ValueError("Parser must inherit from BaseMeshParser")

        if position is None:
            self._parsers.append(parser)
        else:
            self._parsers.insert(position, parser)

    def remove_parser(self, parser_class: type):
        """
        Remove a parser by class type.
        
        Args:
            parser_class: Class type of the parser to remove
        """
        self._parsers = [p for p in self._parsers if not isinstance(p, parser_class)]
