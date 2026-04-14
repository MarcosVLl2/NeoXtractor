"""NPK File Reader"""

import io
import os
import struct

from typing import List, Dict

from arc4 import ARC4

from core.binary_readers import read_uint32, read_uint16, read_uint64
from core.npk.decompression import (
    check_lz4_like,
    check_nxs3,
    decompress_entry,
    unpack_lz4_like,
    unpack_nxs3,
    check_rotor,
    unpack_rotor,
    strip_none_wrapper,
)
from core.npk.decryption import decrypt_entry
from core.npk.enums import NPKFileType
from core.logger import get_logger
from core.formats import process_entry_with_processors

from .detection import get_ext, get_file_category, is_binary
from .keys import KeyGenerator
from .class_types import NPKEntryDataFlags, NPKIndex, NPKEntry, CompressionType, DecryptionType, NPKReadOptions
from .eggparty_mode3 import decrypt_eggparty_index, EGGPARTY_MODE3_INDEX_KEY

EGGPARTY_MAGIC = 0x4B50584E
EGGPARTY_HEADER_FMT = "<IiiBBHiI"
EGGPARTY_ENTRY_FMT = "<IIIIIIHBB"
EGGPARTY_HEADER_SIZE = struct.calcsize(EGGPARTY_HEADER_FMT)
EGGPARTY_ENTRY_SIZE = struct.calcsize(EGGPARTY_ENTRY_FMT)


