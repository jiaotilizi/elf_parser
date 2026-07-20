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

"""Structured context for plugin execution.

Provides typed access to the plugin execution context, replacing bare dicts.
"""

from typing import Dict, List, Any, Optional


class PluginContext:
    """Structured context passed to plugins during initialization and execution.

    Provides typed property access to commonly used context items while
    preserving the underlying dict for backward compatibility.
    """

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    # -- typed accessors --

    @property
    def elf_parser(self):
        """The ELFParser instance."""
        return self._data.get('elf_parser')

    @property
    def dump_reader(self):
        """The DumpReader instance."""
        return self._data.get('dump_reader')

    @property
    def profile(self) -> Dict[str, Any]:
        """The loaded profile configuration."""
        return self._data.get('profile', {})

    @property
    def plugins(self) -> List[Any]:
        """List of loaded plugin instances."""
        return self._data.get('plugins', [])

    @property
    def results(self) -> Dict[str, Any]:
        """Plugin execution results keyed by plugin name."""
        return self._data.get('results', {})

    @results.setter
    def results(self, value: Dict[str, Any]):
        self._data['results'] = value

    @property
    def config(self) -> Dict[str, Any]:
        """Additional configuration."""
        return self._data.get('config', {})

    # -- dict compatibility --

    def get(self, key: str, default=None) -> Any:
        """Dict-style access for backward compatibility."""
        return self._data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any):
        self._data[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def to_dict(self) -> Dict[str, Any]:
        """Return the underlying dict."""
        return self._data

    def __repr__(self) -> str:
        return f"PluginContext({self._data!r})"
