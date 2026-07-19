import logging
from typing import Dict, List, Optional, Any, Callable
from core.plugin_manager import OSPlugin

logger = logging.getLogger(__name__)


class RTOSPlugin(OSPlugin):
    def __init__(self, name: str, version: str, os_name: str, os_version: str, description: str = ""):
        super().__init__(name, version, os_name, os_version, description)
    
    def _walk_created_list(self, 
                          symbol_name: str, 
                          struct_name: str, 
                          next_field_name: str,
                          parse_func: Callable[[int, Dict[str, Any], Any, Any, bool], Optional[Dict[str, Any]]],
                          context: Dict[str, Any]) -> List[Dict[str, Any]]:
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
