import logging
from typing import Dict, List, Optional, Any, Callable

from plugins.base import OSPlugin, normalize_resource_type


class RTOSPlugin(OSPlugin):
    def initialize(self, context: Dict[str, Any]) -> bool:
        self._elf_parser = context.get('elf_parser')
        self._dump_reader = context.get('dump_reader')
        self._profile = context.get('profile')
        self._context = context
        return True

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

        list_item_offset = self._find_member_offset(list_struct_type, 'pxIndex', 4)

        first_item_addr = dump_reader.read_pointer(list_addr + list_item_offset, is_32bit)
        if not first_item_addr:
            return []

        if list_end_addr is None:
            list_end_addr = list_addr + list_item_offset + 4

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

            next_offset = 4
            list_item_struct = elf_parser.get_struct_type('ListItem_t')
            if list_item_struct:
                next_offset = self._find_member_offset(list_item_struct, 'pxNext', 4)

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

logger = logging.getLogger(__name__)


class RTOSPlugin(OSPlugin):
    def initialize(self, context: Dict[str, Any]) -> bool:
        self._elf_parser = context.get('elf_parser')
        self._dump_reader = context.get('dump_reader')
        self._profile = context.get('profile')
        self._context = context
        return True

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

        list_item_offset = self._find_member_offset(list_struct_type, 'pxIndex', 4)

        first_item_addr = dump_reader.read_pointer(list_addr + list_item_offset, is_32bit)
        if not first_item_addr:
            return []

        if list_end_addr is None:
            list_end_addr = list_addr + list_item_offset + 4

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

            next_offset = 4
            list_item_struct = elf_parser.get_struct_type('ListItem_t')
            if list_item_struct:
                next_offset = self._find_member_offset(list_item_struct, 'pxNext', 4)

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
