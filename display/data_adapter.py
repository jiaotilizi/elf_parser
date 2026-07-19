from typing import Dict, List, Any, Optional
from .base import ResourceMetadata


class DataAdapter:
    DEFAULT_METADATA = {
        'tasks': ResourceMetadata(
            resource_type='tasks',
            label='Tasks',
            icon='🧵',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
                {'name': 'state_name', 'label': 'State', 'type': 'string'},
                {'name': 'priority', 'label': 'Priority', 'type': 'number'},
                {'name': 'cpu_usage', 'label': 'CPU %', 'type': 'number'},
                {'name': 'stack_size', 'label': 'Stack Size', 'type': 'number'},
                {'name': 'stack_usage', 'label': 'Stack %', 'type': 'number'},
            ]
        ),
        'mutexes': ResourceMetadata(
            resource_type='mutexes',
            label='Mutexes',
            icon='🔒',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
                {'name': 'owner_info.name', 'label': 'Owner', 'type': 'string'},
                {'name': 'priority', 'label': 'Priority', 'type': 'number'},
            ]
        ),
        'semaphores': ResourceMetadata(
            resource_type='semaphores',
            label='Semaphores',
            icon='🚦',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
                {'name': 'count', 'label': 'Count', 'type': 'number'},
                {'name': 'max_count', 'label': 'Max', 'type': 'number'},
            ]
        ),
        'queues': ResourceMetadata(
            resource_type='queues',
            label='Queues',
            icon='📭',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
                {'name': 'messages', 'label': 'Messages', 'type': 'number'},
                {'name': 'max_messages', 'label': 'Max', 'type': 'number'},
            ]
        ),
        'events': ResourceMetadata(
            resource_type='events',
            label='Event Flags',
            icon='🎯',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
                {'name': 'flags', 'label': 'Flags', 'type': 'hex'},
            ]
        ),
        'timers': ResourceMetadata(
            resource_type='timers',
            label='Timers',
            icon='⏱️',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
                {'name': 'state_name', 'label': 'State', 'type': 'string'},
                {'name': 'period_ticks', 'label': 'Period', 'type': 'number'},
                {'name': 'ticks_remaining', 'label': 'Remaining', 'type': 'number'},
            ]
        ),
        'block_pools': ResourceMetadata(
            resource_type='block_pools',
            label='Block Pools',
            icon='🧱',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
                {'name': 'available_blocks', 'label': 'Available', 'type': 'number'},
                {'name': 'total_blocks', 'label': 'Total', 'type': 'number'},
            ]
        ),
        'byte_pools': ResourceMetadata(
            resource_type='byte_pools',
            label='Byte Pools',
            icon='💧',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
                {'name': 'available_bytes', 'label': 'Available', 'type': 'number'},
                {'name': 'total_bytes', 'label': 'Total', 'type': 'number'},
            ]
        ),
        'test_points': ResourceMetadata(
            resource_type='test_points',
            label='Test Points',
            icon='✅',
            primary_key='id',
            fields=[
                {'name': 'id', 'label': 'ID', 'type': 'number'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
                {'name': 'value', 'label': 'Value', 'type': 'string'},
                {'name': 'timestamp', 'label': 'Time', 'type': 'string'},
            ]
        ),
        'assert_info': ResourceMetadata(
            resource_type='assert_info',
            label='Assert Info',
            icon='⚠️',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'assert_id', 'label': 'Assert ID', 'type': 'number'},
                {'name': 'file_name', 'label': 'File', 'type': 'string'},
                {'name': 'line_number', 'label': 'Line', 'type': 'number'},
            ]
        ),
        'trace_buffer': ResourceMetadata(
            resource_type='trace_buffer',
            label='Trace Buffer',
            icon='📊',
            primary_key='timestamp',
            fields=[
                {'name': 'timestamp', 'label': 'Time', 'type': 'number'},
                {'name': 'type', 'label': 'Type', 'type': 'string'},
                {'name': 'point_id', 'label': 'Point ID', 'type': 'number'},
                {'name': 'task_id', 'label': 'Task ID', 'type': 'number'},
            ]
        ),
    }

    def __init__(self, context: Dict[str, Any], cache_ttl: int = 30):
        self.context = context
        self._cached_data = {}
        self._metadata_cache = {}
        self._cache_timestamp = 0
        self._cache_ttl = cache_ttl
    
    def _load_all_data(self):
        import time
        now = time.time()
        if self._cached_data and (now - self._cache_timestamp) < self._cache_ttl:
            return
        
        plugin_results = self.context.get('results', {})
        for plugin_name, plugin_data in plugin_results.items():
            for key, value in plugin_data.items():
                if isinstance(value, list):
                    self._cached_data[key] = value
        
        self._cache_timestamp = time.time()
    
    def get_all_resource_types(self) -> List[str]:
        self._load_all_data()
        return list(self._cached_data.keys())
    
    def get_resource_data(self, resource_type: str) -> List[Dict]:
        self._load_all_data()
        return self._cached_data.get(resource_type, [])
    
    def get_resource_metadata(self, resource_type: str) -> Optional[ResourceMetadata]:
        if resource_type in self._metadata_cache:
            return self._metadata_cache[resource_type]
        
        if resource_type in self.DEFAULT_METADATA:
            return self.DEFAULT_METADATA[resource_type]
        
        return ResourceMetadata(
            resource_type=resource_type,
            label=resource_type.capitalize(),
        )
    
    def get_detail(self, resource_type: str, address: int) -> Optional[Dict[str, Any]]:
        plugins = self.context.get('plugins', [])
        
        for plugin in plugins:
            if hasattr(plugin, 'get_detail'):
                try:
                    result = plugin.get_detail(resource_type, address)
                    if result is not None:
                        return result
                except Exception:
                    continue
        
        return None
    
    def refresh(self, resource_type: str = None):
        if resource_type:
            self._cached_data.pop(resource_type, None)
        else:
            self._cached_data = {}
            self._metadata_cache = {}
        self._cache_timestamp = 0
    
    def is_cache_valid(self) -> bool:
        import time
        return self._cached_data and (time.time() - self._cache_timestamp) < self._cache_ttl
