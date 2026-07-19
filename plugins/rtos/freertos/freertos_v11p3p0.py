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
        ]
    
    def get_required_structs(self) -> List[str]:
        return [
            'TCB_t',
            'QueueDefinition',
        ]
    
    def _get_task_state(self, tcb_addr: int, elf_parser, dump_reader, is_32bit: bool) -> str:
        current_tcb_sym = elf_parser.get_symbol_by_name('pxCurrentTCB')
        if current_tcb_sym:
            current_tcb_addr = dump_reader.read_pointer(current_tcb_sym['address'], is_32bit)
            if current_tcb_addr == tcb_addr:
                return 'RUNNING'
        
        ready_lists_sym = elf_parser.get_symbol_by_name('pxReadyTasksLists')
        if ready_lists_sym:
            list_struct = elf_parser.get_struct_type('List_t')
            list_size = list_struct.get('byte_size', 20) if list_struct else 20
            
            for priority in range(8):
                list_addr = ready_lists_sym['address'] + priority * list_size
                if self._is_tcb_in_list(tcb_addr, list_addr, elf_parser, dump_reader, is_32bit):
                    return 'READY'
        
        suspended_list_sym = elf_parser.get_symbol_by_name('xSuspendedTaskList')
        if suspended_list_sym and self._is_tcb_in_list(tcb_addr, suspended_list_sym['address'], elf_parser, dump_reader, is_32bit):
            return 'SUSPENDED'
        
        delayed_list1_sym = elf_parser.get_symbol_by_name('xDelayedTaskList1')
        if delayed_list1_sym and self._is_tcb_in_list(tcb_addr, delayed_list1_sym['address'], elf_parser, dump_reader, is_32bit):
            return 'DELAYED'
        
        delayed_list2_sym = elf_parser.get_symbol_by_name('xDelayedTaskList2')
        if delayed_list2_sym and self._is_tcb_in_list(tcb_addr, delayed_list2_sym['address'], elf_parser, dump_reader, is_32bit):
            return 'DELAYED'
        
        return 'UNKNOWN'
    
    def _is_tcb_in_list(self, tcb_addr: int, list_addr: int, elf_parser, dump_reader, is_32bit: bool) -> bool:
        tcb_struct = elf_parser.get_struct_type('TCB_t')
        if not tcb_struct:
            return False
        
        state_list_item_offset = 4
        for member in tcb_struct.get('members', []):
            if member.get('name') == 'xStateListItem':
                state_list_item_offset = member.get('offset', 4)
                break
        
        list_item_offset = 4
        list_struct = elf_parser.get_struct_type('List_t')
        if list_struct:
            for member in list_struct.get('members', []):
                if member.get('name') == 'pxIndex':
                    list_item_offset = member.get('offset', 4)
                    break
        
        first_item_addr = dump_reader.read_pointer(list_addr + list_item_offset, is_32bit)
        if not first_item_addr:
            return False
        
        current_ptr = first_item_addr
        visited = set()
        
        while current_ptr and current_ptr not in visited:
            visited.add(current_ptr)
            item_tcb_addr = current_ptr - state_list_item_offset
            if item_tcb_addr == tcb_addr:
                return True
            
            next_ptr = dump_reader.read_pointer(current_ptr + 4, is_32bit)
            if next_ptr in visited:
                break
            current_ptr = next_ptr
        
        return False
    
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
        
        list_struct = elf_parser.get_struct_type('List_t')
        list_size = list_struct.get('byte_size', 20) if list_struct else 20
        
        for priority in range(8):
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
            'base_priority': 0,
            'stack_start': 0,
            'stack_end': 0,
            'stack_size': 0,
            'stack_usage': 0,
            'current_pc': 0,
            'current_function': '',
            'current_sp': 0,
            'mutexes_held': 0,
        }
        
        for member in tcb_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'pcTaskName':
                result['name'] = dump_reader.read_string(tcb_addr + member_offset, 16) or ''
                if '\xff' in result['name'] or len(result['name']) > 16:
                    return None
                if result['name'] and not result['name'].isprintable():
                    return None
            
            elif member_name == 'uxPriority':
                priority = dump_reader.read_uint32(tcb_addr + member_offset)
                if priority >= 32:
                    return None
                result['priority'] = priority
            
            elif member_name == 'uxBasePriority':
                result['base_priority'] = dump_reader.read_uint32(tcb_addr + member_offset)
            
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
            
            elif member_name == 'uxMutexesHeld':
                result['mutexes_held'] = dump_reader.read_uint32(tcb_addr + member_offset)
        
        if result['stack_start'] and result['stack_end']:
            stack_size = abs(result['stack_start'] - result['stack_end'])
            result['stack_size'] = stack_size
            if 'current_sp' in result and result['current_sp']:
                used = abs(result['current_sp'] - result['stack_end'])
                result['stack_usage'] = used / stack_size * 100 if stack_size > 0 else 0
        
        if result['current_pc']:
            func_info = elf_parser.find_function_by_address(result['current_pc'])
            if func_info:
                result['current_function'] = func_info.get('name', '')
        
        result['state'] = self._get_task_state(tcb_addr, elf_parser, dump_reader, is_32bit)
        
        return result
    
    def get_semaphores(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        semaphores = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return semaphores
        
        is_32bit = elf_parser.is_32bit()
        
        all_symbols = elf_parser.get_all_symbols()
        sem_symbols = [s for s in all_symbols if s['name'].startswith('x') and 
                      ('Sem' in s['name'] or 'sem' in s['name']) and
                      'Task' not in s['name'] and
                      s['type'] == 'global_object']
        
        queue_struct = elf_parser.get_struct_type('QueueDefinition')
        
        for sym in sem_symbols:
            sem_addr = dump_reader.read_pointer(sym['address'], is_32bit)
            if sem_addr:
                sem_info = self._parse_semaphore(sem_addr, queue_struct, dump_reader, is_32bit)
                if sem_info and sem_info['max_count'] > 0:
                    sem_info['name'] = sym['name']
                    semaphores.append(sem_info)
        
        return semaphores
    
    def _parse_semaphore(self, sem_addr: int, queue_struct: Dict[str, Any], 
                        dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': sem_addr,
            'name': '',
            'count': 0,
            'max_count': 0,
            'type': 'binary_semaphore',
        }
        
        members = queue_struct.get('members', []) if queue_struct else []
        
        if members:
            for member in members:
                member_name = member.get('name')
                member_offset = member.get('offset', 0)
                
                if member_name == 'uxMessagesWaiting':
                    result['count'] = dump_reader.read_uint32(sem_addr + member_offset)
                
                elif member_name == 'uxLength':
                    result['max_count'] = dump_reader.read_uint32(sem_addr + member_offset)
                
                elif member_name == 'uxItemSize':
                    item_size = dump_reader.read_uint32(sem_addr + member_offset)
                    if item_size == 0:
                        result['type'] = 'binary_semaphore'
                    else:
                        result['type'] = 'counting_semaphore'
        else:
            result['max_count'] = dump_reader.read_uint32(sem_addr + 60)
            item_size = dump_reader.read_uint32(sem_addr + 64)
            result['count'] = dump_reader.read_uint32(sem_addr + 68)
            
            if result['count'] == 65535:
                result['count'] = result['max_count']
            
            if result['max_count'] > 1:
                result['type'] = 'counting_semaphore'
            else:
                result['type'] = 'binary_semaphore'
        
        return result
    
    def get_mutexes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        mutexes = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return mutexes
        
        is_32bit = elf_parser.is_32bit()
        
        all_symbols = elf_parser.get_all_symbols()
        mutex_symbols = [s for s in all_symbols if s['name'].startswith('x') and 
                        'Mutex' in s['name'] and
                        'Task' not in s['name'] and
                        s['type'] == 'global_object']
        
        queue_struct = elf_parser.get_struct_type('QueueDefinition')
        
        for sym in mutex_symbols:
            mutex_addr = dump_reader.read_pointer(sym['address'], is_32bit)
            if mutex_addr:
                mutex_info = self._parse_mutex(mutex_addr, queue_struct, dump_reader, is_32bit)
                if mutex_info and mutex_info['count'] >= 0:
                    mutex_info['name'] = sym['name']
                    mutexes.append(mutex_info)
        
        return mutexes
    
    def _parse_mutex(self, mutex_addr: int, queue_struct: Dict[str, Any], 
                    dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': mutex_addr,
            'name': '',
            'owner': 0,
            'owner_name': '',
            'count': 0,
            'priority_ceiling': 0,
            'type': 'mutex',
        }
        
        members = queue_struct.get('members', []) if queue_struct else []
        
        if members:
            for member in members:
                member_name = member.get('name')
                member_offset = member.get('offset', 0)
                
                if member_name == 'pxMutexHolder':
                    result['owner'] = dump_reader.read_pointer_or_zero(mutex_addr + member_offset, is_32bit)
                
                elif member_name == 'uxMessagesWaiting':
                    result['count'] = dump_reader.read_uint32(mutex_addr + member_offset)
        else:
            result['owner'] = dump_reader.read_pointer_or_zero(mutex_addr + 44, is_32bit)
            result['count'] = dump_reader.read_uint32(mutex_addr + 68)
            if result['count'] == 65535:
                result['count'] = 0
            if result['owner'] == 0xffffffff:
                result['owner'] = 0
        
        return result
    
    def get_queues(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        queues = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return queues
        
        is_32bit = elf_parser.is_32bit()
        
        all_symbols = elf_parser.get_all_symbols()
        queue_symbols = [s for s in all_symbols if s['name'].startswith('x') and 
                        'Queue' in s['name'] and
                        s['type'] == 'global_object']
        
        queue_struct = elf_parser.get_struct_type('QueueDefinition')
        
        for sym in queue_symbols:
            queue_addr = dump_reader.read_pointer(sym['address'], is_32bit)
            if queue_addr:
                queue_info = self._parse_queue(queue_addr, queue_struct, dump_reader, is_32bit)
                if queue_info:
                    queue_info['name'] = sym['name']
                    queues.append(queue_info)
        
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
        
        members = queue_struct.get('members', []) if queue_struct else []
        
        if members:
            for member in members:
                member_name = member.get('name')
                member_offset = member.get('offset', 0)
                
                if member_name == 'uxMessagesWaiting':
                    result['messages_count'] = dump_reader.read_uint32(queue_addr + member_offset)
                
                elif member_name == 'uxLength':
                    result['messages_max'] = dump_reader.read_uint32(queue_addr + member_offset)
                
                elif member_name == 'uxItemSize':
                    result['message_size'] = dump_reader.read_uint32(queue_addr + member_offset)
        else:
            result['messages_max'] = dump_reader.read_uint32(queue_addr + 60)
            result['message_size'] = dump_reader.read_uint32(queue_addr + 64)
            result['messages_count'] = dump_reader.read_uint32(queue_addr + 68)
            if result['messages_count'] == 65535:
                result['messages_count'] = 0
        
        return result
    
    def get_timers(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        timers = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return timers
        
        is_32bit = elf_parser.is_32bit()
        
        timer_handle_map = {}
        all_symbols = elf_parser.get_all_symbols()
        for sym in all_symbols:
            if sym['name'].startswith('x') and ('Timer' in sym['name'] or 'timer' in sym['name']):
                if sym['type'] in ['global_object', 'local_object']:
                    timer_ptr = dump_reader.read_pointer(sym['address'], is_32bit)
                    if timer_ptr:
                        timer_handle_map[timer_ptr] = sym['name']
        
        current_timer_list_sym = elf_parser.get_symbol_by_name('pxCurrentTimerList')
        if not current_timer_list_sym:
            return timers
        
        current_timer_list_addr = dump_reader.read_pointer(current_timer_list_sym['address'], is_32bit)
        if not current_timer_list_addr:
            return timers
        
        timers.extend(self._parse_timer_list(current_timer_list_addr, elf_parser, dump_reader, is_32bit, timer_handle_map))
        
        overflow_timer_list_sym = elf_parser.get_symbol_by_name('pxOverflowTimerList')
        if overflow_timer_list_sym:
            overflow_timer_list_addr = dump_reader.read_pointer(overflow_timer_list_sym['address'], is_32bit)
            if overflow_timer_list_addr:
                timers.extend(self._parse_timer_list(overflow_timer_list_addr, elf_parser, dump_reader, is_32bit, timer_handle_map))
        
        return timers
    
    def _parse_timer_list(self, list_addr: int, elf_parser, dump_reader, is_32bit: bool, timer_handle_map: Dict[int, str] = None) -> List[Dict[str, Any]]:
        timers = []
        
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
            return timers
        
        current_ptr = first_item_addr
        visited.add(current_ptr)
        
        while current_ptr:
            timer_addr = current_ptr - 4
            timer_info = self._parse_timer(timer_addr, elf_parser, dump_reader, is_32bit, timer_handle_map)
            if timer_info:
                timers.append(timer_info)
            
            next_ptr = dump_reader.read_pointer(current_ptr + 4, is_32bit)
            if next_ptr in visited or next_ptr == list_addr + list_item_offset:
                break
            
            visited.add(next_ptr)
            current_ptr = next_ptr
        
        return timers
    
    def _parse_timer(self, timer_addr: int, elf_parser, dump_reader, is_32bit: bool, timer_handle_map: Dict[int, str] = None) -> Optional[Dict[str, Any]]:
        result = {
            'address': timer_addr,
            'name': '',
            'period_ticks': 0,
            'ticks_remaining': 0,
            'active': False,
            'auto_reload': False,
        }
        
        if timer_handle_map and timer_addr in timer_handle_map:
            result['name'] = timer_handle_map[timer_addr]
        
        timer_struct = elf_parser.get_struct_type('Timer_t')
        if timer_struct:
            for member in timer_struct.get('members', []):
                member_name = member.get('name')
                member_offset = member.get('offset', 0)
                
                if not result['name'] and member_name == 'pcTimerName':
                    name_addr = dump_reader.read_pointer(timer_addr + member_offset, is_32bit)
                    if name_addr:
                        result['name'] = dump_reader.read_string(name_addr, 16) or ''
                
                elif member_name == 'xTimerPeriodInTicks':
                    result['period_ticks'] = dump_reader.read_uint32(timer_addr + member_offset)
                
                elif member_name == 'ucStatus':
                    status = dump_reader.read_uint8(timer_addr + member_offset)
                    result['active'] = (status & 1) != 0
                    result['auto_reload'] = (status & 2) != 0
        else:
            if not result['name']:
                name_addr = dump_reader.read_pointer(timer_addr + 28, is_32bit)
                if name_addr:
                    result['name'] = dump_reader.read_string(name_addr, 16) or ''
            
            period = dump_reader.read_uint32(timer_addr + 8)
            if period == 0 or period > 1000000:
                period = dump_reader.read_uint32(timer_addr + 12)
            
            result['period_ticks'] = period
            status = dump_reader.read_uint8(timer_addr + 32)
            result['active'] = (status & 1) != 0
            result['auto_reload'] = (status & 2) != 0
        
        if result['period_ticks'] > 1000000:
            result['period_ticks'] = 0
        
        if result['name'] and not result['name'].isprintable():
            result['name'] = ''
        
        return result
    
    def get_event_groups(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        event_groups = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return event_groups
        
        is_32bit = elf_parser.is_32bit()
        
        all_symbols = elf_parser.get_all_symbols()
        event_symbols = [s for s in all_symbols if s['name'].startswith('x') and 
                        'EventGrp' in s['name'] and
                        s['type'] == 'global_object']
        
        for sym in event_symbols:
            event_addr = dump_reader.read_pointer(sym['address'], is_32bit)
            if event_addr:
                event_info = self._parse_event_group(event_addr, dump_reader, is_32bit)
                if event_info:
                    event_info['name'] = sym['name']
                    event_groups.append(event_info)
        
        return event_groups
    
    def _parse_event_group(self, event_addr: int, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': event_addr,
            'name': '',
            'bits': 0,
            'suspended_count': 0,
        }
        
        result['bits'] = dump_reader.read_uint32(event_addr)
        
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
            'timers': self.get_timers(context),
            'event_groups': self.get_event_groups(context),
            'heap': self.get_heap_info(context),
        }
