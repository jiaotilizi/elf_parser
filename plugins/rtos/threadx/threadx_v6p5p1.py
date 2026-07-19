import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Dict, List, Optional, Any
from plugins.base import OSPlugin, normalize_resource_type


class ThreadXV6Plugin(OSPlugin):
    def __init__(self):
        super().__init__(
            name='threadx_v6p5p1',
            version='1.0',
            os_name='threadx',
            os_version='v6p5p1',
            description='ThreadX v6p5p1 RTOS analysis plugin'
        )
    
    def _walk_created_list(self, 
                          symbol_name: str, 
                          struct_name: str, 
                          next_field_name: str,
                          parse_func,
                          context: Dict[str, Any]) -> List[Dict[str, Any]]:
        import logging
        logger = logging.getLogger(__name__)
        
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            logger.warning(f"Missing elf_parser or dump_reader in context for {symbol_name}")
            return []
        
        list_sym = elf_parser.get_symbol_by_name(symbol_name)
        if not list_sym:
            logger.warning(f"Symbol not found: {symbol_name}")
            return []
        
        list_addr = list_sym['address']
        is_32bit = elf_parser.is_32bit()
        
        struct_type = elf_parser.get_struct_type(struct_name)
        if not struct_type:
            logger.warning(f"Struct type not found: {struct_name}")
            return []
        
        head_ptr = dump_reader.read_pointer(list_addr, is_32bit)
        if not head_ptr:
            return []
        
        next_offset = 0
        for member in struct_type.get('members', []):
            if member.get('name') == next_field_name:
                next_offset = member.get('offset', 0)
                break
        
        visited = set()
        current_ptr = head_ptr
        results = []
        
        while current_ptr and current_ptr not in visited:
            visited.add(current_ptr)
            
            item_info = parse_func(current_ptr, struct_type, elf_parser, dump_reader, is_32bit)
            if item_info:
                results.append(item_info)
            
            next_ptr = dump_reader.read_pointer(current_ptr + next_offset, is_32bit)
            current_ptr = next_ptr
        
        return results
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        super().initialize(context)
        return True
    
    def get_resource_types(self) -> List[str]:
        return ['tasks', 'semaphores', 'mutexes', 'queues', 'events', 'timers', 'block_pools', 'byte_pools']
    
    def get_resource(self, resource_type: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        resource_map = {
            'tasks': self._get_tasks,
            'semaphores': self._get_semaphores,
            'mutexes': self._get_mutexes,
            'queues': self._get_queues,
            'events': self._get_events,
            'timers': self._get_timers,
            'block_pools': self._get_block_pools,
            'byte_pools': self._get_byte_pools,
        }
        func = resource_map.get(resource_type)
        if func:
            return func(context)
        return []
    
    def get_required_symbols(self) -> List[str]:
        return [
            '_tx_thread_created_ptr',
            '_tx_semaphore_created_ptr',
            '_tx_mutex_created_ptr',
            '_tx_queue_created_ptr',
            '_tx_event_flags_created_ptr',
            '_tx_timer_created_ptr',
            '_tx_block_pool_created_ptr',
            '_tx_byte_pool_created_ptr',
            '_tx_heap_pool',
        ]
    
    def get_required_structs(self) -> List[str]:
        return [
            'TX_THREAD',
            'TX_SEMAPHORE',
            'TX_MUTEX',
            'TX_QUEUE',
            'TX_EVENT_FLAGS_GROUP',
            'TX_TIMER',
            'TX_BLOCK_POOL',
            'TX_BYTE_POOL',
            'TX_HEAP',
        ]
    
    def _get_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        tasks = self._walk_created_list(
            '_tx_thread_created_ptr',
            'TX_THREAD',
            'tx_thread_created_next',
            self._parse_thread,
            context
        )
        
        elf_parser = context['elf_parser']
        dump_reader = context['dump_reader']
        
        current_ptr_sym = elf_parser.get_symbol_by_name('_tx_thread_current_ptr')
        if current_ptr_sym:
            current_ptr_value = dump_reader.read_uint32(current_ptr_sym['address'])
            if current_ptr_value == 0:
                ready_list_sym = elf_parser.get_symbol_by_name('_tx_thread_priority_list')
                if ready_list_sym:
                    ready_list_addr = ready_list_sym['address']
                    for priority in range(32):
                        head_addr = ready_list_addr + priority * 4
                        head = dump_reader.read_uint32(head_addr)
                        if head != 0:
                            for task in tasks:
                                if task['address'] == head:
                                    task['state'] = 0
                                    task['state_name'] = 'TX_READY'
                                    break
                            break
        
        return tasks
    
    def _parse_thread(self, thread_addr: int, thread_struct: Dict[str, Any], 
                     elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': thread_addr,
            'magic': thread_addr,
            'name': '',
            'state': 0,
            'priority': 0,
            'run_count': 0,
            'stack_start': 0,
            'stack_size': 0,
            'stack_current': 0,
            'stack_high_water': 0,
            'current_pc': 0,
            'entry_point': 0,
            'entry_param': 0,
            'timer_remaining': 0,
            'timeout_function': 0,
            'timeout_param': 0,
            'state_name': '',
        }
        
        THREAD_STATE_MAP = {
            0: 'TX_READY',
            1: 'TX_COMPLETED',
            2: 'TX_TERMINATED',
            3: 'TX_SUSPENDED',
            4: 'TX_WAITING_FOR_MESSAGE',
            5: 'TX_WAITING_FOR_SEMAPHORE',
            6: 'TX_WAITING_FOR_MUTEX',
            7: 'TX_WAITING_FOR_EVENT',
            8: 'TX_WAITING_FOR_BLOCK',
            9: 'TX_WAITING_FOR_BYTE',
            10: 'TX_WAITING_FOR_TIME',
            11: 'TX_WAITING_FOR_MEMORY',
            12: 'TX_DELAY',
            13: 'TX_QUEUE_SUSPENDED',
        }
        
        for member in thread_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'tx_thread_name':
                name_addr = dump_reader.read_pointer(thread_addr + member_offset, is_32bit)
                if name_addr:
                    name = dump_reader.read_string(name_addr, 32)
                    if not name:
                        elf_data = elf_parser.read_memory_from_elf(name_addr, 32)
                        if elf_data:
                            null_pos = elf_data.find(b'\x00')
                            if null_pos >= 0:
                                elf_data = elf_data[:null_pos]
                            try:
                                name = elf_data.decode('utf-8')
                            except UnicodeDecodeError:
                                name = elf_data.decode('latin-1')
                    result['name'] = name or ''
            
            elif member_name == 'tx_thread_state':
                result['state'] = dump_reader.read_uint32(thread_addr + member_offset)
                result['state_name'] = THREAD_STATE_MAP.get(result['state'], f'UNKNOWN({result["state"]})')
            
            elif member_name == 'tx_thread_priority':
                result['priority'] = dump_reader.read_uint32(thread_addr + member_offset)
            
            elif member_name == 'tx_thread_run_count':
                result['run_count'] = dump_reader.read_uint32(thread_addr + member_offset)
            
            elif member_name == 'tx_thread_stack_start':
                result['stack_start'] = dump_reader.read_pointer_or_zero(thread_addr + member_offset, is_32bit)
            
            elif member_name == 'tx_thread_stack_size':
                result['stack_size'] = dump_reader.read_uint32(thread_addr + member_offset)
            
            elif member_name == 'tx_thread_stack_ptr':
                result['stack_current'] = dump_reader.read_pointer_or_zero(thread_addr + member_offset, is_32bit)
            
            elif member_name == 'tx_thread_stack_highest_ptr':
                result['stack_highest_ptr'] = dump_reader.read_pointer_or_zero(thread_addr + member_offset, is_32bit)
            
            elif member_name == 'tx_thread_entry':
                result['entry_point'] = dump_reader.read_pointer_or_zero(thread_addr + member_offset, is_32bit)
            
            elif member_name == 'tx_thread_entry_parameter':
                result['entry_param'] = dump_reader.read_pointer_or_zero(thread_addr + member_offset, is_32bit)
            
            elif member_name == 'tx_thread_time_slice':
                result['timer_remaining'] = dump_reader.read_uint32(thread_addr + member_offset)
            
            elif member_name == 'tx_thread_timeout_function':
                result['timeout_function'] = dump_reader.read_pointer_or_zero(thread_addr + member_offset, is_32bit)
            
            elif member_name == 'tx_thread_timeout_parameter':
                result['timeout_param'] = dump_reader.read_pointer_or_zero(thread_addr + member_offset, is_32bit)
        
        if result['stack_start'] and result['stack_size']:
            if result['stack_highest_ptr'] and result['stack_highest_ptr'] != 0:
                result['stack_usage'] = (result['stack_highest_ptr'] - result['stack_start']) / result['stack_size'] * 100
            elif result['stack_current']:
                result['stack_usage'] = (result['stack_current'] - result['stack_start']) / result['stack_size'] * 100
            else:
                result['stack_usage'] = 0.0
        
        if result['entry_point']:
            func_info = elf_parser.find_function_by_address(result['entry_point'])
            if func_info:
                result['entry_function'] = func_info.get('name', '')
        
        return result
    
    def _get_semaphores(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_created_list(
            '_tx_semaphore_created_ptr',
            'TX_SEMAPHORE',
            'tx_semaphore_created_next',
            self._parse_semaphore,
            context
        )
    
    def _parse_semaphore(self, sem_addr: int, sem_struct: Dict[str, Any], 
                        elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': sem_addr,
            'magic': sem_addr,
            'name': '',
            'count': 0,
            'max_count': 0,
            'suspended_count': 0,
        }
        
        for member in sem_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'tx_semaphore_name':
                name_addr = dump_reader.read_pointer(sem_addr + member_offset, is_32bit)
                if name_addr:
                    name = dump_reader.read_string(name_addr, 32)
                    if not name:
                        elf_data = elf_parser.read_memory_from_elf(name_addr, 32)
                        if elf_data:
                            null_pos = elf_data.find(b'\x00')
                            if null_pos >= 0:
                                elf_data = elf_data[:null_pos]
                            try:
                                name = elf_data.decode('utf-8')
                            except UnicodeDecodeError:
                                name = elf_data.decode('latin-1')
                    result['name'] = name or ''
            
            elif member_name == 'tx_semaphore_count':
                result['count'] = dump_reader.read_uint32(sem_addr + member_offset)
                result['max_count'] = 0
            
            elif member_name == 'tx_semaphore_suspended_count':
                result['suspended_count'] = dump_reader.read_uint32(sem_addr + member_offset)
        
        return result
    
    def _get_mutexes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_created_list(
            '_tx_mutex_created_ptr',
            'TX_MUTEX',
            'tx_mutex_created_next',
            self._parse_mutex,
            context
        )
    
    def _parse_mutex(self, mutex_addr: int, mutex_struct: Dict[str, Any], 
                    elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': mutex_addr,
            'magic': mutex_addr,
            'name': '',
            'owner': 0,
            'owner_info': None,
            'inherit_count': 0,
            'priority': 0,
            'suspended_count': 0,
        }
        
        for member in mutex_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'tx_mutex_name':
                name_addr = dump_reader.read_pointer(mutex_addr + member_offset, is_32bit)
                if name_addr:
                    name = dump_reader.read_string(name_addr, 32)
                    if not name:
                        elf_data = elf_parser.read_memory_from_elf(name_addr, 32)
                        if elf_data:
                            null_pos = elf_data.find(b'\x00')
                            if null_pos >= 0:
                                elf_data = elf_data[:null_pos]
                            try:
                                name = elf_data.decode('utf-8')
                            except UnicodeDecodeError:
                                name = elf_data.decode('latin-1')
                    result['name'] = name or ''
            
            elif member_name == 'tx_mutex_owner':
                result['owner'] = dump_reader.read_pointer_or_zero(mutex_addr + member_offset, is_32bit)
            
            elif member_name == 'tx_mutex_inherit_count':
                result['inherit_count'] = dump_reader.read_uint32(mutex_addr + member_offset)
            
            elif member_name == 'tx_mutex_priority':
                result['priority'] = dump_reader.read_uint32(mutex_addr + member_offset)
            
            elif member_name == 'tx_mutex_suspended_count':
                result['suspended_count'] = dump_reader.read_uint32(mutex_addr + member_offset)
        
        if result['owner'] != 0 and elf_parser:
            thread_struct = elf_parser.get_struct_type('TX_THREAD')
            if thread_struct:
                owner_info = self._parse_thread(result['owner'], thread_struct, elf_parser, dump_reader, is_32bit)
                if owner_info:
                    result['owner_info'] = {
                        'address': owner_info['address'],
                        'name': owner_info['name'],
                    }
        
        return result
    
    def _get_queues(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_created_list(
            '_tx_queue_created_ptr',
            'TX_QUEUE',
            'tx_queue_created_next',
            self._parse_queue,
            context
        )
    
    def _parse_queue(self, queue_addr: int, queue_struct: Dict[str, Any], 
                    elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': queue_addr,
            'magic': queue_addr,
            'name': '',
            'max_entries': 0,
            'enqueued_count': 0,
            'message_size': 0,
            'suspended_count': 0,
        }
        
        for member in queue_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'tx_queue_name':
                name_addr = dump_reader.read_pointer(queue_addr + member_offset, is_32bit)
                if name_addr:
                    name = dump_reader.read_string(name_addr, 32)
                    if not name:
                        elf_data = elf_parser.read_memory_from_elf(name_addr, 32)
                        if elf_data:
                            null_pos = elf_data.find(b'\x00')
                            if null_pos >= 0:
                                elf_data = elf_data[:null_pos]
                            try:
                                name = elf_data.decode('utf-8')
                            except UnicodeDecodeError:
                                name = elf_data.decode('latin-1')
                    result['name'] = name or ''
            
            elif member_name == 'tx_queue_enqueued':
                result['enqueued_count'] = dump_reader.read_uint32(queue_addr + member_offset)
            
            elif member_name == 'tx_queue_capacity':
                result['max_entries'] = dump_reader.read_uint32(queue_addr + member_offset)
            
            elif member_name == 'tx_queue_message_size':
                result['message_size'] = dump_reader.read_uint32(queue_addr + member_offset)
            
            elif member_name == 'tx_queue_suspended_count':
                result['suspended_count'] = dump_reader.read_uint32(queue_addr + member_offset)
        
        return result
    
    def _get_events(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_created_list(
            '_tx_event_flags_created_ptr',
            'TX_EVENT_FLAGS_GROUP',
            'tx_event_flags_group_created_next',
            self._parse_event,
            context
        )
    
    def _parse_event(self, event_addr: int, event_struct: Dict[str, Any], 
                    elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': event_addr,
            'magic': event_addr,
            'name': '',
            'flags': 0,
            'suspended_count': 0,
        }
        
        for member in event_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'tx_event_flags_group_name':
                name_addr = dump_reader.read_pointer(event_addr + member_offset, is_32bit)
                if name_addr:
                    name = dump_reader.read_string(name_addr, 32)
                    if not name:
                        elf_data = elf_parser.read_memory_from_elf(name_addr, 32)
                        if elf_data:
                            null_pos = elf_data.find(b'\x00')
                            if null_pos >= 0:
                                elf_data = elf_data[:null_pos]
                            try:
                                name = elf_data.decode('utf-8')
                            except UnicodeDecodeError:
                                name = elf_data.decode('latin-1')
                    result['name'] = name or ''
            
            elif member_name == 'tx_event_flags_group_flags':
                result['flags'] = dump_reader.read_uint32(event_addr + member_offset)
            
            elif member_name == 'tx_event_flags_group_suspended_count':
                result['suspended_count'] = dump_reader.read_uint32(event_addr + member_offset)
        
        return result
    
    def _get_timers(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_created_list(
            '_tx_timer_created_ptr',
            'TX_TIMER',
            'tx_timer_created_next',
            self._parse_timer,
            context
        )
    
    def _parse_timer(self, timer_addr: int, timer_struct: Dict[str, Any], 
                    elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': timer_addr,
            'magic': timer_addr,
            'name': '',
            'active': False,
            'period_ticks': 0,
            'ticks_remaining': 0,
            'expiration_function': 0,
            'expiration_param': 0,
        }
        
        internal_ptr = 0
        
        for member in timer_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'tx_timer_name':
                name_addr = dump_reader.read_pointer(timer_addr + member_offset, is_32bit)
                if name_addr:
                    name = dump_reader.read_string(name_addr, 32)
                    if not name:
                        elf_data = elf_parser.read_memory_from_elf(name_addr, 32)
                        if elf_data:
                            null_pos = elf_data.find(b'\x00')
                            if null_pos >= 0:
                                elf_data = elf_data[:null_pos]
                            try:
                                name = elf_data.decode('utf-8')
                            except UnicodeDecodeError:
                                name = elf_data.decode('latin-1')
                    result['name'] = name or ''
            
            elif member_name == 'tx_timer_internal':
                internal_ptr = timer_addr + member_offset
        
        if internal_ptr:
            result['ticks_remaining'] = dump_reader.read_uint32(internal_ptr + 0) or 0
            result['period_ticks'] = dump_reader.read_uint32(internal_ptr + 4) or 0
            result['expiration_function'] = dump_reader.read_pointer_or_zero(internal_ptr + 8, is_32bit)
            result['expiration_param'] = dump_reader.read_uint32(internal_ptr + 12) or 0
            
            active_next = dump_reader.read_pointer(internal_ptr + 16, is_32bit)
            result['active'] = active_next != 0 and active_next is not None
        
        if result['expiration_function']:
            func_info = elf_parser.find_function_by_address(result['expiration_function'])
            if func_info:
                result['expiration_function_name'] = func_info.get('name', '')
        
        return result
    
    def _get_block_pools(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_created_list(
            '_tx_block_pool_created_ptr',
            'TX_BLOCK_POOL',
            'tx_block_pool_created_next',
            self._parse_block_pool,
            context
        )
    
    def _parse_block_pool(self, pool_addr: int, pool_struct: Dict[str, Any], 
                         elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': pool_addr,
            'magic': pool_addr,
            'name': '',
            'total_blocks': 0,
            'available_blocks': 0,
            'block_size': 0,
        }
        
        for member in pool_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'tx_block_pool_name':
                name_addr = dump_reader.read_pointer(pool_addr + member_offset, is_32bit)
                if name_addr:
                    name = dump_reader.read_string(name_addr, 32)
                    if not name:
                        elf_data = elf_parser.read_memory_from_elf(name_addr, 32)
                        if elf_data:
                            null_pos = elf_data.find(b'\x00')
                            if null_pos >= 0:
                                elf_data = elf_data[:null_pos]
                            try:
                                name = elf_data.decode('utf-8')
                            except UnicodeDecodeError:
                                name = elf_data.decode('latin-1')
                    result['name'] = name or ''
            
            elif member_name == 'tx_block_pool_total':
                result['total_blocks'] = dump_reader.read_uint32(pool_addr + member_offset)
            
            elif member_name == 'tx_block_pool_available':
                result['available_blocks'] = dump_reader.read_uint32(pool_addr + member_offset)
            
            elif member_name == 'tx_block_pool_block_size':
                result['block_size'] = dump_reader.read_uint32(pool_addr + member_offset)
        
        return result
    
    def _get_byte_pools(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_created_list(
            '_tx_byte_pool_created_ptr',
            'TX_BYTE_POOL',
            'tx_byte_pool_created_next',
            self._parse_byte_pool,
            context
        )
    
    def _parse_byte_pool(self, pool_addr: int, pool_struct: Dict[str, Any], 
                        elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': pool_addr,
            'magic': pool_addr,
            'name': '',
            'total_bytes': 0,
            'available_bytes': 0,
            'fragments': 0,
            'largest_available': 0,
        }
        
        for member in pool_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'tx_byte_pool_name':
                name_addr = dump_reader.read_pointer(pool_addr + member_offset, is_32bit)
                if name_addr:
                    name = dump_reader.read_string(name_addr, 32)
                    if not name:
                        elf_data = elf_parser.read_memory_from_elf(name_addr, 32)
                        if elf_data:
                            null_pos = elf_data.find(b'\x00')
                            if null_pos >= 0:
                                elf_data = elf_data[:null_pos]
                            try:
                                name = elf_data.decode('utf-8')
                            except UnicodeDecodeError:
                                name = elf_data.decode('latin-1')
                    result['name'] = name or ''
            
            elif member_name == 'tx_byte_pool_size':
                result['total_bytes'] = dump_reader.read_uint32(pool_addr + member_offset)
            
            elif member_name == 'tx_byte_pool_available':
                result['available_bytes'] = dump_reader.read_uint32(pool_addr + member_offset)
            
            elif member_name == 'tx_byte_pool_fragments':
                result['fragments'] = dump_reader.read_uint32(pool_addr + member_offset)
        
        if result['total_bytes'] > 0:
            result['usage_percent'] = (result['total_bytes'] - result['available_bytes']) / result['total_bytes'] * 100
        
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
            'magic': heap_pool_addr,
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
    
    def get_detail(self, resource_type: str, address: int) -> Optional[Dict[str, Any]]:
        if not self._context:
            return None
        
        resource_type = normalize_resource_type(resource_type)
        resources = self.get_resource(resource_type, self._context)
        
        for resource in resources:
            if resource.get('address') == address or resource.get('magic') == address:
                return resource
        
        return None
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._context = context
        return {
            'tasks': self.get_resource('tasks', context),
            'semaphores': self.get_resource('semaphores', context),
            'mutexes': self.get_resource('mutexes', context),
            'queues': self.get_resource('queues', context),
            'events': self.get_resource('events', context),
            'timers': self.get_resource('timers', context),
            'block_pools': self.get_resource('block_pools', context),
            'byte_pools': self.get_resource('byte_pools', context),
            'heap': self.get_heap_info(context),
        }
