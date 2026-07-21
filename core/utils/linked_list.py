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
from typing import Generator, Optional, Dict, Any

logger = logging.getLogger(__name__)


def walk_singly_linked_list(
    elf_parser,
    dump_reader,
    struct_type: Dict[str, Any],
    head_addr: int,
    next_field: str,
    max_nodes: int = 10000
) -> Generator:
    if not head_addr:
        return
    
    visited = set()
    current_ptr = head_addr
    node_count = 0
    
    from core.elf_parser.struct_accessor import StructAccessor
    
    while current_ptr and current_ptr not in visited:
        if node_count >= max_nodes:
            logger.warning(f"walk_singly_linked_list: reached max_nodes={max_nodes}, stopping")
            break
        
        visited.add(current_ptr)
        node_count += 1
        
        view_node = elf_parser.read_struct_as_node(struct_type, current_ptr, dump_reader)
        if view_node is None:
            break
        
        accessor = StructAccessor(view_node, dump_reader, elf_parser)
        yield accessor
        
        current_ptr = accessor.get_pointer(next_field)


def walk_doubly_linked_list(
    elf_parser,
    dump_reader,
    list_node_type: Dict[str, Any],
    item_struct_type: Dict[str, Any],
    list_head_addr: int,
    next_field: str,
    prev_field: str,
    item_to_struct_offset: int,
    max_nodes: int = 10000
) -> Generator:
    if not list_head_addr:
        return
    
    is_32bit = elf_parser.is_32bit()
    
    xlist_end_offset = elf_parser.get_member_offset('List_t', 'xListEnd', 8)
    xlist_end_addr = list_head_addr + xlist_end_offset
    
    pxnext_offset = elf_parser.get_member_offset('ListItem_t', 'pxNext', 4)
    first_item_addr = dump_reader.read_pointer(xlist_end_addr + pxnext_offset, is_32bit)
    if not first_item_addr or first_item_addr == xlist_end_addr:
        return
    
    visited = set()
    current_ptr = first_item_addr
    node_count = 0
    
    from core.elf_parser.struct_accessor import StructAccessor
    
    while current_ptr and current_ptr not in visited:
        if node_count >= max_nodes:
            logger.warning(f"walk_doubly_linked_list: reached max_nodes={max_nodes}, stopping")
            break
        
        visited.add(current_ptr)
        node_count += 1
        
        if current_ptr == xlist_end_addr:
            break
        
        struct_addr = current_ptr - item_to_struct_offset
        if struct_addr <= 0:
            break
        
        view_node = elf_parser.read_struct_as_node(item_struct_type, struct_addr, dump_reader)
        if view_node is None:
            next_ptr = dump_reader.read_pointer(current_ptr + pxnext_offset, is_32bit)
            current_ptr = next_ptr
            continue
        
        accessor = StructAccessor(view_node, dump_reader, elf_parser)
        yield accessor
        
        next_ptr = dump_reader.read_pointer(current_ptr + pxnext_offset, is_32bit)
        if not next_ptr or next_ptr == 0:
            break
        current_ptr = next_ptr