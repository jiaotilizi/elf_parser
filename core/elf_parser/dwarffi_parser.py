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
import bisect
import logging
import os
import re
import struct
import mmap
import hashlib
import zlib
from typing import Dict, List, Optional, Any, Tuple, Sequence, Iterator

from .base import ELFParser
from .struct_accessor import ViewNode, StructAccessor

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
_ISF_VERSION = 2

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
# kind: 0=scalar, 1=struct/union, 2=array, 3=pointer
_SYMBOL_RECORD_FMT = '<IQIIBII'  # name_idx(4) + address(8) + size(4) + type_idx(4) + kind(1) + element_type_idx(4) + element_count(4)
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

        self._segment_cache: List[Dict[str, Any]] = []
        self._sorted_segment_ranges: List[Tuple[int, int, Dict[str, Any]]] = []

        self._types_index: Dict[str, Tuple[int, int]] = {}
        self._symbols_index: Dict[str, Tuple[int, int]] = {}
        self._types_data_offset = 0
        self._symbols_data_offset = 0
        self._string_pool: Optional[StringPool] = None
        
        self._sorted_functions: List[Tuple[int, int, Dict[str, Any]]] = []
        self._function_addresses: List[int] = []

        self._load_or_generate_isf()
        self._parse_elf_segments_and_symbols()
        self._build_function_index()

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
                    if not sym:
                        continue
                    
                    type_info = sym.type_info
                    
                    kind = 0
                    element_type = ''
                    element_count = 0
                    type_name = None
                    
                    if type_info:
                        ti_kind = type_info.get('kind', '')
                        if ti_kind in ('struct', 'union'):
                            kind = 1
                            type_name = type_info.get('name')
                        elif ti_kind == 'array':
                            kind = 2
                            element_type_info = type_info.get('subtype') or type_info.get('element_type')
                            if element_type_info:
                                element_type = element_type_info.get('name', '')
                            element_count = type_info.get('count', 0) or type_info.get('element_count', 0)
                            type_name = element_type
                        elif ti_kind.startswith('ptr_'):
                            kind = 3
                            type_name = type_info.get('name')
                    
                    symbols_data.append({
                        'name': sym_name,
                        'address': sym.address,
                        'size': 0,
                        'type': type_name if type_name else None,
                        'kind': kind,
                        'element_type': element_type,
                        'element_count': element_count,
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
                _intern(str(sym.get('type', '')) if sym.get('type') else '')
                _intern(sym.get('element_type', ''))

            for td_name, td_target in typedefs_data.items():
                _intern(td_name)
                _intern(td_target)

            str_offsets: List[int] = []
            str_data = bytearray()
            for s in str_list:
                str_offsets.append(len(str_data))
                str_data.extend(s.encode('utf-8'))
                str_data.append(0)
            
            if len(str_list) != len(str_offsets):
                logger.warning(f"String list/offsets mismatch: {len(str_list)} vs {len(str_offsets)}")

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
                type_val = sym.get('type')
                type_idx = _intern(str(type_val) if type_val else '')
                kind = sym.get('kind', 0)
                element_type_idx = _intern(sym.get('element_type', ''))
                element_count = sym.get('element_count', 0)
                record = struct.pack(_SYMBOL_RECORD_FMT,
                                     name_idx, sym['address'], sym['size'], 
                                     type_idx, kind, element_type_idx, element_count)
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
                if type_kind == 'pointer':
                    member_size = self._address_size
                elif hasattr(member, 'size') and member.size > 0:
                    member_size = member.size
                else:
                    member_size = self._address_size
                type_name = type_info.get('name', str(type_kind))
                result['members'].append({
                    'name': member.name,
                    'offset': member.offset,
                    'size': member_size,
                    'type': type_name,
                })
            result['members'].sort(key=lambda m: m['offset'])
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
        entry = self._symbols_index.get(symbol_name)
        if entry is not None:
            data_offset, _data_size = entry
            result = self._decode_symbol(data_offset)
            self._symbol_cache[symbol_name] = result
            return result

        return None

    def _decode_symbol(self, data_offset: int) -> Dict[str, Any]:
        """Decode a single symbol record from ISF fixed binary format."""
        name_idx, address, size, type_idx, kind, element_type_idx, element_count = struct.unpack_from(
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

        element_type_str = None
        if element_type_idx < sp_count:
            element_type_str = cache[element_type_idx]
            if element_type_str is None:
                off = sp._data_offsets[element_type_idx]
                length = sp._lengths[element_type_idx]
                element_type_str = bytes(sp._pool_mv[off:off + length]).decode('utf-8')
                cache[element_type_idx] = element_type_str

        kind_str = ''
        if kind == 1:
            kind_str = 'struct'
        elif kind == 2:
            kind_str = 'array'
        elif kind == 3:
            kind_str = 'pointer'

        return {
            'name': name,
            'address': address,
            'size': size,
            'type': type_str,
            'kind': kind_str,
            'element_type': element_type_str,
            'element_count': element_count,
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

    def match_keywords(self, keywords: List[str],
                        check_elf_only: bool = False) -> List[str]:
        unmatched = []
        with open(self.elf_path, 'rb') as f:
            elf_text = f.read().decode('ascii', errors='ignore').lower()
        for keyword in keywords:
            if keyword.lower() not in elf_text:
                unmatched.append(keyword)
        return unmatched

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

    # ------------------------------------------------------------------
    # ELF segments and symbols (lightweight, no DWARF)
    # ------------------------------------------------------------------

    def _parse_elf_segments_and_symbols(self):
        """Parse ELF segments and symbols using elftools (fast, no DWARF)."""
        try:
            from elftools.elf.elffile import ELFFile

            with open(self.elf_path, 'rb') as f:
                elffile = ELFFile(f)

                self._elf_header_info.update({
                    'class': elffile.elfclass,
                    'machine': elffile.get_machine_arch(),
                    'entry': elffile.header['e_entry'],
                    'num_sections': elffile.num_sections(),
                    'num_segments': elffile.num_segments(),
                })

                for seg in elffile.iter_segments():
                    if seg['p_type'] == 'PT_LOAD':
                        self._segment_cache.append({
                            'vaddr': seg['p_vaddr'],
                            'filesz': seg['p_filesz'],
                            'memsz': seg['p_memsz'],
                            'data': seg.data(),
                        })

                self._sorted_segment_ranges = sorted(
                    [(s['vaddr'], s['vaddr'] + s['memsz'], s) for s in self._segment_cache],
                    key=lambda x: x[0]
                )

                # Parse ELF symbols (from .symtab)
                symtab = elffile.get_section_by_name('.symtab')
                if symtab:
                    for sym in symtab.iter_symbols():
                        name = sym.name
                        if name and sym['st_info']['type'] == 'STT_OBJECT':
                            kind = 'global_object'
                        elif name and sym['st_info']['type'] == 'STT_FUNC':
                            kind = 'function'
                        elif name and sym['st_info']['type'] == 'STT_NOTYPE':
                            kind = 'maybe'
                        else:
                            continue

                        if name not in self._symbol_cache:
                            self._symbol_cache[name] = {
                                'name': name,
                                'address': sym['st_value'],
                                'size': sym['st_size'],
                                'type': kind,
                            }

            logger.debug(f"Parsed ELF segments: {len(self._segment_cache)} "
                         f"PT_LOAD segments, {len(self._symbol_cache)} symbols")

        except Exception as e:
            logger.warning(f"Failed to parse ELF segments/symbols: {e}")

    def _build_function_index(self):
        """Build sorted index for fast function lookup by address."""
        functions = []
        for sym in self._symbol_cache.values():
            if sym.get('type') == 'function':
                addr = sym.get('address', 0)
                size = sym.get('size', 0)
                functions.append((addr, addr + max(size, 1), sym))
        
        functions.sort(key=lambda x: x[0])
        self._sorted_functions = functions
        self._function_addresses = [f[0] for f in functions]
        logger.debug(f"Built function index: {len(functions)} functions")

    def _find_segment_for_address(self, address: int, size: int = 0) -> Optional[Dict[str, Any]]:
        if not self._sorted_segment_ranges:
            return None
        low_addrs = [r[0] for r in self._sorted_segment_ranges]
        idx = bisect.bisect_right(low_addrs, address) - 1
        if idx >= 0:
            start, end, seg = self._sorted_segment_ranges[idx]
            if start <= address < end:
                return seg
        return None

    def read_memory_from_dump(self, address: int, size: int, dump_data: bytes) -> Optional[bytes]:
        seg = self._find_segment_for_address(address, size)
        if seg:
            dump_offset = address - seg['vaddr']
            if dump_offset + size <= len(dump_data):
                return dump_data[dump_offset:dump_offset + size]
        return None

    def read_memory_from_elf(self, address: int, size: int) -> Optional[bytes]:
        seg = self._find_segment_for_address(address, size)
        if seg:
            file_offset = address - seg['vaddr']
            actual_size = min(size, seg['filesz'] - file_offset)
            if actual_size > 0:
                return seg['data'][file_offset:file_offset + actual_size]
        return None

    # ------------------------------------------------------------------
    # StructAccessor API
    # ------------------------------------------------------------------

    def read_struct_as_node(self, struct_type: Dict[str, Any], address: int,
                            dump_reader) -> Optional[ViewNode]:
        """Read a struct from dump memory and return a ViewNode tree."""
        if not dump_reader or not struct_type:
            return None

        byte_size = struct_type.get('byte_size', 0)
        if byte_size <= 0:
            return None

        struct_name = struct_type.get('name', '')

        # Read raw struct data from dump
        try:
            raw_data = dump_reader.read_memory(address, byte_size)
            if raw_data is None or len(raw_data) < byte_size:
                return None
        except Exception:
            return None

        is_32bit = self._is_32bit
        addr_size = self._address_size

        children = []
        members = struct_type.get('members', [])
        for member in members:
            m_name = member.get('name', '')
            m_offset = member.get('offset', 0)
            m_size = member.get('byte_size', 0)
            m_type_name = member.get('type_name', '')

            if m_offset + m_size > byte_size:
                continue

            member_data = raw_data[m_offset:m_offset + m_size]
            child = self._decode_member(m_name, m_type_name, m_size, member_data,
                                        address + m_offset, is_32bit, addr_size, dump_reader)
            children.append(child)

        return ViewNode(
            name=struct_name,
            type_name=struct_name,
            kind='struct',
            address=address,
            byte_size=byte_size,
            children=children,
            expandable=True,
        )

    def _decode_member(self, name: str, type_name: str, byte_size: int,
                       data: bytes, address: int, is_32bit: bool, addr_size: int,
                       dump_reader) -> ViewNode:
        """Decode a single struct member into a ViewNode."""
        # Determine type kind from type_name
        kind = self._infer_type_kind(type_name, byte_size, addr_size)

        if kind == 'ptr_struct' or kind == 'ptr_string' or kind == 'ptr_func' or kind == 'ptr_scalar':
            raw_value = self._unpack_int(data, byte_size, is_32bit)
            target_type = self._resolve_ptr_target_type(type_name)
            display_value = f"0x{raw_value:X}" if raw_value else "NULL"
            meta = {'is_null': raw_value == 0}
            if target_type:
                meta['target_type'] = target_type
            return ViewNode(
                name=name, type_name=type_name, kind=kind,
                raw_value=raw_value, display_value=display_value,
                address=address, byte_size=byte_size, meta=meta,
            )

        elif kind == 'struct':
            return ViewNode(
                name=name, type_name=type_name, kind='struct',
                address=address, byte_size=byte_size,
                expandable=True,
                meta={'struct_type_name': type_name},
            )

        elif kind == 'string':
            # Fixed char array
            try:
                s = data.split(b'\x00')[0].decode('utf-8', errors='replace')
            except Exception:
                s = ''
            return ViewNode(
                name=name, type_name=type_name, kind='string',
                display_value=s, address=address, byte_size=byte_size,
            )

        elif kind == 'enum':
            raw_value = self._unpack_int(data, min(byte_size, 4), is_32bit)
            return ViewNode(
                name=name, type_name=type_name, kind='enum',
                raw_value=raw_value, display_value=f"{type_name}({raw_value})",
                address=address, byte_size=byte_size,
            )

        else:
            # Scalar
            raw_value = self._unpack_int(data, min(byte_size, 8), is_32bit)
            is_signed = 'int' in type_name.lower() and 'unsigned' not in type_name.lower()
            if is_signed and byte_size <= 4:
                if byte_size == 1:
                    raw_value = struct.unpack('<b', data[:1])[0]
                elif byte_size == 2:
                    raw_value = struct.unpack('<h', data[:2])[0]
                elif byte_size == 4:
                    raw_value = struct.unpack('<i', data[:4])[0]
            display_value = str(raw_value)
            return ViewNode(
                name=name, type_name=type_name, kind='scalar',
                raw_value=raw_value, display_value=display_value,
                address=address, byte_size=byte_size,
            )

    def _infer_type_kind(self, type_name: str, byte_size: int, addr_size: int) -> str:
        """Infer the ViewNode kind from the type name and byte size."""
        if not type_name:
            return 'scalar'

        tn = type_name.strip()

        # Pointer types
        if tn.endswith('*') or tn.endswith(' *'):
            if tn == 'CHAR *' or tn == 'char *' or 'char' in tn.lower() and tn.endswith('*'):
                return 'ptr_string'
            base = tn.rstrip(' *').strip()
            if base in self._types_index or base in self._typedef_cache:
                return 'ptr_struct'
            return 'ptr_scalar'

        # Special case: ISF stores pointer types as 'pointer' without target type info
        # When byte_size matches address size, treat as pointer
        if tn == 'pointer' and byte_size == addr_size:
            return 'ptr_scalar'

        # Known struct types
        if tn in self._types_index or tn in self._typedef_cache:
            type_info = self._struct_type_cache.get(tn)
            if type_info and type_info.get('kind') == 'e':
                return 'enum'
            return 'struct'

        # Special case: char arrays
        if byte_size == 1 and ('char' in tn.lower()):
            return 'string'

        # Known type names that indicate enums
        if tn.startswith('TX_') and byte_size == 4:
            # Could be an enum, check if it's in types
            pass

        return 'scalar'

    def _resolve_ptr_target_type(self, type_name: str) -> Optional[Dict[str, Any]]:
        """Resolve a pointer type name to its target type definition."""
        if not type_name:
            return None
        base = type_name.rstrip(' *').strip()
        if base == 'VOID' or base == 'void':
            return None
        target = self.get_struct_type(base)
        if target:
            return target
        return None

    def _unpack_int(self, data: bytes, size: int, is_32bit: bool) -> int:
        """Unpack an integer value from bytes."""
        if size <= 0:
            return 0
        actual = min(size, len(data))
        if actual == 0:
            return 0
        if actual == 1:
            return struct.unpack('<B', data[:1])[0]
        elif actual == 2:
            return struct.unpack('<H', data[:2])[0]
        elif actual == 4:
            return struct.unpack('<I', data[:4])[0]
        elif actual == 8:
            return struct.unpack('<Q', data[:8])[0]
        else:
            return int.from_bytes(data[:actual], byteorder='little')

    def create_accessor(self, var_name: str, dump_reader) -> Optional[StructAccessor]:
        """Create a StructAccessor for a global variable by name."""
        sym = self.get_symbol_by_name(var_name)
        if not sym:
            return None

        var_type = self.get_variable_type(var_name)
        if not var_type:
            return None

        kind = var_type.get('kind', '')
        type_name = var_type.get('name', '')

        # Unwrap typedef/const/volatile
        current = var_type
        while current and current.get('kind') in ('const', 'volatile', 'typedef'):
            current = current.get('ref_type')
        if not current or current.get('kind') not in ('struct', 'union'):
            return None

        struct_view = self.read_struct_as_node(current, sym['address'], dump_reader)
        if struct_view:
            # Set the variable name as the root node name
            struct_view.name = var_name
            return StructAccessor(struct_view, dump_reader, self)

        return None

    # ------------------------------------------------------------------
    # Symbol search and function lookup
    # ------------------------------------------------------------------

    def find_symbols_by_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        """Find symbols matching a regex pattern."""
        results = []
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return results

        # Search ISF symbol index
        for name in self._symbols_index:
            if regex.search(name):
                sym = self.get_symbol_by_name(name)
                if sym:
                    results.append(sym)

        # Also search ELF symbol cache
        for name, sym in self._symbol_cache.items():
            if regex.search(name) and name not in self._symbols_index:
                results.append(sym)

        return results

    def get_function_by_address(self, address: int) -> Optional[Dict[str, Any]]:
        """Find a function containing the given address."""
        return self.find_function_by_address(address)

    def find_function_by_address(self, address: int) -> Optional[Dict[str, Any]]:
        """Find the function containing the given address using binary search."""
        if not self._sorted_functions:
            return None

        idx = bisect.bisect_right(self._function_addresses, address) - 1
        
        if idx < 0:
            return None

        best = None
        best_size = 0
        
        for i in range(max(0, idx - 2), min(len(self._sorted_functions), idx + 3)):
            start, end, sym = self._sorted_functions[i]
            if start <= address < end:
                sym_size = sym.get('size', 0)
                if sym_size > best_size:
                    best = sym
                    best_size = sym_size

        if best:
            return {'name': best['name'], 'address': best['address'], 'size': best['size']}

        return None

    def get_var_type(self, var_name: str) -> Optional[Dict[str, Any]]:
        """Get variable type by name."""
        return self.get_variable_type(var_name)

    def get_variable_type(self, var_name: str) -> Optional[Dict[str, Any]]:
        """Get the type of a global variable."""
        if self._dffi:
            try:
                sym = self._dffi.get_symbol(var_name)
                if sym and sym.type_info:
                    ti = sym.type_info
                    return {
                        'name': ti.get('name', ''),
                        'kind': ti.get('kind', ''),
                        'byte_size': ti.get('size', 0),
                    }
            except Exception:
                pass

        # Fallback: look up symbol from cache and try to infer type
        sym = self.get_symbol_by_name(var_name)
        if sym and sym.get('type'):
            # Try to find a type with the same name
            type_name = sym.get('type')
            struct = self.get_struct_type(type_name)
            if struct:
                return struct

        return None

    def parse_struct_auto(self, var_name: str, dump_reader) -> Optional[Any]:
        """Parse a struct from dump by variable name."""
        return self.create_accessor(var_name, dump_reader)

    def read_struct_tree(self, struct_type_name: str, address: int, dump_reader, 
                         max_depth: int = 1) -> Optional[Dict[str, Any]]:
        """Read struct from memory and return a tree structure for GUI display."""
        struct_type = self.get_struct_type(struct_type_name)
        if not struct_type:
            return None

        view_node = self.read_struct_as_node(struct_type, address, dump_reader)
        if not view_node:
            return None

        return self._view_node_to_tree(view_node, dump_reader, max_depth, set())

    def read_symbol_tree(self, symbol_name: str, dump_reader, 
                         max_depth: int = 1) -> Optional[Dict[str, Any]]:
        """Read a symbol's value as a tree structure for GUI display."""
        sym = self.get_symbol_by_name(symbol_name)
        if not sym:
            return None

        address = sym.get('address', 0)
        byte_size = sym.get('size', 0)

        kind = sym.get('kind', '')
        type_name = sym.get('type', '')
        element_type = sym.get('element_type')
        element_count = sym.get('element_count', 0)

        if kind in ('struct', 'union'):
            if type_name:
                struct_type = self.get_struct_type(type_name)
                if struct_type:
                    return self.read_struct_tree(type_name, address, dump_reader, max_depth)
        
        elif kind == 'array':
            if element_type:
                elem_struct_type = self.get_struct_type(element_type)
                if elem_struct_type:
                    elem_size = elem_struct_type.get('byte_size', 0)
                    if element_count == 0 and byte_size > 0 and elem_size > 0:
                        element_count = byte_size // elem_size
                    return self._read_array_tree_from_type(element_type, elem_struct_type, 
                                                           address, byte_size, element_count, 
                                                           dump_reader, max_depth)
        
        elif kind == 'pointer':
            if type_name:
                target_type = type_name.replace('ptr_', '', 1)
                struct_type = self.get_struct_type(target_type)
                if struct_type:
                    raw_value = None
                    if dump_reader and byte_size > 0:
                        try:
                            data = dump_reader.read_memory(address, min(byte_size, 8))
                            if data:
                                raw_value = struct.unpack('<I' if byte_size == 4 else '<Q', data)[0]
                        except Exception:
                            pass
                    if raw_value:
                        return self.read_struct_tree(target_type, raw_value, dump_reader, max_depth)
            return self._read_scalar_tree(symbol_name, type_name, 'pointer', address, byte_size, dump_reader)

        if type_name:
            struct_type = self.get_struct_type(type_name)
            if struct_type:
                return self.read_struct_tree(type_name, address, dump_reader, max_depth)

        if byte_size > 0 and element_type:
            elem_struct_type = self.get_struct_type(element_type)
            if elem_struct_type:
                elem_size = elem_struct_type.get('byte_size', 0)
                if elem_size > 0:
                    if element_count == 0:
                        element_count = byte_size // elem_size
                    if element_count > 0:
                        return self._read_array_tree_from_type(element_type, elem_struct_type, 
                                                               address, byte_size, element_count, 
                                                               dump_reader, max_depth)

        return self._read_scalar_tree(symbol_name, type_name, 'scalar', address, byte_size, dump_reader)

    def _read_array_tree_from_type(self, element_type_name: str, element_struct_type: Dict[str, Any],
                                  address: int, byte_size: int, element_count: int,
                                  dump_reader, max_depth: int) -> Dict[str, Any]:
        """Read an array symbol when element type is known from ISF."""
        element_size = element_struct_type.get('byte_size', 4)
        
        children = []
        for i in range(element_count):
            elem_addr = address + i * element_size
            child_tree = self.read_struct_tree(element_type_name, elem_addr, dump_reader, max_depth)
            if child_tree:
                children.append(child_tree)

        return {
            'name': f'{element_type_name}[{element_count}]',
            'type_name': element_type_name,
            'kind': 'array',
            'raw_value': None,
            'display_value': f'array[{element_count}]',
            'address': address,
            'byte_size': byte_size,
            'expandable': True,
            'children': children,
        }

    def _read_array_tree(self, var_type: Dict[str, Any], address: int, byte_size: int, 
                         dump_reader, max_depth: int) -> Optional[Dict[str, Any]]:
        """Read an array symbol as a tree structure."""
        element_type = var_type.get('element_type')
        if not element_type:
            return None

        element_count = var_type.get('element_count', 0)
        if element_count == 0 and byte_size > 0:
            element_size = element_type.get('byte_size', 4)
            element_count = byte_size // element_size

        children = []
        for i in range(element_count):
            elem_addr = address + i * element_type.get('byte_size', 4)
            
            if element_type.get('kind') in ('struct', 'union'):
                child_tree = self.read_struct_tree(
                    element_type.get('name', ''), elem_addr, dump_reader, max_depth - 1)
            else:
                child_tree = self._read_scalar_tree(
                    f'[{i}]', element_type.get('name', ''), 
                    element_type.get('kind', 'scalar'),
                    elem_addr, element_type.get('byte_size', 4), dump_reader)
            
            if child_tree:
                children.append(child_tree)

        return {
            'name': var_type.get('name', ''),
            'type_name': var_type.get('name', ''),
            'kind': 'array',
            'raw_value': None,
            'display_value': f'array[{element_count}]',
            'address': address,
            'byte_size': byte_size,
            'expandable': True,
            'children': children,
        }

    def _read_scalar_tree(self, name: str, type_name: str, kind: str, 
                          address: int, byte_size: int, dump_reader) -> Dict[str, Any]:
        """Read a scalar/pointer symbol as a tree structure."""
        raw_value = None
        display_value = ''
        
        if dump_reader and byte_size > 0:
            try:
                data = dump_reader.read_memory(address, min(byte_size, 8))
                if data:
                    if byte_size == 1:
                        raw_value = struct.unpack('<B', data)[0]
                        display_value = f'{raw_value}'
                    elif byte_size == 2:
                        raw_value = struct.unpack('<H', data)[0]
                        display_value = f'{raw_value}'
                    elif byte_size == 4:
                        raw_value = struct.unpack('<I', data)[0]
                        if kind in ('ptr_struct', 'ptr_string', 'ptr_func', 'ptr_scalar'):
                            display_value = f'0x{raw_value:08X}'
                        else:
                            display_value = f'{raw_value}'
                    elif byte_size == 8:
                        raw_value = struct.unpack('<Q', data)[0]
                        if kind in ('ptr_struct', 'ptr_string', 'ptr_func', 'ptr_scalar'):
                            display_value = f'0x{raw_value:016X}'
                        else:
                            display_value = f'{raw_value}'
            except Exception:
                pass

        if raw_value is None:
            display_value = 'N/A'

        return {
            'name': name,
            'type_name': type_name,
            'kind': kind,
            'raw_value': raw_value,
            'display_value': display_value,
            'address': address,
            'byte_size': byte_size,
            'expandable': False,
            'children': [],
        }

    def _view_node_to_tree(self, node: ViewNode, dump_reader, max_depth: int, 
                           visited: set) -> Dict[str, Any]:
        """Convert a ViewNode to a tree dict for GUI display."""
        visit_key = (node.address, id(node))
        if visit_key in visited:
            return {
                'name': node.name,
                'type_name': node.type_name,
                'kind': node.kind,
                'raw_value': node.raw_value,
                'display_value': 'circular reference',
                'address': node.address,
                'byte_size': node.byte_size,
                'expandable': False,
                'children': [],
            }
        visited.add(visit_key)

        result = {
            'name': node.name,
            'type_name': node.type_name,
            'kind': node.kind,
            'raw_value': node.raw_value,
            'display_value': node.display_value,
            'address': node.address,
            'byte_size': node.byte_size,
            'expandable': node.expandable or (max_depth > 0 and node.kind in ('struct', 'union', 'array')),
            'children': [],
        }

        if max_depth > 0 and node.kind in ('struct', 'union'):
            if node.expandable and not node.children:
                self._expand_node(node, dump_reader)
            
            result['children'] = [
                self._view_node_to_tree(child, dump_reader, max_depth - 1, visited)
                for child in node.children
            ]
        
        elif max_depth > 0 and node.kind == 'array':
            result['children'] = [
                self._view_node_to_tree(child, dump_reader, max_depth - 1, visited)
                for child in node.children
            ]

        visited.discard(visit_key)
        return result

    def _expand_node(self, node: ViewNode, dump_reader):
        """Expand a ViewNode by reading its children from memory."""
        if node.kind not in ('struct', 'union'):
            return
        
        struct_type_name = node.meta.get('struct_type_name') or node.type_name
        struct_type = self.get_struct_type(struct_type_name)
        if not struct_type:
            return
        
        view_node = self.read_struct_as_node(struct_type, node.address, dump_reader)
        if view_node:
            node.children = view_node.children
            node.expandable = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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