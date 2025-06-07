import struct
from typing import BinaryIO

def read_uint64(f: BinaryIO):
    """Extract unsigned 64-bit integer from binary stream."""
    return struct.unpack('Q', f.read(8))[0]
def read_uint32(f: BinaryIO):
    """Extract unsigned 32-bit integer from binary stream."""
    return struct.unpack('I', f.read(4))[0]
def read_uint16(f: BinaryIO):
    """Extract unsigned 16-bit integer from binary stream."""
    return struct.unpack('H', f.read(2))[0]
def read_uint8(f: BinaryIO):
    """Extract unsigned 8-bit integer from binary stream."""
    return struct.unpack('B', f.read(1))[0]
def read_float(f: BinaryIO) -> float:
    """Extract float from binary stream."""
    return struct.unpack("<f", f.read(4))[0]
