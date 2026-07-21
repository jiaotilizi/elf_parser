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
import bisect
import logging
import re
import struct
import time
from typing import Dict, List, Optional, Tuple, Any

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection
from elftools.dwarf.dwarfinfo import DWARFInfo
from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE

from .base import ELFParser
from .struct_accessor import ViewNode, StructAccessor

logger = logging.getLogger(__name__)

# DWARF base type encoding constants
_DW_ATE_unsigned = 0x07
_DW_ATE_unsigned_char = 0x08
_DW_ATE_signed = 0x05
_DW_ATE_signed_char = 0x06


class ElftoolsParser(ELFParser):
    # Maximum recursion depth for DWARF type parsing and _read_typed_value.
    # Based on empirical observation of embedded RTOS struct nesting depth;
    # legitimate struct hierarchies rarely exceed 10 levels. A value of 20
    # provides a generous safety margin against infinite recursion from
    # circular type references while never truncating valid data.
    _MAX_RECURSION_DEPTH = 20

    def __init__(self, elf_path: str):
        self.elf_path = elf_path
        self.elffile = None
        self.dwarfinfo = None
        
        self._symbol_cache: Dict[str, Tuple[int, int, str]] = {}
        self._all_symbols_cache: Optional[List[Dict[str, Any]]] = None
        self._cu_cache: List[Tuple[int, int, int]] = []
        self._struct_type_cache: Dict[str, Any] = {}
        
        self._is_32bit = False
        self._address_size = 4
        
        self._segment_cache: List[Dict[str, Any]] = []
        self._sorted_segment_ranges: List[Tuple[int, int, Dict[str, Any]]] = []  # (vaddr, vaddr+memsz, seg)
        self._elf_header_info: Dict[str, Any] = {}
        
        self._dwarf_version: str = 'unknown'
        self._compiler_name: str = 'unknown'
        self._compiler_version: str = 'unknown'
        self._producer_string: str = ''
        
        self._parse_elf()
    
    def _parse_elf(self):
        t_total = time.time()
        with open(self.elf_path, 'rb') as f:
            t0 = time.time()
            self.elffile = ELFFile(f)
            self._is_32bit = self.elffile.elfclass == 32
            self._address_size = 4 if self._is_32bit else 8
            
            self._elf_header_info = {
                'class': self.elffile.elfclass,
                'machine': self.elffile.get_machine_arch(),
                'entry': self.elffile.header['e_entry'],
                'num_sections': self.elffile.num_sections(),
                'num_segments': self.elffile.num_segments(),
            }
            
            for seg in self.elffile.iter_segments():
                if seg['p_type'] == 'PT_LOAD':
                    seg_vaddr = seg['p_vaddr']
                    seg_filesz = seg['p_filesz']
                    seg_memsz = seg['p_memsz']
                    seg_data = seg.data()
                    self._segment_cache.append({
                        'vaddr': seg_vaddr,
                        'filesz': seg_filesz,
                        'memsz': seg_memsz,
                        'data': seg_data,
                    })
            
            self._sorted_segment_ranges = sorted(
                [(s['vaddr'], s['vaddr'] + s['memsz'], s) for s in self._segment_cache],
                key=lambda x: x[0]
            )
            t_elf_init = time.time() - t0
            print(f"  [elftools] ELF file open + headers + segments: {t_elf_init:.3f}s")
            
            t0 = time.time()
            self._parse_symbols()
            t_symbols = time.time() - t0
            print(f"  [elftools] _parse_symbols: {t_symbols:.3f}s ({len(self._symbol_cache)} symbols)")
            
            if self.elffile.has_dwarf_info():
                t0 = time.time()
                self.dwarfinfo = self.elffile.get_dwarf_info()
                t_dwarf = time.time() - t0
                print(f"  [elftools] get_dwarf_info: {t_dwarf:.3f}s")
                
                t0 = time.time()
                self._parse_build_info()
                t_build = time.time() - t0
                print(f"  [elftools] _parse_build_info: {t_build:.3f}s")
                
                t0 = time.time()
                self._build_cu_index()
                t_cu = time.time() - t0
                print(f"  [elftools] _build_cu_index: {t_cu:.3f}s ({len(self._cu_cache)} CUs)")
                
                t0 = time.time()
                self._build_type_cache()
                t_type = time.time() - t0
                print(f"  [elftools] _build_type_cache: {t_type:.3f}s")
        
        t_total = time.time() - t_total
        print(f"  [elftools] Total parser init: {t_total:.3f}s")
    
    def _parse_symbols(self):
        for section in self.elffile.iter_sections():
            if isinstance(section, SymbolTableSection):
                for sym in section.iter_symbols():
                    name = sym.name
                    addr = sym['st_value']
                    size = sym['st_size']
                    stype = self._get_symbol_type(sym)

                    if name:
                        self._symbol_cache[name] = (addr, size, stype)
    
    def _parse_build_info(self):
        if not self.dwarfinfo:
            return
        
        if hasattr(self.dwarfinfo, 'version'):
            self._dwarf_version = str(self.dwarfinfo.version)
        elif hasattr(self.dwarfinfo, 'header') and hasattr(self.dwarfinfo.header, 'version'):
            self._dwarf_version = str(self.dwarfinfo.header.version)
        else:
            self._dwarf_version = 'unknown'
        
        for cu in self.dwarfinfo.iter_CUs():
            top_die = cu.get_top_DIE()
            if 'DW_AT_producer' in top_die.attributes:
                producer = top_die.attributes['DW_AT_producer'].value
                if isinstance(producer, bytes):
                    producer = producer.decode('utf-8', errors='replace')
                self._producer_string = producer

                armcc_match = re.search(r'ARM Compiler|armclang|ARM C/C\+\+ Compiler', producer, re.IGNORECASE)
                gcc_match = re.search(r'GCC|gnu|gcc', producer, re.IGNORECASE)
                iar_match = re.search(r'IAR|IAR Systems', producer, re.IGNORECASE)
                
                if armcc_match:
                    self._compiler_name = 'ARMCC'
                elif gcc_match:
                    self._compiler_name = 'GCC'
                elif iar_match:
                    self._compiler_name = 'IAR'
                
                version_match = re.search(r'(\d+\.\d+(\.\d+)*)', producer)
                if version_match:
                    self._compiler_version = version_match.group(1)
                break
    
    def print_build_info(self):
        print("=" * 40)
        print("ELF Build Information")
        print("=" * 40)
        print(f"ELF Path: {self.elf_path}")
        print(f"Architecture: {'32-bit' if self._is_32bit else '64-bit'}")
        print(f"DWARF Version: DWARF{self._dwarf_version}")
        print(f"Compiler: {self._compiler_name}")
        print(f"Compiler Version: {self._compiler_version}")
        if self._producer_string:
            print(f"Producer: {self._producer_string}")
        print("=" * 40)
    
    def _get_symbol_type(self, sym) -> str:
        st_info = sym['st_info']
        st_bind = st_info['bind']
        st_type = st_info['type']
        
        type_map = {
            'STT_NOTYPE': 'undefined',
            'STT_OBJECT': 'object',
            'STT_FUNC': 'function',
            'STT_SECTION': 'section',
            'STT_FILE': 'file',
            'STT_COMMON': 'common',
            'STT_TLS': 'tls',
        }
        
        bind_map = {
            'STB_LOCAL': 'local',
            'STB_GLOBAL': 'global',
            'STB_WEAK': 'weak',
        }
        
        return f"{bind_map.get(st_bind, 'unknown')}_{type_map.get(st_type, 'unknown')}"
    
    def _build_cu_index(self):
        start = time.time()
        if not self.dwarfinfo:
            return
        
        for cu in self.dwarfinfo.iter_CUs():
            low_pc = None
            high_pc = None
            try:
                die = cu.get_top_DIE()
                if 'DW_AT_low_pc' in die.attributes:
                    low_pc = die.attributes['DW_AT_low_pc'].value
                if 'DW_AT_high_pc' in die.attributes:
                    high_pc_attr = die.attributes['DW_AT_high_pc']
                    high_pc = high_pc_attr.value
                    if hasattr(high_pc, 'value'):
                        high_pc = high_pc.value
                    if isinstance(low_pc, int) and isinstance(high_pc, int):
                        if high_pc_attr.form == 'DW_FORM_data1' or high_pc_attr.form == 'DW_FORM_data2' or \
                           high_pc_attr.form == 'DW_FORM_data4' or high_pc_attr.form == 'DW_FORM_data8':
                            high_pc = low_pc + high_pc
            except Exception:
                pass
            
            if low_pc is not None and high_pc is not None:
                self._cu_cache.append((low_pc, high_pc, cu))
        
        self._cu_cache.sort(key=lambda x: x[0])
        elapsed = time.time() - start
        logger.debug("_build_cu_index: %d CUs, %.3fs", len(self._cu_cache), elapsed)
    
    def _find_cu_by_address(self, address: int) -> Optional[CompileUnit]:
        if not self._cu_cache:
            return None
        
        low_pcs = [cu[0] for cu in self._cu_cache]
        idx = bisect.bisect_right(low_pcs, address) - 1
        if idx >= 0:
            low_pc, high_pc, cu = self._cu_cache[idx]
            if low_pc <= address < high_pc:
                return cu
        return None
    
    def _build_type_cache(self):
        """索引优先 + 懒加载：只建索引，不做任何解析。实际查询时才解析并缓存。"""
        start = time.time()
        if not self.dwarfinfo:
            return

        _RELEVANT_TAGS = frozenset({
            'DW_TAG_structure_type', 'DW_TAG_union_type',
            'DW_TAG_enumeration_type', 'DW_TAG_base_type',
            'DW_TAG_typedef', 'DW_TAG_pointer_type',
            'DW_TAG_array_type', 'DW_TAG_const_type',
            'DW_TAG_volatile_type', 'DW_TAG_subroutine_type',
            'DW_TAG_variable',
        })

        die_by_offset: Dict[int, 'DIE'] = {}
        type_name_to_offset: Dict[str, int] = {}
        var_name_to_offset: Dict[str, int] = {}
        die_count = 0

        for cu in self.dwarfinfo.iter_CUs():
            for die in cu.iter_DIEs():
                if not die.tag or die.tag not in _RELEVANT_TAGS:
                    continue
                die_by_offset[die.offset] = die
                die_count += 1

                name_attr = die.attributes.get('DW_AT_name')
                if not name_attr:
                    continue
                name = name_attr.value.decode('utf-8', errors='replace')
                if die.tag == 'DW_TAG_variable':
                    var_name_to_offset[name] = die.offset
                else:
                    # Prefer the actual definition over a forward declaration.
                    # If the name already exists, check if the existing DIE
                    # is a declaration and the new one is not — replace it.
                    existing_offset = type_name_to_offset.get(name)
                    if existing_offset is not None:
                        existing_die = die_by_offset.get(existing_offset)
                        if existing_die is not None:
                            existing_is_decl = existing_die.attributes.get('DW_AT_declaration')
                            new_is_decl = die.attributes.get('DW_AT_declaration')
                            if existing_is_decl and not new_is_decl:
                                type_name_to_offset[name] = die.offset
                            elif not existing_is_decl and new_is_decl:
                                pass  # Keep the existing definition
                            elif (existing_die.attributes.get('DW_AT_byte_size') is None
                                  and die.attributes.get('DW_AT_byte_size') is not None):
                                type_name_to_offset[name] = die.offset
                    else:
                        type_name_to_offset[name] = die.offset

        self._die_by_offset = die_by_offset
        self._type_name_to_offset = type_name_to_offset
        self._var_name_to_offset = var_name_to_offset
        self._var_type_cache: Dict[str, Dict[str, Any]] = {}

        elapsed = time.time() - start
        logger.debug("_build_type_cache: %d DIEs indexed, %.3fs",
                     die_count, elapsed)

    def _resolve_type_ref(self, die: 'DIE', die_by_offset: Dict[int, 'DIE']) -> Optional['DIE']:
        """解析 DW_AT_type 引用，把 CU 相对偏移转为 .debug_info 绝对偏移再查找 DIE。

        DWARF 中 DW_FORM_ref1/2/4/8 的值是相对于当前 CU 的偏移，
        需要加上 die.cu.cu_offset 才是 .debug_info 段中的绝对偏移。
        DW_FORM_ref_addr 则是绝对偏移，无需转换。
        """
        attr = die.attributes.get('DW_AT_type')
        if not attr:
            return None
        offset = attr.value
        if attr.form.startswith('DW_FORM_ref') and attr.form != 'DW_FORM_ref_addr':
            offset += die.cu.cu_offset
        return die_by_offset.get(offset)

    def _parse_struct_die(self, die: DIE, die_by_offset: Dict[int, 'DIE'], _depth: int = 0, 
                         _visited: Optional[set] = None) -> Dict[str, Any]:
        if _visited is None:
            _visited = set()
        
        if die.offset in _visited:
            return {'kind': 'struct', 'name': None, 'byte_size': 0, 'members': [], '_circular_ref': True}
        
        _visited.add(die.offset)
        
        if _depth > ElftoolsParser._MAX_RECURSION_DEPTH:
            logger.debug("Deep recursion in struct parsing (depth=%d), die offset=0x%x", _depth, die.offset)
            return {'kind': 'struct', 'name': None, 'byte_size': 0, 'members': [], '_deep_truncated': True}
        
        info = {
            'kind': 'struct',
            'tag': die.tag,
            'name': None,
            'byte_size': 0,
            'members': [],
        }
        if 'DW_AT_name' in die.attributes:
            info['name'] = die.attributes['DW_AT_name'].value.decode('utf-8', errors='replace')
        if 'DW_AT_byte_size' in die.attributes:
            info['byte_size'] = die.attributes['DW_AT_byte_size'].value

        for child in die.iter_children():
            if child.tag == 'DW_TAG_member':
                member = self._parse_member(child, die_by_offset, _depth + 1, _visited)
                if member:
                    info['members'].append(member)
        
        _visited.discard(die.offset)
        return info

    def _parse_typedef_die(self, die: DIE, die_by_offset: Dict[int, 'DIE'], _depth: int = 0, 
                           _visited: Optional[set] = None) -> Dict[str, Any]:
        info = {
            'kind': 'typedef',
            'tag': die.tag,
            'name': None,
            'byte_size': 0,
            'ref_type_offset': None,
            'ref_type': None,
        }
        if 'DW_AT_name' in die.attributes:
            info['name'] = die.attributes['DW_AT_name'].value.decode('utf-8', errors='replace')

        ref_die = self._resolve_type_ref(die, die_by_offset)
        if ref_die:
            info['ref_type_offset'] = ref_die.offset
            # 递归解析被 typedef 的真实类型，把 byte_size 和 members 提升上来
            ref_info = self._parse_any_die(ref_die, die_by_offset, _depth + 1, _visited)
            if ref_info:
                info['ref_type'] = ref_info
                info['byte_size'] = ref_info.get('byte_size', 0)
                # typedef 直接继承被引用类型的 members，这样上层可当作结构体使用
                if 'members' in ref_info:
                    info['members'] = ref_info['members']
        return info

    def _parse_pointer_die(self, die: DIE, die_by_offset: Dict[int, 'DIE'], _depth: int = 0, 
                           _visited: Optional[set] = None) -> Dict[str, Any]:
        info = {
            'kind': 'pointer',
            'tag': die.tag,
            'name': None,
            'byte_size': 4,
            'ref_type_offset': None,
            'ref_type': None,
        }
        if 'DW_AT_byte_size' in die.attributes:
            info['byte_size'] = die.attributes['DW_AT_byte_size'].value

        ref_die = self._resolve_type_ref(die, die_by_offset)
        if ref_die:
            info['ref_type_offset'] = ref_die.offset
            info['ref_type'] = self._parse_any_die(ref_die, die_by_offset, _depth + 1, _visited)
            # 如果最终指向 char（可能经过 const_type 修饰），给个友好名字
            if self._classify_pointer_kind(info) == 'ptr_string':
                info['name'] = 'char*'
        return info

    def _classify_pointer_kind(self, type_info: Dict[str, Any]) -> str:
        """Classify a pointer type into one of: ptr_struct, ptr_string, ptr_func, ptr_scalar.

        Follows the DWARF Type → ViewNode Behavior Contract:
        - target struct/union/class → ptr_struct
        - target char (byte_size=1) → ptr_string
        - target function/subroutine → ptr_func
        - everything else (void/base/unresolved) → ptr_scalar
        """
        ref_type = type_info.get('ref_type')
        if not ref_type:
            return 'ptr_scalar'

        # Unwrap const/volatile/typedef via shared helper
        current = self._unwrap_type(ref_type)

        if not current:
            return 'ptr_scalar'

        kind = current.get('kind')

        if kind in ('struct', 'union', 'class'):
            return 'ptr_struct'

        if kind == 'base' and current.get('name') == 'char' and current.get('byte_size') == 1:
            return 'ptr_string'

        if kind in ('subroutine', 'subroutine_type', 'function'):
            return 'ptr_func'

        return 'ptr_scalar'

    def _unwrap_type(self, type_info: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """剥离 typedef/const/volatile 包装，返回最内层的真实类型。"""
        if not type_info:
            return None
        current = type_info
        seen = set()
        while current and id(current) not in seen:
            kind = current.get('kind')
            if kind in ('const', 'volatile', 'typedef'):
                seen.add(id(current))
                current = current.get('ref_type')
            else:
                return current
        return None

    def _parse_const_die(self, die: DIE, die_by_offset: Dict[int, 'DIE'], _depth: int = 0, 
                         _visited: Optional[set] = None) -> Dict[str, Any]:
        info = {
            'kind': 'const',
            'tag': die.tag,
            'name': None,
            'byte_size': 0,
            'ref_type_offset': None,
            'ref_type': None,
        }
        ref_die = self._resolve_type_ref(die, die_by_offset)
        if ref_die:
            info['ref_type_offset'] = ref_die.offset
            info['ref_type'] = self._parse_any_die(ref_die, die_by_offset, _depth + 1, _visited)
            if info['ref_type']:
                info['byte_size'] = info['ref_type'].get('byte_size', 0)
                if info['ref_type'].get('name'):
                    info['name'] = 'const ' + info['ref_type']['name']
        return info

    def _parse_array_die(self, die: DIE, die_by_offset: Dict[int, 'DIE'], _depth: int = 0, 
                         _visited: Optional[set] = None) -> Dict[str, Any]:
        info = {
            'kind': 'array',
            'tag': die.tag,
            'name': None,
            'byte_size': 0,
            'element_type_offset': None,
            'element_type': None,
            'element_count': 0,
        }
        ref_die = self._resolve_type_ref(die, die_by_offset)
        if ref_die:
            info['element_type_offset'] = ref_die.offset
            info['element_type'] = self._parse_any_die(ref_die, die_by_offset, _depth + 1, _visited)

        # 子节点 DW_TAG_subrange_type 包含数组长度
        for child in die.iter_children():
            if child.tag == 'DW_TAG_subrange_type':
                count_attr = child.attributes.get('DW_AT_upper_bound')
                if count_attr is not None:
                    # upper_bound 是最后一个元素的索引，所以 count = upper_bound + 1
                    try:
                        info['element_count'] = count_attr.value + 1
                    except TypeError:
                        info['element_count'] = 0
                else:
                    info['element_count'] = 0

        if info['element_type'] and info['element_type'].get('byte_size'):
            info['byte_size'] = info['element_count'] * info['element_type']['byte_size']
        return info

    def _parse_enum_die(self, die: DIE) -> Dict[str, Any]:
        info = {
            'kind': 'enum',
            'tag': die.tag,
            'name': None,
            'byte_size': 0,
            'members': [],
        }
        if 'DW_AT_name' in die.attributes:
            info['name'] = die.attributes['DW_AT_name'].value.decode('utf-8', errors='replace')
        if 'DW_AT_byte_size' in die.attributes:
            info['byte_size'] = die.attributes['DW_AT_byte_size'].value

        for child in die.iter_children():
            if child.tag == 'DW_TAG_enumerator':
                enum_val = self._parse_enumerator(child)
                if enum_val:
                    info['members'].append(enum_val)
        return info

    def _parse_any_die(self, die: 'DIE', die_by_offset: Dict[int, 'DIE'], _depth: int = 0, 
                       _visited: Optional[set] = None) -> Optional[Dict[str, Any]]:
        tag = die.tag
        if tag in ('DW_TAG_structure_type', 'DW_TAG_union_type'):
            return self._parse_struct_die(die, die_by_offset, _depth, _visited)
        elif tag == 'DW_TAG_enumeration_type':
            return self._parse_enum_die(die)
        elif tag == 'DW_TAG_base_type':
            return self._parse_base_type(die)
        elif tag == 'DW_TAG_typedef':
            return self._parse_typedef_die(die, die_by_offset, _depth, _visited)
        elif tag == 'DW_TAG_pointer_type':
            return self._parse_pointer_die(die, die_by_offset, _depth, _visited)
        elif tag == 'DW_TAG_array_type':
            return self._parse_array_die(die, die_by_offset, _depth, _visited)
        elif tag == 'DW_TAG_const_type':
            return self._parse_const_die(die, die_by_offset, _depth, _visited)
        elif tag == 'DW_TAG_volatile_type':
            # volatile 处理逻辑同 const
            return self._parse_const_die(die, die_by_offset, _depth, _visited)
        return None
    
    def _parse_base_type(self, die: DIE) -> Dict[str, Any]:
        name_attr = die.attributes.get('DW_AT_name')
        bs_attr = die.attributes.get('DW_AT_byte_size')
        enc_attr = die.attributes.get('DW_AT_encoding')
        info = {
            'kind': 'base',
            'tag': die.tag,
            'name': name_attr.value.decode('utf-8', errors='replace') if name_attr else None,
            'byte_size': bs_attr.value if bs_attr else 0,
            'encoding': enc_attr.value if enc_attr else None,
        }
        return info

    def _parse_member(self, die: DIE, die_by_offset: Dict[int, 'DIE'], _depth: int = 0, 
                      _visited: Optional[set] = None) -> Dict[str, Any]:
        member = {
            'name': None,
            'offset': 0,
            'byte_size': 0,
            'type': None,
            'type_name': None,
            'type_offset': None,
        }

        if 'DW_AT_name' in die.attributes:
            member['name'] = die.attributes['DW_AT_name'].value.decode('utf-8', errors='replace')

        if 'DW_AT_data_member_location' in die.attributes:
            loc_attr = die.attributes['DW_AT_data_member_location']
            val = loc_attr.value
            # 数据成员位置可能是 DW_FORM_exprloc（一个 DWARF 表达式字节数组）
            if isinstance(val, bytes):
                member['offset'] = self._parse_dw_op_location(val)
            else:
                member['offset'] = val

        if 'DW_AT_byte_size' in die.attributes:
            member['byte_size'] = die.attributes['DW_AT_byte_size'].value

        if 'DW_AT_type' in die.attributes:
            ref_die = self._resolve_type_ref(die, die_by_offset)
            if ref_die:
                member['type_offset'] = ref_die.offset
                type_info = self._parse_any_die(ref_die, die_by_offset, _depth + 1, _visited)
                if type_info:
                    member['type'] = type_info
                    member['type_name'] = type_info.get('name') or type_info.get('kind')
                    if type_info.get('byte_size'):
                        member['byte_size'] = type_info['byte_size']
        return member

    @staticmethod
    def _parse_dw_op_location(expr: bytes) -> int:
        """Parse a DWARF location expression to extract a member offset.

        Supports common DW_OP encodings used by GCC, IAR, and ARMCC:
        - DW_OP_plus_uconst (0x23) + ULEB128 → offset = N
        - DW_OP_constu (0x10) + ULEB128 + DW_OP_plus (0x22) → offset = N

        For unrecognized opcodes, logs a warning and returns 0 to avoid
        silent data corruption.
        """
        i = 0
        while i < len(expr):
            op = expr[i]
            i += 1

            if op == 0x23:  # DW_OP_plus_uconst
                n, _ = ElftoolsParser._read_uleb128(expr, i)
                return n

            if op == 0x10:  # DW_OP_constu
                n, consumed = ElftoolsParser._read_uleb128(expr, i)
                i += consumed
                # Expect DW_OP_plus next
                if i < len(expr) and expr[i] == 0x22:  # DW_OP_plus
                    return n

            # DW_OP_addr (0x03): skip address-sized operand
            if op == 0x03:
                i += 4  # 32-bit address; 64-bit would be 8 but rare in this context
                continue

            # DW_OP_deref (0x06), DW_OP_dup (0x12), DW_OP_drop (0x13): no operand
            if op in (0x06, 0x12, 0x13, 0x22):
                continue

            # DW_OP_lit0..DW_OP_lit31 (0x30..0x4F): no operand
            if 0x30 <= op <= 0x4F:
                continue

            # DW_OP_reg0..DW_OP_reg31 (0x50..0x6F): no operand
            if 0x50 <= op <= 0x6F:
                continue

            # DW_OP_breg0..DW_OP_breg31 (0x70..0x8F): followed by ULEB128
            if 0x70 <= op <= 0x8F:
                _, consumed = ElftoolsParser._read_uleb128(expr, i)
                i += consumed
                continue

            # Unknown opcode: warn and abort
            logger.warning(
                "Unrecognized DW_OP code 0x%02x in member location expression "
                "(offset=0x%x). Member offset will be 0; data may be incorrect.",
                op, i - 1
            )
            return 0

        return 0

    @staticmethod
    def _read_uleb128(data: bytes, offset: int) -> Tuple[int, int]:
        """Read a ULEB128-encoded integer from bytes starting at offset.

        Returns (value, bytes_consumed).
        """
        n = 0
        shift = 0
        consumed = 0
        while offset + consumed < len(data):
            b = data[offset + consumed]
            consumed += 1
            n |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        return n, consumed

    # ------------------------------------------------------------------
    # 自动结构体解析（递归展开嵌套结构体、数组、指针）
    # ------------------------------------------------------------------

    @staticmethod
    def _read_uint_by_size(dump_reader, address: int, byte_size: int) -> Optional[int]:
        """Read an unsigned integer of the given byte size from dump_reader.

        Centralizes the byte_size → read_uint* dispatch to eliminate
        duplicated if/elif chains in _read_typed_value.
        """
        _READERS = {
            1: dump_reader.read_uint8,
            2: dump_reader.read_uint16,
            4: dump_reader.read_uint32,
            8: dump_reader.read_uint64,
        }
        reader = _READERS.get(byte_size)
        return reader(address) if reader else None

    @staticmethod
    def _is_unsigned_encoding(encoding) -> bool:
        """Check if a DW_AT_encoding value represents an unsigned type."""
        if encoding is None:
            return False
        if isinstance(encoding, int):
            return encoding in (_DW_ATE_unsigned, _DW_ATE_unsigned_char)
        return str(encoding).lower() in ('unsigned', 'unsigned_char')

    @staticmethod
    def _build_enum_display(value: int, enum_members: list) -> str:
        """Build display_value for an enum: 'ENUM_NAME(value)' or 'value'."""
        for member in enum_members:
            if member.get('value') == value:
                return f"{member.get('name', '?')}({value})"
        return str(value)

    @staticmethod
    def _get_pointer_target_name(type_info: Dict[str, Any]) -> str:
        """Get a human-readable name for what a pointer points to."""
        ref_type = type_info.get('ref_type')
        if not ref_type:
            return 'void'
        current = ref_type
        while current:
            kind = current.get('kind')
            if kind in ('const', 'volatile', 'typedef'):
                name = current.get('name')
                if name and kind == 'typedef':
                    return name
                current = current.get('ref_type')
            else:
                return current.get('name') or kind
        return 'void'

    def parse_struct_auto(self, var_name: str, dump_reader) -> Optional[Dict[str, Any]]:
        """根据符号名 + DWARF 类型信息，自动从 dump_reader 中递归展开结构体。

        完全依赖 DWARF 中变量声明（DW_TAG_variable）的真实类型信息，
        不做任何符号名→类型名的猜测。

        支持:
        - 基础类型 (uint8_t/uint32_t/...)
        - 嵌套结构体
        - 结构体数组（含元素个数从 DWARF upper_bound 自动推断）
        - char* 指针（自动解引用读取字符串）
        - 一般指针（读取指针值并以 hex 显示）

        返回 dict 格式（向后兼容）。新代码应使用 read_struct_as_node() 获取 ViewNode。
        """
        sym = self.get_symbol_by_name(var_name)
        if not sym:
            return None

        type_info = self.get_variable_type(var_name)
        if not type_info:
            return None

        view_node = self._read_typed_value(type_info, sym['address'], dump_reader, depth=0)
        if view_node is None:
            return None
        return view_node.to_dict(dump_reader=dump_reader, elf_parser=self)

    def read_struct_as_node(self, struct_type: Dict[str, Any], address: int,
                            dump_reader) -> Optional[ViewNode]:
        """Read a struct at the given address and return a ViewNode tree.

        This is the new API for reading typed values. Unlike parse_struct_auto
        which returns a plain dict, this returns a ViewNode tree that can be
        used with StructAccessor for convenient field access.

        Args:
            struct_type: DWARF type info dict (from get_struct_type or get_variable_type).
            address: Memory address to read from.
            dump_reader: DumpReader instance.

        Returns:
            ViewNode tree, or None if the read failed.
        """
        return self._read_typed_value(struct_type, address, dump_reader, depth=0)

    def create_accessor(self, var_name: str, dump_reader) -> Optional[StructAccessor]:
        """Create a StructAccessor for a global variable.

        Convenience method that combines get_variable_type + _read_typed_value
        + StructAccessor construction.

        Args:
            var_name: Global variable name.
            dump_reader: DumpReader instance.

        Returns:
            StructAccessor, or None if the variable or its type is not found.
        """
        sym = self.get_symbol_by_name(var_name)
        if not sym:
            return None
        type_info = self.get_variable_type(var_name)
        if not type_info:
            return None
        view_node = self._read_typed_value(type_info, sym['address'], dump_reader, depth=0)
        if view_node is None:
            return None
        return StructAccessor(view_node, dump_reader, self)

    def _read_typed_value(self, type_info: Dict[str, Any], address: int,
                         dump_reader, depth: int = 0,
                         _visited: Optional[set] = None) -> Optional[ViewNode]:
        """Read a typed value from memory and return a ViewNode tree.

        This is the core method for the new architecture. It recursively reads
        values from dump_reader based on DWARF type information and returns
        ViewNode trees instead of raw dicts.

        Args:
            type_info: DWARF type info dict.
            address: Memory address to read from.
            dump_reader: DumpReader instance.
            depth: Current recursion depth.
            _visited: Set of visited addresses for cycle detection.

        Returns:
            ViewNode tree, or None on error.
        """
        if _visited is None:
            _visited = set()

        if depth > ElftoolsParser._MAX_RECURSION_DEPTH:
            logger.debug("Deep recursion in _read_typed_value (depth=%d), address=0x%x", depth, address)
            return None

        if not type_info:
            return None

        kind = type_info.get('kind')
        type_name = type_info.get('name') or ''

        # typedef/const/volatile：透明穿透，保留 type_chain 在 meta
        if kind in ('typedef', 'const', 'volatile'):
            inner = self._read_typed_value(type_info.get('ref_type'), address, dump_reader, depth + 1, _visited)
            if inner:
                chain = inner.meta.get('type_chain', [])
                chain.append({'kind': kind, 'name': type_name})
                inner.meta['type_chain'] = chain
            return inner

        # 基础类型 → scalar
        if kind == 'base':
            bs = type_info.get('byte_size', 4)
            raw = self._read_uint_by_size(dump_reader, address, bs)
            if raw is None:
                return None

            encoding = type_info.get('encoding')
            if self._is_unsigned_encoding(encoding) or 'unsigned' in (type_name or '').lower():
                display = f'0x{raw:X}'
            else:
                display = str(raw)

            return ViewNode(
                name='', type_name=type_name, kind='scalar',
                raw_value=raw, display_value=display,
                address=address, byte_size=bs,
                meta={'encoding': encoding}
            )

        # 枚举类型
        if kind == 'enum':
            bs = type_info.get('byte_size', 4)
            raw = self._read_uint_by_size(dump_reader, address, bs)
            if raw is None:
                return None

            enum_members = type_info.get('members', [])
            display = self._build_enum_display(raw, enum_members)

            return ViewNode(
                name='', type_name=type_name, kind='enum',
                raw_value=raw, display_value=display,
                address=address, byte_size=bs,
                meta={'enum_members': enum_members}
            )

        # ── 指针类型：严格按照 Contract 分为四种 kind ──
        # 禁止在 ViewNode 构建阶段对任何指针执行目标地址内存读取
        if kind == 'pointer':
            ptr_size = type_info.get('byte_size', self._address_size)
            if ptr_size == 4:
                ptr_val = dump_reader.read_uint32(address)
            elif ptr_size == 8:
                ptr_val = dump_reader.read_uint64(address)
            else:
                raw = dump_reader.read_memory(address, ptr_size)
                ptr_val = int.from_bytes(raw, 'little') if raw else 0

            hex_width = 16 if ptr_size == 8 else 8
            is_null = (ptr_val == 0 or ptr_val is None)
            ref_type = type_info.get('ref_type')
            ptr_target_name = type_info.get('name') or self._get_pointer_target_name(type_info)

            # Classify pointer sub-kind
            ptr_kind = self._classify_pointer_kind(type_info)

            # Build display_value (no target memory reads)
            if ptr_kind == 'ptr_func':
                display = f'&{ptr_target_name}'
            elif is_null:
                display = 'NULL'
            else:
                display = f'→ {ptr_target_name} @ 0x{ptr_val:0{hex_width}x}'

            return ViewNode(
                name='', type_name=ptr_target_name, kind=ptr_kind,
                raw_value=ptr_val if not is_null else 0,
                display_value=display,
                address=address, byte_size=ptr_size,
                meta={
                    'target_type': ref_type,
                    'is_null': is_null,
                    'is_valid': not is_null,
                }
            )

        # 数组：逐元素读取；char 数组特化为 string
        if kind == 'array':
            elem_type = type_info.get('element_type')
            count = type_info.get('element_count', 0)
            elem_size = elem_type.get('byte_size', 0) if elem_type else 0
            if not elem_size or count == 0:
                return ViewNode(
                    name='', type_name=type_name, kind='array',
                    address=address, byte_size=0,
                    display_value='[0 items]',
                    meta={'element_count': 0}
                )

            # char 数组（含 const char[]）→ kind='string'
            unwrapped_elem = self._unwrap_type(elem_type)
            if unwrapped_elem and unwrapped_elem.get('kind') == 'base' \
                    and unwrapped_elem.get('name') == 'char':
                try:
                    s = dump_reader.read_string(address, max_length=count)
                    display = s if s is not None else ''
                except Exception:
                    display = ''
                return ViewNode(
                    name='', type_name=f'char[{count}]', kind='string',
                    display_value=display,
                    address=address, byte_size=type_info.get('byte_size', 0),
                    meta={'element_count': count}
                )

            children = []
            for i in range(count):
                elem_addr = address + i * elem_size
                child_node = self._read_typed_value(elem_type, elem_addr, dump_reader, depth + 1, _visited)
                if child_node:
                    child_node.name = f'[{i}]'
                    children.append(child_node)

            return ViewNode(
                name='', type_name=type_name, kind='array',
                children=children,
                address=address, byte_size=type_info.get('byte_size', 0),
                display_value=f'[{count} items]',
                meta={'element_count': count}
            )

        # 结构体/联合体：逐成员读取（嵌套结构体延迟加载）
        if kind in ('struct', 'union'):
            type_offset = type_info.get('type_offset')
            visit_key = None
            if type_offset is not None:
                visit_key = (address, type_offset)
                if visit_key in _visited:
                    return None
                _visited.add(visit_key)

            children = []
            for m in type_info.get('members', []):
                m_name = m.get('name') or f'<anon@{m.get("offset")}>'
                m_addr = address + m.get('offset', 0)
                m_type = m.get('type')
                
                if m_type and m_type.get('kind') in ('struct', 'union'):
                    m_type_name = m_type.get('name', '')
                    child_node = ViewNode(
                        name=m_name, type_name=m_type_name, kind=m_type['kind'],
                        address=m_addr, byte_size=m_type.get('byte_size', 0),
                        expandable=True,
                        meta={'struct_type_name': m_type_name}
                    )
                else:
                    child_node = self._read_typed_value(m_type, m_addr, dump_reader, depth + 1, _visited)
                    if child_node:
                        child_node.name = m_name
                
                if child_node:
                    children.append(child_node)

            if visit_key is not None:
                _visited.discard(visit_key)

            return ViewNode(
                name='', type_name=type_name, kind=kind,
                children=children,
                address=address,
                byte_size=type_info.get('byte_size', 0)
            )

        return None
    
    def _parse_enumerator(self, die: DIE) -> Dict[str, Any]:
        enum_val = {
            'name': None,
            'value': 0,
        }
        
        if 'DW_AT_name' in die.attributes:
            enum_val['name'] = die.attributes['DW_AT_name'].value.decode('utf-8', errors='replace')
        
        if 'DW_AT_const_value' in die.attributes:
            enum_val['value'] = die.attributes['DW_AT_const_value'].value
        
        return enum_val
    
    def get_symbol_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        if name in self._symbol_cache:
            addr, size, stype = self._symbol_cache[name]
            return {
                'name': name,
                'address': addr,
                'size': size,
                'type': stype,
            }
        return None
    
    def get_all_symbols(self) -> List[Dict[str, Any]]:
        if self._all_symbols_cache is not None:
            return self._all_symbols_cache
        result = []
        for name in self._symbol_cache:
            addr, size, stype = self._symbol_cache[name]
            result.append({
                'name': name,
                'address': addr,
                'size': size,
                'type': stype,
            })
        self._all_symbols_cache = result
        return result

    def get_variable_type(self, name: str) -> Optional[Dict[str, Any]]:
        """Deprecated: use get_var_type() instead.

        This method is kept for backward compatibility. External callers
        (e.g. FreeRTOS plugin) should migrate to get_var_type().
        """
        return self.get_var_type(name)

    def get_var_type(self, name: str) -> Optional[Dict[str, Any]]:
        """获取全局变量的 DWARF 类型信息（懒加载：首次查询时按需解析）。"""
        if name in self._var_type_cache:
            return self._var_type_cache[name]

        offset = self._var_name_to_offset.get(name)
        if offset is None:
            return None

        die = self._die_by_offset.get(offset)
        if die is None or die.tag != 'DW_TAG_variable':
            return None

        ref_die = self._resolve_type_ref(die, self._die_by_offset)
        if ref_die:
            var_type_info = self._parse_any_die(ref_die, self._die_by_offset)
            if var_type_info:
                self._var_type_cache[name] = var_type_info
                return var_type_info
        return None

    def find_symbols_by_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        result = []
        for name in self._symbol_cache:
            if pattern in name:
                addr, size, stype = self._symbol_cache[name]
                result.append({
                    'name': name,
                    'address': addr,
                    'size': size,
                    'type': stype,
                })
        return result
    
    def find_function_by_address(self, address: int) -> Optional[Dict[str, Any]]:
        for low_pc, high_pc, cu in self._cu_cache:
            if low_pc <= address < high_pc:
                return self._search_function_in_cu(address, cu)
        
        return None
    
    def get_function_by_address(self, address: int) -> Optional[Dict[str, Any]]:
        """Get function info containing the given address."""
        return self.find_function_by_address(address)
    
    def _search_function_in_cu(self, address: int, cu: CompileUnit) -> Optional[Dict[str, Any]]:
        for die in cu.iter_DIEs():
            if die.tag == 'DW_TAG_subprogram':
                low_pc_attr = die.attributes.get('DW_AT_low_pc')
                high_pc_attr = die.attributes.get('DW_AT_high_pc')
                
                if low_pc_attr and high_pc_attr:
                    low_pc = low_pc_attr.value
                    high_pc = high_pc_attr.value
                    
                    if hasattr(high_pc, 'value'):
                        high_pc = high_pc.value
                    
                    if low_pc <= address < high_pc:
                        func_name = die.attributes.get('DW_AT_name', '').value.decode('utf-8', errors='replace') if die.attributes.get('DW_AT_name') else None
                        return {
                            'name': func_name,
                            'low_pc': low_pc,
                            'high_pc': high_pc,
                            'size': high_pc - low_pc,
                        }
        return None
    
    def get_struct_type(self, struct_name: str) -> Optional[Dict[str, Any]]:
        """懒加载：首次查询时按需解析，之后命中缓存。"""
        if struct_name in self._struct_type_cache:
            return self._struct_type_cache[struct_name]

        offset = self._type_name_to_offset.get(struct_name)
        if offset is None:
            return None

        die = self._die_by_offset.get(offset)
        if die is None:
            return None

        type_info = self._parse_any_die(die, self._die_by_offset)
        if type_info:
            self._struct_type_cache[struct_name] = type_info
        return type_info

    def _find_segment_for_address(self, address: int, size: int = 0) -> Optional[Dict[str, Any]]:
        if not self._sorted_segment_ranges:
            return None
        low_addrs = [r[0] for r in self._sorted_segment_ranges]
        idx = bisect.bisect_right(low_addrs, address) - 1
        if idx >= 0:
            start, end, seg = self._sorted_segment_ranges[idx]
            if start <= address < end:
                return seg
        return None
    
    def read_memory_from_dump(self, address: int, size: int, dump_data: bytes) -> Optional[bytes]:
        seg = self._find_segment_for_address(address, size)
        if seg:
            dump_offset = address - seg['vaddr']
            if dump_offset + size <= len(dump_data):
                return dump_data[dump_offset:dump_offset + size]
        return None
    
    def read_memory_from_elf(self, address: int, size: int) -> Optional[bytes]:
        seg = self._find_segment_for_address(address, size)
        if seg:
            file_offset = address - seg['vaddr']
            actual_size = min(size, seg['filesz'] - file_offset)
            if actual_size > 0:
                return seg['data'][file_offset:file_offset + actual_size]
        return None
    
    def parse_struct_from_dump(self, struct_name: str, address: int, dump_data: bytes) -> Optional[Dict[str, Any]]:
        struct_type = self.get_struct_type(struct_name)
        if not struct_type:
            return None
        
        result = {
            'struct_name': struct_name,
            'address': address,
            'size': struct_type['byte_size'],
            'members': {},
        }
        
        struct_data = self.read_memory_from_dump(address, struct_type['byte_size'], dump_data)
        if not struct_data:
            return None
        
        for member in struct_type['members']:
            member_name = member['name']
            member_offset = member['offset']
            member_size = member['byte_size']
            
            if member_offset + member_size <= len(struct_data):
                member_data = struct_data[member_offset:member_offset + member_size]
                member_value = self._unpack_value(member_data, member_size)
                
                result['members'][member_name] = {
                    'offset': member_offset,
                    'size': member_size,
                    'type_name': member.get('type_name'),
                    'value': member_value,
                    'raw': member_data.hex(),
                }
        
        return result
    
    def _unpack_value(self, data: bytes, size: int) -> Any:
        if size == 1:
            return struct.unpack('<B', data)[0]
        elif size == 2:
            return struct.unpack('<H', data)[0]
        elif size == 4:
            return struct.unpack('<I', data)[0]
        elif size == 8:
            return struct.unpack('<Q', data)[0]
        else:
            return int.from_bytes(data, byteorder='little')

    def get_elf_header(self) -> Dict[str, Any]:
        return self._elf_header_info
    
    def is_32bit(self) -> bool:
        return self._is_32bit
    
    def get_address_size(self) -> int:
        return self._address_size
    
    def match_keywords(self, keywords: List[str], check_elf_only: bool = False) -> List[str]:
        unmatched = []
        
        with open(self.elf_path, 'rb') as f:
            elf_text = f.read().decode('ascii', errors='ignore').lower()
        
        for keyword in keywords:
            if keyword.lower() not in elf_text:
                unmatched.append(keyword)
        
        return unmatched

    def read_struct_tree(self, struct_type_name: str, address: int, dump_reader, 
                         max_depth: int = 1) -> Optional[Dict[str, Any]]:
        """Read struct from memory and return a tree structure for GUI display."""
        struct_type = self.get_struct_type(struct_type_name)
        if not struct_type:
            return None

        view_node = self.read_struct_as_node(struct_type, address, dump_reader)
        if not view_node:
            return None

        return self._view_node_to_tree(view_node, dump_reader, max_depth, set())

    def read_symbol_tree(self, symbol_name: str, dump_reader, 
                         max_depth: int = 1) -> Optional[Dict[str, Any]]:
        """Read a symbol's value as a tree structure for GUI display."""
        sym = self.get_symbol_by_name(symbol_name)
        if not sym:
            return None

        address = sym.get('address', 0)
        byte_size = sym.get('size', 0)

        var_type = self.get_var_type(symbol_name)
        if var_type:
            kind = var_type.get('kind', '')
            type_name = var_type.get('name', '')
            
            if kind in ('struct', 'union'):
                return self.read_struct_tree(type_name, address, dump_reader, max_depth)
            
            if kind == 'array':
                return self._read_array_tree(var_type, address, byte_size, dump_reader, max_depth)
            
            return self._read_scalar_tree(symbol_name, type_name, kind, address, byte_size, dump_reader)

        struct_type = self.get_struct_type(symbol_name)
        if struct_type:
            return self.read_struct_tree(symbol_name, address, dump_reader, max_depth)

        type_name = sym.get('type', '')
        struct_type = self.get_struct_type(type_name)
        if struct_type:
            return self.read_struct_tree(type_name, address, dump_reader, max_depth)

        return self._read_scalar_tree(symbol_name, type_name, 'scalar', address, byte_size, dump_reader)

    def _read_array_tree(self, var_type: Dict[str, Any], address: int, byte_size: int, 
                         dump_reader, max_depth: int) -> Optional[Dict[str, Any]]:
        """Read an array symbol as a tree structure."""
        element_type = var_type.get('element_type')
        if not element_type:
            return None

        element_count = var_type.get('element_count', 0)
        if element_count == 0 and byte_size > 0:
            element_size = element_type.get('byte_size', 4)
            element_count = byte_size // element_size

        children = []
        for i in range(element_count):
            elem_addr = address + i * element_type.get('byte_size', 4)
            
            if element_type.get('kind') in ('struct', 'union'):
                child_tree = self.read_struct_tree(
                    element_type.get('name', ''), elem_addr, dump_reader, max_depth - 1)
            else:
                child_tree = self._read_scalar_tree(
                    f'[{i}]', element_type.get('name', ''), 
                    element_type.get('kind', 'scalar'),
                    elem_addr, element_type.get('byte_size', 4), dump_reader)
            
            if child_tree:
                children.append(child_tree)

        return {
            'name': var_type.get('name', ''),
            'type_name': var_type.get('name', ''),
            'kind': 'array',
            'raw_value': None,
            'display_value': f'array[{element_count}]',
            'address': address,
            'byte_size': byte_size,
            'expandable': True,
            'children': children,
        }

    def _read_scalar_tree(self, name: str, type_name: str, kind: str, 
                          address: int, byte_size: int, dump_reader) -> Dict[str, Any]:
        """Read a scalar/pointer symbol as a tree structure."""
        raw_value = None
        display_value = ''
        
        if dump_reader and byte_size > 0:
            try:
                data = dump_reader.read_memory(address, min(byte_size, 8))
                if data:
                    if byte_size == 1:
                        raw_value = struct.unpack('<B', data)[0]
                        display_value = f'{raw_value}'
                    elif byte_size == 2:
                        raw_value = struct.unpack('<H', data)[0]
                        display_value = f'{raw_value}'
                    elif byte_size == 4:
                        raw_value = struct.unpack('<I', data)[0]
                        if kind in ('ptr_struct', 'ptr_string', 'ptr_func', 'ptr_scalar'):
                            display_value = f'0x{raw_value:08X}'
                        else:
                            display_value = f'{raw_value}'
                    elif byte_size == 8:
                        raw_value = struct.unpack('<Q', data)[0]
                        if kind in ('ptr_struct', 'ptr_string', 'ptr_func', 'ptr_scalar'):
                            display_value = f'0x{raw_value:016X}'
                        else:
                            display_value = f'{raw_value}'
            except Exception:
                pass

        if raw_value is None:
            display_value = 'N/A'

        return {
            'name': name,
            'type_name': type_name,
            'kind': kind,
            'raw_value': raw_value,
            'display_value': display_value,
            'address': address,
            'byte_size': byte_size,
            'expandable': False,
            'children': [],
        }

    def _view_node_to_tree(self, node, dump_reader, max_depth: int, 
                           visited: set) -> Dict[str, Any]:
        """Convert a ViewNode to a tree dict for GUI display."""
        visit_key = (node.address, id(node))
        if visit_key in visited:
            return {
                'name': node.name,
                'type_name': node.type_name,
                'kind': node.kind,
                'raw_value': node.raw_value,
                'display_value': 'circular reference',
                'address': node.address,
                'byte_size': node.byte_size,
                'expandable': False,
                'children': [],
            }
        visited.add(visit_key)

        result = {
            'name': node.name,
            'type_name': node.type_name,
            'kind': node.kind,
            'raw_value': node.raw_value,
            'display_value': node.display_value,
            'address': node.address,
            'byte_size': node.byte_size,
            'expandable': node.expandable or (max_depth > 0 and node.kind in ('struct', 'union', 'array')),
            'children': [],
        }

        if max_depth > 0 and node.kind in ('struct', 'union'):
            if node.expandable and not node.children:
                self._expand_node(node, dump_reader)
            
            result['children'] = [
                self._view_node_to_tree(child, dump_reader, max_depth - 1, visited)
                for child in node.children
            ]
        
        elif max_depth > 0 and node.kind == 'array':
            result['children'] = [
                self._view_node_to_tree(child, dump_reader, max_depth - 1, visited)
                for child in node.children
            ]

        visited.discard(visit_key)
        return result

    def _expand_node(self, node, dump_reader):
        """Expand a ViewNode by reading its children from memory."""
        if node.kind not in ('struct', 'union'):
            return
        
        struct_type_name = node.meta.get('struct_type_name') or node.type_name
        struct_type = self.get_struct_type(struct_type_name)
        if not struct_type:
            return
        
        view_node = self.read_struct_as_node(struct_type, node.address, dump_reader)
        if view_node:
            node.children = view_node.children
            node.expandable = False


from .base import ELFParserFactory
ELFParserFactory.register('elftools', ElftoolsParser)