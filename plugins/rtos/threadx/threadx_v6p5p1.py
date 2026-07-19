import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Dict, List, Optional, Any
from core.plugin_manager import OSPlugin


class ThreadXV6Plugin(OSPlugin):
    def __init__(self):
        super().__init__(
            name='threadx_v6p5p1',
            version='1.0',
            os_name='threadx',
            os_version='v6p5p1',
            description='ThreadX v6p5p1 RTOS analysis plugin'
        )
    
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
    
    def get_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_created_list(
            '_tx_thread_created_ptr',
            'TX_THREAD',
            'tx_thread_created_next',
            self._parse_thread,
            context
        )
    
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
            
            elif member_name == 'tx_thread_stack_current':
                result['stack_current'] = dump_reader.read_pointer_or_zero(thread_addr + member_offset, is_32bit)
            
            elif member_name == 'tx_thread_stack_high_water':
                result['stack_high_water'] = dump_reader.read_uint32(thread_addr + member_offset)
            
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
            result['stack_usage'] = (result['stack_size'] - result['stack_high_water']) / result['stack_size'] * 100
        
        if result['entry_point']:
            func_info = elf_parser.find_function_by_address(result['entry_point'])
            if func_info:
                result['entry_function'] = func_info.get('name', '')
        
        return result
    
    def get_semaphores(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
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
            
            elif member_name == 'tx_semaphore_max_count':
                result['max_count'] = dump_reader.read_uint32(sem_addr + member_offset)
            
            elif member_name == 'tx_semaphore_suspended_count':
                result['suspended_count'] = dump_reader.read_uint32(sem_addr + member_offset)
        
        return result
    
    def get_mutexes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
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
    
    def get_queues(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
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
            
            elif member_name == 'tx_queue_messages_count':
                result['enqueued_count'] = dump_reader.read_uint32(queue_addr + member_offset)
            
            elif member_name == 'tx_queue_messages_max':
                result['max_entries'] = dump_reader.read_uint32(queue_addr + member_offset)
            
            elif member_name == 'tx_queue_message_size':
                result['message_size'] = dump_reader.read_uint32(queue_addr + member_offset)
            
            elif member_name == 'tx_queue_enqueue_suspended_count':
                result['suspended_count'] = dump_reader.read_uint32(queue_addr + member_offset)
        
        return result
    
    def get_events(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
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
    
    def get_timers(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
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
    
    def get_block_pools(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
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
            
            elif member_name == 'tx_block_pool_total_blocks':
                result['total_blocks'] = dump_reader.read_uint32(pool_addr + member_offset)
            
            elif member_name == 'tx_block_pool_available':
                result['available_blocks'] = dump_reader.read_uint32(pool_addr + member_offset)
            
            elif member_name == 'tx_block_pool_block_size':
                result['block_size'] = dump_reader.read_uint32(pool_addr + member_offset)
        
        return result
    
    def get_byte_pools(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
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
            
            elif member_name == 'tx_byte_pool_total_bytes':
                result['total_bytes'] = dump_reader.read_uint32(pool_addr + member_offset)
            
            elif member_name == 'tx_byte_pool_available':
                result['available_bytes'] = dump_reader.read_uint32(pool_addr + member_offset)
            
            elif member_name == 'tx_byte_pool_fragments':
                result['fragments'] = dump_reader.read_uint32(pool_addr + member_offset)
            
            elif member_name == 'tx_byte_pool_largest_available':
                result['largest_available'] = dump_reader.read_uint32(pool_addr + member_offset)
        
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
        
        from plugins import normalize_resource_type
        resource_type = normalize_resource_type(resource_type)
        
        if resource_type == 'tasks':
            tasks = self.get_tasks(self._context)
            for task in tasks:
                if task.get('address') == address or task.get('magic') == address:
                    return task
        elif resource_type == 'mutexes':
            mutexes = self.get_mutexes(self._context)
            for mutex in mutexes:
                if mutex.get('address') == address or mutex.get('magic') == address:
                    return mutex
        elif resource_type == 'semaphores':
            semaphores = self.get_semaphores(self._context)
            for sem in semaphores:
                if sem.get('address') == address or sem.get('magic') == address:
                    return sem
        elif resource_type == 'queues':
            queues = self.get_queues(self._context)
            for queue in queues:
                if queue.get('address') == address or queue.get('magic') == address:
                    return queue
        elif resource_type == 'events':
            events = self.get_events(self._context)
            for event in events:
                if event.get('address') == address or event.get('magic') == address:
                    return event
        elif resource_type == 'timers':
            timers = self.get_timers(self._context)
            for timer in timers:
                if timer.get('address') == address or timer.get('magic') == address:
                    return timer
        elif resource_type == 'block_pools':
            pools = self.get_block_pools(self._context)
            for pool in pools:
                if pool.get('address') == address or pool.get('magic') == address:
                    return pool
        elif resource_type == 'byte_pools':
            pools = self.get_byte_pools(self._context)
            for pool in pools:
                if pool.get('address') == address or pool.get('magic') == address:
                    return pool
        
        return None
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._context = context
        return {
            'tasks': self.get_tasks(context),
            'semaphores': self.get_semaphores(context),
            'mutexes': self.get_mutexes(context),
            'queues': self.get_queues(context),
            'events': self.get_events(context),
            'timers': self.get_timers(context),
            'block_pools': self.get_block_pools(context),
            'byte_pools': self.get_byte_pools(context),
            'heap': self.get_heap_info(context),
        }
