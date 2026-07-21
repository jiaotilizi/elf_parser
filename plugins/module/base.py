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
from typing import Dict, Any
from plugins.base import Plugin


class ModulePlugin(Plugin):
    def __init__(self, name: str, version: str, module_type: str, description: str = ""):
        super().__init__(name, version, description)
        self.module_type = module_type
        self._elf_parser = None
        self._dump_reader = None
        self._profile = None
        self._context = None

    def initialize(self, context: Dict[str, Any]) -> bool:
        """Initialize the module plugin with execution context.

        Stores elf_parser and dump_reader with underscore-prefixed names
        for consistency with RTOSPlugin base class.
        """
        self._elf_parser = context.get('elf_parser')
        self._dump_reader = context.get('dump_reader')
        self._profile = context.get('profile')
        self._context = context
        return True

    @property
    def elf_parser(self):
        return self._elf_parser

    @property
    def dump_reader(self):
        return self._dump_reader

    @property
    def profile(self):
        return self._profile

    def _get_elf_parser(self):
        return self._elf_parser

    def _get_dump_reader(self):
        return self._dump_reader

    def get_display_config(self) -> Dict[str, Any]:
        return {
            'display_type': 'table',
            'title': self.name,
            'view_config': {
                'show_hex': True,
            }
        }
