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
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Maximum string length for lazy pointer dereference when reading
# char* values. Prevents unbounded memory reads from corrupted pointers.
_MAX_STRING_READ_LENGTH = 256


class ViewNode:
    """Data view node representing a typed value from memory.

    This is the core abstraction for the new architecture. It represents
    a value read from memory with its DWARF type information, and can
    have children for composite types (structs, arrays, etc.).

    Attributes:
        name: Member name (for struct members) or variable name.
        type_name: DWARF type name (e.g., 'TX_THREAD', 'unsigned int', 'char*').
        kind: Type kind per DWARF Type → ViewNode Behavior Contract:
              'scalar'    - base type (no children, not expandable)
              'enum'      - enumeration type (no children)
              'ptr_struct' - pointer to struct/union/class (deref() support)
              'ptr_string' - pointer to char (get_string() lazy read)
              'ptr_func'   - pointer to function (display only)
              'ptr_scalar' - pointer to void/base/unresolved (display only)
              'string'    - char array (no children, display_value is string)
              'array'     - non-char array (children lazy-loaded)
              'struct'    - structure type (children fully parsed)
              'union'     - union type (children fully parsed)
        raw_value: The raw numeric value (for scalar/enum/pointer types).
        display_value: Human-readable formatted string.
        children: Child ViewNodes (for struct/union/array members).
        meta: Additional metadata dict.
        address: Memory address of this value.
        byte_size: Size in bytes.
        expandable: Whether this node can be lazily expanded.
    """

    def __init__(self, name: str = '', type_name: str = '', kind: str = 'scalar',
                 raw_value: Any = None, display_value: str = '',
                 children: Optional[List['ViewNode']] = None,
                 meta: Optional[Dict[str, Any]] = None,
                 address: int = 0, byte_size: int = 0,
                 expandable: bool = False):
        self.name = name
        self.type_name = type_name
        self.kind = kind
        self.raw_value = raw_value
        self.display_value = display_value
        self.children = children or []
        self.meta = meta or {}
        self.address = address
        self.byte_size = byte_size
        self.expandable = expandable

    def find_child(self, name: str) -> Optional['ViewNode']:
        """Find a direct child by name."""
        for child in self.children:
            if child.name == name:
                return child
        return None

    def to_dict(self, dump_reader=None, elf_parser=None,
                _visited: Optional[set] = None) -> Any:
        """Convert to dict format for backward compatibility.

        Mirrors the old _read_typed_value output format:
        - scalar types → int
        - enum types → int
        - string (char arrays) → string
        - ptr_string → string (lazy dereference for backward compat)
        - ptr_struct → nested dict (auto-dereference for backward compat)
        - ptr_scalar / ptr_func → display_value string
        - arrays → list
        - structs / unions → dict of member_name: value

        Args:
            dump_reader: Optional DumpReader for dereferencing pointers.
            elf_parser: Optional ELFParser for dereferencing pointers.
            _visited: Internal recursion guard.
        """
        if _visited is None:
            _visited = set()

        kind = self.kind

        if kind == 'scalar':
            return self.raw_value

        if kind == 'enum':
            return self.raw_value

        if kind == 'string':
            return self.display_value

        # ── Pointer kinds ──
        if kind in ('ptr_struct', 'ptr_string', 'ptr_func', 'ptr_scalar'):
            if self.meta.get('is_null'):
                return None

            # ptr_string: lazy dereference for backward compat
            if kind == 'ptr_string':
                if dump_reader and self.raw_value:
                    try:
                        s = dump_reader.read_string(self.raw_value, max_length=_MAX_STRING_READ_LENGTH)
                        if s is not None:
                            return s
                    except Exception:
                        pass
                return ''

            # ptr_struct: auto-dereference for backward compat
            if kind == 'ptr_struct':
                ptr_target = self.raw_value
                target_type = self.meta.get('target_type')
                visit_key = ('deref', ptr_target, id(target_type) if target_type else 0)
                if visit_key in _visited:
                    return {'error': 'circular pointer reference',
                            'ptr': f'0x{ptr_target:X}'}
                _visited.add(visit_key)
                result = self._deref_to_dict(dump_reader, elf_parser, _visited)
                _visited.discard(visit_key)
                return result

            # ptr_scalar / ptr_func: return display_value
            return self.display_value

        if kind == 'array':
            return [child.to_dict(dump_reader, elf_parser, _visited)
                    for child in self.children]

        if kind in ('struct', 'union'):
            visit_key = (self.address, id(self))
            if visit_key in _visited:
                return {'error': 'circular reference detected'}
            _visited.add(visit_key)
            result = {}
            for child in self.children:
                result[child.name] = child.to_dict(dump_reader, elf_parser, _visited)
            _visited.discard(visit_key)
            return result

        if kind in ('typedef', 'const', 'volatile'):
            if self.children:
                return self.children[0].to_dict(dump_reader, elf_parser, _visited) \
                    if len(self.children) == 1 else None
            return self.raw_value

        return self.raw_value

    def _deref_to_dict(self, dump_reader, elf_parser, _visited: set) -> Any:
        """Dereference a struct pointer and return the struct dict.

        When dump_reader and elf_parser are available, actually reads the
        struct from memory. Otherwise returns a placeholder dict.
        """
        target_type = self.meta.get('target_type')
        if not target_type:
            return self.display_value
        # Unwrap const/volatile/typedef
        current = target_type
        while current and current.get('kind') in ('const', 'volatile', 'typedef'):
            current = current.get('ref_type')
        if not current or current.get('kind') not in ('struct', 'union'):
            return self.display_value

        ptr_target = self.raw_value
        if not ptr_target:
            return {'error': 'null pointer target'}

        if dump_reader and elf_parser:
            # Verify the pointer target address is valid
            if dump_reader.read_memory(ptr_target, 1) is None:
                return {'error': 'invalid pointer address'}
            # Actually read the struct from memory
            try:
                deref_node = elf_parser.read_struct_as_node(current, ptr_target, dump_reader)
                if deref_node:
                    return deref_node.to_dict(dump_reader, elf_parser, _visited)
                return {'error': 'invalid pointer address'}
            except Exception:
                return {'error': 'invalid pointer address'}

        # Fallback without dump_reader: return placeholder dict
        result = {}
        for member in current.get('members', []):
            m_name = member.get('name') or f'<anon@{member.get("offset")}>'
            result[m_name] = None
        return result

    def __repr__(self) -> str:
        return (f"ViewNode(name={self.name!r}, kind={self.kind!r}, "
                f"type={self.type_name!r}, dv={self.display_value!r})")


