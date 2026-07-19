from .base import DisplayBase, ResourceMetadata
from typing import Dict, List, Any
import json


class CliBasicDisplay(DisplayBase):
    def __init__(self, profile: Dict[str, Any], data_adapter=None):
        super().__init__(profile, data_adapter)
        self.show_hex = self.options.get('show_hex', True)
    
    def _format_value(self, value, field_type: str = None):
        if field_type == 'hex':
            if isinstance(value, int):
                return f"0x{value:08X}"
        elif field_type == 'number':
            return str(value)
        elif field_type == 'string':
            return str(value)
        
        if isinstance(value, int):
            if value < 0:
                return str(value)
            return f"0x{value:08X}"
        return str(value)
    
    def _print_section(self, title: str, icon: str, data: List[Dict], metadata: ResourceMetadata):
        if not data:
            print(f"\n{icon} [{title}] Empty")
            return
        
        print(f"\n{icon} [{title}]")
        print("-" * 80)
        
        if metadata.fields:
            headers = [f['label'] for f in metadata.fields]
            header_line = " | ".join(f"{h:<16}" for h in headers)
            print(header_line)
            print("-" * 80)
            
            for item in data:
                values = []
                for field in metadata.fields:
                    field_name = field['name']
                    field_type = field.get('type', 'string')
                    value = self._get_nested_value(item, field_name)
                    formatted = self._format_value(value, field_type)
                    values.append(f"{formatted:<16}")
                print(" | ".join(values))
        else:
            if self.show_hex:
                for item in data:
                    print(json.dumps(item, indent=2, default=self._json_default))
            else:
                for item in data:
                    print(item)
    
    def _get_nested_value(self, item: Dict, field_name: str):
        keys = field_name.split('.')
        value = item
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return ''
        return value
    
    def _json_default(self, obj):
        if isinstance(obj, int):
            if obj < 0:
                return obj
            return f"0x{obj:08X}"
        return str(obj)
    
    def show_resource(self, resource_type: str, data: List[Dict], metadata: ResourceMetadata):
        self._print_section(metadata.label, metadata.icon, data, metadata)
    
    def show_detail(self, resource_type: str, address: int):
        if self.data_adapter:
            detail = self.data_adapter.get_detail(resource_type, address)
            print(f"\n[Detail] {resource_type} @ 0x{address:08X}")
            print("-" * 80)
            print(json.dumps(detail, indent=2, default=self._json_default))
        else:
            print(f"[Detail] No data adapter available")
    
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
                
        except Exception as e:
            print(f"Error during display: {e}")