import logging
from typing import Dict, List, Optional, Any, Callable

from ..base import RTOSPlugin

logger = logging.getLogger(__name__)

# ============================================================================
# FreeRTOS v11 内核常量（基于源码中结构体固定布局）
# 这些值源于 FreeRTOS 内核源码中的结构体定义，不是任意魔术值。
# 当 DWARF 类型信息可用时，优先使用 DWARF 推导的偏移量；
# 这些常量仅作为 DWARF 缺失时的回退。
# ============================================================================

# configMAX_TASK_NAME_LEN 默认值（FreeRTOS 默认配置）
# FreeRTOS 中 pcTaskName 是 char[configMAX_TASK_NAME_LEN] 固定数组
_FREERTOS_MAX_TASK_NAME_LEN = 16

# QueueDefinition 结构体头部大小（4 个指针/整型字段，在 2 个 List_t 之前）
# 结构体布局（32 位）：
#   int8_t *pcHead;              // offset 0,  size 4
#   int8_t *pcTail;              // offset 4,  size 4
#   int8_t *pcWriteTo;           // offset 8,  size 4
#   UBaseType_t uxRecursiveCallCount; // offset 12, size 4
#   List_t xTasksWaitingToSend;   // offset 16, size sizeof(List_t)
#   List_t xTasksWaitingToReceive;// offset 16+sizeof(List_t), size sizeof(List_t)
_FREERTOS_QUEUE_DEF_HEADER_SIZE = 16  # 4 个字段 × 4 字节

# QueueDefinition 中 List_t 成员数量
_FREERTOS_QUEUE_DEF_LIST_COUNT = 2

# pxMutexHolder 相对于 uxMessagesWaiting 的偏移量
# 在 QueueDefinition 中，成员顺序为：
#   uxMessagesWaiting (4 bytes)
#   uxLength (4 bytes)
#   uxItemSize (4 bytes)
#   pxMutexHolder (4 bytes)  ← 偏移 = uxMessagesWaiting + 12
_FREERTOS_MUTEX_HOLDER_OFFSET_FROM_MESSAGES = 12

# pxTopOfStack 中 PC 的偏移量（Cortex-M 异常栈帧中 PC 的位置）
# 注意：此偏移量是架构相关的，不是通用值
# Cortex-M 硬件自动压栈顺序：xPSR, PC, LR, R12, R3, R2, R1, R0
# pxTopOfStack 指向栈顶（最低地址），即 xPSR 的位置
# PC 在 xPSR 之后，偏移为 4
_FREERTOS_PC_OFFSET_IN_STACK_FRAME = 4

