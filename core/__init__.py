"""Core module for ELF/Dump parsing and profile management."""

from .elf_parser import ELFParser
from .dump_reader import DumpReader, MemoryRegion
from .profile_loader import ProfileLoader, PluginRegistry
from .context import PluginContext
from .exceptions import (
    ELFParserError,
    ProfileError,
    PluginError,
    DWARFError,
    MemoryReadError,
    ResourceNotFoundError,
)

__all__ = [
    'ELFParser',
    'DumpReader',
    'MemoryRegion',
    'ProfileLoader',
    'PluginRegistry',
    'PluginContext',
    'ELFParserError',
    'ProfileError',
    'PluginError',
    'DWARFError',
    'MemoryReadError',
    'ResourceNotFoundError',
]
