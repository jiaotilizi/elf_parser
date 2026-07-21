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
from typing import Dict, List, Any, Optional
from .base import ResourceMetadata


class DataAdapter:
    DEFAULT_METADATA = {
        'tasks': ResourceMetadata(
            resource_type='tasks',
            label='Tasks',
            icon='[Tasks]',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'state_name', 'label': 'State', 'type': 'string'},
                {'name': 'priority', 'label': 'Priority', 'type': 'number'},
                {'name': 'schedule_ratio', 'label': 'Sched %', 'type': 'number'},
                {'name': 'stack_size', 'label': 'Stack Sz', 'type': 'number'},
                {'name': 'stack_usage', 'label': 'Stack Used', 'type': 'number'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
            ]
        ),
        'mutexes': ResourceMetadata(
            resource_type='mutexes',
            label='Mutexes',
            icon='[Mutexes]',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'owner_info.name', 'label': 'Owner', 'type': 'string'},
                {'name': 'priority', 'label': 'Priority', 'type': 'number'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
            ]
        ),
        'semaphores': ResourceMetadata(
            resource_type='semaphores',
            label='Semaphores',
            icon='[Semaphores]',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'count', 'label': 'Count', 'type': 'number'},
                {'name': 'max_count', 'label': 'Max', 'type': 'number'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
            ]
        ),
        'queues': ResourceMetadata(
            resource_type='queues',
            label='Queues',
            icon='[Queues]',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'messages', 'label': 'Messages', 'type': 'number'},
                {'name': 'max_messages', 'label': 'Max', 'type': 'number'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
            ]
        ),
        'events': ResourceMetadata(
            resource_type='events',
            label='Event Flags',
            icon='[Events]',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'flags', 'label': 'Flags', 'type': 'hex'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
            ]
        ),
        'timers': ResourceMetadata(
            resource_type='timers',
            label='Timers',
            icon='[Timers]',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'state_name', 'label': 'State', 'type': 'string'},
                {'name': 'period_ticks', 'label': 'Period', 'type': 'number'},
                {'name': 'ticks_remaining', 'label': 'Remaining', 'type': 'number'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
            ]
        ),
        'block_pools': ResourceMetadata(
            resource_type='block_pools',
            label='Block Pools',
            icon='[BlockPools]',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'available_blocks', 'label': 'Available', 'type': 'number'},
                {'name': 'total_blocks', 'label': 'Total', 'type': 'number'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
            ]
        ),
        'byte_pools': ResourceMetadata(
            resource_type='byte_pools',
            label='Byte Pools',
            icon='[BytePools]',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'available_bytes', 'label': 'Available', 'type': 'number'},
                {'name': 'total_bytes', 'label': 'Total', 'type': 'number'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
            ]
        ),
        'test_points': ResourceMetadata(
            resource_type='test_points',
            label='Test Points',
            icon='[TestPoints]',
            primary_key='id',
            fields=[
                {'name': 'id', 'label': 'ID', 'type': 'number'},
                {'name': 'value', 'label': 'Value', 'type': 'string'},
                {'name': 'timestamp', 'label': 'Time', 'type': 'string'},
                {'name': 'name', 'label': 'Name', 'type': 'string'},
            ]
        ),
        'assert_info': ResourceMetadata(
            resource_type='assert_info',
            label='Assert Info',
            icon='[Assert]',
            primary_key='address',
            fields=[
                {'name': 'address', 'label': 'Address', 'type': 'hex'},
                {'name': 'assert_id', 'label': 'Assert ID', 'type': 'number'},
                {'name': 'file_name', 'label': 'File', 'type': 'string'},
                {'name': 'line_number', 'label': 'Line', 'type': 'number'},
            ]
        ),
        'stack': ResourceMetadata(
            resource_type='stack',
            label='Stack',
            icon='[Stack]',
            primary_key='address',
            fields=[
                {'name': 'name', 'label': 'Name', 'type': 'string'},
                {'name': 'stack_start', 'label': 'Low', 'type': 'hex'},
                {'name': 'stack_end', 'label': 'High', 'type': 'hex'},
                {'name': 'stack_current', 'label': 'SP', 'type': 'hex'},
                {'name': 'stack_usage', 'label': 'Usage %', 'type': 'number'},
            ]
        ),
        'trace_buffer': ResourceMetadata(
            resource_type='trace_buffer',
            label='Trace Buffer',
            icon='[Trace]',
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
        
        plugins = self.context.get('plugins', [])
        for plugin in plugins:
            if hasattr(plugin, 'get_resource_metadata'):
                metadata = plugin.get_resource_metadata(resource_type)
                if metadata is not None:
                    self._metadata_cache[resource_type] = metadata
                    return metadata
        
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
