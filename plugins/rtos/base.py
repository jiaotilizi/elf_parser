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
import logging
from enum import Enum
from typing import Dict, List, Optional, Any

from plugins.base import Plugin

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


class RTOSPlugin(Plugin):
    def __init__(self, name: str, version: str, os_name: str, os_version: str, description: str = ""):
        super().__init__(name, version, description)
        self.os_name = os_name
        self.os_version = os_version
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        self._elf_parser = context.get('elf_parser')
        self._dump_reader = context.get('dump_reader')
        self._profile = context.get('profile')
        self._context = context
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