"""
MIT License

Copyright (c) 2026 Tom Yang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import logging
import os
import struct
import mmap
import hashlib
import zlib
from typing import Dict, List, Optional, Any, Tuple, Sequence, Iterator

from .base import ELFParser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ISF file format constants
# Header: magic(4) + version(4) + header_size(4) + checksum(4) + file_size(8)
#        + meta_offset(8) + meta_size(8) + types_count(8) + symbols_count(8)
#        + typedefs_count(8) + types_table_offset(8) + symbols_table_offset(8)
#        + typedefs_table_offset(8) + types_data_offset(8) + symbols_data_offset(8)
#        + string_pool_offset(8) + string_pool_size(8)
# Total: 4+4+4+4+8 + 8*13 = 120 bytes, 17 fields
# ---------------------------------------------------------------------------
_ISF_HEADER_FORMAT = '<4sIIIQQQQQQQQQQQQQ'
_ISF_HEADER_SIZE = struct.calcsize(_ISF_HEADER_FORMAT)
_ISF_MAGIC = b'ISF\x00'
_ISF_VERSION = 1

# Meta format: arch(1) + bits(1) + endian(1) + padding(1)
#   arch: 'A'=ARM, '6'=ARM64
#   bits: 32 or 64
#   endian: 'L'=little, 'B'=big
_META_FORMAT = '<4s'
_META_SIZE = 4

# Type record field sizes (fixed format)
_TYPE_RECORD_HEADER_FMT = '<BIII'  # kind(1) + name_idx(4) + size(4) + members_count(4)
_TYPE_RECORD_HEADER_SIZE = struct.calcsize(_TYPE_RECORD_HEADER_FMT)
_TYPE_MEMBER_FMT = '<IHII'  # offset(4) + size(2) + name_idx(4) + type_idx(4)
_TYPE_MEMBER_SIZE = struct.calcsize(_TYPE_MEMBER_FMT)

# Symbol record format (fixed)
_SYMBOL_RECORD_FMT = '<IQII'  # name_idx(4) + address(8) + size(4) + type_idx(4)
_SYMBOL_RECORD_SIZE = struct.calcsize(_SYMBOL_RECORD_FMT)

# ---------------------------------------------------------------------------
# Safety bounds
# ---------------------------------------------------------------------------
_MAX_NAME_LEN = 4096
_MAX_TYPE_LEN = 4096
_MAX_MEMBERS_COUNT = 10000
_MAX_STRING_POOL_SIZE = 100 * 1024 * 1024  # 100MB
_MAX_TYPES_COUNT = 1000000
_MAX_SYMBOLS_COUNT = 5000000
_CRC_CHUNK_SIZE = 64 * 1024  # 64KB chunks for CRC32


class ISFCorruptedError(Exception):
    """Raised when an ISF cache file is corrupted or has an unrecognized format."""
    pass


# ---------------------------------------------------------------------------
# MembersView: lazy member parsing
# ---------------------------------------------------------------------------
class MembersView(Sequence):
    """A lightweight read-only view over a type's member list in mmap data.

    Members are NOT eagerly parsed into dicts. Each member is unpacked
    on-demand via struct.unpack_from when __getitem__ or __iter__ is called.
    This is the key to controlling memory peak.

    MembersView behaves like a tuple of dicts, supporting indexing and iteration.
    """

    __slots__ = ('_buffer', '_base_offset', '_count', '_string_pool')

    def __init__(self, buffer: mmap.mmap, base_offset: int, count: int,
                 string_pool: 'StringPool'):
        self._buffer = buffer
        self._base_offset = base_offset
        self._count = count
        self._string_pool = string_pool

    def __len__(self) -> int:
        return self._count

    def __getitem__(self, index: int) -> Dict[str, Any]:
        if isinstance(index, slice):
            raise TypeError("MembersView does not support slicing")
        if index < 0:
            index += self._count
        if index < 0 or index >= self._count:
            raise IndexError(f"Member index {index} out of range [0, {self._count})")

        member_offset = self._base_offset + index * _TYPE_MEMBER_SIZE
        m_offset, m_size, m_name_idx, m_type_idx = struct.unpack_from(
            _TYPE_MEMBER_FMT, self._buffer, member_offset)

        sp = self._string_pool
        cache = sp._cache

        m_name = cache[m_name_idx]
        if m_name is None:
            off = sp._data_offsets[m_name_idx]
            length = sp._lengths[m_name_idx]
            m_name = bytes(sp._pool_mv[off:off + length]).decode('utf-8')
            cache[m_name_idx] = m_name

        m_type = cache[m_type_idx]
        if m_type is None:
            off = sp._data_offsets[m_type_idx]
            length = sp._lengths[m_type_idx]
            m_type = bytes(sp._pool_mv[off:off + length]).decode('utf-8')
            cache[m_type_idx] = m_type

        return {
            'name': m_name,
            'offset': m_offset,
            'byte_size': m_size,
            'type_name': m_type,
        }

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        for i in range(self._count):
            yield self[i]

    def __repr__(self) -> str:
        return f"MembersView(count={self._count})"


# ---------------------------------------------------------------------------
# StringPool: zero-copy lazy string decoding
# ---------------------------------------------------------------------------
class StringPool:
    """Zero-copy string pool backed by mmap memoryview.

    Strings are NOT decoded during loading. The .decode('utf-8') is deferred
    until get() is called, and hot strings are cached via a simple array cache.
    All string references stay as memoryview slices into the mmap buffer.
    """

    __slots__ = ('_pool_mv', '_data_offsets', '_lengths', '_count', '_cache')

    def __init__(self, buffer: mmap.mmap, pool_offset: int, pool_size: int):
        self._pool_mv = memoryview(buffer)[pool_offset:pool_offset + pool_size]

        self._count = struct.unpack_from('<Q', self._pool_mv, 0)[0]
        if self._count > _MAX_TYPES_COUNT + _MAX_SYMBOLS_COUNT:
            raise ValueError(
                f"String pool count {self._count} exceeds safety limit")

        # Pre-compute data offsets and lengths to avoid null-terminator scan
        # on every decode call
        self._data_offsets = []
        self._lengths = []
        offsets_table_size = 8 + self._count * 8
        for i in range(self._count):
            off = struct.unpack_from('<Q', self._pool_mv, 8 + i * 8)[0]
            data_start = offsets_table_size + off
            # Find null terminator (one-time scan during init)
            end = data_start
            while end < len(self._pool_mv) and self._pool_mv[end] != 0:
                end += 1
            self._data_offsets.append(data_start)
            self._lengths.append(end - data_start)

        # Simple array cache (O(1) lookup, no lru_cache overhead)
        self._cache: List[Optional[str]] = [None] * self._count

    def get(self, index: int) -> str:
        """Get a string by index. Uses simple array cache for hot strings."""
        if index < 0 or index >= self._count:
            return f"<invalid_index:{index}>"
        result = self._cache[index]
        if result is None:
            off = self._data_offsets[index]
            length = self._lengths[index]
            result = str(self._pool_mv[off:off + length].tobytes(), 'utf-8')
            self._cache[index] = result
        return result


# ---------------------------------------------------------------------------
# CRC32 chunked verification
# ---------------------------------------------------------------------------
def _compute_crc32_chunked(buffer: mmap.mmap, start: int, size: int) -> int:
    """Compute CRC32 of a buffer region using 64KB chunks.

    Avoids loading the entire region at once, which would spike memory
    for large files.
    """
    crc = 0
    offset = start
    remaining = size
    while remaining > 0:
        chunk_size = min(_CRC_CHUNK_SIZE, remaining)
        crc = zlib.crc32(buffer[offset:offset + chunk_size], crc)
        offset += chunk_size
        remaining -= chunk_size
    return crc & 0xFFFFFFFF


# ---------------------------------------------------------------------------
# DwarffiParser
# ---------------------------------------------------------------------------
class DwarffiParser(ELFParser):
    """ELF parser using dwarffi for high-performance DWARF parsing.

    Uses ISF binary cache format for fast subsequent loads:
    - Fixed binary records with struct.unpack_from
    - String pool with zero-copy memoryview + lazy decode + array cache
    - MembersView for lazy member parsing
    - CRC32 chunked file integrity verification
    """

    def __init__(self, elf_path: str):
        super().__init__(elf_path)
        self._is_32bit = False
        self._address_size = 4
        self._elf_header_info: Dict[str, Any] = {}
        self._symbol_cache: Dict[str, Dict[str, Any]] = {}
        self._struct_type_cache: Dict[str, Any] = {}
        self._typedef_cache: Dict[str, str] = {}
        self._dffi = None
        self._mmap = None

        self._types_index: Dict[str, Tuple[int, int]] = {}
        self._symbols_index: Dict[str, Tuple[int, int]] = {}
        self._types_data_offset = 0
        self._symbols_data_offset = 0
        self._string_pool: Optional[StringPool] = None

        self._load_or_generate_isf()

    def __del__(self):
        if self._mmap is not None:
            try:
                self._string_pool = None
                self._mmap.close()
            except Exception:
                pass

    def _get_isf_path(self) -> str:
        with open(self.elf_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:16]
        cache_dir = os.path.join(os.path.dirname(self.elf_path), '.elf_cache')
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, f'{file_hash}.isf')

    # ------------------------------------------------------------------
    # ISF generation
    # ------------------------------------------------------------------

    def _generate_isf(self, isf_path: str) -> bool:
        """Generate ISF cache with fixed binary format and string pool."""
        try:
            from dwarffi import DFFI
            dffi = DFFI()
            dffi.load_elf(self.elf_path)
            self._dffi = dffi

            pointer_size = dffi.base_types.get('pointer', None)
            self._is_32bit = pointer_size is not None and pointer_size.size == 4
            self._address_size = pointer_size.size if pointer_size else 4

            arch_byte = ord('6') if not self._is_32bit else ord('A')
            bits_byte = 64 if not self._is_32bit else 32
            endian_byte = ord('L')
            meta_bytes = struct.pack(
                '<BBBx', arch_byte, bits_byte, endian_byte)

            # ---- Collect all type data ----
            types_data: Dict[str, Dict[str, Any]] = {}
            for type_name in dffi.types.keys():
                try:
                    dtype = dffi.get_type(type_name)
                    types_data[type_name] = self._dtype_to_isf(dtype)
                except Exception:
                    pass

            # ---- Collect typedefs ----
            typedefs_data: Dict[str, str] = {}
            try:
                for path in dffi._file_order:
                    vj = dffi.vtypejsons[path]
                    for td_name, td_info in vj._isf.typedefs.items():
                        target = td_info.get('name', td_name) if isinstance(td_info, dict) else str(td_info)
                        typedefs_data[td_name] = target
            except Exception:
                pass

            # ---- Collect symbols ----
            symbols_data: List[Dict[str, Any]] = []
            for sym_name in dffi.symbols:
                try:
                    sym = dffi.get_symbol(sym_name)
                    symbols_data.append({
                        'name': sym_name,
                        'address': sym.address,
                        'size': 0,
                        'type': str(sym.type_info.get('name')) if sym.type_info else None,
                    })
                except Exception:
                    pass

            # ---- Build string pool ----
            str_set: Dict[str, int] = {}
            str_list: List[str] = []

            def _intern(s: str) -> int:
                if s not in str_set:
                    str_set[s] = len(str_list)
                    str_list.append(s)
                return str_set[s]

            for name, info in types_data.items():
                _intern(name)
                _intern(info.get('kind', ''))
                for m in info.get('members', []):
                    _intern(m['name'])
                    _intern(m['type'])

            for sym in symbols_data:
                _intern(sym['name'])
                _intern(sym.get('type', ''))

            for td_name, td_target in typedefs_data.items():
                _intern(td_name)
                _intern(td_target)

            str_offsets: List[int] = []
            str_data = bytearray()
            for s in str_list:
                str_offsets.append(len(str_data))
                str_data.extend(s.encode('utf-8'))
                str_data.append(0)

            # ---- Build type records (fixed format) ----
            type_records: List[Tuple[str, bytes]] = []
            for name, info in types_data.items():
                name_idx = _intern(name)
                kind_str = info.get('kind', '')
                kind_byte = ord(kind_str[0]) if kind_str else 0
                size = info.get('size', 0)
                members = info.get('members', [])

                if len(members) > _MAX_MEMBERS_COUNT:
                    logger.warning(f"Type '{name}' has {len(members)} members, "
                                   f"capping at {_MAX_MEMBERS_COUNT}")
                    members = members[:_MAX_MEMBERS_COUNT]

                record = bytearray(_TYPE_RECORD_HEADER_SIZE + len(members) * _TYPE_MEMBER_SIZE)
                struct.pack_into(_TYPE_RECORD_HEADER_FMT, record, 0,
                                 kind_byte, name_idx, size, len(members))

                for i, m in enumerate(members):
                    m_name_idx = _intern(m['name'])
                    m_type_idx = _intern(m['type'])
                    struct.pack_into(_TYPE_MEMBER_FMT, record,
                                     _TYPE_RECORD_HEADER_SIZE + i * _TYPE_MEMBER_SIZE,
                                     m['offset'], m['size'], m_name_idx, m_type_idx)

                type_records.append((name, bytes(record)))

            # ---- Build symbol records (fixed format) ----
            symbol_records: List[Tuple[str, bytes]] = []
            for sym in symbols_data:
                name_idx = _intern(sym['name'])
                type_idx = _intern(sym.get('type', ''))
                record = struct.pack(_SYMBOL_RECORD_FMT,
                                     name_idx, sym['address'], sym['size'], type_idx)
                symbol_records.append((sym['name'], record))

            # ---- Calculate offsets ----
            types_table_size = sum(2 + len(name) + 12 for name, _ in type_records)
            symbols_table_size = sum(2 + len(name) + 12 for name, _ in symbol_records)

            typedef_entries = list(typedefs_data.items())
            typedefs_table_size = sum(2 + len(name) + 2 + len(target)
                                      for name, target in typedef_entries)

            types_data_size = sum(len(record) for _, record in type_records)
            symbols_data_size = sum(len(record) for _, record in symbol_records)
            string_pool_size = 8 + len(str_offsets) * 8 + len(str_data)

            current_offset = _ISF_HEADER_SIZE

            meta_offset = current_offset
            meta_size = len(meta_bytes)
            current_offset += meta_size

            types_table_offset = current_offset
            current_offset += types_table_size

            symbols_table_offset = current_offset
            current_offset += symbols_table_size

            typedefs_table_offset = current_offset
            current_offset += typedefs_table_size

            types_data_offset = current_offset
            types_data_positions = []
            for _, record in type_records:
                types_data_positions.append(current_offset)
                current_offset += len(record)

            symbols_data_offset = current_offset
            symbols_data_positions = []
            for _, record in symbol_records:
                symbols_data_positions.append(current_offset)
                current_offset += len(record)

            string_pool_offset = current_offset
            total_file_size = current_offset + string_pool_size

            # ---- Write header (checksum placeholder) ----
            header = bytearray(_ISF_HEADER_SIZE)
            struct.pack_into(_ISF_HEADER_FORMAT, header, 0,
                             _ISF_MAGIC,
                             _ISF_VERSION,
                             _ISF_HEADER_SIZE,
                             0,  # checksum placeholder
                             total_file_size,
                             meta_offset, meta_size,
                             len(type_records),
                             len(symbol_records),
                             len(typedef_entries),
                             types_table_offset,
                             symbols_table_offset,
                             typedefs_table_offset,
                             types_data_offset,
                             symbols_data_offset,
                             string_pool_offset,
                             string_pool_size)

            # ---- Write file ----
            with open(isf_path, 'wb') as f:
                f.write(header)
                f.write(meta_bytes)

                for i, (name, record) in enumerate(type_records):
                    name_bytes = name.encode('utf-8')
                    f.write(struct.pack('<H', len(name_bytes)))
                    f.write(name_bytes)
                    f.write(struct.pack('<Q', types_data_positions[i]))
                    f.write(struct.pack('<I', len(record)))

                for i, (name, record) in enumerate(symbol_records):
                    name_bytes = name.encode('utf-8')
                    f.write(struct.pack('<H', len(name_bytes)))
                    f.write(name_bytes)
                    f.write(struct.pack('<Q', symbols_data_positions[i]))
                    f.write(struct.pack('<I', len(record)))

                for name, target in typedef_entries:
                    name_bytes = name.encode('utf-8')
                    target_bytes = target.encode('utf-8')
                    f.write(struct.pack('<H', len(name_bytes)))
                    f.write(name_bytes)
                    f.write(struct.pack('<H', len(target_bytes)))
                    f.write(target_bytes)

                for _, record in type_records:
                    f.write(record)

                for _, record in symbol_records:
                    f.write(record)

                f.write(struct.pack('<Q', len(str_offsets)))
                for off in str_offsets:
                    f.write(struct.pack('<Q', off))
                f.write(str_data)

            # ---- Compute CRC32 and write checksum ----
            with open(isf_path, 'r+b') as f:
                mm = mmap.mmap(f.fileno(), 0)
                crc = _compute_crc32_chunked(mm, _ISF_HEADER_SIZE,
                                             total_file_size - _ISF_HEADER_SIZE)
                mm[12:16] = struct.pack('<I', crc)
                mm.close()

            logger.debug(f"Generated ISF file: {isf_path} ({total_file_size} bytes)")
            return True

        except Exception as e:
            logger.warning(f"Failed to generate ISF with dwarffi: {e}")
            return False

    def _dtype_to_isf(self, dtype) -> Dict[str, Any]:
        result = {
            'name': dtype.name,
            'kind': dtype.kind,
            'size': dtype.size,
            'members': [],
        }
        if hasattr(dtype, 'members') and dtype.members:
            for member_name, member in dtype.members.items():
                type_info = member.type_info if hasattr(member, 'type_info') and member.type_info else {}
                type_kind = type_info.get('kind', 'unknown')
                member_size = self._address_size if type_kind == 'pointer' else 0
                type_name = type_info.get('name', str(type_kind))
                result['members'].append({
                    'name': member.name,
                    'offset': member.offset,
                    'size': member_size,
                    'type': type_name,
                })
        return result

    # ------------------------------------------------------------------
    # Cache loading
    # ------------------------------------------------------------------

    def _load_or_generate_isf(self):
        isf_path = self._get_isf_path()

        if os.path.exists(isf_path):
            logger.debug(f"Loading ISF from cache: {isf_path}")
            if self._load_isf(isf_path):
                return
            # File exists but failed to load: corrupted or wrong format
            logger.warning("ISF cache loading failed, regenerating...")

        logger.debug(f"Generating ISF: {isf_path}")
        if self._generate_isf(isf_path):
            if self._load_isf(isf_path):
                return

        raise RuntimeError(
            "Failed to initialize DwarffiParser: could not generate or load ISF cache. "
            "Ensure dwarffi is installed and the ELF file is valid.")

    def _load_isf(self, isf_path: str) -> bool:
        """Load ISF cache with CRC32 verification.

        Raises ISFCorruptedError if the file is corrupted or has an
        unrecognized format.
        """
        try:
            with open(isf_path, 'rb') as f:
                self._mmap = mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ)

            header = self._mmap[:_ISF_HEADER_SIZE]
            unpacked = struct.unpack(_ISF_HEADER_FORMAT, header)

            magic = unpacked[0]
            version = unpacked[1]
            header_size = unpacked[2]
            stored_checksum = unpacked[3]
            file_size = unpacked[4]

            if magic != _ISF_MAGIC or version != _ISF_VERSION:
                self._string_pool = None
                self._mmap.close()
                self._mmap = None
                raise ISFCorruptedError(
                    f"Unrecognized ISF format (magic={magic!r}, version={version}). "
                    "File is corrupted or in an incompatible format. "
                    "Please delete the cache and regenerate.")

            computed_crc = _compute_crc32_chunked(
                self._mmap, _ISF_HEADER_SIZE,
                file_size - _ISF_HEADER_SIZE)
            if computed_crc != stored_checksum:
                self._string_pool = None
                self._mmap.close()
                self._mmap = None
                raise ISFCorruptedError(
                    f"ISF CRC32 mismatch (stored={stored_checksum:08x}, "
                    f"computed={computed_crc:08x}). "
                    "File is corrupted. Please delete the cache and regenerate.")

            (_, _, _, _, _,
             meta_offset, meta_size,
             types_count, symbols_count, typedefs_count,
             types_table_offset, symbols_table_offset,
             typedefs_table_offset,
             types_data_offset, symbols_data_offset,
             string_pool_offset, string_pool_size) = unpacked

            if types_count > _MAX_TYPES_COUNT:
                raise ValueError(f"Types count {types_count} exceeds limit")
            if symbols_count > _MAX_SYMBOLS_COUNT:
                raise ValueError(f"Symbols count {symbols_count} exceeds limit")
            if string_pool_size > _MAX_STRING_POOL_SIZE:
                raise ValueError(f"String pool size {string_pool_size} exceeds limit")

            self._types_data_offset = types_data_offset
            self._symbols_data_offset = symbols_data_offset

            # Parse meta (struct-based, 4 bytes)
            meta_bytes = self._mmap[meta_offset:meta_offset + meta_size]
            arch_byte, bits_byte, endian_byte, _ = struct.unpack('<BBBB', meta_bytes[:4])
            self._is_32bit = (bits_byte == 32)
            self._address_size = 4 if self._is_32bit else 8
            self._elf_header_info = {
                'is_32bit': self._is_32bit,
                'bits': bits_byte,
                'endian': 'little' if chr(endian_byte) == 'L' else 'big',
            }

            self._string_pool = StringPool(
                self._mmap, string_pool_offset, string_pool_size)

            # Build types index
            offset = types_table_offset
            for _ in range(types_count):
                name_len = struct.unpack_from('<H', self._mmap, offset)[0]
                if name_len > _MAX_NAME_LEN:
                    raise ValueError(f"Type name length {name_len} exceeds limit")
                name = self._mmap[offset + 2:offset + 2 + name_len].decode('utf-8')
                data_offset = struct.unpack_from('<Q', self._mmap, offset + 2 + name_len)[0]
                data_size = struct.unpack_from('<I', self._mmap, offset + 2 + name_len + 8)[0]
                self._types_index[name] = (data_offset, data_size)
                offset += 2 + name_len + 12

            # Build symbols index
            offset = symbols_table_offset
            for _ in range(symbols_count):
                name_len = struct.unpack_from('<H', self._mmap, offset)[0]
                if name_len > _MAX_NAME_LEN:
                    raise ValueError(f"Symbol name length {name_len} exceeds limit")
                name = self._mmap[offset + 2:offset + 2 + name_len].decode('utf-8')
                data_offset = struct.unpack_from('<Q', self._mmap, offset + 2 + name_len)[0]
                data_size = struct.unpack_from('<I', self._mmap, offset + 2 + name_len + 8)[0]
                self._symbols_index[name] = (data_offset, data_size)
                offset += 2 + name_len + 12

            # Build typedefs index
            offset = typedefs_table_offset
            for _ in range(typedefs_count):
                name_len = struct.unpack_from('<H', self._mmap, offset)[0]
                if name_len > _MAX_NAME_LEN:
                    raise ValueError(f"Typedef name length {name_len} exceeds limit")
                name = self._mmap[offset + 2:offset + 2 + name_len].decode('utf-8')
                target_len = struct.unpack_from('<H', self._mmap, offset + 2 + name_len)[0]
                if target_len > _MAX_TYPE_LEN:
                    raise ValueError(f"Typedef target length {target_len} exceeds limit")
                target = self._mmap[offset + 2 + name_len + 2:
                                    offset + 2 + name_len + 2 + target_len].decode('utf-8')
                self._typedef_cache[name] = target
                offset += 2 + name_len + 2 + target_len

            logger.debug(f"Loaded ISF: {types_count} types, {symbols_count} symbols, "
                         f"{typedefs_count} typedefs, string_pool={string_pool_size} bytes")
            return True

        except ISFCorruptedError:
            raise
        except Exception as e:
            self._string_pool = None
            if self._mmap:
                self._mmap.close()
                self._mmap = None
            logger.warning(f"Failed to load ISF: {e}")
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_32bit(self) -> bool:
        return self._is_32bit

    def get_address_size(self) -> int:
        return self._address_size

    def get_elf_header(self) -> Dict[str, Any]:
        return self._elf_header_info

    def get_symbol_by_name(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        if self._dffi:
            try:
                sym = self._dffi.get_symbol(symbol_name)
                return {
                    'name': symbol_name,
                    'address': sym.address,
                    'size': 0,
                    'type': str(sym.type_info.get('name')) if sym.type_info else None,
                }
            except Exception:
                pass

        if symbol_name in self._symbol_cache:
            return self._symbol_cache[symbol_name]

        entry = self._symbols_index.get(symbol_name)
        if entry is not None:
            data_offset, _data_size = entry
            result = self._decode_symbol(data_offset)
            self._symbol_cache[symbol_name] = result
            return result

        return None

    def _decode_symbol(self, data_offset: int) -> Dict[str, Any]:
        """Decode a single symbol record from ISF fixed binary format."""
        name_idx, address, size, type_idx = struct.unpack_from(
            _SYMBOL_RECORD_FMT, self._mmap, data_offset)
        sp = self._string_pool
        cache = sp._cache
        sp_count = sp._count

        name = cache[name_idx]
        if name is None:
            off = sp._data_offsets[name_idx]
            length = sp._lengths[name_idx]
            name = bytes(sp._pool_mv[off:off + length]).decode('utf-8')
            cache[name_idx] = name

        type_str = None
        if type_idx < sp_count:
            type_str = cache[type_idx]
            if type_str is None:
                off = sp._data_offsets[type_idx]
                length = sp._lengths[type_idx]
                type_str = bytes(sp._pool_mv[off:off + length]).decode('utf-8')
                cache[type_idx] = type_str

        return {
            'name': name,
            'address': address,
            'size': size,
            'type': type_str,
        }

    def get_struct_type(self, struct_name: str) -> Optional[Dict[str, Any]]:
        if self._dffi:
            try:
                dtype = self._dffi.get_type(struct_name)
                isf_type = self._dtype_to_isf(dtype)
                return {
                    'kind': isf_type.get('kind'),
                    'name': isf_type.get('name'),
                    'byte_size': isf_type.get('size'),
                    'members': [
                        {
                            'name': m['name'],
                            'offset': m['offset'],
                            'byte_size': m['size'],
                            'type_name': m['type'],
                        } for m in isf_type.get('members', [])
                    ],
                }
            except Exception:
                pass

        if struct_name in self._typedef_cache:
            struct_name = self._typedef_cache[struct_name]

        if struct_name in self._struct_type_cache:
            return self._struct_type_cache[struct_name]

        entry = self._types_index.get(struct_name)
        if entry is not None:
            data_offset, _data_size = entry
            result = self._decode_type(struct_name, data_offset)
            self._struct_type_cache[struct_name] = result
            return result

        return None

    def _decode_type(self, struct_name: str, data_offset: int) -> Dict[str, Any]:
        """Decode a single type record from ISF fixed binary format.

        Members are returned as a lazy MembersView, not eagerly parsed
        into a list of dicts. This is the key to controlling memory.
        """
        kind_byte, name_idx, size, members_count = struct.unpack_from(
            _TYPE_RECORD_HEADER_FMT, self._mmap, data_offset)

        if members_count > _MAX_MEMBERS_COUNT:
            raise ValueError(
                f"Type '{struct_name}' members_count {members_count} exceeds limit")

        kind = chr(kind_byte) if 32 <= kind_byte < 127 else 'struct'

        sp = self._string_pool
        cache = sp._cache
        name = cache[name_idx]
        if name is None:
            off = sp._data_offsets[name_idx]
            length = sp._lengths[name_idx]
            name = bytes(sp._pool_mv[off:off + length]).decode('utf-8')
            cache[name_idx] = name

        if members_count > 0:
            members_base = data_offset + _TYPE_RECORD_HEADER_SIZE
            members = MembersView(self._mmap, members_base, members_count, sp)
        else:
            members = []

        return {
            'kind': kind,
            'name': name,
            'byte_size': size,
            'members': members,
        }

    def get_var_type(self, var_name: str) -> Optional[Dict[str, Any]]:
        return None

    def parse_struct_from_dump(self, struct_name: str, address: int,
                                dump_data: bytes) -> Optional[Dict[str, Any]]:
        struct_type = self.get_struct_type(struct_name)
        if not struct_type:
            return None

        result = {
            'struct_name': struct_name,
            'address': address,
            'size': struct_type['byte_size'],
            'members': {},
        }

        struct_data = self.read_memory_from_dump(
            address, struct_type['byte_size'], dump_data)
        if not struct_data:
            return None

        for member in struct_type.get('members', []):
            member_name = member['name']
            member_offset = member['offset']
            member_size = member['byte_size']

            if member_offset + member_size <= len(struct_data):
                member_data = struct_data[member_offset:member_offset + member_size]
                member_value = self._unpack_value(member_data, member_size)

                result['members'][member_name] = {
                    'offset': member_offset,
                    'size': member_size,
                    'type_name': member.get('type_name'),
                    'value': member_value,
                    'raw': member_data.hex(),
                }

        return result

    def read_memory_from_dump(self, address: int, size: int,
                               dump_data: bytes) -> Optional[bytes]:
        return None

    def read_memory_from_elf(self, address: int, size: int) -> Optional[bytes]:
        return None

    def match_keywords(self, keywords: List[str],
                        check_elf_only: bool = False) -> List[str]:
        unmatched = []
        with open(self.elf_path, 'rb') as f:
            elf_text = f.read().decode('ascii', errors='ignore').lower()
        for keyword in keywords:
            if keyword.lower() not in elf_text:
                unmatched.append(keyword)
        return unmatched

    def find_symbols_by_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        return []

    def get_function_by_address(self, address: int) -> Optional[Dict[str, Any]]:
        return None

    def find_function_by_address(self, address: int) -> Optional[Dict[str, Any]]:
        return self.get_function_by_address(address)

    def parse_struct_auto(self, var_name: str, dump_reader) -> Optional[Any]:
        return None

    def get_all_symbols(self) -> List[Dict[str, Any]]:
        if self._symbol_cache:
            return list(self._symbol_cache.values())

        if self._symbols_index:
            result = []
            for name in self._symbols_index:
                sym = self.get_symbol_by_name(name)
                if sym:
                    result.append(sym)
            return result

        return []

    def _unpack_value(self, data: bytes, size: int) -> Any:
        if size == 1:
            return struct.unpack('<B', data)[0]
        elif size == 2:
            return struct.unpack('<H', data)[0]
        elif size == 4:
            return struct.unpack('<I', data)[0]
        elif size == 8:
            return struct.unpack('<Q', data)[0]
        else:
            return int.from_bytes(data, byteorder='little')


from .base import ELFParserFactory
ELFParserFactory.register('dwarffi', DwarffiParser)