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
    
    def _parse_thread(self, thread_addr: int, thread_struct: Dict[str, Any], 
                     elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': thread_addr,
            'name': '',
            'state': '',
            'priority': 0,
            'stack_start': 0,
            'stack_size': 0,
            'stack_current': 0,
            'stack_high_water': 0,
            'current_pc': 0,
            'entry_point': 0,
        }
        
        THREAD_STATE_MAP = {
            0: 'READY',
            1: 'RUNNING',
            2: 'SUSPENDED',
            3: 'DELAYED',
            4: 'PENDING',
            5: 'TIMEOUT',
        }
        
        for member in thread_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            member_size = member.get('byte_size', 4)
            
            if member_name == 'tx_thread_name':
                name_addr = dump_reader.read_pointer(thread_addr + member_offset, is_32bit)
                if name_addr:
                    result['name'] = dump_reader.read_string(name_addr, 16) or ''
            
            elif member_name == 'tx_thread_state':
                result['state'] = self._normalize_task_state(dump_reader.read_uint32(thread_addr + member_offset), THREAD_STATE_MAP)
            
            elif member_name == 'tx_thread_priority':
                result['priority'] = dump_reader.read_uint32(thread_addr + member_offset)
            
            elif member_name == 'tx_thread_stack_start':
                result['stack_start'] = dump_reader.read_pointer_or_zero(thread_addr + member_offset, is_32bit)
            
            elif member_name == 'tx_thread_stack_size':
                result['stack_size'] = dump_reader.read_uint32(thread_addr + member_offset)
            
            elif member_name == 'tx_thread_stack_current':
                result['stack_current'] = dump_reader.read_pointer_or_zero(thread_addr + member_offset, is_32bit)
            
            elif member_name == 'tx_thread_stack_high_water':
                result['stack_high_water'] = dump_reader.read_uint32(thread_addr + member_offset)
            
            elif member_name == 'tx_thread_entry':
                result['entry_point'] = dump_reader.read_pointer_or_zero(thread_addr + member_offset, is_32bit)
        
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
    
    def _parse_semaphore(self, sem_addr: int, sem_struct: Dict[str, Any], 
                        dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': sem_addr,
            'name': '',
            'count': 0,
            'max_count': 0,
            'first_suspended': 0,
            'suspended_count': 0,
        }
        
        for member in sem_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'tx_semaphore_name':
                name_addr = dump_reader.read_pointer(sem_addr + member_offset, is_32bit)
                if name_addr:
                    result['name'] = dump_reader.read_string(name_addr, 16) or ''
            
            elif member_name == 'tx_semaphore_count':
                result['count'] = dump_reader.read_uint32(sem_addr + member_offset)
            
            elif member_name == 'tx_semaphore_max_count':
                result['max_count'] = dump_reader.read_uint32(sem_addr + member_offset)
            
            elif member_name == 'tx_semaphore_suspended_count':
                result['suspended_count'] = dump_reader.read_uint32(sem_addr + member_offset)
        
        return result
    
    def _get_mutexes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_singly_linked_list(
            '_tx_mutex_list',
            'TX_MUTEX',
            'tx_mutex_created_next',
            self._parse_mutex,
            context
        )
    
    def _parse_mutex(self, mutex_addr: int, mutex_struct: Dict[str, Any], 
                    dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': mutex_addr,
            'name': '',
            'owner': 0,
            'priority': 0,
            'inherit_count': 0,
            'first_suspended': 0,
            'suspended_count': 0,
        }
        
        for member in mutex_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'tx_mutex_name':
                name_addr = dump_reader.read_pointer(mutex_addr + member_offset, is_32bit)
                if name_addr:
                    result['name'] = dump_reader.read_string(name_addr, 16) or ''
            
            elif member_name == 'tx_mutex_owner':
                result['owner'] = dump_reader.read_pointer_or_zero(mutex_addr + member_offset, is_32bit)
            
            elif member_name == 'tx_mutex_inherit_count':
                result['inherit_count'] = dump_reader.read_uint32(mutex_addr + member_offset)
            
            elif member_name == 'tx_mutex_suspended_count':
                result['suspended_count'] = dump_reader.read_uint32(mutex_addr + member_offset)
        
        return result
    
    def _get_queues(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_singly_linked_list(
            '_tx_queue_list',
            'TX_QUEUE',
            'tx_queue_created_next',
            self._parse_queue,
            context
        )
    
    def _parse_queue(self, queue_addr: int, queue_struct: Dict[str, Any], 
                    dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': queue_addr,
            'name': '',
            'messages_count': 0,
            'messages_max': 0,
            'message_size': 0,
            'enqueue_suspended_count': 0,
            'dequeue_suspended_count': 0,
        }
        
        for member in queue_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'tx_queue_name':
                name_addr = dump_reader.read_pointer(queue_addr + member_offset, is_32bit)
                if name_addr:
                    result['name'] = dump_reader.read_string(name_addr, 16) or ''
            
            elif member_name == 'tx_queue_messages_count':
                result['messages_count'] = dump_reader.read_uint32(queue_addr + member_offset)
            
            elif member_name == 'tx_queue_messages_max':
                result['messages_max'] = dump_reader.read_uint32(queue_addr + member_offset)
            
            elif member_name == 'tx_queue_message_size':
                result['message_size'] = dump_reader.read_uint32(queue_addr + member_offset)
            
            elif member_name == 'tx_queue_enqueue_suspended_count':
                result['enqueue_suspended_count'] = dump_reader.read_uint32(queue_addr + member_offset)
            
            elif member_name == 'tx_queue_dequeue_suspended_count':
                result['dequeue_suspended_count'] = dump_reader.read_uint32(queue_addr + member_offset)
        
        return result
    
    def get_heap_info(self, context: Dict[str, Any]) -> Dict[str, Any]:
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return {}
        
        heap_pool_sym = elf_parser.get_symbol_by_name('_tx_heap_pool')
        if not heap_pool_sym:
            return {}
        
        heap_pool_addr = heap_pool_sym['address']
        is_32bit = elf_parser.is_32bit()
        
        heap_struct = elf_parser.get_struct_type('TX_HEAP')
        if not heap_struct:
            return {}
        
        heap_info = {
            'address': heap_pool_addr,
            'total_bytes': 0,
            'available_bytes': 0,
            'fragments': 0,
            'largest_available': 0,
        }
        
        for member in heap_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'tx_heap_total_bytes':
                heap_info['total_bytes'] = dump_reader.read_uint32(heap_pool_addr + member_offset)
            
            elif member_name == 'tx_heap_available_bytes':
                heap_info['available_bytes'] = dump_reader.read_uint32(heap_pool_addr + member_offset)
            
            elif member_name == 'tx_heap_fragments':
                heap_info['fragments'] = dump_reader.read_uint32(heap_pool_addr + member_offset)
            
            elif member_name == 'tx_heap_largest_available':
                heap_info['largest_available'] = dump_reader.read_uint32(heap_pool_addr + member_offset)
        
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
