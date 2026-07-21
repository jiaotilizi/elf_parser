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

from .base import ELFParser, ELFParserFactory

logger = logging.getLogger(__name__)


@ELFParserFactory.register('gimli')
class GimliParser(ELFParser):
    """ELF parser using Rust gimli library for high-performance DWARF parsing.

    This parser is reserved for future implementation. Currently, it raises
    NotImplementedError. The factory will fall back to elftools when this
    parser is selected.

    Planned capabilities:
    - Zero-copy DWARF parsing via rkyv Archive + mmap
    - PyO3 native extension for minimal Python overhead
    - Shared memory support for cross-process access
    """

    def __init__(self, elf_path: str):
        super().__init__(elf_path)
        raise NotImplementedError(
            "GimliParser is not yet implemented. "
            "It is reserved for future Rust-based gimli integration. "
            "Use 'elftools' or 'dwarffi' parser instead.")

    def is_32bit(self) -> bool:
        raise NotImplementedError("GimliParser is not yet implemented.")

    def get_address_size(self) -> int:
        raise NotImplementedError("GimliParser is not yet implemented.")

    def get_elf_header(self) -> Dict[str, Any]:
        raise NotImplementedError("GimliParser is not yet implemented.")

    def get_symbol_by_name(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("GimliParser is not yet implemented.")

    def get_struct_type(self, struct_name: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("GimliParser is not yet implemented.")

    def get_var_type(self, var_name: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("GimliParser is not yet implemented.")

    def parse_struct_from_dump(self, struct_name: str, address: int,
                                dump_data: bytes) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("GimliParser is not yet implemented.")

    def read_memory_from_dump(self, address: int, size: int,
                               dump_data: bytes) -> Optional[bytes]:
        raise NotImplementedError("GimliParser is not yet implemented.")

    def read_memory_from_elf(self, address: int, size: int) -> Optional[bytes]:
        raise NotImplementedError("GimliParser is not yet implemented.")

    def match_keywords(self, keywords: List[str],
                        check_elf_only: bool = False) -> List[str]:
        raise NotImplementedError("GimliParser is not yet implemented.")

    def find_symbols_by_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        raise NotImplementedError("GimliParser is not yet implemented.")

    def get_function_by_address(self, address: int) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("GimliParser is not yet implemented.")

    def get_all_symbols(self) -> List[Dict[str, Any]]:
        raise NotImplementedError("GimliParser is not yet implemented.")