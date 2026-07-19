import logging
from enum import Enum
from typing import Dict, List, Optional, Any, Callable

from plugins.base import Plugin

logger = logging.getLogger(__name__)

# ============================================================================
# FreeRTOS List_t 结构体布局常量
# 这些值源于 FreeRTOS 内核源码中 ListItem_t / MiniListItem_t 的固定布局
# ============================================================================

# MiniListItem_t 中 pxNext 的偏移量（MiniListItem_t 只有 xItemValue 和 pxNext 两个字段）
#   TickType_t xItemValue;  // offset 0
#   ListItem_t *pxNext;     // offset 4
_FREERTOS_LIST_ITEM_PX_NEXT_OFFSET = 4


class ResourceType(str, Enum):
    TASKS = 'tasks'
    MUTEXES = 'mutexes'
    SEMAPHORES = 'semaphores'
    QUEUES = 'queues'
    EVENTS = 'events'
    TIMERS = 'timers'
    BLOCK_POOLS = 'block_pools'
    BYTE_POOLS = 'byte_pools'
    TEST_POINTS = 'test_points'
    ASSERT_INFO = 'assert_info'


RESOURCE_TYPE_MAP = {
    'task': ResourceType.TASKS,
    'mutex': ResourceType.MUTEXES,
    'semaphore': ResourceType.SEMAPHORES,
    'queue': ResourceType.QUEUES,
    'event': ResourceType.EVENTS,
    'timer': ResourceType.TIMERS,
    'block_pool': ResourceType.BLOCK_POOLS,
    'byte_pool': ResourceType.BYTE_POOLS,
    'test_point': ResourceType.TEST_POINTS,
}


def normalize_resource_type(resource_type: str) -> str:
    if not resource_type:
        return resource_type
    try:
        return ResourceType(resource_type).value
    except ValueError:
        return RESOURCE_TYPE_MAP.get(resource_type, resource_type)