# MiniListItem_t 中 pxNext 的偏移量（MiniListItem_t 只有 xItemValue 和 pxNext 两个字段）
#   TickType_t xItemValue;  // offset 0
#   ListItem_t *pxNext;     // offset 4
_FREERTOS_LIST_ITEM_PX_NEXT_OFFSET = 4


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
    
    # ========================================================================
    # FreeRTOS 专用双向链表遍历（从 base.py 下沉）
    # ========================================================================
    
    def _walk_doubly_linked_list(self,
                                list_addr: int,
                                struct_type: Dict[str, Any],
                                list_struct_type: Dict[str, Any],
                                item_to_struct_offset: int,
                                parse_func: Callable,
                                context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """遍历 FreeRTOS List_t 双向链表。
        
        FreeRTOS List_t 中 xListEnd 是哨兵节点（offset 8），
        pxIndex（offset 4）是 round-robin 调度提示，不是链表头。
        正确遍历从 xListEnd.pxNext 开始。
        """
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return []
        
        is_32bit = elf_parser.is_32bit()
        
        if not list_struct_type:
            logger.warning("List_t struct type not found")
            return []
        
        xlist_end_offset = self._find_member_offset(list_struct_type, 'xListEnd', 8)
        xlist_end_addr = list_addr + xlist_end_offset
        
        # 从 xListEnd.pxNext 开始（offset 4 within MiniListItem_t）
        first_item_addr = dump_reader.read_pointer(xlist_end_addr + 4, is_32bit)
        if not first_item_addr:
            return []
        
        if first_item_addr == xlist_end_addr:
            return []
        
        current_ptr = first_item_addr
        visited = set()
        results = []
        
        while current_ptr and current_ptr not in visited:
            visited.add(current_ptr)
            
            if current_ptr == xlist_end_addr:
                break
            
            struct_addr = current_ptr - item_to_struct_offset
            if struct_addr <= 0:
                break
            
            item_info = parse_func(struct_addr, struct_type, elf_parser, dump_reader, is_32bit)
            if item_info:
                results.append(item_info)
            
            next_offset = _FREERTOS_LIST_ITEM_PX_NEXT_OFFSET
            list_item_struct = elf_parser.get_struct_type('ListItem_t')
            if list_item_struct:
                next_offset = self._find_member_offset(list_item_struct, 'pxNext', _FREERTOS_LIST_ITEM_PX_NEXT_OFFSET)
            
            next_ptr = dump_reader.read_pointer(current_ptr + next_offset, is_32bit)
            current_ptr = next_ptr
        
        return results
    
    def _calculate_stack_usage(self,
                              stack_start: int,
                              stack_end: int,
                              current_sp: int,
                              stack_size: int = 0) -> float:
        """计算 FreeRTOS 任务栈使用率（栈向下增长）。
        
        FreeRTOS 在 ARM 上栈向下增长，pxStack 指向栈底（高地址），
        pxEndOfStack 指向栈顶（低地址），pxTopOfStack 指向当前栈顶。
        """
        if not stack_start or not stack_end:
            return 0.0
        
        if stack_size <= 0:
            stack_size = abs(stack_start - stack_end)
        
        if stack_size <= 0:
            return 0.0
        
        if current_sp:
            used = abs(current_sp - min(stack_start, stack_end))
        else:
            return 0.0
        
        return used / stack_size * 100 if stack_size > 0 else 0.0
    
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
        
        state_list_item_offset = self._find_member_offset(tcb_struct, 'xStateListItem', 4)
        
        # 从 xListEnd.pxNext 开始遍历（offset 8 + 4 = 12 within List_t）
        xlist_end_offset = self._find_member_offset(list_struct, 'xListEnd', 8)
        xlist_end_addr = list_addr + xlist_end_offset
        
        first_item_addr = dump_reader.read_pointer(xlist_end_addr + 4, is_32bit)
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
            
            next_ptr = dump_reader.read_pointer(current_ptr + 4, is_32bit)
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
        state_list_item_offset = self._find_member_offset(tcb_struct, 'xStateListItem', 4)
        
        for priority in range(max_priorities):
            list_addr = ready_lists_addr + priority * list_size
            
            ux_number_of_items = dump_reader.read_uint32(list_addr)
            if ux_number_of_items == 0 or ux_number_of_items is None:
                continue
            
            tasks.extend(self._walk_doubly_linked_list(
                list_addr,
                tcb_struct,
                list_struct,
                state_list_item_offset,
                self._parse_tcb_with_context,
                context
            ))
        
        suspended_list_sym = elf_parser.get_symbol_by_name('xSuspendedTaskList')
        if suspended_list_sym:
            tasks.extend(self._walk_doubly_linked_list(
                suspended_list_sym['address'],
                tcb_struct,
                list_struct,
                state_list_item_offset,
                self._parse_tcb_with_context,
                context
            ))
        
        delayed_list1_sym = elf_parser.get_symbol_by_name('xDelayedTaskList1')
        if delayed_list1_sym:
            tasks.extend(self._walk_doubly_linked_list(
                delayed_list1_sym['address'],
                tcb_struct,
                list_struct,
                state_list_item_offset,
                self._parse_tcb_with_context,
                context
            ))
        
        delayed_list2_sym = elf_parser.get_symbol_by_name('xDelayedTaskList2')
        if delayed_list2_sym:
            tasks.extend(self._walk_doubly_linked_list(
                delayed_list2_sym['address'],
                tcb_struct,
                list_struct,
                state_list_item_offset,
                self._parse_tcb_with_context,
                context
            ))
        
        # Deduplicate by TCB address: a task may appear in multiple lists
        # when the delayed/suspended list overlaps with the ready list array.
        seen = set()
        deduped = []
        for task in tasks:
            addr = task.get('address')
            if addr and addr not in seen:
                seen.add(addr)
                deduped.append(task)
        
        return deduped
    
    def _parse_tcb_with_context(self, tcb_addr: int, tcb_struct: Dict[str, Any], 
                               elf_parser, dump_reader, is_32bit: bool) -> Optional[Dict[str, Any]]:
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
        
        return self._parse_tcb(tcb_addr, tcb_struct, elf_parser, dump_reader, is_32bit, max_priorities)
    
    def _parse_tcb(self, tcb_addr: int, tcb_struct: Dict[str, Any], 
                  elf_parser, dump_reader, is_32bit: bool, max_priorities: int) -> Optional[Dict[str, Any]]:
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
            'stack_used_bytes': 0,
            'current_pc': 0,
            'current_function': '',
            'current_sp': 0,
            'mutexes_held': 0,
        }
        
        for member in tcb_struct.get('members', []):
            member_name = member.get('name')
            member_offset = member.get('offset', 0)
            
            if member_name == 'pcTaskName':
                result['name'] = dump_reader.read_string(tcb_addr + member_offset, _FREERTOS_MAX_TASK_NAME_LEN) or ''
                # Sanitize rather than reject: FreeRTOS pcTaskName is a fixed
                # 16-byte char array. Unused bytes may contain 0xFF or other
                # garbage. Truncate at the first null or 0xFF byte, then keep
                # only printable ASCII characters.
                result['name'] = result['name'].split('\x00')[0].split('\xff')[0]
                result['name'] = ''.join(c for c in result['name'] if 0x20 <= ord(c) <= 0x7E)
                result['name'] = result['name'][:16]
            
            elif member_name == 'uxPriority':
                priority = dump_reader.read_uint32(tcb_addr + member_offset)
                if priority is None:
                    return None
                if priority >= max_priorities:
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
                    result['current_pc'] = dump_reader.read_pointer_or_zero(
                        top_of_stack + _FREERTOS_PC_OFFSET_IN_STACK_FRAME, is_32bit)
            
            elif member_name == 'uxMutexesHeld':
                result['mutexes_held'] = dump_reader.read_uint32(tcb_addr + member_offset)
        
        # 计算栈使用率：优先使用 pxEndOfStack（如果 DWARF 中有）
        # pxEndOfStack 仅在 configRECORD_STACK_HIGH_ADDRESS == 1 时存在
        # 某些平台（如 Cortex-R52）可能不包含此字段
        if result['stack_start'] and result['current_sp']:
            # ARM 栈向下增长，pxStack 指向栈底（低地址），pxTopOfStack 指向当前栈顶
            result['stack_used_bytes'] = abs(result['current_sp'] - result['stack_start'])
            if result['stack_end']:
                result['stack_size'] = abs(result['stack_start'] - result['stack_end'])
                if result['stack_size'] > 0:
                    result['stack_usage'] = round(result['stack_used_bytes'] / result['stack_size'] * 100, 1)
                else:
                    result['stack_usage'] = result['stack_used_bytes']
            else:
                # pxEndOfStack 不可用：无法计算总栈大小，显示绝对字节数
                result['stack_size'] = 0
                result['stack_usage'] = result['stack_used_bytes']
        
        if result['current_pc']:
            func_info = elf_parser.find_function_by_address(result['current_pc'])
            if func_info:
                result['current_function'] = func_info.get('name', '')
        
        result['state'] = self._get_task_state(tcb_addr, elf_parser, dump_reader, is_32bit)
        result['state_name'] = result['state']
        
        return result
    
    def _get_semaphores(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        semaphores = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return semaphores
        
        is_32bit = elf_parser.is_32bit()
        queue_struct = elf_parser.get_struct_type('QueueDefinition')
        
        # 通过 DWARF 类型发现 SemaphoreHandle_t 句柄（不依赖变量名称）
        handles = self._discover_handles_by_type(elf_parser, ['SemaphoreHandle_t'])
        
        for h in handles:
            obj_addr = dump_reader.read_pointer(h['address'], is_32bit)
            if not obj_addr:
                continue
            
            # 分类：排除互斥锁和队列
            classification = self._classify_queue_object(obj_addr, queue_struct, dump_reader, is_32bit, elf_parser)
            if classification == 'mutex' or classification == 'queue':
                continue
            
            sem_info = self._parse_semaphore(obj_addr, queue_struct, dump_reader, is_32bit, elf_parser)
            if sem_info and sem_info['max_count'] > 0:
                sem_info['name'] = h['name']
                semaphores.append(sem_info)
        
        return semaphores
    
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
        
        FreeRTOS 内核中 xQueueCreateMutex() 将 pcHead 设为 NULL，
        而 xSemaphoreCreateBinary() 会分配 1 字节存储，pcHead 非 NULL。
        这是结构层面的区分依据，不依赖变量名称。
        
        Returns: 'queue', 'semaphore', 或 'mutex'
        """
        members = queue_struct.get('members', []) if queue_struct else []
        
        ux_item_size = 0
        ux_length = 0
        px_mutex_holder = 0
        pc_head = 0
        
        if members:
            for member in members:
                member_name = member.get('name')
                member_offset = member.get('offset', 0)
                
                if member_name == 'pcHead':
                    pc_head = dump_reader.read_pointer_or_zero(obj_addr + member_offset, is_32bit)
                elif member_name == 'uxItemSize':
                    ux_item_size = dump_reader.read_uint32(obj_addr + member_offset) or 0
                elif member_name == 'uxLength':
                    ux_length = dump_reader.read_uint32(obj_addr + member_offset) or 0
                elif member_name == 'pxMutexHolder':
                    px_mutex_holder = dump_reader.read_pointer_or_zero(obj_addr + member_offset, is_32bit)
        else:
            list_struct = elf_parser.get_struct_type('List_t')
            if not list_struct:
                return 'semaphore'
            list_size = list_struct.get('byte_size', 0)
            if list_size <= 0:
                return 'semaphore'
            
            # DWARF 不可用时，通过固定偏移读取 pcHead（offset 0）
            pc_head = dump_reader.read_pointer_or_zero(obj_addr, is_32bit)
            
            ux_messages_waiting_offset = _FREERTOS_QUEUE_DEF_HEADER_SIZE + _FREERTOS_QUEUE_DEF_LIST_COUNT * list_size
            ux_length_offset = ux_messages_waiting_offset + 4
            ux_item_size_offset = ux_length_offset + 4
            
            ux_item_size = dump_reader.read_uint32(obj_addr + ux_item_size_offset) or 0
            ux_length = dump_reader.read_uint32(obj_addr + ux_length_offset) or 0
        
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
    
    def _parse_semaphore(self, sem_addr: int, queue_struct: Dict[str, Any], 
                        dump_reader, is_32bit: bool, elf_parser) -> Optional[Dict[str, Any]]:
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
            list_struct = elf_parser.get_struct_type('List_t')
            if not list_struct:
                logger.warning("Cannot parse semaphore at 0x%x: List_t struct missing from DWARF", sem_addr)
                return None
            list_size = list_struct.get('byte_size', 0)
            if list_size <= 0:
                logger.warning("Cannot parse semaphore at 0x%x: List_t byte_size is 0", sem_addr)
                return None
            
            # 基于 FreeRTOS QueueDefinition 结构体布局计算偏移量
            # 详见文件顶部 _FREERTOS_QUEUE_DEF_HEADER_SIZE 等常量注释
            ux_messages_waiting_offset = _FREERTOS_QUEUE_DEF_HEADER_SIZE + _FREERTOS_QUEUE_DEF_LIST_COUNT * list_size
            ux_length_offset = ux_messages_waiting_offset + 4
            ux_item_size_offset = ux_length_offset + 4
            
            result['max_count'] = dump_reader.read_uint32(sem_addr + ux_length_offset)
            item_size = dump_reader.read_uint32(sem_addr + ux_item_size_offset)
            result['count'] = dump_reader.read_uint32(sem_addr + ux_messages_waiting_offset)
            
            if result['max_count'] > 1:
                result['type'] = 'counting_semaphore'
            else:
                result['type'] = 'binary_semaphore'
        
        return result
    
    def _get_mutexes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        mutexes = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return mutexes
        
        is_32bit = elf_parser.is_32bit()
        queue_struct = elf_parser.get_struct_type('QueueDefinition')
        
        # 通过 DWARF 类型发现 SemaphoreHandle_t 句柄（不依赖变量名称）
        handles = self._discover_handles_by_type(elf_parser, ['SemaphoreHandle_t'])
        
        for h in handles:
            obj_addr = dump_reader.read_pointer(h['address'], is_32bit)
            if not obj_addr:
                continue
            
            # 分类：仅保留互斥锁
            classification = self._classify_queue_object(obj_addr, queue_struct, dump_reader, is_32bit, elf_parser)
            if classification != 'mutex':
                continue
            
            mutex_info = self._parse_mutex(obj_addr, queue_struct, dump_reader, is_32bit, elf_parser)
            if mutex_info and mutex_info['count'] >= 0:
                mutex_info['name'] = h['name']
                mutexes.append(mutex_info)
        
        return mutexes
    
    def _parse_mutex(self, mutex_addr: int, queue_struct: Dict[str, Any], 
                    dump_reader, is_32bit: bool, elf_parser) -> Optional[Dict[str, Any]]:
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
            list_struct = elf_parser.get_struct_type('List_t')
            if not list_struct:
                logger.warning("Cannot parse mutex at 0x%x: List_t struct missing from DWARF", mutex_addr)
                return None
            list_size = list_struct.get('byte_size', 0)
            if list_size <= 0:
                logger.warning("Cannot parse mutex at 0x%x: List_t byte_size is 0", mutex_addr)
                return None
            
            # 基于 FreeRTOS QueueDefinition 结构体布局计算偏移量
            # 详见文件顶部 _FREERTOS_QUEUE_DEF_HEADER_SIZE 等常量注释
            ux_messages_waiting_offset = _FREERTOS_QUEUE_DEF_HEADER_SIZE + _FREERTOS_QUEUE_DEF_LIST_COUNT * list_size
            px_mutex_holder_offset = ux_messages_waiting_offset + _FREERTOS_MUTEX_HOLDER_OFFSET_FROM_MESSAGES
            
            result['owner'] = dump_reader.read_pointer_or_zero(mutex_addr + px_mutex_holder_offset, is_32bit)
            result['count'] = dump_reader.read_uint32(mutex_addr + ux_messages_waiting_offset)
        
        return result
    
    def _get_queues(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        queues = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return queues
        
        is_32bit = elf_parser.is_32bit()
        queue_struct = elf_parser.get_struct_type('QueueDefinition')
        
        # 通过 DWARF 类型发现 QueueHandle_t 句柄（不依赖变量名称）
        handles = self._discover_handles_by_type(elf_parser, ['QueueHandle_t'])
        
        for h in handles:
            obj_addr = dump_reader.read_pointer(h['address'], is_32bit)
            if not obj_addr:
                continue
            
            # 分类：仅保留真正的队列（排除信号量和互斥锁）
            classification = self._classify_queue_object(obj_addr, queue_struct, dump_reader, is_32bit, elf_parser)
            if classification != 'queue':
                continue
            
            queue_info = self._parse_queue(obj_addr, queue_struct, dump_reader, is_32bit, elf_parser)
            if queue_info:
                queue_info['name'] = h['name']
                queues.append(queue_info)
        
        return queues
    
    def _parse_queue(self, queue_addr: int, queue_struct: Dict[str, Any], 
                    dump_reader, is_32bit: bool, elf_parser) -> Optional[Dict[str, Any]]:
        result = {
            'address': queue_addr,
            'name': '',
            'messages': 0,
            'max_messages': 0,
            'message_size': 0,
        }
        
        members = queue_struct.get('members', []) if queue_struct else []
        
        if members:
            for member in members:
                member_name = member.get('name')
                member_offset = member.get('offset', 0)
                
                if member_name == 'uxMessagesWaiting':
                    result['messages'] = dump_reader.read_uint32(queue_addr + member_offset)
                
                elif member_name == 'uxLength':
                    result['max_messages'] = dump_reader.read_uint32(queue_addr + member_offset)
                
                elif member_name == 'uxItemSize':
                    result['message_size'] = dump_reader.read_uint32(queue_addr + member_offset)
        else:
            list_struct = elf_parser.get_struct_type('List_t')
            if not list_struct:
                logger.warning("Cannot parse queue at 0x%x: List_t struct missing from DWARF", queue_addr)
                return None
            list_size = list_struct.get('byte_size', 0)
            if list_size <= 0:
                logger.warning("Cannot parse queue at 0x%x: List_t byte_size is 0", queue_addr)
                return None
            
            # 基于 FreeRTOS QueueDefinition 结构体布局计算偏移量
            # 详见文件顶部 _FREERTOS_QUEUE_DEF_HEADER_SIZE 等常量注释
            ux_messages_waiting_offset = _FREERTOS_QUEUE_DEF_HEADER_SIZE + _FREERTOS_QUEUE_DEF_LIST_COUNT * list_size
            ux_length_offset = ux_messages_waiting_offset + 4
            ux_item_size_offset = ux_length_offset + 4
            
            result['max_messages'] = dump_reader.read_uint32(queue_addr + ux_length_offset)
            result['message_size'] = dump_reader.read_uint32(queue_addr + ux_item_size_offset)
            result['messages'] = dump_reader.read_uint32(queue_addr + ux_messages_waiting_offset)
        
        return result
    
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
        
        timer_list_item_offset = self._find_member_offset(timer_struct, 'xTimerListItem', 4)
        
        # 从 xListEnd.pxNext 开始遍历（而非 pxIndex）
        xlist_end_offset = self._find_member_offset(list_struct, 'xListEnd', 8)
        xlist_end_addr = list_addr + xlist_end_offset
        
        first_item_addr = dump_reader.read_pointer(xlist_end_addr + 4, is_32bit)
        if not first_item_addr or first_item_addr == xlist_end_addr:
            return timers
        
        current_ptr = first_item_addr
        visited = set()
        visited.add(current_ptr)
        
        while current_ptr:
            timer_addr = current_ptr - timer_list_item_offset
            timer_info = self._parse_timer(timer_addr, elf_parser, dump_reader, is_32bit, timer_handle_map)
            if timer_info:
                timers.append(timer_info)
            
            next_ptr = dump_reader.read_pointer(current_ptr + 4, is_32bit)
            if not next_ptr or next_ptr in visited or next_ptr == xlist_end_addr:
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
            logger.warning("Cannot parse timer at 0x%x: Timer_t struct missing from DWARF", timer_addr)
            return None
        
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
                event_info = self._parse_event_group(event_addr, dump_reader, is_32bit)
                if event_info:
                    event_info['name'] = h['name']
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
            logger.warning("HeapStats_t struct missing from DWARF, cannot parse heap info")
            return {}
        
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