class NPKFile:
    """Main class for handling NPK files."""

    def __init__(self, file_path: str, options: NPKReadOptions | None = None):
        """Initialize the NPK file handler.

        Args:
            file_path: Optional path to an NPK file to open
        """
        self.file_path = file_path
        self.entries: Dict[int, NPKEntry] = {}
        self.indices: List[NPKIndex] = []

        # NPK header information
        self.file_count: int = 0
        self.index_offset: int = 0
        self.hash_mode: int = 0
        self.encrypt_mode: int = 0
        self.info_size: int = 0

        # EggParty-specific header information
        self.archive_variant: str = "standard"
        self.header_encrypt_flag: int = 0
        self.format_flag: int = 0
        self.version: int = 0

        # Options when reading the NPK file
        self.options = options if options is not None else NPKReadOptions()

        # NXFN file information
        self.nxfn_files = None

        # Key generator for advanced decryption
        self.key_generator = KeyGenerator()

        get_logger().info("Opening NPK file: %s", self.file_path)

        with open(self.file_path, 'rb') as file:
            # Read NPK header.
            self._read_header(file)

            # Read the indices but don't load data yet
            self._read_indices(file)

    def _looks_like_valid_eggparty_indices(
        self,
        raw_index: bytes,
        file_size: int,
        index_offset: int,
    ) -> bool:
        """Best-effort structural validation for EggParty index rows."""
        entry_count = len(raw_index) // EGGPARTY_ENTRY_SIZE
        if entry_count <= 0:
            return False

        good = 0
        for i in range(entry_count):
            off = i * EGGPARTY_ENTRY_SIZE
            row = raw_index[off:off + EGGPARTY_ENTRY_SIZE]
            if len(row) != EGGPARTY_ENTRY_SIZE:
                break

            (
                _file_signature,
                offset_lo,
                compressed_size,
                uncompressed_size,
                _compressed_hash,
                _uncompressed_hash,
                decompress_type,
                encrypt_type,
                offset_hi,
            ) = struct.unpack(EGGPARTY_ENTRY_FMT, row)

            file_offset = ((offset_hi & 0xFF) << 32) | (offset_lo & 0xFFFFFFFF)

            if not (EGGPARTY_HEADER_SIZE <= file_offset < index_offset):
                continue
            if not (0 < compressed_size <= index_offset):
                continue
            if not (0 < uncompressed_size <= 1024 * 1024 * 1024):
                continue
            if decompress_type not in (0, 1, 2, 3, 4, 5, 6, 7):
                continue
            if encrypt_type not in (0, 1, 2, 3):
                continue
            if file_offset + compressed_size > index_offset:
                continue
            if file_offset + compressed_size > file_size:
                continue

            good += 1

        need = max(3, entry_count // 2)
        return good >= need

    def _try_read_eggparty_header(self, file: io.BufferedReader) -> bool:
        """Try to interpret the archive as the EggParty NPK variant."""
        file.seek(0)
        raw = file.read(EGGPARTY_HEADER_SIZE)
        if len(raw) != EGGPARTY_HEADER_SIZE:
            return False

        (
            signature,
            count,
            highword,
            indice_encrypt,
            flags,
            _reserved,
            version,
            offset_lo,
        ) = struct.unpack(EGGPARTY_HEADER_FMT, raw)

        if signature != EGGPARTY_MAGIC:
            return False
        if count <= 0:
            return False
        if indice_encrypt not in (0, 3):
            return False

        index_offset = ((highword & 0xFFFFFFFF) << 32) | (offset_lo & 0xFFFFFFFF)
        file_size = os.fstat(file.fileno()).st_size
        if not (EGGPARTY_HEADER_SIZE <= index_offset <= file_size):
            return False

        probe_entry_count = min(count, 16)
        if indice_encrypt == 3 and probe_entry_count >= 4:
            probe_entry_count -= probe_entry_count % 4
            if probe_entry_count == 0:
                probe_entry_count = 4

        probe_size = probe_entry_count * EGGPARTY_ENTRY_SIZE
        file.seek(index_offset)
        encrypted_probe = file.read(probe_size)
        if len(encrypted_probe) != probe_size:
            return False

        probe = encrypted_probe
        if indice_encrypt == 3:
            try:
                probe = decrypt_eggparty_index(encrypted_probe, EGGPARTY_MODE3_INDEX_KEY)
            except Exception:
                return False

        if not self._looks_like_valid_eggparty_indices(probe, file_size, index_offset):
            return False

        self.archive_variant = "eggparty"
        self.file_type = NPKFileType.NXPK
        self.file_count = count
        self.index_offset = index_offset
        self.header_encrypt_flag = indice_encrypt
        self.format_flag = flags
        self.version = version

        # Keep the rest of the reader on the standard happy path.
        self.hash_mode = 0
        self.encrypt_mode = 0
        self.info_size = EGGPARTY_ENTRY_SIZE
        self.nxfn_files = None

        return True

    def _read_header(self, file: io.BufferedReader) -> bool:
        """Open an NPK file and read its header information."""
        get_logger().debug("Reading NPK header from %s", self.file_path)

        magic = file.read(4)
        file.seek(0)

        if magic == b'NXPK':
            self.file_type = NPKFileType.NXPK
            if self._try_read_eggparty_header(file):
                get_logger().info("Detected EggParty NPK variant")
                get_logger().info("NPK entry count: %d", self.file_count)
                get_logger().info("EggParty indice_encrypt: %d", self.header_encrypt_flag)
                get_logger().info("EggParty flags: %d", self.format_flag)
                get_logger().info("EggParty version: %d", self.version)
                get_logger().info("EggParty index offset: 0x%X", self.index_offset)
                return True
        elif magic == b'EXPK':
            self.file_type = NPKFileType.EXPK
        else:
            file.close()
            raise ValueError(f"Not a valid NPK file: {self.file_path}")

        get_logger().debug("NPK type: %s", self.file_type)

        # Read basic header info
        file.seek(4)
        self.file_count = read_uint32(file)
        var1 = read_uint32(file)  # Unknown variable
        self.encrypt_mode = read_uint32(file)
        self.hash_mode = read_uint32(file)
        self.index_offset = read_uint32(file)

        get_logger().info("NPK entry count: %d", self.file_count)
        get_logger().info("NPK unknown var: %d", var1)
        get_logger().info("NPK encryption mode: %s", self.encrypt_mode)
        get_logger().info("NPK hash mode: %s", self.hash_mode)
        get_logger().info("NPK index offset: 0x%X", self.index_offset)

        # Determine index entry size
        self.info_size = self._determine_info_size(file) if self.options.info_size is None else self.options.info_size

        get_logger().debug("NPK index entry size: %d", self.info_size)

        if self.hash_mode == 2:
            file.seek(self.index_offset + (self.file_count * self.info_size))
            self.nxfn_files = [x for x in (file.read()).split(b'\x00') if x != b'']
        elif self.hash_mode == 3:
            self.arc_key = ARC4(b'61ea476e-8201-11e5-864b-fcaa147137b7')
        elif self.encrypt_mode == 256:
            file.seek(self.index_offset + (self.file_count * self.info_size) + 16)
            self.nxfn_files = [x for x in (file.read()).split(b'\x00') if x != b'']

        return True

    def __enter__(self):
        return self

    def _determine_info_size(self, file: io.BufferedReader) -> int:
        """Determine the size of each index entry."""
        if self.encrypt_mode == 256 or self.hash_mode == 2:
            return 0x1C  # 28 bytes

        current_pos = file.tell()
        file.seek(self.index_offset)
        buf = file.read()
        file.seek(current_pos)

        # The total size of the index divided by number of files gives us the entry size
        return len(buf) // self.file_count

    def _read_indices_eggparty(self, file: io.BufferedReader) -> None:
        """Read EggParty index rows."""
        self.indices = []

        file.seek(self.index_offset)
        index_size = self.file_count * EGGPARTY_ENTRY_SIZE
        index_data = file.read(index_size)
        if len(index_data) != index_size:
            raise ValueError(
                f"Failed to read EggParty index table: expected {index_size} bytes, got {len(index_data)}"
            )

        if self.header_encrypt_flag == 3:
            index_data = decrypt_eggparty_index(index_data, EGGPARTY_MODE3_INDEX_KEY)
        elif self.header_encrypt_flag != 0:
            raise NotImplementedError(
                f"Unsupported EggParty indice_encrypt={self.header_encrypt_flag}"
            )

        with io.BytesIO(index_data) as buf:
            for i in range(self.file_count):
                index = NPKIndex()

                (
                    index.file_signature,
                    offset_lo,
                    index.file_length,
                    index.file_original_length,
                    index.zcrc,
                    index.crc,
                    zip_flag,
                    encrypt_flag,
                    offset_hi,
                ) = struct.unpack(EGGPARTY_ENTRY_FMT, buf.read(EGGPARTY_ENTRY_SIZE))

                index.file_offset = ((offset_hi & 0xFF) << 32) | (offset_lo & 0xFFFFFFFF)
                index.zip_flag = CompressionType(zip_flag)
                index.encrypt_flag = DecryptionType(encrypt_flag)
                index.file_structure = None
                index.filename = hex(index.file_signature)

                get_logger().debug("EggParty index %d: %s", i, index)

                self.indices.append(index)

    def _read_indices(self, file: io.BufferedReader) -> None:
        """Read all the index entries from the NPK file."""
        if self.archive_variant == "eggparty":
            self._read_indices_eggparty(file)
            return

        self.indices = []

        file.seek(self.index_offset)
        index_data = file.read(self.file_count * self.info_size)

        if self.file_type == NPKFileType.EXPK:
            index_data = self.key_generator.decrypt(index_data)
        if self.hash_mode == 3:
            index_data = self.arc_key.decrypt(index_data)

        with io.BytesIO(index_data) as buf:
            for i in range(self.file_count):
                index = NPKIndex()

                # Read the file signature
                if self.info_size == 28:
                    # 32-bit file signature
                    index.file_signature = read_uint32(buf)
                elif self.info_size == 32:
                    # 64-bit file signature (NeoX 2.0)
                    index.file_signature = read_uint64(buf)

                # Read the rest of the index entry
                index.file_offset = read_uint32(buf)
                index.file_length = read_uint32(buf)
                index.file_original_length = read_uint32(buf)
                index.zcrc = read_uint32(buf)
                index.crc = read_uint32(buf)

                zip_flag = read_uint16(buf)
                if zip_flag == 5:
                    # Still LZ4
                    zip_flag = 2
                index.zip_flag = CompressionType(zip_flag)

                encrypt_flag = read_uint16(buf)
                if encrypt_flag == 3:
                    # Still Advanced XOR
                    encrypt_flag = 2

                index.encrypt_flag = DecryptionType(encrypt_flag)

                # Store file structure name if available
                if self.nxfn_files and i < len(self.nxfn_files):
                    index.file_structure = self.nxfn_files[i]
                else:
                    index.file_structure = None

                get_logger().debug("Index %d: %s", i, index)

                # Generate a filename
                if index.file_structure:
                    try:
                        index.filename = index.file_structure.decode("utf-8")
                    except UnicodeDecodeError:
                        index.filename = hex(index.file_signature)
                else:
                    index.filename = hex(index.file_signature)

                self.indices.append(index)

    def is_entry_loaded(self, index: int) -> bool:
        """Check if an entry is already loaded."""
        return index in self.entries

    def read_entry(self, index: int) -> NPKEntry:
        """Get an entry by its index.

        If the entry has been loaded before, returns the cached entry.
        Otherwise, loads the entry from the NPK file.
        """
        if index in self.entries:
            return self.entries[index]

        # Create a new entry based on the index
        entry = NPKEntry()

        # Check if the index is valid
        if not 0 <= index < len(self.indices):
            get_logger().critical("Entry index out of range: %d", index)
            entry.data_flags |= NPKEntryDataFlags.ERROR
            return entry

        idx = self.indices[index]

        # Copy index attributes to entry
        for attr in vars(idx):
            setattr(entry, attr, getattr(idx, attr))

        with open(self.file_path, 'rb') as file:
            # Load the actual data
            self._load_entry_data(entry, file)

        # Update filename with extension.
        # For NXFN-backed names, keep an existing extension, otherwise append the detected one.
        _base_name, existing_ext = os.path.splitext(entry.filename)
        if not existing_ext and entry.extension:
            entry.filename = f"{entry.filename}.{entry.extension}"

        # Store in the cache
        self.entries[index] = entry
        return entry

    def _load_entry_data(self, entry: NPKEntry, file: io.BufferedReader):
        """Load the data for an entry from the NPK file."""
        # Position file pointer to the file data
        file.seek(entry.file_offset)

        # Read the file data
        entry.data = file.read(entry.file_length)

        # Decrypt EXPK data if needed
        if self.file_type == NPKFileType.EXPK:
            entry.data = self.key_generator.decrypt(entry.data)

        # EggParty entry-level encryption is not implemented yet.
        # Keep the raw payload instead of trying legacy XOR handlers.
        if self.archive_variant == "eggparty" and entry.encrypt_flag != DecryptionType.NONE:
            entry.data_flags |= NPKEntryDataFlags.ENCRYPTED
            entry.extension = f"enc{int(entry.encrypt_flag)}.bin"
            entry.category = get_file_category(entry.extension)
            get_logger().debug("Entry %s left encrypted (EggParty etype=%s)", entry.filename, entry.encrypt_flag)
            return

        # Decrypt if needed
        if entry.encrypt_flag != DecryptionType.NONE:
            entry.data = decrypt_entry(entry, self.options.decryption_key)

        # Decompress if needed
        if entry.zip_flag != CompressionType.NONE:
            try:
                entry.data = decompress_entry(entry)
            except Exception:
                if entry.encrypt_flag == DecryptionType.BASIC_XOR:
                    get_logger().error("Error decompressing the file, did you choose the correct key for this NPK?")
                    entry.data_flags |= NPKEntryDataFlags.ENCRYPTED
                else:
                    get_logger().critical(
                        "Error decompressing the file using %s compression, open a GitHub issue",
                        entry.zip_flag.get_name(entry.zip_flag)
                    )
                    entry.data_flags |= NPKEntryDataFlags.ERROR
                return

        # Continuously strip simple wrappers and unpack nested payloads.
        entry.unwrap_layers = []
        seen_signatures: set[tuple[int, bytes]] = set()
        max_layers = 32
        for _ in range(max_layers):
            signature = (len(entry.data), entry.data[:16])
            if signature in seen_signatures:
                break
            seen_signatures.add(signature)

            stripped = strip_none_wrapper(entry.data)
            if stripped != entry.data:
                entry.data = stripped
                entry.unwrap_layers.append("NONE")
                continue

            if check_lz4_like(entry.data):
                try:
                    unpacked = unpack_lz4_like(entry.data)
                except Exception:
                    break
                if unpacked and unpacked != entry.data:
                    entry.data = unpacked
                    entry.unwrap_layers.append("LZ4_LIKE")
                    continue

            if check_rotor(entry):
                entry.data_flags |= NPKEntryDataFlags.ROTOR_PACKED
                entry.data = unpack_rotor(entry.data)
                entry.unwrap_layers.append("ROTOR")
                continue

            if check_nxs3(entry):
                entry.data_flags |= NPKEntryDataFlags.NXS3_PACKED
                entry.data = unpack_nxs3(entry.data)
                entry.unwrap_layers.append("NXS3")
                continue

            break

        binary = is_binary(entry.data)
        # Mark the data as text data
        if not binary:
            entry.data_flags |= NPKEntryDataFlags.TEXT

        # Detect the extension before any optional post-processing so raw exports can preserve it.
        entry.source_extension = get_ext(entry.data, entry.data_flags)

        processed = process_entry_with_processors(entry)
        if processed and not is_binary(entry.data):
            entry.data_flags |= NPKEntryDataFlags.TEXT

        entry.extension = entry.extension or get_ext(entry.data, entry.data_flags)
        entry.category = get_file_category(entry.extension)

        get_logger().debug("Entry %s: %s", entry.filename, entry.category)