class RTOSPlugin(Plugin):
    def __init__(self, name: str, version: str, os_name: str, os_version: str, description: str = ""):
        super().__init__(name, version, description)
        self.os_name = os_name
        self.os_version = os_version
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        self._elf_parser = context.get('elf_parser')
        self._dump_reader = context.get('dump_reader')
        self._profile = context.get('profile')
        self._context = context
        return True
    
    def get_resource_types(self) -> List[str]:
        return []
    
    def get_resource(self, resource_type: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        normalized_type = normalize_resource_type(resource_type)
        return []
    
    def get_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('tasks', context)
    
    def get_semaphores(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('semaphores', context)
    
    def get_mutexes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('mutexes', context)
    
    def get_queues(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('queues', context)
    
    def get_timers(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('timers', context)
    
    def get_events(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('events', context)
    
    def get_heap_info(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {}
    
    def get_display_config(self) -> Dict[str, Any]:
        return {
            'display_type': 'tree',
            'title': f"{self.os_name} {self.os_version}",
            'view_config': {
                'expand_level': 2,
                'show_address': True,
            }
        }
    
    def _get_elf_parser(self):
        return self._elf_parser
    
    def _get_dump_reader(self):
        return self._dump_reader
    
    def _is_32bit(self) -> bool:
        return self._elf_parser.is_32bit() if self._elf_parser else True
    
    def _find_member_offset(self, struct_type: Dict[str, Any], member_name: str, default_offset: int = 0) -> int:
        if not struct_type:
            return default_offset
        for member in struct_type.get('members', []):
            if member.get('name') == member_name:
                return member.get('offset', default_offset)
        return default_offset
    
    def _find_member(self, struct_type: Dict[str, Any], member_name: str) -> Optional[Dict[str, Any]]:
        if not struct_type:
            return None
        for member in struct_type.get('members', []):
            if member.get('name') == member_name:
                return member
        return None
    
    def _read_string(self, addr: int, max_length: int = 32) -> str:
        if not self._dump_reader or addr <= 0:
            return ''
        try:
            return self._dump_reader.read_string(addr, max_length) or ''
        except Exception:
            return ''

    def _read_resource_name(self, addr: int, name_ptr_addr: int,
                            is_32bit: bool = True, max_length: int = 32) -> str:
        """Read a resource name from a pointer field.

        Tries to read the string from the dump at the pointer address first.
        If the dump read fails (e.g., name is in .rodata not in the dump),
        falls back to reading from the ELF file.

        Args:
            addr: Base address of the resource struct.
            name_ptr_addr: Address of the name pointer field (addr + offset).
            is_32bit: Whether the target is 32-bit.
            max_length: Maximum string length.
        """
        name_addr = self._dump_reader.read_pointer(name_ptr_addr, is_32bit)
        if not name_addr:
            return ''

        name = self._read_string(name_addr, max_length)
        if name:
            return name

        # Fallback: try reading from ELF (e.g., .rodata section)
        if self._elf_parser:
            elf_data = self._elf_parser.read_memory_from_elf(name_addr, max_length)
            if elf_data:
                null_pos = elf_data.find(b'\x00')
                if null_pos >= 0:
                    elf_data = elf_data[:null_pos]
                try:
                    return elf_data.decode('utf-8')
                except UnicodeDecodeError:
                    return elf_data.decode('latin-1')
        return ''
    
    def _walk_singly_linked_list(self,
                                symbol_name: str,
                                struct_name: str,
                                next_field_name: str,
                                parse_func: Callable,
                                context: Dict[str, Any]) -> List[Dict[str, Any]]:
        elf_parser = context.get('elf_parser') or self._elf_parser
        dump_reader = context.get('dump_reader') or self._dump_reader

        if not elf_parser or not dump_reader:
            logger.warning(f"Missing elf_parser or dump_reader for {symbol_name}")
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

        next_offset = self._find_member_offset(struct_type, next_field_name)

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
    
    def _walk_doubly_linked_list(self,
                                list_addr: int,
                                struct_type: Dict[str, Any],
                                list_struct_type: Dict[str, Any],
                                item_to_struct_offset: int,
                                parse_func: Callable,
                                context: Dict[str, Any],
                                list_end_addr: Optional[int] = None) -> List[Dict[str, Any]]:
        elf_parser = context.get('elf_parser') or self._elf_parser
        dump_reader = context.get('dump_reader') or self._dump_reader

        if not elf_parser or not dump_reader:
            return []

        is_32bit = elf_parser.is_32bit()

        if not list_struct_type:
            logger.warning("List_t struct type not found")
            return []

        # In FreeRTOS List_t, xListEnd is the sentinel anchor at offset 8.
        # pxIndex (offset 4) is a scheduling hint used for round-robin,
        # not the list head. The correct traversal starts from xListEnd.pxNext
        # (offset 12 within List_t = offset 4 within MiniListItem_t).
        xlist_end_offset = self._find_member_offset(list_struct_type, 'xListEnd', 8)
        xlist_end_addr = list_addr + xlist_end_offset

        if list_end_addr is None:
            list_end_addr = xlist_end_addr

        # Read xListEnd.pxNext (offset 4 within MiniListItem_t)
        first_item_addr = dump_reader.read_pointer(xlist_end_addr + 4, is_32bit)
        if not first_item_addr:
            return []

        if first_item_addr == list_end_addr:
            return []

        current_ptr = first_item_addr
        visited = set()
        results = []

        while current_ptr and current_ptr not in visited:
            visited.add(current_ptr)

            if current_ptr == list_end_addr:
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
    
    def _calculate_stack_usage_highest(self,
                                       stack_start: int,
                                       stack_size: int,
                                       stack_highest_ptr: int,
                                       stack_current: int = 0) -> float:
        if not stack_start or stack_size <= 0:
            return 0.0

        if stack_highest_ptr:
            used = abs(stack_highest_ptr - stack_start)
        elif stack_current:
            used = abs(stack_current - stack_start)
        else:
            return 0.0

        return used / stack_size * 100 if stack_size > 0 else 0.0
    
    def _normalize_task_state(self, state: int, state_map: Dict[int, str]) -> str:
        return state_map.get(state, f'UNKNOWN({state})')
    
    def _normalize_resource_type(self, resource_type: str) -> str:
        return normalize_resource_type(resource_type)
