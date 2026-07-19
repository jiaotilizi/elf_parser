from typing import Dict, Any
from plugins.base import Plugin


class ModulePlugin(Plugin):
    def __init__(self, name: str, version: str, module_type: str, description: str = ""):
        super().__init__(name, version, description)
        self.module_type = module_type
    
    def get_display_config(self) -> Dict[str, Any]:
        return {
            'display_type': 'table',
            'title': self.name,
            'view_config': {
                'show_hex': True,
            }
        }
