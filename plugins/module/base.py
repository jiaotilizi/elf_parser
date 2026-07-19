from typing import Dict, Any
from plugins.base import Plugin


class ModulePlugin(Plugin):
    def __init__(self, name: str, version: str, module_type: str, description: str = ""):
        super().__init__(name, version, description)
        self.module_type = module_type

    def initialize(self, context: Dict[str, Any]) -> bool:
        """Initialize the module plugin with execution context.

        Stores elf_parser and dump_reader with underscore-prefixed names
        for consistency with RTOSPlugin base class.
        """
        self._elf_parser = context.get('elf_parser')
        self._dump_reader = context.get('dump_reader')
        self._profile = context.get('profile')
        self._context = context
        # Backward-compatible non-underscore attributes
        self.elf_parser = self._elf_parser
        self.dump_reader = self._dump_reader
        self.profile = self._profile
        return True

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
