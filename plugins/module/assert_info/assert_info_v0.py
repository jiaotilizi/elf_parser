from typing import Dict, List, Optional, Any
from plugins.module.base import ModulePlugin


class AssertInfoPlugin(ModulePlugin):
    def __init__(self):
        super().__init__(
            name='assert_info',
            version='0.1',
            module_type='analysis',
            description='Parse assertion/fault information from dump'
        )
        self._context = None
    
    def get_required_symbols(self) -> List[str]:
        return [
            'g_assert_info',
            's_assert_record',
            'g_fault_log',
        ]
    
    def get_required_structs(self) -> List[str]:
        return [
            'assert_info_t',
            'fault_record_t',
        ]
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        self.elf_parser = context.get('elf_parser')
        self.dump_reader = context.get('dump_reader')
        self.profile = context.get('profile')
        self._context = context
        return True
    
    def parse_assert_info(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return results
        
        is_32bit = elf_parser.is_32bit()
        
        assert_symbols = [
            'g_assert_info',
            's_assert_record',
            'assert_info',
            'g_fault_info',
        ]
        
        for sym_name in assert_symbols:
            sym = elf_parser.get_symbol_by_name(sym_name)
            if not sym:
                continue
            
            addr = sym['address']
            size = sym['size']
            
            assert_struct = elf_parser.get_struct_type('assert_info_t')
            if assert_struct:
                struct_size = assert_struct.get('byte_size', 64)
                count = min(size // struct_size, 10)
                
                for i in range(count):
                    assert_addr = addr + i * struct_size
                    parsed = elf_parser.parse_struct_from_dump(assert_struct.get('name', ''), assert_addr, dump_reader.dump_data)
                    if parsed:
                        results.append({
                            'address': assert_addr,
                            'index': i,
                            'struct': parsed,
                            **self._extract_assert_fields(parsed, is_32bit),
                        })
            else:
                raw_data = dump_reader.read_memory(addr, min(size, 512))
                if raw_data:
                    records = self._parse_raw_assert_info(raw_data, is_32bit)
                    results.extend(records)
        
        return results
    
    def _extract_assert_fields(self, parsed: Dict, is_32bit: bool) -> Dict:
        fields = {}
        
        for key, value in parsed.items():
            if isinstance(value, dict) and 'value' in value:
                fields[key] = value['value']
            else:
                fields[key] = value
        
        return fields
    
    def _parse_raw_assert_info(self, data: bytes, is_32bit: bool) -> List[Dict[str, Any]]:
        records = []
        record_size = 64
        
        num_records = min(len(data) // record_size, 10)
        
        for i in range(num_records):
            offset = i * record_size
            if offset + record_size > len(data):
                break
            
            record_data = data[offset:offset + record_size]
            
            record = {
                'address': 0,
                'index': i,
                'assert_id': 0,
                'file_name': '',
                'line_number': 0,
                'task_name': '',
                'timestamp': 0,
                'fault_code': 0,
            }
            
            record['assert_id'] = int.from_bytes(record_data[0:4], byteorder='little')
            
            name_addr = int.from_bytes(record_data[4:8], byteorder='little') if is_32bit else int.from_bytes(record_data[4:12], byteorder='little')
            if name_addr != 0 and hasattr(self, 'dump_reader'):
                record['file_name'] = self.dump_reader.read_string(name_addr, 64) or ''
            
            record['line_number'] = int.from_bytes(record_data[8:12], byteorder='little') if is_32bit else int.from_bytes(record_data[12:20], byteorder='little')
            
            task_name_addr = int.from_bytes(record_data[12:16], byteorder='little') if is_32bit else int.from_bytes(record_data[20:28], byteorder='little')
            if task_name_addr != 0 and hasattr(self, 'dump_reader'):
                record['task_name'] = self.dump_reader.read_string(task_name_addr, 32) or ''
            
            record['timestamp'] = int.from_bytes(record_data[16:20], byteorder='little') if is_32bit else int.from_bytes(record_data[28:36], byteorder='little')
            record['fault_code'] = int.from_bytes(record_data[20:24], byteorder='little') if is_32bit else int.from_bytes(record_data[36:44], byteorder='little')
            
            if record['assert_id'] != 0 or record['fault_code'] != 0:
                records.append(record)
        
        return records
    
    def get_detail(self, resource_type: str, address: int) -> Optional[Dict[str, Any]]:
        if not self._context:
            return None
        
        assert_info = self.parse_assert_info(self._context)
        for info in assert_info:
            if info.get('address') == address:
                return info
        
        return None
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._context = context
        return {
            'assert_info': self.parse_assert_info(context),
        }
