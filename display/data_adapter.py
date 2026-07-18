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
                {'name': 'name', 'label': 'Name', 'type': 'string'},
                {'name': 'state', 'label': 'State', 'type': 'string'},
                {'name': 'priority', 'label': 'Priority', 'type': 'number'},
                {'name': 'stack_size', 'label': 'Stack Size', 'type': 'number'},
                {'name': 'stack_used', 'label': 'Stack Used', 'type': 'number'},
            ]
        ),
        'mutexes': ResourceMetadata(
            resource_type='mutexes',
            label='Mutexes',
            icon='🔒',
            primary_key='address',
            fields=[
                {'name': 'name', 'label': 'Name', 'type': 'string'},
                {'name': 'owner', 'label': 'Owner', 'type': 'string'},
                {'name': 'priority', 'label': 'Priority', 'type': 'number'},
            ]
        ),
        'semaphores': ResourceMetadata(
            resource_type='semaphores',
            label='Semaphores',
            icon='🚦',
            primary_key='address',
            fields=[
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
                {'name': 'name', 'label': 'Name', 'type': 'string'},
                {'name': 'state', 'label': 'State', 'type': 'string'},
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
    }

    def __init__(self, plugin_manager, context: Dict[str, Any]):
        self.plugin_manager = plugin_manager
        self.context = context
        self._cached_data = {}
        self._metadata_cache = {}
    
    def _get_os_plugin(self):
        profile = self.context.get('profile', {})
        os_config = profile.get('os', {})
        os_name = os_config.get('name')
        os_version = os_config.get('version')
        
        if os_name and os_version:
            return self.plugin_manager.get_os_plugin(os_name, os_version)
        
        if os_name:
            for plugin in self.plugin_manager.os_plugins.values():
                if plugin.os_name == os_name:
                    return plugin
        
        for plugin in self.plugin_manager.os_plugins.values():
            return plugin
        return None
    
    def _get_test_point_plugin(self):
        return self.plugin_manager.module_plugins.get('test_point')
    
    def _load_all_data(self):
        if self._cached_data:
            return
        
        os_plugin = self._get_os_plugin()
        if os_plugin:
            try:
                os_data = os_plugin.execute(self.context)
                for key, value in os_data.items():
                    if isinstance(value, list):
                        self._cached_data[key] = value
            except Exception as e:
                print(f"Error getting OS data: {e}")
        
        tp_plugin = self._get_test_point_plugin()
        if tp_plugin:
            try:
                tp_data = tp_plugin.execute(self.context)
                if 'test_points' in tp_data:
                    self._cached_data['test_points'] = tp_data['test_points']
                if 'trace_buffer' in tp_data:
                    self._cached_data['trace_buffer'] = tp_data['trace_buffer']
            except Exception as e:
                print(f"Error getting test point data: {e}")
    
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
        
        os_plugin = self._get_os_plugin()
        if os_plugin and hasattr(os_plugin, 'get_metadata'):
            try:
                meta = os_plugin.get_metadata(resource_type)
                if meta:
                    self._metadata_cache[resource_type] = meta
                    return meta
            except Exception:
                pass
        
        return ResourceMetadata(
            resource_type=resource_type,
            label=resource_type.capitalize(),
        )
    
    def get_detail(self, resource_type: str, address: int) -> Optional[Dict[str, Any]]:
        os_plugin = self._get_os_plugin()
        if os_plugin and hasattr(os_plugin, 'get_detail'):
            try:
                return os_plugin.get_detail(resource_type, address)
            except Exception as e:
                print(f"Error getting detail: {e}")
        
        tp_plugin = self._get_test_point_plugin()
        if tp_plugin and hasattr(tp_plugin, 'get_detail'):
            try:
                return tp_plugin.get_detail(resource_type, address)
            except Exception as e:
                print(f"Error getting test point detail: {e}")
        
        return None
    
    def refresh(self):
        self._cached_data = {}
        self._metadata_cache = {}