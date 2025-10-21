"""Provides decompression functions."""

from typing import cast
import zlib
import lz4.block
import zstandard
import struct

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa

from core.npk.enums import CompressionType
from core.npk.class_types import NPKEntry
from core.rotor import Rotor

def init_rotor():
    """Initializes the rotor instance."""
    asdf_dn = 'j2h56ogodh3se'
    asdf_dt = '=dziaq.'
    asdf_df = '|os=5v7!"-234'
    asdf_tm = asdf_dn * 4 + (asdf_dt + asdf_dn + asdf_df) * 5 + '!' + '#' + asdf_dt * 7 + asdf_df * 2 + '*' + '&' + "'"
    rot = Rotor(asdf_tm)
    return rot

def _reverse_string(s):
    l = list(s)
    l = list(map(lambda x: x ^ 154, l[0:128])) + l[128:]
    l.reverse()
    return bytes(l)

def decompress_entry(entry: NPKEntry):
    """
    This function determines the compression type specified in the `zip_flag` attribute
    of the provided `entry` and applies the corresponding decompression algorithm.
    The decompressed data is returned as the output.

    Returns:
        bytes: The decompressed data.

        The decompressed data is returned as a new object and does not modify the original
        `data` attribute of the `entry` object.
    """

    if entry.zip_flag == CompressionType.ZLIB:
        return zlib.decompress(entry.data, bufsize=entry.file_original_length)

    if entry.zip_flag == CompressionType.LZ4:
        return lz4.block.decompress(entry.data,
                                          uncompressed_size=entry.file_original_length)

    if entry.zip_flag == CompressionType.ZSTANDARD:
        return zstandard.ZstdDecompressor().decompress(entry.data)

    # No matched compression.
    return entry.data

def check_nxs3(entry: NPKEntry) -> bool:
    """Check if the data is wrapped in NXS3 format."""
    return entry.data[:8] == b"NXS3\x03\x00\x00\x01"

def check_rotor(entry: NPKEntry) -> bool:
    """Check if the data is ROTOR encrypted."""
    return (entry.data[:2] == bytes([0x1D, 0x04]) or entry.data[:2] == bytes([0x15, 0x23]))

def check_stzb(entry: NPKEntry) -> bool:
    return entry.data[:4] == b'STZB'

def unpack_rotor(data):
    """Unpacks the ROTOR decryption with the RSA public key and zlib decompression"""
    return _reverse_string(zlib.decompress(init_rotor().decrypt(data)))

def unpack_stzb(data):
    """Unpacks STZB encrypted data - completely aligned with the second script"""
    if data[:4] != b'STZB':
        return data
    
    magic = data[0:4]
    unknown = data[4:8]
    compressed_len = struct.unpack('<I', data[8:12])[0]
    encrypted_len = struct.unpack('<I', data[12:16])[0]
    
    xor_key = b'\x8E\x50\x9F\xE8\x59\x67\x91\xFB'
    decrypted_data = bytearray()
    
    for i, byte in enumerate(encrypted_data):
        key_byte = xor_key[i % len(xor_key)]
        decrypted_data.append(byte ^ key_byte)
    
    return bytes(decrypted_data)

def rsa_public_decrypt(signature: bytes, key: rsa.RSAPublicKey) -> bytes:
    """Converts a signature to an integer and decrypts it using the RSA public key."""
    public_numbers = key.public_numbers()
    e = public_numbers.e
    n = public_numbers.n

    k = (n.bit_length() + 7) // 8  # key length in bytes
    if len(signature) != k:
        raise ValueError("Signature length does not match key size")

    # Convert signature to integer
    sig_int = int.from_bytes(signature, byteorder='big')

    # RSA public operation: m = sig^e mod n
    m_int = pow(sig_int, e, n)

    # Convert back to bytes
    decrypted = m_int.to_bytes(k, byteorder='big')

    # Remove PKCS#1 v1.5 padding
    if decrypted[0] != 0x00 or decrypted[1] != 0x01:
        raise ValueError("Incorrect padding")

    # Padding is 0xFF ... 0x00, then the message
    try:
        padding_end = decrypted.index(0x00, 2)
    except ValueError as e:
        raise ValueError("Padding end not found") from e

    return decrypted[padding_end + 1:]

def unpack_nxs3(data):
    """
    Decrypts and unpacks data encrypted with a custom algorithm using an RSA public key.
    This function extracts an encrypted key from the input data, decrypts it using
    an RSA public key, and uses the resulting ephemeral key to decrypt the remaining
    data. The decryption process involves XOR operations and bitwise manipulations.
    Args:
        data (bytes): The input data to be decrypted. The data must contain an
                      encrypted key starting at offset 20, followed by the encrypted payload.
    Returns:
        bytes: The decrypted data.
    Raises:
        ValueError: If the decryption of the encrypted key fails.
    """

    # Parse the RSA public key
    pem_key = b"""-----BEGIN RSA PUBLIC KEY-----
MIGJAoGBAOZAaZe2qB7dpT9Y8WfZIdDv+ooS1HsFEDW2hFnnvcuFJ4vIuPgKhISm
pY4/jT3aipwPNVTjM6yHbzOLhrnGJh7Ec3CQG/FZu6VKoCqVEtCeh15hjcu6QYtn
YWIEf8qgkylqsOQ3IIn76udV6m0AWC2jDlmLeRcR04w9NNw7+9t9AgMBAAE=
-----END RSA PUBLIC KEY-----"""

    rsa_key = cast(rsa.RSAPublicKey, serialization.load_pem_public_key(pem_key, backend=default_backend()))

    wrapped_key = rsa_public_decrypt(data[20:20+128], rsa_key)[:4]

    if wrapped_key is None:
        raise ValueError("Decryption of the encrypted key failed.")

    # Convert to int
    ephemeral_key = int.from_bytes(wrapped_key, "little")

    # Continue with the existing decryption logic
    decrypted = []

    for i, x in enumerate(data[20 + 128:]):
        val = x ^ ((ephemeral_key >> (i % 4 * 8)) & 0xff)
        if i % 4 == 3:
            ror = (ephemeral_key >> 19) | ((ephemeral_key << (32 - 19)) & 0xFFFFFFFF)
            ephemeral_key = (ror + ((ror << 2) & 0xFFFFFFFF) + 0xE6546B64) & 0xFFFFFFFF
        decrypted.append(val)

    decrypted = bytes(decrypted)
    return decrypted
    