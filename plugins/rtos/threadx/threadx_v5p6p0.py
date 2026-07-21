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
import struct
from typing import Dict, List, Optional, Any

from ..base import RTOSPlugin

logger = logging.getLogger(__name__)


class ThreadXV5Plugin(RTOSPlugin):
    def __init__(self):
        super().__init__(
            name='threadx_v5p6p0',
            version='1.0',
            os_name='threadx',
            os_version='v5p6p0',
            description='ThreadX v5p6p0 RTOS analysis plugin'
        )
    
    def get_resource_types(self) -> List[str]:
        return ['tasks', 'semaphores', 'mutexes', 'queues']
    
    def get_resource(self, resource_type: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        resource_map = {
            'tasks': self._get_tasks,
            'semaphores': self._get_semaphores,
            'mutexes': self._get_mutexes,
            'queues': self._get_queues,
        }
        func = resource_map.get(resource_type)
        if func:
            return func(context)
        return []
    
    def get_required_symbols(self) -> List[str]:
        return [
            '_tx_thread_list',
            '_tx_semaphore_list',
            '_tx_mutex_list',
            '_tx_queue_list',
            '_tx_heap_pool',
        ]
    
    def get_required_structs(self) -> List[str]:
        return [
            'TX_THREAD',
            'TX_SEMAPHORE',
            'TX_MUTEX',
            'TX_QUEUE',
            'TX_HEAP',
        ]
    
    def _get_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_singly_linked_list(
            '_tx_thread_list',
            'TX_THREAD',
            'tx_thread_created_next',
            self._parse_thread,
            context
        )
    
    def _parse_thread(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': accessor.address,
            'name': accessor.get_string('tx_thread_name'),
            'state': '',
            'priority': accessor.get_int('tx_thread_priority'),
            'stack_start': accessor.get_ptr('tx_thread_stack_start'),
            'stack_size': accessor.get_int('tx_thread_stack_size'),
            'stack_current': accessor.get_ptr('tx_thread_stack_current'),
            'stack_high_water': accessor.get_int('tx_thread_stack_high_water'),
            'current_pc': 0,
            'entry_point': accessor.get_ptr('tx_thread_entry'),
        }
        
        THREAD_STATE_MAP = {
            0: 'READY',
            1: 'RUNNING', 
            2: 'SUSPENDED',
            3: 'DELAYED',
            4: 'PENDING',
            5: 'TIMEOUT',
        }
        
        result['state'] = accessor.get_enum_name('tx_thread_state', fallback_map=THREAD_STATE_MAP)
        
        if result['stack_start'] and result['stack_size']:
            used = result['stack_size'] - result['stack_high_water']
            result['stack_usage'] = used / result['stack_size'] * 100
        
        if result['entry_point']:
            func_info = elf_parser.find_function_by_address(result['entry_point'])
            if func_info:
                result['entry_function'] = func_info.get('name', '')
        
        return result
    
    def _get_semaphores(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_singly_linked_list(
            '_tx_semaphore_list',
            'TX_SEMAPHORE',
            'tx_semaphore_created_next',
            self._parse_semaphore,
            context
        )
    
    def _parse_semaphore(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        return {
            'address': accessor.address,
            'name': accessor.get_string('tx_semaphore_name'),
            'count': accessor.get_int('tx_semaphore_count'),
            'max_count': accessor.get_int('tx_semaphore_max_count'),
            'first_suspended': 0,
            'suspended_count': accessor.get_int('tx_semaphore_suspended_count'),
        }
    
    def _get_mutexes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_singly_linked_list(
            '_tx_mutex_list',
            'TX_MUTEX',
            'tx_mutex_created_next',
            self._parse_mutex,
            context
        )
    
    def _parse_mutex(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        owner = accessor.get_ptr('tx_mutex_owner')
        result = {
            'address': accessor.address,
            'name': accessor.get_string('tx_mutex_name'),
            'owner': owner,
            'owner_info': None,
            'priority': 0,
            'inherit_count': accessor.get_int('tx_mutex_inherit_count'),
            'first_suspended': 0,
            'suspended_count': accessor.get_int('tx_mutex_suspended_count'),
        }
        
        if owner != 0 and elf_parser:
            try:
                thread_struct = elf_parser.get_struct_type('TX_THREAD')
                if thread_struct:
                    thread_view = elf_parser.read_struct_as_node(thread_struct, owner, dump_reader)
                    if thread_view:
                        from core.elf_parser.struct_accessor import StructAccessor
                        owner_accessor = StructAccessor(thread_view, dump_reader, elf_parser)
                        owner_name = owner_accessor.get_string('tx_thread_name')
                        if owner_name:
                            result['owner_info'] = {
                                'address': owner,
                                'name': owner_name.split('\x00')[0].strip(),
                            }
            except Exception:
                pass
        
        return result
    
    def _get_queues(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_singly_linked_list(
            '_tx_queue_list',
            'TX_QUEUE',
            'tx_queue_created_next',
            self._parse_queue,
            context
        )
    
    def _parse_queue(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        return {
            'address': accessor.address,
            'name': accessor.get_string('tx_queue_name'),
            'messages_count': accessor.get_int('tx_queue_messages_count'),
            'messages_max': accessor.get_int('tx_queue_messages_max'),
            'message_size': accessor.get_int('tx_queue_message_size'),
            'enqueue_suspended_count': accessor.get_int('tx_queue_enqueue_suspended_count'),
            'dequeue_suspended_count': accessor.get_int('tx_queue_dequeue_suspended_count'),
        }
    
    def get_heap_info(self, context: Dict[str, Any]) -> Dict[str, Any]:
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return {}
        
        heap_pool_sym = elf_parser.get_symbol_by_name('_tx_heap_pool')
        if not heap_pool_sym:
            return {}
        
        heap_pool_addr = heap_pool_sym['address']
        
        heap_struct = elf_parser.get_struct_type('TX_HEAP')
        if not heap_struct:
            return {}
        
        from core.elf_parser.struct_accessor import StructAccessor
        
        view_node = elf_parser.read_struct_as_node(heap_struct, heap_pool_addr, dump_reader)
        if not view_node:
            return {}
        
        accessor = StructAccessor(view_node, dump_reader, elf_parser)
        
        heap_info = {
            'address': heap_pool_addr,
            'total_bytes': accessor.get_int('tx_heap_total_bytes'),
            'available_bytes': accessor.get_int('tx_heap_available_bytes'),
            'fragments': accessor.get_int('tx_heap_fragments'),
            'largest_available': accessor.get_int('tx_heap_largest_available'),
        }
        
        if heap_info['total_bytes'] > 0:
            heap_info['usage_percent'] = (heap_info['total_bytes'] - heap_info['available_bytes']) / heap_info['total_bytes'] * 100
        
        return heap_info
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'tasks': self.get_resource('tasks', context),
            'semaphores': self.get_resource('semaphores', context),
            'mutexes': self.get_resource('mutexes', context),
            'queues': self.get_resource('queues', context),
            'heap': self.get_heap_info(context),
        }
