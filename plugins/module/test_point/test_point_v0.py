from typing import Dict, List, Optional, Any
from plugins.base import ModulePlugin


class TestPointPlugin(ModulePlugin):
    def __init__(self):
        super().__init__(
            name='test_point',
            version='0.1',
            module_type='test',
            description='Parse test point/trace information from global variable structures'
        )
        self._context = None
    
    def get_required_symbols(self) -> List[str]:
        return [
            'g_test_point_array',
            'g_trace_buffer',
            's_test_points',
        ]
    
    def get_required_structs(self) -> List[str]:
        return [
            'test_point_t',
            'trace_record_t',
        ]
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        self.elf_parser = context.get('elf_parser')
        self.dump_reader = context.get('dump_reader')
        self.profile = context.get('profile')
        self._context = context
        return True
    
    def parse_test_points(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return results
        
        is_32bit = elf_parser.is_32bit()
        
        tp_symbols = [
            'g_test_point_array',
            's_test_points',
            'test_point_array',
            'g_tp_array',
        ]
        
        for cpu_id, sym_name in enumerate(tp_symbols):
            sym = elf_parser.get_symbol_by_name(sym_name)
            if not sym:
                continue
            
            addr = sym['address']
            size = sym['size']
            
            tp_struct = elf_parser.get_struct_type('test_point_t')
            if tp_struct:
                struct_size = tp_struct.get('byte_size', 32)
                count = size // struct_size
                
                if count > 0:
                    for i in range(count):
                        tp_addr = addr + i * struct_size
                        parsed = elf_parser.parse_struct_from_dump(tp_struct.get('name', ''), tp_addr, dump_reader.dump_data)
                        if parsed:
                            results.append({
                                'cpu': cpu_id,
                                'index': i,
                                'address': tp_addr,
                                'struct': parsed,
                                **self._extract_test_point_fields(parsed, is_32bit),
                            })
            else:
                raw_data = dump_reader.read_memory(addr, min(size, 512))
                if raw_data:
                    records = self._parse_raw_test_points(raw_data, size, is_32bit, cpu_id)
                    results.extend(records)
        
        return results
    
    def _extract_test_point_fields(self, parsed: Dict, is_32bit: bool) -> Dict:
        fields = {}
        
        for key, value in parsed.items():
            if isinstance(value, dict) and 'value' in value:
                fields[key] = value['value']
            else:
                fields[key] = value
        
        return fields
    
    def _parse_raw_test_points(self, data: bytes, size: int, is_32bit: bool, cpu_id: int = 0) -> List[Dict[str, Any]]:
        records = []
        record_size = 32
        
        num_records = size // record_size
        
        for i in range(num_records):
            offset = i * record_size
            if offset + record_size > len(data):
                break
            
            record_data = data[offset:offset + record_size]
            
            record = {
                'cpu': cpu_id,
                'index': i,
                'id': 0,
                'name': '',
                'count': 0,
                'timestamp_first': 0,
                'timestamp_last': 0,
                'min_duration': 0,
                'max_duration': 0,
                'avg_duration': 0,
            }
            
            record['id'] = int.from_bytes(record_data[0:4], byteorder='little')
            
            name_addr = int.from_bytes(record_data[4:8], byteorder='little') if is_32bit else int.from_bytes(record_data[4:12], byteorder='little')
            if name_addr != 0 and hasattr(self, 'dump_reader'):
                record['name'] = self.dump_reader.read_string(name_addr, 32) or ''
            
            record['count'] = int.from_bytes(record_data[8:12], byteorder='little') if is_32bit else int.from_bytes(record_data[12:20], byteorder='little')
            record['timestamp_first'] = int.from_bytes(record_data[12:16], byteorder='little') if is_32bit else int.from_bytes(record_data[20:28], byteorder='little')
            record['timestamp_last'] = int.from_bytes(record_data[16:20], byteorder='little') if is_32bit else int.from_bytes(record_data[28:36], byteorder='little')
            
            if is_32bit:
                record['min_duration'] = int.from_bytes(record_data[20:24], byteorder='little')
                record['max_duration'] = int.from_bytes(record_data[24:28], byteorder='little')
                record['avg_duration'] = int.from_bytes(record_data[28:32], byteorder='little')
            
            if record['id'] != 0 or record['name']:
                records.append(record)
        
        return records
    
    def parse_trace_buffer(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        elf_parser = context.get('elf_parser')
        dump_reader = context.get('dump_reader')
        
        if not elf_parser or not dump_reader:
            return results
        
        is_32bit = elf_parser.is_32bit()
        
        trace_symbols = [
            'g_trace_buffer',
            's_trace_buffer',
            'trace_buffer',
            'g_tb',
        ]
        
        for cpu_id, sym_name in enumerate(trace_symbols):
            sym = elf_parser.get_symbol_by_name(sym_name)
            if not sym:
                continue
            
            addr = sym['address']
            size = sym['size']
            
            trace_struct = elf_parser.get_struct_type('trace_record_t')
            if trace_struct:
                struct_size = trace_struct.get('byte_size', 24)
                count = size // struct_size
                
                if count > 0:
                    for i in range(count):
                        trace_addr = addr + i * struct_size
                        parsed = elf_parser.parse_struct_from_dump(trace_struct.get('name', ''), trace_addr, dump_reader.dump_data)
                        if parsed:
                            results.append({
                                'cpu': cpu_id,
                                'index': i,
                                'address': trace_addr,
                                'struct': parsed,
                                **self._extract_trace_fields(parsed, is_32bit),
                            })
            else:
                raw_data = dump_reader.read_memory(addr, min(size, 1024))
                if raw_data:
                    records = self._parse_raw_trace_records(raw_data, size, is_32bit, cpu_id)
                    results.extend(records)
        
        return results
    
    def _extract_trace_fields(self, parsed: Dict, is_32bit: bool) -> Dict:
        fields = {}
        
        for key, value in parsed.items():
            if isinstance(value, dict) and 'value' in value:
                fields[key] = value['value']
            else:
                fields[key] = value
        
        return fields
    
    def _parse_raw_trace_records(self, data: bytes, size: int, is_32bit: bool, cpu_id: int = 0) -> List[Dict[str, Any]]:
        records = []
        record_size = 24
        
        num_records = size // record_size
        
        for i in range(num_records):
            offset = i * record_size
            if offset + record_size > len(data):
                break
            
            record_data = data[offset:offset + record_size]
            
            record = {
                'cpu': cpu_id,
                'index': i,
                'timestamp': 0,
                'point_id': 0,
                'task_id': 0,
                'event_type': 0,
                'data': 0,
                'type': self._get_trace_type(0),
            }
            
            record['timestamp'] = int.from_bytes(record_data[0:4], byteorder='little') if is_32bit else int.from_bytes(record_data[0:8], byteorder='little')
            record['point_id'] = int.from_bytes(record_data[4:8], byteorder='little') if is_32bit else int.from_bytes(record_data[8:12], byteorder='little')
            record['task_id'] = int.from_bytes(record_data[8:12], byteorder='little') if is_32bit else int.from_bytes(record_data[12:16], byteorder='little')
            record['event_type'] = int.from_bytes(record_data[12:16], byteorder='little') if is_32bit else int.from_bytes(record_data[16:20], byteorder='little')
            record['data'] = int.from_bytes(record_data[16:20], byteorder='little') if is_32bit else int.from_bytes(record_data[20:28], byteorder='little')
            record['type'] = self._get_trace_type(record['event_type'])
            
            if record['timestamp'] != 0:
                records.append(record)
        
        return records
    
    def _get_trace_type(self, event_type: int) -> str:
        type_map = {
            0: 'TEST POINT',
            1: 'ENTER SLEEP',
            2: 'LEAVE SLEEP',
            3: 'ENTER IRQ',
            4: 'LEAVE IRQ',
            5: 'IDLE',
            6: 'TASK',
        }
        return type_map.get(event_type, f'UNKNOWN({event_type})')
    
    def get_detail(self, resource_type: str, address: int) -> Optional[Dict[str, Any]]:
        if not self._context:
            return None
        
        if resource_type == 'test_points':
            test_points = self.parse_test_points(self._context)
            for tp in test_points:
                if tp.get('address') == address:
                    return tp
        
        return None
    
    def format_trace_log(self, trace_records: List[Dict]) -> str:
        lines = []
        lines.append("timestamp      |cpu|type          |point_id|task_id|data")
        lines.append("--------------|---|--------------|--------|-------|-----")
        
        for record in trace_records:
            timestamp = record.get('timestamp', 0)
            cpu = record.get('cpu', 0)
            trace_type = record.get('type', '')
            point_id = record.get('point_id', 0)
            task_id = record.get('task_id', 0)
            data = record.get('data', 0)
            
            lines.append(f"{timestamp:14d}|{cpu:3d}|{trace_type:14s}|{point_id:8d}|{task_id:7d}|{data:X}")
        
        return '\n'.join(lines)
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._context = context
        return {
            'test_points': self.parse_test_points(context),
            'trace_buffer': self.parse_trace_buffer(context),
        }
