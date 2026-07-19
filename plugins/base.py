import logging
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger(__name__)


class PluginResult:
    def __init__(self, 
                 display_type: str = 'raw',
                 title: str = '',
                 columns: List[str] = None,
                 rows: List[Dict] = None,
                 data: Any = None,
                 view_config: Dict = None):
        self.display_type = display_type
        self.title = title
        self.columns = columns or []
        self.rows = rows or []
        self.data = data
        self.view_config = view_config or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'display_type': self.display_type,
            'title': self.title,
            'columns': self.columns,
            'rows': self.rows,
            'data': self.data,
            'view_config': self.view_config,
        }


class Plugin:
    def __init__(self, name: str, version: str, description: str = ""):
        self.name = name
        self.version = version
        self.description = description
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        return True
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {}
    
    def get_required_symbols(self) -> List[str]:
        return []
    
    def get_required_structs(self) -> List[str]:
        return []
    
    def get_display_config(self) -> Dict[str, Any]:
        return {
            'display_type': 'table',
            'title': self.name,
        }


class OSPlugin(Plugin):
    def __init__(self, name: str, version: str, os_name: str, os_version: str, description: str = ""):
        super().__init__(name, version, description)
        self.os_name = os_name
        self.os_version = os_version
        self._context = None
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        self._context = context
        return True
    
    def get_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []
    
    def get_semaphores(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []
    
    def get_mutexes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []
    
    def get_queues(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []
    
    def get_heap_info(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {}
    
    def get_current_task(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None
    
    def get_display_config(self) -> Dict[str, Any]:
        return {
            'display_type': 'tree',
            'title': f"{self.os_name} {self.os_version}",
            'view_config': {
                'expand_level': 2,
                'show_address': True,
            }
        }


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
