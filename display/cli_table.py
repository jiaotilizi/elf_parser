from .base import DisplayBase, ResourceMetadata
from typing import Dict, List, Any
import re


class CliTableDisplay(DisplayBase):
    def __init__(self, profile: Dict[str, Any], data_adapter=None):
        super().__init__(profile, data_adapter)
        self.show_hex = self.options.get('show_hex', True)
        self.show_address = self.options.get('show_address', True)
        self.max_rows = self.options.get('max_rows', 50)
        self.current_panel = 'tasks'
    
    def _format_hex(self, value: int) -> str:
        if value is None:
            return '-'
        if value < 0:
            return str(value)
        return f"0x{value:08X}"
    
    def _parse_jump_mark(self, mark_str: str) -> Dict:
        match = re.match(r'\[0x([0-9A-Fa-f]+)\|(.+)\]', mark_str)
        if match:
            return {
                'address': int(match.group(1), 16),
                'name': match.group(2)
            }
        return None
    
    def _get_nested_value(self, item: Dict, field_name: str):
        keys = field_name.split('.')
        value = item
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return ''
        return value
    
    def _print_table(self, header: List[str], rows: List[List[str]]):
        if not rows:
            print("  (Empty)")
            return
        
        col_widths = [max(len(str(row[i])) for row in rows + [header]) for i in range(len(header))]
        
        header_str = "  ".join(f"{h:{w}}" for h, w in zip(header, col_widths))
        print(f"  {header_str}")
        print("  " + "-" * sum(col_widths) + "-" * (len(header) - 1) * 2)
        
        for row in rows[:self.max_rows]:
            row_str = "  ".join(f"{str(c):{w}}" for c, w in zip(row, col_widths))
            print(f"  {row_str}")
        
        if len(rows) > self.max_rows:
            print(f"  ... ({len(rows) - self.max_rows} more)")
    
    def _format_value(self, value, field_type: str = None):
        if field_type == 'hex':
            if isinstance(value, int):
                return self._format_hex(value)
        elif field_type == 'number':
            return str(value)
        elif field_type == 'string':
            return str(value)
        
        if isinstance(value, int):
            return self._format_hex(value)
        elif isinstance(value, dict):
            if 'address' in value and 'name' in value:
                return f"[0x{value['address']:08X}|{value['name']}]"
            return str(value)
        return str(value)
    
    def show_resource(self, resource_type: str, data: List[Dict], metadata: ResourceMetadata):
        print(f"\n--- {metadata.icon} {metadata.label} ---")
        
        if metadata.fields:
            headers = [f['label'] for f in metadata.fields]
            rows = []
            
            for item in data:
                row = []
                for field in metadata.fields:
                    field_name = field['name']
                    value = self._get_nested_value(item, field_name)
                    field_type = field.get('type', 'string')
                    formatted = self._format_value(value, field_type)
                    max_len = field.get('max_len', 25)
                    row.append(str(formatted)[:max_len])
                rows.append(row)
            
            self._print_table(headers, rows)
        else:
            for item in data[:self.max_rows]:
                name = item.get('name', '')
                addr = item.get('address', 0)
                print(f"  [{self._format_hex(addr)}] {name}")
    
    def show_detail(self, resource_type: str, address: int):
        if not self.data_adapter:
            print("  No data adapter available")
            return
        
        detail = self.data_adapter.get_detail(resource_type, address)
        if not detail:
            print(f"  No detail found for {resource_type} @ 0x{address:08X}")
            return
        
        print(f"\n--- Detail: {resource_type} @ 0x{address:08X} ---")
        for key, value in detail.items():
            value_str = self._format_value(value)
            print(f"  {key}: {value_str}")
    
    def run(self):
        if not self.data_adapter:
            print("Error: Data adapter not provided")
            return
        
        try:
            resource_types = self.data_adapter.get_all_resource_types()
            
            for resource_type in resource_types:
                data = self.data_adapter.get_resource_data(resource_type)
                metadata = self.data_adapter.get_resource_metadata(resource_type)
                self.show_resource(resource_type, data, metadata)
            
            print("\n--- Navigation ---")
            print("  Press Enter to select, Tab to switch panel, Q to quit")
            
        except Exception as e:
            print(f"Error during display: {e}")