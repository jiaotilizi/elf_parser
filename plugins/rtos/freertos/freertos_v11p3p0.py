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
from typing import Dict, List, Optional, Any

from ..base import RTOSPlugin
from core.utils.linked_list import walk_doubly_linked_list
from core.utils.stack import calculate_stack_usage

logger = logging.getLogger(__name__)

_FREERTOS_PC_OFFSET_IN_STACK_FRAME = 4


class FreeRTOSV11Plugin(RTOSPlugin):
    def __init__(self):
        super().__init__(
            name='freertos_v11p3p0',
            version='1.0',
            os_name='freertos',
            os_version='v11p3p0',
            description='FreeRTOS v11p3p0 analysis plugin'
        )
    
    def get_resource_types(self) -> List[str]:
        return ['tasks', 'semaphores', 'mutexes', 'queues', 'timers', 'events']
    
    def get_resource(self, resource_type: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        resource_map = {
            'tasks': self._get_tasks,
            'semaphores': self._get_semaphores,
            'mutexes': self._get_mutexes,
            'queues': self._get_queues,
            'timers': self._get_timers,
            'events': self._get_events,
        }
        func = resource_map.get(resource_type)
        if func:
            return func(context)
        return []
    
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
    
    # ========================================================================
    # DWARF 类型驱动的对象发现（不依赖变量名称关键词）
    # ========================================================================
    
    # FreeRTOS 句柄类型 → 对象类型映射
    # 通过 DWARF 类型信息发现对象，而非变量名称模式匹配
    _HANDLE_TYPE_MAP = {
        'SemaphoreHandle_t': 'semaphore_or_mutex',  # 信号量和互斥锁共用此类型
        'QueueHandle_t': 'queue',
        'TimerHandle_t': 'timer',
        'EventGroupHandle_t': 'event',
    }
    
    def _discover_handles_by_type(self, elf_parser, type_names: List[str]) -> List[Dict[str, Any]]:
        """通过 DWARF 类型信息发现全局句柄变量。
        
        不依赖变量名称关键词，完全基于 DWARF 类型系统。
        
        Args:
            elf_parser: ELFParser 实例
            type_names: DWARF 类型名列表（如 ['SemaphoreHandle_t', 'QueueHandle_t']）
        
        Returns:
            句柄信息列表，每个元素包含 name、address、dwarf_type
        """
        handles = []
        all_symbols = elf_parser.get_all_symbols()
        
        for sym in all_symbols:
            if sym.get('type') != 'global_object':
                continue
            
            var_type = elf_parser.get_variable_type(sym['name'])
            if not var_type:
                continue
            
            type_name = var_type.get('name', '')
            if type_name in type_names:
                handles.append({
                    'name': sym['name'],
                    'address': sym['address'],
                    'dwarf_type': type_name,
                })
        
        return handles
    
    
    
    def _get_config_max_priorities(self, elf_parser) -> int:
        """从 pxReadyTasksLists 的 ELF 符号大小推导 configMAX_PRIORITIES。
        
        pxReadyTasksLists 是 List_t[configMAX_PRIORITIES] 数组，
        符号大小 = configMAX_PRIORITIES * sizeof(List_t)。
        当无法推导时返回 0，调用方应优雅降级。
        """
        ready_lists_sym = elf_parser.get_symbol_by_name('pxReadyTasksLists')
        if not ready_lists_sym:
            logger.warning("pxReadyTasksLists symbol not found, cannot derive configMAX_PRIORITIES")
            return 0
        
        list_struct = elf_parser.get_struct_type('List_t')
        if not list_struct:
            logger.warning("List_t struct not found in DWARF, cannot derive configMAX_PRIORITIES")
            return 0
        
        list_size = list_struct.get('byte_size', 0)
        if list_size <= 0:
            logger.warning("List_t byte_size is 0, cannot derive configMAX_PRIORITIES")
            return 0
        
        symbol_size = ready_lists_sym.get('size', 0)
        if symbol_size <= 0:
            logger.warning("pxReadyTasksLists symbol size is 0, cannot derive configMAX_PRIORITIES")
            return 0
        
        max_priorities = symbol_size // list_size
        if max_priorities <= 0:
            logger.warning("Derived configMAX_PRIORITIES=%d is invalid", max_priorities)
            return 0
        
        logger.debug("Derived configMAX_PRIORITIES=%d from pxReadyTasksLists size=%d / sizeof(List_t)=%d",
                     max_priorities, symbol_size, list_size)
        return max_priorities
    
    def _get_task_state(self, tcb_addr: int, elf_parser, dump_reader, is_32bit: bool) -> str:
        """返回 FreeRTOS 任务状态的可读描述。
        
        状态判断基于 FreeRTOS 内核的任务调度机制：
        - pxCurrentTCB → 当前正在执行
        - pxReadyTasksLists → 就绪
        - xSuspendedTaskList → 被 vTaskSuspend() 挂起
        - xDelayedTaskList1/2 → 等待超时
        - 不在任何已知列表 → 阻塞（等待信号量/互斥锁/队列/事件等）
        """
        current_tcb_sym = elf_parser.get_symbol_by_name('pxCurrentTCB')
        if current_tcb_sym:
            current_tcb_addr = dump_reader.read_pointer(current_tcb_sym['address'], is_32bit)
            if current_tcb_addr == tcb_addr:
                return 'Running'
        
        ready_lists_sym = elf_parser.get_symbol_by_name('pxReadyTasksLists')
        if ready_lists_sym:
            list_struct = elf_parser.get_struct_type('List_t')
            if not list_struct:
                return 'Blocked'
            list_size = list_struct.get('byte_size', 0)
            if list_size <= 0:
                return 'Blocked'
            
            max_priorities = self._get_config_max_priorities(elf_parser)
            if max_priorities <= 0:
                return 'Blocked'
            
            for priority in range(max_priorities):
                list_addr = ready_lists_sym['address'] + priority * list_size
                if self._is_tcb_in_list(tcb_addr, list_addr, elf_parser, dump_reader, is_32bit):
                    return 'Ready'
        
        suspended_list_sym = elf_parser.get_symbol_by_name('xSuspendedTaskList')
        if suspended_list_sym and self._is_tcb_in_list(tcb_addr, suspended_list_sym['address'], elf_parser, dump_reader, is_32bit):
            return 'Suspended'
        
        delayed_list1_sym = elf_parser.get_symbol_by_name('xDelayedTaskList1')
        if delayed_list1_sym and self._is_tcb_in_list(tcb_addr, delayed_list1_sym['address'], elf_parser, dump_reader, is_32bit):
            return 'Blocked(Time)'
        
        delayed_list2_sym = elf_parser.get_symbol_by_name('xDelayedTaskList2')
        if delayed_list2_sym and self._is_tcb_in_list(tcb_addr, delayed_list2_sym['address'], elf_parser, dump_reader, is_32bit):
            return 'Blocked(Time)'
        
        return 'Blocked'
    
    def _is_tcb_in_list(self, tcb_addr: int, list_addr: int, elf_parser, dump_reader, is_32bit: bool) -> bool:
        """检查 TCB 是否在指定的 FreeRTOS List_t 中。
        
        从 xListEnd.pxNext 开始遍历（而非 pxIndex），
        pxIndex 是 round-robin 调度提示，不是链表头。
        """
        tcb_struct = elf_parser.get_struct_type('TCB_t')
        if not tcb_struct:
            return False
        
        list_struct = elf_parser.get_struct_type('List_t')
        if not list_struct:
            return False
        
        state_list_item_offset = elf_parser.get_member_offset('TCB_t', 'xStateListItem', 4)
        
        # 从 xListEnd.pxNext 开始遍历
        pxnext_offset = elf_parser.get_member_offset('ListItem_t', 'pxNext', 4)
        xlist_end_offset = elf_parser.get_member_offset('List_t', 'xListEnd', 8)
        xlist_end_addr = list_addr + xlist_end_offset
        
        first_item_addr = dump_reader.read_pointer(xlist_end_addr + pxnext_offset, is_32bit)
        if not first_item_addr:
            return False
        
        if first_item_addr == xlist_end_addr:
            return False
        
        current_ptr = first_item_addr
        visited = set()
        
        while current_ptr and current_ptr not in visited:
            visited.add(current_ptr)
            
            if current_ptr == xlist_end_addr:
                break
            
            item_tcb_addr = current_ptr - state_list_item_offset
            if item_tcb_addr == tcb_addr:
                return True
            
            next_ptr = dump_reader.read_pointer(current_ptr + pxnext_offset, is_32bit)
            if next_ptr in visited:
                break
            current_ptr = next_ptr
        
        return False
    
    def _get_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
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
        if not list_struct:
            return tasks
        list_size = list_struct.get('byte_size', 0)
        if list_size <= 0:
            return tasks
        
        max_priorities = self._get_config_max_priorities(elf_parser)
        if max_priorities <= 0:
            return tasks
        
        tcb_struct = elf_parser.get_struct_type('TCB_t')
        state_list_item_offset = elf_parser.get_member_offset('TCB_t', 'xStateListItem', 4)
        
        for priority in range(max_priorities):
            list_addr = ready_lists_addr + priority * list_size
            
            ux_number_of_items = dump_reader.read_uint32(list_addr)
            if ux_number_of_items == 0 or ux_number_of_items is None:
                continue
            
            for accessor in walk_doubly_linked_list(
                elf_parser, dump_reader, list_struct, tcb_struct,
                list_addr, 'pxNext', 'pxPrevious', state_list_item_offset,
                max_nodes=ux_number_of_items * 2
            ):
                task_info = self._parse_tcb_with_context(accessor, elf_parser, dump_reader, is_32bit)
                if task_info:
                    tasks.append(task_info)
        
        suspended_list_sym = elf_parser.get_symbol_by_name('xSuspendedTaskList')
        if suspended_list_sym:
            for accessor in walk_doubly_linked_list(
                elf_parser, dump_reader, list_struct, tcb_struct,
                suspended_list_sym['address'], 'pxNext', 'pxPrevious', state_list_item_offset
            ):
                task_info = self._parse_tcb_with_context(accessor, elf_parser, dump_reader, is_32bit)
                if task_info:
                    tasks.append(task_info)
        
        delayed_list1_sym = elf_parser.get_symbol_by_name('xDelayedTaskList1')
        if delayed_list1_sym:
            for accessor in walk_doubly_linked_list(
                elf_parser, dump_reader, list_struct, tcb_struct,
                delayed_list1_sym['address'], 'pxNext', 'pxPrevious', state_list_item_offset
            ):
                task_info = self._parse_tcb_with_context(accessor, elf_parser, dump_reader, is_32bit)
                if task_info:
                    tasks.append(task_info)
        
        delayed_list2_sym = elf_parser.get_symbol_by_name('xDelayedTaskList2')
        if delayed_list2_sym:
            for accessor in walk_doubly_linked_list(
                elf_parser, dump_reader, list_struct, tcb_struct,
                delayed_list2_sym['address'], 'pxNext', 'pxPrevious', state_list_item_offset
            ):
                task_info = self._parse_tcb_with_context(accessor, elf_parser, dump_reader, is_32bit)
                if task_info:
                    tasks.append(task_info)
        
        # Deduplicate by TCB address: a task may appear in multiple lists
        # when the delayed/suspended list overlaps with the ready list array.
        seen = set()
        deduped = []
        for task in tasks:
            addr = task.get('address')
            if addr and addr not in seen:
                seen.add(addr)
                deduped.append(task)
        
        # 降级策略：当链表解析未发现任何任务时，尝试扫描 Data/BSS 段
        if not deduped:
            logger.warning("No tasks found via linked list traversal, falling back to BSS/Data scan")
            deduped = self._scan_bss_for_tcbs(elf_parser, dump_reader, is_32bit, max_priorities)
        
        return deduped
    
    def _scan_bss_for_tcbs(self, elf_parser, dump_reader, is_32bit: bool, max_priorities: int) -> List[Dict[str, Any]]:
        """降级策略：扫描 Data/BSS 段寻找 TCB_t 特征模式。
        
        当链表遍历失败时（如链表头指针损坏），尝试在内存中按 TCB_t 大小
        扫描数据段，通过验证任务名称可打印性和优先级合法性来识别 TCB。
        
        这是防御性降级，仅在主解析路径失败时触发。
        """
        tcb_struct = elf_parser.get_struct_type('TCB_t')
        if not tcb_struct:
            return []
        
        tcb_size = tcb_struct.get('byte_size', 0)
        if tcb_size <= 0 or tcb_size > 4096:
            return []
        
        from core.elf_parser.struct_accessor import StructAccessor
        
        tasks = []
        seen = set()
        
        # 扫描 dump 的所有内存区域
        for region in dump_reader.memory_regions:
            # 每次扫描步进为 tcb_size（对齐扫描）
            for offset in range(0, region.size - tcb_size, tcb_size):
                addr = region.start_addr + offset
                if addr in seen:
                    continue
                seen.add(addr)
                
                view_node = elf_parser.read_struct_as_node(tcb_struct, addr, dump_reader)
                if not view_node:
                    continue
                
                accessor = StructAccessor(view_node, dump_reader, elf_parser)
                
                # 快速验证：任务名称必须可打印
                task_name = accessor.get_string('pcTaskName')
                if not task_name:
                    continue
                task_name = task_name.split('\x00')[0]
                if not task_name or not all(0x20 <= ord(c) <= 0x7E for c in task_name):
                    continue
                
                # 优先级必须在合法范围内
                priority = accessor.get_int('uxPriority')
                if priority >= max_priorities:
                    continue
                
                # 栈指针必须非零且在合法内存区域
                stack_start = accessor.get_ptr('pxStack')
                if stack_start <= 0:
                    continue
                if dump_reader.get_memory_region(stack_start) is None:
                    continue
                
                result = self._parse_tcb(accessor, elf_parser, dump_reader, is_32bit, max_priorities)
                if result:
                    tasks.append(result)
        
        logger.info("BSS/Data scan found %d potential TCBs", len(tasks))
        return tasks
    
    def _parse_tcb_with_context(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        tcb_addr = accessor.address if accessor else 0
        if tcb_addr <= 0:
            return None
        
        # 地址有效性检查：验证 TCB 地址在 dump 的内存区域内
        if dump_reader:
            region = dump_reader.get_memory_region(tcb_addr)
            if not region:
                return None
        
        max_priorities = self._get_config_max_priorities(elf_parser)
        if max_priorities <= 0:
            return None
        
        result = self._parse_tcb(accessor, elf_parser, dump_reader, is_32bit, max_priorities)
        if not result:
            return None
        
        # 栈地址有效性检查：验证 pxStack 在合法 RAM 范围内
        if result.get('stack_start') and result['stack_start'] > 0:
            stack_region = dump_reader.get_memory_region(result['stack_start'])
            if not stack_region:
                logger.debug("TCB 0x%x: stack_start 0x%x not in any valid memory region",
                             tcb_addr, result['stack_start'])
                # 不丢弃该 TCB，仅标记栈地址无效
                result['stack_valid'] = False
            else:
                result['stack_valid'] = True
        
        return result
    
    def _parse_tcb(self, accessor, elf_parser, dump_reader, is_32bit: bool, max_priorities: int) -> Optional[Dict[str, Any]]:
        result = {
            'address': accessor.address,
            'name': accessor.get_string('pcTaskName'),
            'state': '',
            'priority': accessor.get_int('uxPriority'),
            'base_priority': accessor.get_int('uxBasePriority'),
            'stack_start': accessor.get_ptr('pxStack'),
            'stack_end': accessor.get_ptr('pxEndOfStack'),
            'stack_size': 0,
            'stack_usage': 0,
            'stack_used_bytes': 0,
            'current_pc': 0,
            'current_function': '',
            'current_sp': 0,
            'mutexes_held': accessor.get_int('uxMutexesHeld'),
        }
        
        # Sanitize task name
        result['name'] = result['name'].split('\x00')[0].split('\xff')[0]
        result['name'] = ''.join(c for c in result['name'] if 0x20 <= ord(c) <= 0x7E)
        result['name'] = result['name'][:16]
        
        # Validate priority
        if result['priority'] >= max_priorities:
            return None
        
        # Read pxTopOfStack for current PC
        top_of_stack = accessor.get_ptr('pxTopOfStack')
        if top_of_stack:
            result['current_sp'] = top_of_stack
            result['current_pc'] = dump_reader.read_pointer_or_zero(
                top_of_stack + _FREERTOS_PC_OFFSET_IN_STACK_FRAME, is_32bit)
        
        # 计算栈使用率
        if result['stack_start'] and result['current_sp']:
            result['stack_used_bytes'] = abs(result['current_sp'] - result['stack_start'])
            if result['stack_end']:
                result['stack_size'] = abs(result['stack_start'] - result['stack_end'])
                result['stack_usage'] = round(calculate_stack_usage(
                    result['stack_start'], result['stack_end'], result['current_sp'], result['stack_size']
                ), 1)
            else:
                result['stack_size'] = 0
                result['stack_usage'] = result['stack_used_bytes']
        
        if result['current_pc']:
            func_info = elf_parser.find_function_by_address(result['current_pc'])
            if func_info:
                result['current_function'] = func_info.get('name', '')
        
        result['state'] = self._get_task_state(accessor.address, elf_parser, dump_reader, is_32bit)
        result['state_name'] = result['state']
        
        return result
    
    def _get_handle_based_resources(self, context: Dict[str, Any], handle_types: List[str],
                                     struct_name: str, expected_classification: str,
                                     parse_func) -> List[Dict[str, Any]]:
        """通用句柄驱动资源发现方法。

        Args:
            context: 执行上下文
            handle_types: 句柄类型列表（如 ['SemaphoreHandle_t']）
            struct_name: 目标结构体名称
            expected_classification: 期望的分类类型（用于过滤），None 表示不过滤
            parse_func: 解析函数，接收 (accessor, elf_parser, dump_reader, is_32bit)

        Returns:
            资源列表
        """
        resources = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return resources
        
        is_32bit = elf_parser.is_32bit()
        target_struct = elf_parser.get_struct_type(struct_name)
        if not target_struct:
            return resources
        
        handles = self._discover_handles_by_type(elf_parser, handle_types)
        
        from core.elf_parser.struct_accessor import StructAccessor
        
        for h in handles:
            obj_addr = dump_reader.read_pointer(h['address'], is_32bit)
            if not obj_addr:
                continue
            
            if expected_classification is not None:
                classification = self._classify_queue_object(obj_addr, target_struct, dump_reader, is_32bit, elf_parser)
                if classification != expected_classification:
                    continue
            
            view_node = elf_parser.read_struct_as_node(target_struct, obj_addr, dump_reader)
            if view_node:
                accessor = StructAccessor(view_node, dump_reader, elf_parser)
                resource_info = parse_func(accessor, elf_parser, dump_reader, is_32bit)
                if resource_info:
                    resource_info['name'] = h['name']
                    resources.append(resource_info)
        
        return resources
    
    def _get_semaphores(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        def filter_fn(accessor, elf_parser, dump_reader, is_32bit):
            sem_info = self._parse_semaphore(accessor, elf_parser, dump_reader, is_32bit)
            return sem_info if sem_info and sem_info['max_count'] > 0 else None
        
        return self._get_handle_based_resources(
            context,
            ['SemaphoreHandle_t'],
            'QueueDefinition',
            'semaphore',
            filter_fn
        )
    
    def _classify_queue_object(self, obj_addr: int, queue_struct: Dict[str, Any],
                                dump_reader, is_32bit: bool, elf_parser) -> str:
        """基于 QueueDefinition 结构体字段分类对象类型。
        
        不依赖变量名称，仅通过结构体字段值判断：
        - uxItemSize > 0 → queue
        - uxItemSize == 0:
          - uxLength > 1 → semaphore (counting)
          - uxLength == 1:
            - pcHead == NULL → mutex（FreeRTOS 互斥锁不分配数据存储）
            - pxMutexHolder 非零 → mutex（已被持有的互斥锁）
            - 否则 → semaphore (binary)
        
        Returns: 'queue', 'semaphore', 或 'mutex'
        """
        from core.elf_parser.struct_accessor import StructAccessor
        
        view_node = elf_parser.read_struct_as_node(queue_struct, obj_addr, dump_reader)
        if not view_node:
            logger.warning("Cannot classify queue object at 0x%x: struct read failed, DWARF required", obj_addr)
            return 'semaphore'
        accessor = StructAccessor(view_node, dump_reader, elf_parser)
        ux_item_size = accessor.get_int('uxItemSize')
        ux_length = accessor.get_int('uxLength')
        pc_head = accessor.get_ptr('pcHead')
        px_mutex_holder = accessor.get_ptr('pxMutexHolder')
        
        if ux_item_size > 0:
            return 'queue'
        
        if ux_length > 1:
            return 'semaphore'
        
        # uxLength == 1 and uxItemSize == 0
        # FreeRTOS 互斥锁：pcHead == NULL（不分配数据存储）
        if pc_head == 0:
            return 'mutex'
        
        if px_mutex_holder != 0:
            return 'mutex'
        
        return 'semaphore'
    
    def _parse_semaphore(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': accessor.address,
            'name': '',
            'count': accessor.get_int('uxMessagesWaiting'),
            'max_count': accessor.get_int('uxLength'),
            'type': 'binary_semaphore',
        }
        item_size = accessor.get_int('uxItemSize')
        if item_size == 0:
            result['type'] = 'binary_semaphore'
        else:
            result['type'] = 'counting_semaphore'
        return result
    
    def _get_mutexes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        def filter_fn(accessor, elf_parser, dump_reader, is_32bit):
            mutex_info = self._parse_mutex(accessor, elf_parser, dump_reader, is_32bit)
            return mutex_info if mutex_info and mutex_info['count'] >= 0 else None
        
        return self._get_handle_based_resources(
            context,
            ['SemaphoreHandle_t'],
            'QueueDefinition',
            'mutex',
            filter_fn
        )
    
    def _parse_mutex(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        owner = accessor.get_ptr('pxMutexHolder')
        result = {
            'address': accessor.address,
            'name': '',
            'owner': owner,
            'owner_info': None,
            'owner_name': '',
            'count': accessor.get_int('uxMessagesWaiting'),
            'priority_ceiling': 0,
            'type': 'mutex',
        }
        
        if owner != 0 and elf_parser:
            try:
                tcb_struct = elf_parser.get_struct_type('TCB_t')
                if tcb_struct:
                    thread_view = elf_parser.read_struct_as_node(tcb_struct, owner, dump_reader)
                    if thread_view:
                        from core.elf_parser.struct_accessor import StructAccessor
                        owner_accessor = StructAccessor(thread_view, dump_reader, elf_parser)
                        owner_name = owner_accessor.get_string('pcTaskName')
                        if owner_name:
                            result['owner_info'] = {
                                'address': owner,
                                'name': owner_name.split('\x00')[0].strip(),
                            }
                            result['owner_name'] = result['owner_info']['name']
            except Exception:
                pass
        
        return result
    
    def _get_queues(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._get_handle_based_resources(
            context,
            ['QueueHandle_t'],
            'QueueDefinition',
            'queue',
            self._parse_queue
        )
    
    def _parse_queue(self, accessor, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        return {
            'address': accessor.address,
            'name': '',
            'messages': accessor.get_int('uxMessagesWaiting'),
            'max_messages': accessor.get_int('uxLength'),
            'message_size': accessor.get_int('uxItemSize'),
        }
    
    def _get_timers(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        timers = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return timers
        
        is_32bit = elf_parser.is_32bit()
        
        # 通过 DWARF 类型发现 TimerHandle_t 句柄（不依赖变量名称关键词）
        timer_handle_map = {}
        handles = self._discover_handles_by_type(elf_parser, ['TimerHandle_t'])
        for h in handles:
            timer_ptr = dump_reader.read_pointer(h['address'], is_32bit)
            if timer_ptr:
                timer_handle_map[timer_ptr] = h['name']
        
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
        
        list_struct = elf_parser.get_struct_type('List_t')
        if not list_struct:
            return timers
        
        timer_struct = elf_parser.get_struct_type('Timer_t')
        if not timer_struct:
            logger.warning("Cannot parse timer list: Timer_t struct missing from DWARF")
            return []
        
        from core.elf_parser.struct_accessor import StructAccessor
        
        timer_list_item_offset = elf_parser.get_member_offset('Timer_t', 'xTimerListItem', 4)
        
        # 从 xListEnd.pxNext 开始遍历（而非 pxIndex）
        pxnext_offset = elf_parser.get_member_offset('ListItem_t', 'pxNext', 4)
        xlist_end_offset = elf_parser.get_member_offset('List_t', 'xListEnd', 8)
        xlist_end_addr = list_addr + xlist_end_offset
        
        first_item_addr = dump_reader.read_pointer(xlist_end_addr + pxnext_offset, is_32bit)
        if not first_item_addr or first_item_addr == xlist_end_addr:
            return timers
        
        current_ptr = first_item_addr
        visited = set()
        visited.add(current_ptr)
        
        while current_ptr:
            timer_addr = current_ptr - timer_list_item_offset
            view_node = elf_parser.read_struct_as_node(timer_struct, timer_addr, dump_reader)
            if view_node:
                accessor = StructAccessor(view_node, dump_reader, elf_parser)
                timer_info = self._parse_timer(accessor, elf_parser, dump_reader, is_32bit, timer_handle_map)
                if timer_info:
                    timers.append(timer_info)
            
            next_ptr = dump_reader.read_pointer(current_ptr + pxnext_offset, is_32bit)
            if not next_ptr or next_ptr in visited or next_ptr == xlist_end_addr:
                break
            
            visited.add(next_ptr)
            current_ptr = next_ptr
        
        return timers
    
    def _parse_timer(self, accessor, elf_parser, dump_reader, is_32bit: bool, timer_handle_map: Dict[int, str] = None) -> Optional[Dict[str, Any]]:
        timer_addr = accessor.address
        result = {
            'address': timer_addr,
            'name': '',
            'period_ticks': accessor.get_int('xTimerPeriodInTicks'),
            'ticks_remaining': 0,
            'active': False,
            'auto_reload': False,
        }
        
        if timer_handle_map and timer_addr in timer_handle_map:
            result['name'] = timer_handle_map[timer_addr]
        
        if not result['name']:
            result['name'] = accessor.get_string('pcTimerName')
        
        status = accessor.get_int('ucStatus')
        result['active'] = (status & 1) != 0
        result['auto_reload'] = (status & 2) != 0
        
        if result['name'] and not result['name'].isprintable():
            result['name'] = ''
        
        return result
    
    def _get_events(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        event_groups = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return event_groups
        
        is_32bit = elf_parser.is_32bit()
        
        # 通过 DWARF 类型发现 EventGroupHandle_t 句柄（不依赖变量名称）
        handles = self._discover_handles_by_type(elf_parser, ['EventGroupHandle_t'])
        
        for h in handles:
            event_addr = dump_reader.read_pointer(h['address'], is_32bit)
            if event_addr:
                event_info = self._parse_event_group(event_addr, elf_parser, dump_reader, is_32bit)
                if event_info:
                    event_info['name'] = h['name']
                    event_groups.append(event_info)
        
        return event_groups
    
    def _parse_event_group(self, event_addr: int, elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
        result = {
            'address': event_addr,
            'name': '',
            'bits': 0,
            'suspended_count': 0,
        }
        event_struct = elf_parser.get_struct_type('EventGroup_t')
        if event_struct:
            from core.elf_parser.struct_accessor import StructAccessor
            view_node = elf_parser.read_struct_as_node(event_struct, event_addr, dump_reader)
            if view_node:
                accessor = StructAccessor(view_node, dump_reader, elf_parser)
                result['bits'] = accessor.get_int('uxEventBits')
        else:
            result['bits'] = dump_reader.read_uint32(event_addr) or 0
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
        
        heap_stats_struct = elf_parser.get_struct_type('HeapStats_t')
        if not heap_stats_struct:
            logger.warning("HeapStats_t struct missing from DWARF, cannot parse heap info")
            return {}
        
        from core.elf_parser.struct_accessor import StructAccessor
        
        view_node = elf_parser.read_struct_as_node(heap_stats_struct, heap_stats_addr, dump_reader)
        if not view_node:
            return {}
        
        accessor = StructAccessor(view_node, dump_reader, elf_parser)
        
        heap_info = {
            'address': heap_stats_addr,
            'total_bytes': accessor.get_int('xTotalSize'),
            'free_bytes': accessor.get_int('xFreeBytesRemaining'),
            'largest_free_block': accessor.get_int('xLargestFreeBlock'),
            'minimum_free_bytes': accessor.get_int('xMinimumEverFreeBytesRemaining'),
            'allocation_count': accessor.get_int('xNumberOfSuccessfulAllocations'),
            'free_count': accessor.get_int('xNumberOfSuccessfulFrees'),
        }
        
        if heap_info['total_bytes'] > 0:
            heap_info['usage_percent'] = (heap_info['total_bytes'] - heap_info['free_bytes']) / heap_info['total_bytes'] * 100
        
        return heap_info
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'tasks': self.get_resource('tasks', context),
            'semaphores': self.get_resource('semaphores', context),
            'mutexes': self.get_resource('mutexes', context),
            'queues': self.get_resource('queues', context),
            'timers': self.get_resource('timers', context),
            'events': self.get_resource('events', context),
            'heap': self.get_heap_info(context),
        }
