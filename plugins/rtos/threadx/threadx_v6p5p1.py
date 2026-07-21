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
import time
from typing import Dict, List, Optional, Any

from ..base import RTOSPlugin

logger = logging.getLogger(__name__)

# ThreadX 信号量最大计数值（ThreadX 计数信号量无固定上限）
_TX_SEMAPHORE_MAX_COUNT = 0xFFFFFFFF

# ThreadX 线程状态映射表（tx_thread_state → 名称）
# 来源：OpenOCD ThreadX.c 源码 + ThreadX tx_api.h 枚举定义
_THREAD_STATE_MAP = {
    0: 'TX_READY',
    1: 'TX_COMPLETED',
    2: 'TX_TERMINATED',
    3: 'TX_SUSPENDED',
    4: 'TX_SLEEP',
    5: 'TX_QUEUE_SUSP',
    6: 'TX_SEMAPHORE_SUSP',
    7: 'TX_EVENT_FLAG',
    8: 'TX_BLOCK_MEMORY',
    9: 'TX_BYTE_MEMORY',
    10: 'TX_IO_SUSP',
    11: 'TX_FILE_SUSP',
    12: 'TX_NETWORK_SUSP',
    13: 'TX_MUTEX_SUSP',
}


class ThreadXV6Plugin(RTOSPlugin):
    def __init__(self):
        super().__init__(
            name='threadx_v6p5p1',
            version='1.0',
            os_name='threadx',
            os_version='v6p5p1',
            description='ThreadX v6p5p1 RTOS analysis plugin'
        )
    
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
        tasks = self._walk_singly_linked_list(
            '_tx_thread_created_ptr',
            'TX_THREAD',
            'tx_thread_created_next',
            self._parse_thread,
            context
        )
        
        elf_parser = context['elf_parser']
        dump_reader = context['dump_reader']
        ptr_size = 4 if elf_parser.is_32bit() else 8
        
        current_ptr_sym = elf_parser.get_symbol_by_name('_tx_thread_current_ptr')
        if current_ptr_sym:
            current_ptr_value = dump_reader.read_pointer_by_size(current_ptr_sym['address'], byte_size=ptr_size)
            if current_ptr_value == 0:
                ready_list_sym = elf_parser.get_symbol_by_name('_tx_thread_priority_list')
                if ready_list_sym:
                    ready_list_addr = ready_list_sym['address']
                    priority_list_size = ready_list_sym.get('size', 0)
                    if priority_list_size > 0:
                        max_priorities = priority_list_size // ptr_size
                    else:
                        max_priorities = 0
                    for priority in range(max_priorities):
                        head_addr = ready_list_addr + priority * ptr_size
                        head = dump_reader.read_pointer_by_size(head_addr, byte_size=ptr_size)
                        if head != 0:
                            for task in tasks:
                                if task['address'] == head:
                                    task['state'] = 0
                                    task['state_name'] = 'TX_READY'
                                    break
                            break
        
        self._calculate_cpu_usage(tasks)
        
        return tasks
    
    def _calculate_cpu_usage(self, tasks: List[Dict[str, Any]]):
        """Calculate schedule ratio for each task based on run_count.

        IMPORTANT: ThreadX tx_thread_run_count records only the number of
        times a thread has been scheduled, NOT cumulative execution time.
        This field is labeled 'schedule_ratio' (not 'cpu_usage') to reflect
        that it measures scheduling frequency, not actual CPU time.
        In systems with unequal time slices or interrupt preemption,
        this metric may diverge significantly from true CPU utilization.
        """
        total_run_count = sum(task.get('run_count', 0) for task in tasks)
        
        if total_run_count > 0:
            for task in tasks:
                run_count = task.get('run_count', 0)
                task['schedule_ratio'] = round((run_count / total_run_count) * 100, 1)
        else:
            for task in tasks:
                task['schedule_ratio'] = 0.0
    
    def _parse_thread(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        thread_addr = accessor.address

        state = accessor.get_int('tx_thread_state')
        result = {
            'address': thread_addr,
            'magic': thread_addr,
            'name': accessor.get_string('tx_thread_name'),
            'state': state,
            'priority': accessor.get_int('tx_thread_priority'),
            'run_count': accessor.get_int('tx_thread_run_count'),
            'stack_start': accessor.get_ptr('tx_thread_stack_start'),
            'stack_size': accessor.get_int('tx_thread_stack_size'),
            'stack_current': accessor.get_ptr('tx_thread_stack_ptr'),
            'stack_high_water': 0,
            'current_pc': 0,
            'entry_point': accessor.get_ptr('tx_thread_entry'),
            'entry_param': accessor.get_ptr('tx_thread_entry_parameter'),
            'timer_remaining': accessor.get_int('tx_thread_time_slice'),
            'timeout_function': accessor.get_ptr('tx_thread_timeout_function'),
            'timeout_param': accessor.get_ptr('tx_thread_timeout_parameter'),
            'state_name': accessor.get_enum_name('tx_thread_state', fallback_map=_THREAD_STATE_MAP),
        }

        stack_highest_ptr = accessor.get_ptr('tx_thread_stack_highest_ptr')
        result['stack_highest_ptr'] = stack_highest_ptr
        stack_usage = self._calculate_stack_usage_highest(
            result['stack_start'],
            result['stack_size'],
            stack_highest_ptr,
            result['stack_current']
        )
        result['stack_usage'] = round(stack_usage, 1) if stack_usage is not None else 0.0

        if result['entry_point']:
            func_info = elf_parser.find_function_by_address(result['entry_point'])
            if func_info:
                result['entry_function'] = func_info.get('name', '')

        return result
    
    def _get_semaphores(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_singly_linked_list(
            '_tx_semaphore_created_ptr',
            'TX_SEMAPHORE',
            'tx_semaphore_created_next',
            self._parse_semaphore,
            context
        )
    
    def _parse_semaphore(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        sem_addr = accessor.address
        return {
            'address': sem_addr,
            'magic': sem_addr,
            'name': accessor.get_string('tx_semaphore_name'),
            'count': accessor.get_int('tx_semaphore_count'),
            'max_count': _TX_SEMAPHORE_MAX_COUNT,
            'suspended_count': accessor.get_int('tx_semaphore_suspended_count'),
        }
    
    def _get_mutexes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_singly_linked_list(
            '_tx_mutex_created_ptr',
            'TX_MUTEX',
            'tx_mutex_created_next',
            self._parse_mutex,
            context
        )
    
    def _parse_mutex(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        mutex_addr = accessor.address
        owner = accessor.get_ptr('tx_mutex_owner')
        result = {
            'address': mutex_addr,
            'magic': mutex_addr,
            'name': accessor.get_string('tx_mutex_name'),
            'owner': owner,
            'owner_info': None,
            'inherit_count': accessor.get_int('tx_mutex_ownership_count'),
            'priority': accessor.get_int('tx_mutex_original_priority'),
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
                        owner_info = self._parse_thread(owner_accessor, elf_parser, dump_reader, is_32bit)
                        if owner_info:
                            result['owner_info'] = {
                                'address': owner_info['address'],
                                'name': owner_info['name'],
                            }
            except Exception:
                logger.debug("Failed to parse mutex owner at 0x%x for mutex 0x%x",
                             owner, mutex_addr, exc_info=True)

        return result
    
    def _get_queues(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_singly_linked_list(
            '_tx_queue_created_ptr',
            'TX_QUEUE',
            'tx_queue_created_next',
            self._parse_queue,
            context
        )
    
    def _parse_queue(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        queue_addr = accessor.address
        return {
            'address': queue_addr,
            'magic': queue_addr,
            'name': accessor.get_string('tx_queue_name'),
            'max_messages': accessor.get_int('tx_queue_capacity'),
            'messages': accessor.get_int('tx_queue_enqueued'),
            'message_size': accessor.get_int('tx_queue_message_size'),
            'suspended_count': accessor.get_int('tx_queue_suspended_count'),
        }
    
    def _get_events(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_singly_linked_list(
            '_tx_event_flags_created_ptr',
            'TX_EVENT_FLAGS_GROUP',
            'tx_event_flags_group_created_next',
            self._parse_event,
            context
        )
    
    def _parse_event(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        event_addr = accessor.address
        return {
            'address': event_addr,
            'magic': event_addr,
            'name': accessor.get_string('tx_event_flags_group_name'),
            'flags': accessor.get_int('tx_event_flags_group_flags'),
            'suspended_count': accessor.get_int('tx_event_flags_group_suspended_count'),
        }
    
    def _get_timers(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_singly_linked_list(
            '_tx_timer_created_ptr',
            'TX_TIMER',
            'tx_timer_created_next',
            self._parse_timer,
            context
        )
    
    def _parse_timer(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        timer_addr = accessor.address
        result = {
            'address': timer_addr,
            'magic': timer_addr,
            'name': accessor.get_string('tx_timer_name'),
            'active': False,
            'state_name': '',
            'period_ticks': 0,
            'ticks_remaining': 0,
            'expiration_function': 0,
            'expiration_param': 0,
        }

        # 使用点分路径访问嵌套结构体 TX_TIMER_INTERNAL
        result['ticks_remaining'] = accessor.get_int('tx_timer_internal.tx_timer_internal_remaining_ticks')
        result['period_ticks'] = accessor.get_int('tx_timer_internal.tx_timer_internal_re_initialize_ticks')
        result['expiration_function'] = accessor.get_ptr('tx_timer_internal.tx_timer_internal_timeout_function')
        result['expiration_param'] = accessor.get_int('tx_timer_internal.tx_timer_internal_timeout_param')

        active_next = accessor.get_ptr('tx_timer_internal.tx_timer_internal_active_next')
        result['active'] = active_next != 0
        result['state_name'] = 'ACTIVE' if result['active'] else 'INACTIVE'

        if result['expiration_function']:
            func_info = elf_parser.find_function_by_address(result['expiration_function'])
            if func_info:
                result['expiration_function_name'] = func_info.get('name', '')

        return result
    
    def _get_block_pools(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_singly_linked_list(
            '_tx_block_pool_created_ptr',
            'TX_BLOCK_POOL',
            'tx_block_pool_created_next',
            self._parse_block_pool,
            context
        )
    
    def _parse_block_pool(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        pool_addr = accessor.address
        return {
            'address': pool_addr,
            'magic': pool_addr,
            'name': accessor.get_string('tx_block_pool_name'),
            'total_blocks': accessor.get_int('tx_block_pool_total'),
            'available_blocks': accessor.get_int('tx_block_pool_available'),
            'block_size': accessor.get_int('tx_block_pool_block_size'),
        }
    
    def _get_byte_pools(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._walk_singly_linked_list(
            '_tx_byte_pool_created_ptr',
            'TX_BYTE_POOL',
            'tx_byte_pool_created_next',
            self._parse_byte_pool,
            context
        )
    
    def _parse_byte_pool(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        pool_addr = accessor.address
        total_bytes = accessor.get_int('tx_byte_pool_size')
        available_bytes = accessor.get_int('tx_byte_pool_available')
        result = {
            'address': pool_addr,
            'magic': pool_addr,
            'name': accessor.get_string('tx_byte_pool_name'),
            'total_bytes': total_bytes,
            'available_bytes': available_bytes,
            'fragments': accessor.get_int('tx_byte_pool_fragments'),
            'largest_available': 0,
        }

        if total_bytes > 0:
            result['usage_percent'] = (total_bytes - available_bytes) / total_bytes * 100

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

        heap_struct = elf_parser.get_struct_type('TX_HEAP')
        if not heap_struct:
            return {}

        view_node = elf_parser.read_struct_as_node(heap_struct, heap_pool_addr, dump_reader)
        if not view_node:
            return {}

        from core.elf_parser.struct_accessor import StructAccessor
        accessor = StructAccessor(view_node, dump_reader, elf_parser)

        total_bytes = accessor.get_int('tx_heap_total_bytes')
        available_bytes = accessor.get_int('tx_heap_available_bytes')
        heap_info = {
            'address': heap_pool_addr,
            'magic': heap_pool_addr,
            'total_bytes': total_bytes,
            'available_bytes': available_bytes,
            'fragments': accessor.get_int('tx_heap_fragments'),
            'largest_available': accessor.get_int('tx_heap_largest_available'),
        }

        if total_bytes > 0:
            heap_info['usage_percent'] = (total_bytes - available_bytes) / total_bytes * 100

        return heap_info
    
    def get_detail(self, resource_type: str, address: int) -> Optional[Dict[str, Any]]:
        if not self._context:
            return None
        
        resource_type = self._normalize_resource_type(resource_type)
        resources = self.get_resource(resource_type, self._context)
        
        for resource in resources:
            if resource.get('address') == address or resource.get('magic') == address:
                return resource
        
        return None
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._context = context
        result = {}
        
        for key, func in [('tasks', self._get_tasks), ('semaphores', self._get_semaphores),
                          ('mutexes', self._get_mutexes), ('queues', self._get_queues),
                          ('events', self._get_events), ('timers', self._get_timers),
                          ('block_pools', self._get_block_pools), ('byte_pools', self._get_byte_pools)]:
            t0 = time.time()
            result[key] = func(context)
            elapsed = time.time() - t0
            count = len(result[key]) if isinstance(result[key], list) else 0
            print(f"    {key}: {elapsed:.3f}s ({count} items)")
        
        t0 = time.time()
        result['heap'] = self.get_heap_info(context)
        elapsed = time.time() - t0
        print(f"    heap: {elapsed:.3f}s")
        
        return result