class StructAccessor:
    """Plugin-friendly accessor for struct ViewNodes.

    Provides convenient methods for accessing struct members by name,
    with automatic type conversion and dotted path support for nested structs.

    Constructor args:
        view_node: The root ViewNode (typically kind='struct' or 'union').
        dump_reader: DumpReader instance for reading raw memory.
        elf_parser: ELFParser instance for type lookups and dereference.
    """

    def __init__(self, view_node: ViewNode, dump_reader, elf_parser):
        self._node = view_node
        self._dump_reader = dump_reader
        self._elf_parser = elf_parser
        self._address = view_node.address if view_node else 0

    @property
    def address(self) -> int:
        """The base address of the struct this accessor wraps."""
        return self._address

    @property
    def node(self) -> ViewNode:
        """The underlying ViewNode."""
        return self._node

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    def _resolve_path(self, path: str) -> Optional[ViewNode]:
        """Resolve a dotted path (e.g. 'tx_timer_internal.remaining_ticks')
        to a ViewNode by walking the children tree."""
        if not path or not self._node:
            return None
        parts = path.split('.')
        current = self._node
        for part in parts:
            if current is None or current.kind not in ('struct', 'union'):
                return None
            found = current.find_child(part)
            if found is None:
                return None
            current = found
        return current

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def get(self, name: str, default: Any = None) -> Optional[ViewNode]:
        """Get a member ViewNode by name, supporting dotted paths.

        Args:
            name: Member name or dotted path (e.g. 'tx_timer_internal.remaining_ticks').
            default: Value to return if not found.

        Returns:
            The ViewNode for the member, or default if not found.
        """
        node = self._resolve_path(name)
        return node if node is not None else default

    def get_int(self, name: str, default: int = 0) -> int:
        """Get an integer value from a member.

        Works for scalar, enum, and pointer types.

        Args:
            name: Member name or dotted path.
            default: Value to return if not found or not convertible.

        Returns:
            Integer value.
        """
        node = self._resolve_path(name)
        if node is None:
            return default
        if node.kind in ('scalar', 'enum', 'ptr_struct', 'ptr_string', 'ptr_func', 'ptr_scalar'):
            return node.raw_value if node.raw_value is not None else default
        return default

    def get_string(self, name: str, default: str = '') -> str:
        """Get a string value from a member.

        Automatically handles char[] (kind='string') and char* (kind='ptr_string').

        Args:
            name: Member name or dotted path.
            default: Value to return if not found or not a string.

        Returns:
            String value.
        """
        node = self._resolve_path(name)
        if node is None:
            return default

        # char array → kind='string', display_value is the string
        if node.kind == 'string':
            return node.display_value if node.display_value else default

        # char* pointer → kind='ptr_string', lazy dereference
        if node.kind == 'ptr_string':
            ptr_val = node.raw_value
            if not ptr_val:
                return default
            try:
                s = self._dump_reader.read_string(ptr_val, max_length=_MAX_STRING_READ_LENGTH)
                return s if s is not None else default
            except Exception:
                return default

        return default

    def get_enum_name(self, name: str, fallback_map: Optional[Dict[int, str]] = None) -> str:
        """Get the enum name for a member.

        DWARF enum names take priority. If DWARF info is not available,
        falls back to the provided fallback_map.

        Args:
            name: Member name or dotted path.
            fallback_map: Dict mapping enum values to names (e.g. {0: 'TX_READY', ...}).

        Returns:
            Enum name string, or empty string if not found.
        """
        node = self._resolve_path(name)
        if node is None:
            return ''

        # DWARF enum: display_value format is "ENUM_NAME(value)"
        if node.kind == 'enum':
            dv = node.display_value
            if dv and '(' in dv:
                return dv.split('(')[0]
            return dv

        # Fallback: use the provided map with the raw value
        if fallback_map is not None and node.raw_value is not None:
            raw = node.raw_value
            if node.kind in ('scalar', 'enum', 'ptr_struct', 'ptr_string', 'ptr_func', 'ptr_scalar'):
                return fallback_map.get(raw, f'UNKNOWN({raw})')

        return ''

    def get_ptr(self, name: str) -> int:
        """Get a pointer value as integer.

        Args:
            name: Member name or dotted path.

        Returns:
            Pointer address, or 0 if not found.
        """
        node = self._resolve_path(name)
        if node is None:
            return 0
        if node.kind in ('ptr_struct', 'ptr_string', 'ptr_func', 'ptr_scalar'):
            return node.raw_value if node.raw_value is not None else 0
        return 0

    def deref(self, ptr_node_name: str) -> Optional['StructAccessor']:
        """Lazily dereference a ptr_struct member and return a StructAccessor.

        Follows the DWARF Type → ViewNode Behavior Contract: pointer
        dereference is performed on-demand, never during ViewNode construction.

        Args:
            ptr_node_name: Name of the pointer member (e.g. 'pxStack').

        Returns:
            StructAccessor wrapping the dereferenced struct, or None if:
            - the member is not found
            - the member is not a ptr_struct
            - the pointer is null
            - the target address is invalid/unreadable
        """
        node = self._resolve_path(ptr_node_name)
        if node is None:
            return None
        if node.kind != 'ptr_struct':
            return None
        if node.meta.get('is_null'):
            return None

        ptr_addr = node.raw_value
        if not ptr_addr:
            return None

        # Verify the target address is readable
        if self._dump_reader.read_memory(ptr_addr, 1) is None:
            return None

        # Unwrap typedef/const/volatile to get the actual struct type
        target_type = node.meta.get('target_type')
        if not target_type:
            return None
        current = target_type
        while current and current.get('kind') in ('const', 'volatile', 'typedef'):
            current = current.get('ref_type')
        if not current or current.get('kind') not in ('struct', 'union'):
            return None

        # Read the dereferenced struct and wrap in a new StructAccessor
        view_node = self._elf_parser.read_struct_as_node(current, ptr_addr, self._dump_reader)
        if view_node:
            return StructAccessor(view_node, self._dump_reader, self._elf_parser)

        return None

    def get_child_accessor(self, name: str) -> Optional['StructAccessor']:
        """Get a nested StructAccessor for a child struct/union member.

        Args:
            name: Member name (must be a struct/union type).

        Returns:
            StructAccessor for the child, or None if not found or not a struct.
        """
        node = self._resolve_path(name)
        if node is None:
            return None
        if node.kind not in ('struct', 'union'):
            return None
        return StructAccessor(node, self._dump_reader, self._elf_parser)

    def keys(self) -> List[str]:
        """Return the list of member names in this struct."""
        if not self._node:
            return []
        return [child.name for child in self._node.children]

    def __repr__(self) -> str:
        return f"StructAccessor(addr=0x{self._address:X}, keys={self.keys()})"