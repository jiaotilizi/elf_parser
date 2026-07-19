"""Plugin system for ELF parser.

Provides base classes and registry for RTOS and module plugins.
"""

from .base import Plugin, PluginResult

__all__ = ['Plugin', 'PluginResult']
