import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Dict, List, Optional, Any
from plugins.rtos.base import RTOSPlugin


class FreeRTOSV11Plugin(RTOSPlugin):
    def __init__(self):
        super().__init__(
            name='freertos_v11p3p0',
            version='1.0',
            os_name='freertos',
            os_version='v11p3p0',
            description='FreeRTOS v11p3p0 analysis plugin'
        )
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        self.elf_parser = context.get('elf_parser')
        self.dump_reader = context.get('dump_reader')
        self.profile = context.get('profile')
        return True
    
    def get_required_symbols(self) -> List[str]:
        return [
            'pxCurrentTCB',
            'pxReadyTasksLists',
            'xSuspendedTaskList',
            'xDelayedTaskList1',
            'xDelayedTaskList2',
            'xSemaphoreRegistry',
            'xQueueRegistry',
        ]
    
    def get_required_structs(self) -> List[str]:
        return [
            'TCB_t',
            'QueueDefinition',
            'SemaphoreData_t',
            'StaticSemaphore_t',
        ]
    
    def get_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        tasks = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return tasks
        
        is_32bit = elf_parser.is_32bit()
        
        ready_lists_sym = elf_parser.get_symbol_by_name('pxReadyTasksLists')
        if not ready_lists_sym:
            return tasks
        
        ready_lists_addr = ready_lists_sym['address']
        max_priority = 8
        
        list_struct = elf_parser.get_struct_type('List_t')
        list_size = list_struct.get('byte_size', 20) if list_struct else 20
        
        for priority in range(max_priority):
            list_addr = ready_lists_addr + priority * list_size
            tasks.extend(self._parse_task_list(list_addr, elf_parser, dump_reader, is_32bit))
        
        suspended_list_sym = elf_parser.get_symbol_by_name('xSuspendedTaskList')
        if suspended_list_sym:
            tasks.extend(self._parse_task_list(suspended_list_sym['address'], elf_parser, dump_reader, is_32bit))
        
        delayed_list1_sym = elf_parser.get_symbol_by_name('xDelayedTaskList1')
        if delayed_list1_sym:
            tasks.extend(self._parse_task_list(delayed_list1_sym['address'], elf_parser, dump_reader, is_32bit))
        
        delayed_list2_sym = elf_parser.get_symbol_by_name('xDelayedTaskList2')
        if delayed_list2_sym:
            tasks.extend(self._parse_task_list(delayed_list2_sym['address'], elf_parser, dump_reader, is_32bit))
        
        return tasks
    
    def _parse_task_list(self, list_addr: int, elf_parser, dump_reader, is_32bit: bool) -> List[Dict[str, Any]]:
        tasks = []
        
        tcb_struct = elf_parser.get_struct_type('TCB_t')
        if not tcb_struct:
            return tasks
        
        visited = set()
        
        list_item_offset = 4
        list_struct = elf_parser.get_struct_type('List_t')
        if list_struct:
            for member in list_struct.get('members', []):
                if member.get('name') == 'pxIndex':
                    list_item_offset = member.get('offset', 4)
                    break
        
        first_item_addr = dump_reader.read_pointer(list_addr + list_item_offset, is_32bit)
        if not first_item_addr:
            return tasks
        
        current_ptr = first_item_addr
        visited.add(current_ptr)
        
        state_list_item_offset = 4
        for member in tcb_struct.get('members', []):
            if member.get('name') == 'xStateListItem':
                state_list_item_offset = member.get('offset', 4)
                break
        
        while current_ptr:
            tcb_addr = current_ptr - state_list_item_offset
            task_info = self._parse_tcb(tcb_addr, tcb_struct, elf_parser, dump_reader, is_32bit)
            if task_info:
                tasks.append(task_info)
            
            next_ptr = dump_reader.read_pointer(current_ptr + 4, is_32bit)
            if next_ptr in visited or next_ptr == list_addr + state_list_item_offset:
                break
            
            visited.add(next_ptr)
            current_ptr = next_ptr
        
        return tasks
    
    def _parse_tcb(self, tcb_addr: int, tcb_struct: Dict[str, Any], 
                  elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': tcb_addr,
            'name': '',
            'state': '',
            'priority': 0,
            'stack_start': 0,
            'stack_end': 0,
            'current_pc': 0,
            'entry_point': 0,
        }
        
        priority_value = None
        stack_start = None
        
        for member in tcb_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'uxPriority':
                priority_value = dump_reader.read_uint32(tcb_addr + member_offset)
            
            elif member_name == 'pxStack':
                stack_start = dump_reader.read_pointer(tcb_addr + member_offset, is_32bit)
        
        if priority_value is None or priority_value >= 32:
            return None
        
        if stack_start is None or stack_start < 0x20000000 or stack_start > 0x20010000:
            return None
        
        for member in tcb_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'pcTaskName':
                result['name'] = dump_reader.read_string(tcb_addr + member_offset, 16) or ''
                if '\xff' in result['name']:
                    return None
            
            elif member_name == 'uxPriority':
                result['priority'] = dump_reader.read_uint32(tcb_addr + member_offset)
            
            elif member_name == 'pxStack':
                result['stack_start'] = dump_reader.read_pointer_or_zero(tcb_addr + member_offset, is_32bit)
            
            elif member_name == 'pxEndOfStack':
                result['stack_end'] = dump_reader.read_pointer_or_zero(tcb_addr + member_offset, is_32bit)
            
            elif member_name == 'pxTopOfStack':
                top_of_stack = dump_reader.read_pointer(tcb_addr + member_offset, is_32bit)
                if top_of_stack:
                    result['current_sp'] = top_of_stack
                    pc_offset = 0
                    result['current_pc'] = dump_reader.read_pointer_or_zero(top_of_stack + pc_offset, is_32bit)
        
        if result['stack_start'] and result['stack_end']:
            stack_size = abs(result['stack_start'] - result['stack_end'])
            result['stack_size'] = stack_size
            if 'current_sp' in result:
                used = abs(result['current_sp'] - result['stack_end'])
                result['stack_usage'] = used / stack_size * 100 if stack_size > 0 else 0
        
        if result['current_pc']:
            func_info = elf_parser.find_function_by_address(result['current_pc'])
            if func_info:
                result['current_function'] = func_info.get('name', '')
        
        current_tcb_sym = elf_parser.get_symbol_by_name('pxCurrentTCB')
        if current_tcb_sym:
            current_tcb_addr = dump_reader.read_pointer(current_tcb_sym['address'], is_32bit)
            if current_tcb_addr == tcb_addr:
                result['state'] = 'RUNNING'
        
        return result
    
    def get_semaphores(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        semaphores = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return semaphores
        
        is_32bit = elf_parser.is_32bit()
        
        sem_registry_sym = elf_parser.get_symbol_by_name('xSemaphoreRegistry')
        if not sem_registry_sym:
            return semaphores
        
        sem_registry_addr = sem_registry_sym['address']
        sem_registry_ptr = dump_reader.read_pointer(sem_registry_addr, is_32bit)
        
        if not sem_registry_ptr:
            return semaphores
        
        queue_struct = elf_parser.get_struct_type('QueueDefinition')
        if not queue_struct:
            return semaphores
        
        visited = set()
        current_ptr = sem_registry_ptr
        
        while current_ptr and current_ptr not in visited:
            visited.add(current_ptr)
            
            sem_info = self._parse_semaphore(current_ptr, queue_struct, dump_reader, is_32bit)
            if sem_info:
                semaphores.append(sem_info)
            
            next_ptr = dump_reader.read_pointer(current_ptr + 4, is_32bit)
            current_ptr = next_ptr
        
        return semaphores
    
    def _parse_semaphore(self, sem_addr: int, queue_struct: Dict[str, Any], 
                        dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': sem_addr,
            'name': '',
            'count': 0,
            'max_count': 0,
            'type': '',
        }
        
        for member in queue_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'pcQueueName':
                name_addr = dump_reader.read_pointer(sem_addr + member_offset, is_32bit)
                if name_addr:
                    result['name'] = dump_reader.read_string(name_addr, 16) or ''
            
            elif member_name == 'uxMessagesWaiting':
                result['count'] = dump_reader.read_uint32(sem_addr + member_offset)
            
            elif member_name == 'uxLength':
                result['max_count'] = dump_reader.read_uint32(sem_addr + member_offset)
            
            elif member_name == 'uxItemSize':
                item_size = dump_reader.read_uint32(sem_addr + member_offset)
                if item_size == 0:
                    result['type'] = 'binary_semaphore'
                else:
                    result['type'] = 'counting_semaphore'
        
        return result
    
    def get_mutexes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        mutexes = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return mutexes
        
        is_32bit = elf_parser.is_32bit()
        
        queue_registry_sym = elf_parser.get_symbol_by_name('xQueueRegistry')
        if not queue_registry_sym:
            return mutexes
        
        queue_registry_addr = queue_registry_sym['address']
        queue_registry_ptr = dump_reader.read_pointer(queue_registry_addr, is_32bit)
        
        if not queue_registry_ptr:
            return mutexes
        
        queue_struct = elf_parser.get_struct_type('QueueDefinition')
        if not queue_struct:
            return mutexes
        
        visited = set()
        current_ptr = queue_registry_ptr
        
        while current_ptr and current_ptr not in visited:
            visited.add(current_ptr)
            
            mutex_info = self._parse_mutex(current_ptr, queue_struct, dump_reader, is_32bit)
            if mutex_info:
                mutexes.append(mutex_info)
            
            next_ptr = dump_reader.read_pointer(current_ptr + 4, is_32bit)
            current_ptr = next_ptr
        
        return mutexes
    
    def _parse_mutex(self, mutex_addr: int, queue_struct: Dict[str, Any], 
                    dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': mutex_addr,
            'name': '',
            'owner': 0,
            'count': 0,
            'priority_ceiling': 0,
        }
        
        for member in queue_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'pcQueueName':
                name_addr = dump_reader.read_pointer(mutex_addr + member_offset, is_32bit)
                if name_addr:
                    result['name'] = dump_reader.read_string(name_addr, 16) or ''
            
            elif member_name == 'pxMutexHolder':
                result['owner'] = dump_reader.read_pointer_or_zero(mutex_addr + member_offset, is_32bit)
            
            elif member_name == 'uxMessagesWaiting':
                result['count'] = dump_reader.read_uint32(mutex_addr + member_offset)
            
            elif member_name == 'uxQueueType':
                queue_type = dump_reader.read_uint32(mutex_addr + member_offset)
                if queue_type != 0:
                    result['type'] = 'mutex'
        
        return result
    
    def get_queues(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        queues = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return queues
        
        is_32bit = elf_parser.is_32bit()
        
        queue_registry_sym = elf_parser.get_symbol_by_name('xQueueRegistry')
        if not queue_registry_sym:
            return queues
        
        queue_registry_addr = queue_registry_sym['address']
        queue_registry_ptr = dump_reader.read_pointer(queue_registry_addr, is_32bit)
        
        if not queue_registry_ptr:
            return queues
        
        queue_struct = elf_parser.get_struct_type('QueueDefinition')
        if not queue_struct:
            return queues
        
        visited = set()
        current_ptr = queue_registry_ptr
        
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
        }
        
        for member in queue_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'pcQueueName':
                name_addr = dump_reader.read_pointer(queue_addr + member_offset, is_32bit)
                if name_addr:
                    result['name'] = dump_reader.read_string(name_addr, 16) or ''
            
            elif member_name == 'uxMessagesWaiting':
                result['messages_count'] = dump_reader.read_uint32(queue_addr + member_offset)
            
            elif member_name == 'uxLength':
                result['messages_max'] = dump_reader.read_uint32(queue_addr + member_offset)
            
            elif member_name == 'uxItemSize':
                result['message_size'] = dump_reader.read_uint32(queue_addr + member_offset)
        
        return result
    
    def get_heap_info(self, context: Dict[str, Any]) -> Dict[str, Any]:
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return {}
        
        heap_stats_sym = elf_parser.get_symbol_by_name('xHeapStats')
        if not heap_stats_sym:
            return {}
        
        heap_stats_addr = heap_stats_sym['address']
        
        heap_info = {
            'address': heap_stats_addr,
            'total_bytes': 0,
            'free_bytes': 0,
            'largest_free_block': 0,
            'minimum_free_bytes': 0,
            'allocation_count': 0,
            'free_count': 0,
        }
        
        heap_stats_struct = elf_parser.get_struct_type('HeapStats_t')
        if heap_stats_struct:
            for member in heap_stats_struct.get('members', []):
                member_name = member.get('name')
                member_offset = member.get('offset', 0)
                
                if member_name == 'xTotalSize':
                    heap_info['total_bytes'] = dump_reader.read_uint32(heap_stats_addr + member_offset)
                
                elif member_name == 'xFreeBytesRemaining':
                    heap_info['free_bytes'] = dump_reader.read_uint32(heap_stats_addr + member_offset)
                
                elif member_name == 'xLargestFreeBlock':
                    heap_info['largest_free_block'] = dump_reader.read_uint32(heap_stats_addr + member_offset)
                
                elif member_name == 'xMinimumEverFreeBytesRemaining':
                    heap_info['minimum_free_bytes'] = dump_reader.read_uint32(heap_stats_addr + member_offset)
                
                elif member_name == 'xNumberOfSuccessfulAllocations':
                    heap_info['allocation_count'] = dump_reader.read_uint32(heap_stats_addr + member_offset)
                
                elif member_name == 'xNumberOfSuccessfulFrees':
                    heap_info['free_count'] = dump_reader.read_uint32(heap_stats_addr + member_offset)
        else:
            heap_info['total_bytes'] = dump_reader.read_uint32(heap_stats_addr)
            heap_info['free_bytes'] = dump_reader.read_uint32(heap_stats_addr + 4)
            heap_info['largest_free_block'] = dump_reader.read_uint32(heap_stats_addr + 8)
            heap_info['minimum_free_bytes'] = dump_reader.read_uint32(heap_stats_addr + 12)
        
        if heap_info['total_bytes'] > 0:
            heap_info['usage_percent'] = (heap_info['total_bytes'] - heap_info['free_bytes']) / heap_info['total_bytes'] * 100
        
        return heap_info
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'tasks': self.get_tasks(context),
            'semaphores': self.get_semaphores(context),
            'mutexes': self.get_mutexes(context),
            'queues': self.get_queues(context),
            'heap': self.get_heap_info(context),
        }