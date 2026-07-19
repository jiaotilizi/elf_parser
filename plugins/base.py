import logging
from typing import Dict, List, Optional, Any

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
