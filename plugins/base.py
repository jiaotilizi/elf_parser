import logging
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ResourceType(str, Enum):
    TASKS = 'tasks'
    MUTEXES = 'mutexes'
    SEMAPHORES = 'semaphores'
    QUEUES = 'queues'
    EVENTS = 'events'
    TIMERS = 'timers'
    BLOCK_POOLS = 'block_pools'
    BYTE_POOLS = 'byte_pools'
    TEST_POINTS = 'test_points'
    ASSERT_INFO = 'assert_info'


RESOURCE_TYPE_MAP = {
    'task': ResourceType.TASKS,
    'mutex': ResourceType.MUTEXES,
    'semaphore': ResourceType.SEMAPHORES,
    'queue': ResourceType.QUEUES,
    'event': ResourceType.EVENTS,
    'timer': ResourceType.TIMERS,
    'block_pool': ResourceType.BLOCK_POOLS,
    'byte_pool': ResourceType.BYTE_POOLS,
    'test_point': ResourceType.TEST_POINTS,
}


def normalize_resource_type(resource_type: str) -> str:
    if not resource_type:
        return resource_type
    try:
        return ResourceType(resource_type).value
    except ValueError:
        return RESOURCE_TYPE_MAP.get(resource_type, resource_type)


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
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        return True
    
    def get_resource_types(self) -> List[str]:
        return []
    
    def get_resource(self, resource_type: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        normalized_type = normalize_resource_type(resource_type)
        return []
    
    def get_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('tasks', context)
    
    def get_semaphores(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('semaphores', context)
    
    def get_mutexes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('mutexes', context)
    
    def get_queues(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('queues', context)
    
    def get_timers(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('timers', context)
    
    def get_events(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('events', context)
    
    def get_heap_info(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {}
    
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
