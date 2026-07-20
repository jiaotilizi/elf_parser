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
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class PluginResult:
    def __init__(self, 
                 display_type: str = 'raw',
                 title: str = '',
                 columns: List[str] = None,
                 rows: List[Dict] = None,
                 data: Any = None,
                 view_config: Dict = None):
        self.display_type = display_type
        self.title = title
        self.columns = columns or []
        self.rows = rows or []
        self.data = data
        self.view_config = view_config or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'display_type': self.display_type,
            'title': self.title,
            'columns': self.columns,
            'rows': self.rows,
            'data': self.data,
            'view_config': self.view_config,
        }


class Plugin:
    def __init__(self, name: str, version: str, description: str = ""):
        self.name = name
        self.version = version
        self.description = description
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        return True
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {}
    
    def get_required_symbols(self) -> List[str]:
        return []
    
    def get_required_structs(self) -> List[str]:
        return []
    
    def get_display_config(self) -> Dict[str, Any]:
        return {
            'display_type': 'table',
            'title': self.name,
        }
