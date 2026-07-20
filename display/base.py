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
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class ResourceMetadata:
    def __init__(self, resource_type: str, label: str, icon: str = None, 
                 primary_key: str = 'address', fields: List[Dict] = None):
        self.resource_type = resource_type
        self.label = label
        self.icon = icon or '[Resource]'
        self.primary_key = primary_key
        self.fields = fields or []


class DisplayBase(ABC):
    def __init__(self, profile: Dict[str, Any], data_adapter=None):
        self.profile = profile
        self.data_adapter = data_adapter
        self.options = profile.get('display', {}).get('options', {})
    
    def get_resource_metadata(self, resource_type: str) -> Optional[ResourceMetadata]:
        if self.data_adapter:
            return self.data_adapter.get_resource_metadata(resource_type)
        return None
    
    def get_all_resource_types(self) -> List[str]:
        if self.data_adapter:
            return self.data_adapter.get_all_resource_types()
        return []
    
    def get_resource_data(self, resource_type: str) -> List[Dict]:
        if self.data_adapter:
            return self.data_adapter.get_resource_data(resource_type)
        return []
    
    @abstractmethod
    def show_resource(self, resource_type: str, data: List[Dict], metadata: ResourceMetadata):
        pass
    
    @abstractmethod
    def show_detail(self, resource_type: str, address: int):
        pass
    
    @abstractmethod
    def run(self):
        pass