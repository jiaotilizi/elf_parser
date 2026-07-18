import os
import struct
from typing import Dict, List, Optional, Tuple, Any
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection
from elftools.dwarf.dwarfinfo import DWARFInfo
from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE


class ELFParser:
    def __init__(self, elf_path: str):
        self.elf_path = elf_path
        self.elffile = None
        self.dwarfinfo = None
        
        self._symbol_cache: Dict[str, Tuple[int, int, str]] = {}
        self._cu_cache: List[Tuple[int, int, int]] = []
        self._struct_type_cache: Dict[str, Any] = {}
        
        self._is_32bit = False
        self._address_size = 4
        
        self._parse_elf()
    
    def _parse_elf(self):
        with open(self.elf_path, 'rb') as f:
            self.elffile = ELFFile(f)
            self._is_32bit = self.elffile.elfclass == 32
            self._address_size = 4 if self._is_32bit else 8
            
            self._parse_symbols()
            
            if self.elffile.has_dwarf_info():
                self.dwarfinfo = self.elffile.get_dwarf_info()
                self._build_cu_index()
                self._build_type_cache()
    
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
        if not self.dwarfinfo:
            return
        
        for cu_idx, cu in enumerate(self.dwarfinfo.iter_CUs()):
            try:
                low_pc = cu.get_low_pc()
                high_pc = cu.get_high_pc()
            except AttributeError:
                low_pc = None
                high_pc = None
            
            if low_pc is not None and high_pc is not None:
                self._cu_cache.append((low_pc, high_pc, cu_idx))
        
        self._cu_cache.sort(key=lambda x: x[0])
    
    def _build_type_cache(self):
        if not self.dwarfinfo:
            return

        # 第一遍：收集所有类型 DIE，按 offset 建立索引
        die_by_offset: Dict[int, 'DIE'] = {}
        for cu in self.dwarfinfo.iter_CUs():
            for die in cu.iter_DIEs():
                if die.tag:
                    die_by_offset[die.offset] = die

        # 第二遍：构建类型信息
        for die in die_by_offset.values():
            tag = die.tag
            type_info = None

            if tag in ('DW_TAG_structure_type', 'DW_TAG_union_type'):
                type_info = self._parse_struct_die(die, die_by_offset)
            elif tag == 'DW_TAG_enumeration_type':
                type_info = self._parse_enum_die(die)
            elif tag == 'DW_TAG_base_type':
                type_info = self._parse_base_type(die)
            elif tag == 'DW_TAG_typedef':
                type_info = self._parse_typedef_die(die, die_by_offset)
            elif tag == 'DW_TAG_pointer_type':
                type_info = self._parse_pointer_die(die, die_by_offset)
            elif tag == 'DW_TAG_array_type':
                type_info = self._parse_array_die(die, die_by_offset)

            if type_info:
                # 把 typedef 名字、有名字的结构体/枚举/基础类型都登记到 _struct_type_cache
                name = type_info.get('name')
                if name:
                    self._struct_type_cache[name] = type_info

        # 第三遍：构建全局变量的类型索引（按变量名 → 类型信息）
        self._var_type_cache: Dict[str, Dict[str, Any]] = {}
        for die in die_by_offset.values():
            if die.tag == 'DW_TAG_variable':
                name_attr = die.attributes.get('DW_AT_name')
                if not name_attr:
                    continue
                var_name = name_attr.value.decode('utf-8', errors='replace')
                ref_die = self._resolve_type_ref(die, die_by_offset)
                if ref_die:
                    var_type_info = self._parse_any_die(ref_die, die_by_offset)
                    if var_type_info:
                        # 同时存"按原始类型偏移"和"按变量名"两份索引
                        self._var_type_cache[var_name] = var_type_info

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

    def _parse_struct_die(self, die: DIE, die_by_offset: Dict[int, 'DIE'], _depth: int = 0) -> Dict[str, Any]:
        if _depth > 8:
            return {'kind': 'struct', 'name': None, 'byte_size': 0, 'members': [], '_truncated': True}
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
                member = self._parse_member(child, die_by_offset, _depth + 1)
                if member:
                    info['members'].append(member)
        return info

    def _parse_typedef_die(self, die: DIE, die_by_offset: Dict[int, 'DIE'], _depth: int = 0) -> Dict[str, Any]:
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
            ref_info = self._parse_any_die(ref_die, die_by_offset, _depth)
            if ref_info:
                info['ref_type'] = ref_info
                info['byte_size'] = ref_info.get('byte_size', 0)
                # typedef 直接继承被引用类型的 members，这样上层可当作结构体使用
                if 'members' in ref_info:
                    info['members'] = ref_info['members']
        return info

    def _parse_pointer_die(self, die: DIE, die_by_offset: Dict[int, 'DIE'], _depth: int = 0) -> Dict[str, Any]:
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
            info['ref_type'] = self._parse_any_die(ref_die, die_by_offset, _depth)
            # 如果最终指向 char（可能经过 const_type 修饰），给个友好名字
            if self._is_char_pointer(info):
                info['name'] = 'char*'
        return info

    def _is_char_pointer(self, type_info: Optional[Dict[str, Any]]) -> bool:
        """递归判断一个 pointer 类型是否最终指向 char。"""
        if not type_info:
            return False
        ref = type_info.get('ref_type')
        while ref:
            kind = ref.get('kind')
            if kind == 'base':
                return ref.get('name') == 'char'
            elif kind in ('const', 'volatile', 'typedef'):
                ref = ref.get('ref_type')
            else:
                return False
        return False

    def _parse_const_die(self, die: DIE, die_by_offset: Dict[int, 'DIE'], _depth: int = 0) -> Dict[str, Any]:
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
            info['ref_type'] = self._parse_any_die(ref_die, die_by_offset, _depth)
            if info['ref_type']:
                info['byte_size'] = info['ref_type'].get('byte_size', 0)
                if info['ref_type'].get('name'):
                    info['name'] = 'const ' + info['ref_type']['name']
        return info

    def _parse_array_die(self, die: DIE, die_by_offset: Dict[int, 'DIE'], _depth: int = 0) -> Dict[str, Any]:
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
            info['element_type'] = self._parse_any_die(ref_die, die_by_offset, _depth)

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

    def _parse_any_die(self, die: 'DIE', die_by_offset: Dict[int, 'DIE'], _depth: int = 0) -> Optional[Dict[str, Any]]:
        tag = die.tag
        if tag in ('DW_TAG_structure_type', 'DW_TAG_union_type'):
            return self._parse_struct_die(die, die_by_offset, _depth)
        elif tag == 'DW_TAG_enumeration_type':
            return self._parse_enum_die(die)
        elif tag == 'DW_TAG_base_type':
            return self._parse_base_type(die)
        elif tag == 'DW_TAG_typedef':
            return self._parse_typedef_die(die, die_by_offset, _depth)
        elif tag == 'DW_TAG_pointer_type':
            return self._parse_pointer_die(die, die_by_offset, _depth)
        elif tag == 'DW_TAG_array_type':
            return self._parse_array_die(die, die_by_offset, _depth)
        elif tag == 'DW_TAG_const_type':
            return self._parse_const_die(die, die_by_offset, _depth)
        elif tag == 'DW_TAG_volatile_type':
            # volatile 处理逻辑同 const
            return self._parse_const_die(die, die_by_offset, _depth)
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

    def _parse_member(self, die: DIE, die_by_offset: Dict[int, 'DIE'], _depth: int = 0) -> Dict[str, Any]:
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
            # 数据成员位置可能是 DW_FORM_exprloc（一个字节数组，如 [DW_OP_plus_uconst, N]）
            if isinstance(val, bytes):
                # 解析简单的 DW_OP_plus_uconst (0x23) 后跟 LEB128
                if len(val) >= 2 and val[0] == 0x23:
                    n = 0
                    shift = 0
                    for b in val[1:]:
                        n |= (b & 0x7f) << shift
                        if not (b & 0x80):
                            break
                        shift += 7
                    member['offset'] = n
            else:
                member['offset'] = val

        if 'DW_AT_byte_size' in die.attributes:
            member['byte_size'] = die.attributes['DW_AT_byte_size'].value

        if 'DW_AT_type' in die.attributes:
            ref_die = self._resolve_type_ref(die, die_by_offset)
            if ref_die:
                member['type_offset'] = ref_die.offset
                type_info = self._parse_any_die(ref_die, die_by_offset, _depth)
                if type_info:
                    member['type'] = type_info
                    member['type_name'] = type_info.get('name') or type_info.get('kind')
                    if type_info.get('byte_size'):
                        member['byte_size'] = type_info['byte_size']
        return member

    # ------------------------------------------------------------------
    # 自动结构体解析（递归展开嵌套结构体、数组、指针）
    # ------------------------------------------------------------------
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
        """
        sym = self.get_symbol_by_name(var_name)
        if not sym:
            return None

        # 直接用 DWARF 中变量声明的真实类型
        type_info = self._var_type_cache.get(var_name)
        if not type_info:
            return None

        return self._read_typed_value(type_info, sym['address'], dump_reader, depth=0)

    def _read_typed_value(self, type_info: Dict[str, Any], address: int,
                         dump_reader, depth: int = 0) -> Any:
        if depth > 8:
            return {'error': 'max depth exceeded'}

        if not type_info:
            return None

        kind = type_info.get('kind')

        # typedef/const/volatile：解引用后再走一遍
        if kind in ('typedef', 'const', 'volatile'):
            return self._read_typed_value(type_info.get('ref_type'), address, dump_reader, depth + 1)

        # 基础类型：直接读取
        if kind == 'base':
            bs = type_info.get('byte_size', 4)
            if bs == 1:
                return dump_reader.read_uint8(address)
            elif bs == 2:
                return dump_reader.read_uint16(address)
            elif bs == 4:
                return dump_reader.read_uint32(address)
            elif bs == 8:
                return dump_reader.read_uint64(address)
            return None

        # 指针
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
            # char* → 自动解引用读取字符串
            if self._is_char_pointer(type_info):
                if ptr_val == 0:
                    return None
                try:
                    return dump_reader.read_string(ptr_val)
                except Exception:
                    return f'<ptr 0x{ptr_val:0{hex_width}x}>'
            # 其他指针：返回 hex 值
            return f'<ptr 0x{ptr_val:0{hex_width}x}>'

        # 数组：逐元素读取
        if kind == 'array':
            elem_type = type_info.get('element_type')
            count = type_info.get('element_count', 0)
            elem_size = elem_type.get('byte_size', 0) if elem_type else 0
            if not elem_size:
                return []
            result = []
            for i in range(count):
                elem_addr = address + i * elem_size
                result.append(self._read_typed_value(elem_type, elem_addr, dump_reader, depth + 1))
            return result

        # 结构体：逐成员读取
        if kind in ('struct', 'union'):
            result = {}
            for m in type_info.get('members', []):
                m_name = m.get('name') or f'<anon@{m.get("offset")}>'
                m_addr = address + m.get('offset', 0)
                result[m_name] = self._read_typed_value(m.get('type'), m_addr, dump_reader, depth + 1)
            return result

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
        result = []
        for name in self._symbol_cache:
            addr, size, stype = self._symbol_cache[name]
            result.append({
                'name': name,
                'address': addr,
                'size': size,
                'type': stype,
            })
        return result

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
        for low_pc, high_pc, cu_idx in self._cu_cache:
            if low_pc <= address < high_pc:
                cu = list(self.dwarfinfo.iter_CUs())[cu_idx]
                return self._search_function_in_cu(address, cu)
        
        return None
    
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
        return self._struct_type_cache.get(struct_name)

    def read_memory_from_dump(self, address: int, size: int, dump_data: bytes) -> Optional[bytes]:
        for seg in self.elffile.iter_segments():
            if seg['p_type'] == 'PT_LOAD':
                seg_vaddr = seg['p_vaddr']
                seg_memsz = seg['p_memsz']

                if seg_vaddr <= address < seg_vaddr + seg_memsz:
                    dump_offset = address - seg_vaddr
                    if dump_offset + size <= len(dump_data):
                        return dump_data[dump_offset:dump_offset + size]
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
        return {
            'class': self.elffile.elfclass,
            'machine': self.elffile.get_machine_arch(),
            'entry': self.elffile.header['e_entry'],
            'num_sections': self.elffile.num_sections(),
            'num_segments': self.elffile.num_segments(),
        }
    
    def is_32bit(self) -> bool:
        return self._is_32bit
    
    def get_address_size(self) -> int:
        return self._address_size