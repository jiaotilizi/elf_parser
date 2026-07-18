from typing import Dict, List, Optional, Any
from core.plugin_manager import ModulePlugin


class AssertInfoPlugin(ModulePlugin):
    def __init__(self):
        super().__init__(
            name='assert_info',
            version='1.0',
            module_type='assert',
            description='Parse assertion information from global variable structures'
        )
    
    def get_required_symbols(self) -> List[str]:
        return [
            'g_assert_info',
            'g_assert_record',
            's_assert_buffer',
        ]
    
    def get_required_structs(self) -> List[str]:
        return [
            'assert_info_t',
            'assert_record_t',
        ]
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        self.elf_parser = context.get('elf_parser')
        self.dump_reader = context.get('dump_reader')
        self.profile = context.get('profile')
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
            'g_assert_record',
            's_assert_buffer',
            'assert_info',
            'assert_record',
        ]
        
        for sym_name in assert_symbols:
            sym = elf_parser.get_symbol_by_name(sym_name)
            if not sym:
                continue
            
            addr = sym['address']
            size = sym['size']
            
            assert_struct = elf_parser.get_struct_type('assert_info_t')
            if not assert_struct:
                assert_struct = elf_parser.get_struct_type('assert_record_t')
            
            if assert_struct:
                parsed = elf_parser.parse_struct_from_dump(assert_struct.get('name', ''), addr, dump_reader.dump_data)
                if parsed:
                    results.append({
                        'symbol': sym_name,
                        'address': addr,
                        'size': size,
                        'struct': parsed,
                    })
            else:
                raw_data = dump_reader.read_memory(addr, min(size, 256))
                if raw_data:
                    results.append({
                        'symbol': sym_name,
                        'address': addr,
                        'size': size,
                        'raw_hex': raw_data.hex(),
                    })
        
        return results
    
    def parse_assert_buffer(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return results
        
        is_32bit = elf_parser.is_32bit()
        
        buffer_symbols = [
            's_assert_buffer',
            'g_assert_buffer',
            'assert_buffer',
        ]
        
        for sym_name in buffer_symbols:
            sym = elf_parser.get_symbol_by_name(sym_name)
            if not sym:
                continue
            
            addr = sym['address']
            size = sym['size']
            
            if size > 0:
                buffer_data = dump_reader.read_memory(addr, size)
                if buffer_data:
                    records = self._parse_assert_records(buffer_data, size, is_32bit)
                    results.append({
                        'symbol': sym_name,
                        'address': addr,
                        'size': size,
                        'records': records,
                    })
        
        return results
    
    def _parse_assert_records(self, buffer_data: bytes, buffer_size: int, is_32bit: bool) -> List[Dict[str, Any]]:
        records = []
        record_size = 64
        
        num_records = buffer_size // record_size
        
        for i in range(num_records):
            offset = i * record_size
            if offset + record_size > len(buffer_data):
                break
            
            record_data = buffer_data[offset:offset + record_size]
            
            record = {
                'index': i,
                'file_name': '',
                'line_number': 0,
                'function_name': '',
                'assert_condition': '',
                'timestamp': 0,
                'task_id': 0,
            }
            
            file_name_addr = int.from_bytes(record_data[0:4], byteorder='little') if is_32bit else int.from_bytes(record_data[0:8], byteorder='little')
            record['line_number'] = int.from_bytes(record_data[4:8], byteorder='little') if is_32bit else int.from_bytes(record_data[8:16], byteorder='little')
            
            if file_name_addr != 0:
                record['file_name'] = self.dump_reader.read_string(file_name_addr, 64) if hasattr(self, 'dump_reader') else ''
            
            func_name_addr = int.from_bytes(record_data[8:12], byteorder='little') if is_32bit else int.from_bytes(record_data[16:24], byteorder='little')
            if func_name_addr != 0:
                record['function_name'] = self.dump_reader.read_string(func_name_addr, 64) if hasattr(self, 'dump_reader') else ''
            
            cond_addr = int.from_bytes(record_data[12:16], byteorder='little') if is_32bit else int.from_bytes(record_data[24:32], byteorder='little')
            if cond_addr != 0:
                record['assert_condition'] = self.dump_reader.read_string(cond_addr, 64) if hasattr(self, 'dump_reader') else ''
            
            record['timestamp'] = int.from_bytes(record_data[16:20], byteorder='little') if is_32bit else int.from_bytes(record_data[32:40], byteorder='little')
            record['task_id'] = int.from_bytes(record_data[20:24], byteorder='little') if is_32bit else int.from_bytes(record_data[40:44], byteorder='little')
            
            if record['file_name'] or record['line_number'] != 0:
                records.append(record)
        
        return records
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'assert_info': self.parse_assert_info(context),
            'assert_buffer': self.parse_assert_buffer(context),
        }