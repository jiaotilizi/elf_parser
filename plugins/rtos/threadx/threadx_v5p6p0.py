import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Dict, List, Optional, Any
from core.plugin_manager import OSPlugin


class ThreadXV5Plugin(OSPlugin):
    def __init__(self):
        super().__init__(
            name='threadx_v5p6p0',
            version='1.0',
            os_name='threadx',
            os_version='v5p6p0',
            description='ThreadX v5p6p0 RTOS analysis plugin'
        )
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        self.elf_parser = context.get('elf_parser')
        self.dump_reader = context.get('dump_reader')
        self.profile = context.get('profile')
        return True
    
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
    
    def get_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        tasks = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return tasks
        
        thread_list_sym = elf_parser.get_symbol_by_name('_tx_thread_list')
        if not thread_list_sym:
            return tasks
        
        thread_list_addr = thread_list_sym['address']
        is_32bit = elf_parser.is_32bit()
        
        thread_ptr = dump_reader.read_pointer(thread_list_addr, is_32bit)
        if not thread_ptr:
            return tasks
        
        tx_thread_struct = elf_parser.get_struct_type('TX_THREAD')
        if not tx_thread_struct:
            return tasks
        
        thread_size = tx_thread_struct.get('byte_size', 0x200)
        
        visited = set()
        current_ptr = thread_ptr
        
        while current_ptr and current_ptr not in visited:
            visited.add(current_ptr)
            
            task_info = self._parse_thread(current_ptr, tx_thread_struct, elf_parser, dump_reader, is_32bit)
            if task_info:
                tasks.append(task_info)
            
            next_ptr = dump_reader.read_pointer(current_ptr + 4, is_32bit)
            current_ptr = next_ptr
        
        return tasks
    
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
        
        for member in thread_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            member_size = member.get('byte_size', 4)
            
            if member_name == 'tx_thread_name':
                name_addr = dump_reader.read_pointer(thread_addr + member_offset, is_32bit)
                if name_addr:
                    result['name'] = dump_reader.read_string(name_addr, 16) or ''
            
            elif member_name == 'tx_thread_state':
                result['state'] = self._get_thread_state(dump_reader.read_uint32(thread_addr + member_offset))
            
            elif member_name == 'tx_thread_priority':
                result['priority'] = dump_reader.read_uint32(thread_addr + member_offset)
            
            elif member_name == 'tx_thread_stack_start':
                result['stack_start'] = dump_reader.read_pointer(thread_addr + member_offset, is_32bit) or 0
            
            elif member_name == 'tx_thread_stack_size':
                result['stack_size'] = dump_reader.read_uint32(thread_addr + member_offset)
            
            elif member_name == 'tx_thread_stack_current':
                result['stack_current'] = dump_reader.read_pointer(thread_addr + member_offset, is_32bit) or 0
            
            elif member_name == 'tx_thread_stack_high_water':
                result['stack_high_water'] = dump_reader.read_uint32(thread_addr + member_offset)
            
            elif member_name == 'tx_thread_entry':
                result['entry_point'] = dump_reader.read_pointer(thread_addr + member_offset, is_32bit) or 0
        
        if result['stack_start'] and result['stack_size']:
            result['stack_usage'] = (result['stack_size'] - result['stack_high_water']) / result['stack_size'] * 100
        
        if result['entry_point']:
            func_info = elf_parser.find_function_by_address(result['entry_point'])
            if func_info:
                result['entry_function'] = func_info.get('name', '')
        
        return result
    
    def _get_thread_state(self, state_val: int) -> str:
        state_map = {
            0: 'READY',
            1: 'RUNNING',
            2: 'SUSPENDED',
            3: 'DELAYED',
            4: 'PENDING',
            5: 'TIMEOUT',
        }
        return state_map.get(state_val, f'UNKNOWN({state_val})')
    
    def get_semaphores(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        semaphores = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return semaphores
        
        sem_list_sym = elf_parser.get_symbol_by_name('_tx_semaphore_list')
        if not sem_list_sym:
            return semaphores
        
        sem_list_addr = sem_list_sym['address']
        is_32bit = elf_parser.is_32bit()
        
        sem_struct = elf_parser.get_struct_type('TX_SEMAPHORE')
        if not sem_struct:
            return semaphores
        
        sem_ptr = dump_reader.read_pointer(sem_list_addr, is_32bit)
        sem_size = sem_struct.get('byte_size', 0x60)
        
        visited = set()
        current_ptr = sem_ptr
        
        while current_ptr and current_ptr not in visited:
            visited.add(current_ptr)
            
            sem_info = self._parse_semaphore(current_ptr, sem_struct, dump_reader, is_32bit)
            if sem_info:
                semaphores.append(sem_info)
            
            next_ptr = dump_reader.read_pointer(current_ptr + 4, is_32bit)
            current_ptr = next_ptr
        
        return semaphores
    
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
    
    def get_mutexes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        mutexes = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return mutexes
        
        mutex_list_sym = elf_parser.get_symbol_by_name('_tx_mutex_list')
        if not mutex_list_sym:
            return mutexes
        
        mutex_list_addr = mutex_list_sym['address']
        is_32bit = elf_parser.is_32bit()
        
        mutex_struct = elf_parser.get_struct_type('TX_MUTEX')
        if not mutex_struct:
            return mutexes
        
        mutex_ptr = dump_reader.read_pointer(mutex_list_addr, is_32bit)
        mutex_size = mutex_struct.get('byte_size', 0x80)
        
        visited = set()
        current_ptr = mutex_ptr
        
        while current_ptr and current_ptr not in visited:
            visited.add(current_ptr)
            
            mutex_info = self._parse_mutex(current_ptr, mutex_struct, dump_reader, is_32bit)
            if mutex_info:
                mutexes.append(mutex_info)
            
            next_ptr = dump_reader.read_pointer(current_ptr + 4, is_32bit)
            current_ptr = next_ptr
        
        return mutexes
    
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
                result['owner'] = dump_reader.read_pointer(mutex_addr + member_offset, is_32bit) or 0
            
            elif member_name == 'tx_mutex_inherit_count':
                result['inherit_count'] = dump_reader.read_uint32(mutex_addr + member_offset)
            
            elif member_name == 'tx_mutex_suspended_count':
                result['suspended_count'] = dump_reader.read_uint32(mutex_addr + member_offset)
        
        return result
    
    def get_queues(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        queues = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return queues
        
        queue_list_sym = elf_parser.get_symbol_by_name('_tx_queue_list')
        if not queue_list_sym:
            return queues
        
        queue_list_addr = queue_list_sym['address']
        is_32bit = elf_parser.is_32bit()
        
        queue_struct = elf_parser.get_struct_type('TX_QUEUE')
        if not queue_struct:
            return queues
        
        queue_ptr = dump_reader.read_pointer(queue_list_addr, is_32bit)
        queue_size = queue_struct.get('byte_size', 0xA0)
        
        visited = set()
        current_ptr = queue_ptr
        
        while current_ptr and current_ptr not in visited:
            visited.add(current_ptr)
            
            queue_info = self._parse_queue(current_ptr, queue_struct, dump_reader, is_32bit)
            if queue_info:
                queues.append(queue_info)
            
            next_ptr = dump_reader.read_pointer(current_ptr + 4, is_32bit)
            current_ptr = next_ptr
        
        return queues
    
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
            'tasks': self.get_tasks(context),
            'semaphores': self.get_semaphores(context),
            'mutexes': self.get_mutexes(context),
            'queues': self.get_queues(context),
            'heap': self.get_heap_info(context),
        }