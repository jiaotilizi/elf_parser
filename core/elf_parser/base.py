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
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ELFParser(ABC):
    """Abstract base class for ELF parsers.

    All ELF parser implementations must inherit from this class and implement
    the abstract methods. This provides a common interface for different
    parsing backends (elftools, dwarffi, gimli).

    All return values from public API methods must be JSON-serializable
    primitive types (str, int, list, dict, None). No Python objects,
    generators, C FFI pointers, or opaque handles are allowed in return values.
    """

    def __init__(self, elf_path: str):
        self.elf_path = elf_path

    @abstractmethod
    def is_32bit(self) -> bool:
        """Return True if the ELF is 32-bit."""
        pass

    @abstractmethod
    def get_address_size(self) -> int:
        """Return the address size (4 for 32-bit, 8 for 64-bit)."""
        pass

    @abstractmethod
    def get_elf_header(self) -> Dict[str, Any]:
        """Return ELF header information."""
        pass

    @abstractmethod
    def get_symbol_by_name(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        """Get symbol info by name.

        Returns:
            Dict with keys: name, address, size, type
        """
        pass

    @abstractmethod
    def get_struct_type(self, struct_name: str) -> Optional[Dict[str, Any]]:
        """Get struct type definition by name.

        Returns:
            Dict with keys: kind, name, byte_size, members
            Each member has: name, offset, byte_size, type_name
        """
        pass

    @abstractmethod
    def get_var_type(self, var_name: str) -> Optional[Dict[str, Any]]:
        """Get variable type by name."""
        pass

    @abstractmethod
    def parse_struct_from_dump(self, struct_name: str, address: int, dump_data: bytes) -> Optional[Dict[str, Any]]:
        """Parse struct data from dump at given address."""
        pass

    @abstractmethod
    def read_memory_from_dump(self, address: int, size: int, dump_data: bytes) -> Optional[bytes]:
        """Read memory from dump data."""
        pass

    @abstractmethod
    def read_memory_from_elf(self, address: int, size: int) -> Optional[bytes]:
        """Read memory from ELF file."""
        pass

    @abstractmethod
    def match_keywords(self, keywords: List[str], check_elf_only: bool = False) -> List[str]:
        """Match keywords against ELF content."""
        pass

    @abstractmethod
    def find_symbols_by_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        """Find symbols matching a regex pattern."""
        pass

    @abstractmethod
    def get_function_by_address(self, address: int) -> Optional[Dict[str, Any]]:
        """Get function info containing the given address."""
        pass

    @abstractmethod
    def get_all_symbols(self) -> List[Dict[str, Any]]:
        """Get all symbols in the ELF file."""
        pass

    def get_member_offset(self, struct_name: str, member_name: str, default: int = 0) -> int:
        """Get the byte offset of a member within a struct type.

        This is a DWARF-level type introspection query, not data access.
        Used by FreeRTOS doubly-linked list traversal to compute
        container-of relationships (e.g., TCB address from ListItem address).

        Args:
            struct_name: DWARF struct/union type name.
            member_name: Name of the member within the struct.
            default: Value to return if struct or member is not found.

        Returns:
            Byte offset of the member within the struct.
        """
        struct_type = self.get_struct_type(struct_name)
        if not struct_type:
            return default
        for member in struct_type.get('members', []):
            if member.get('name') == member_name:
                return member.get('offset', default)
        return default


class ELFParserFactory:
    """Factory for creating ELF parser instances based on configuration.

    Parsers are independent of each other and do not cross-reference.
    If a parser fails to initialize, the factory can fall back to elftools.
    """

    _parsers = {}

    @classmethod
    def register(cls, name: str, parser_class):
        """Register a parser class with the factory."""
        cls._parsers[name] = parser_class

    @classmethod
    def create(cls, elf_path: str, parser_type: str = 'elftools') -> ELFParser:
        """Create an ELF parser instance.

        Args:
            elf_path: Path to the ELF/AXF file
            parser_type: Type of parser to use ('elftools', 'dwarffi', or 'gimli')

        Returns:
            An instance of the appropriate ELF parser

        Raises:
            ValueError: If the parser type is unknown
        """
        parser_class = cls._parsers.get(parser_type)
        if not parser_class:
            raise ValueError(
                f"Unknown parser type: {parser_type}. "
                f"Available: {list(cls._parsers.keys())}")

        try:
            return parser_class(elf_path)
        except Exception as e:
            if parser_type != 'elftools':
                logger.warning(
                    f"Parser '{parser_type}' failed to initialize: {e}. "
                    f"Falling back to 'elftools'.")
                fallback = cls._parsers.get('elftools')
                if fallback:
                    return fallback(elf_path)
            raise