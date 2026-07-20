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
from typing import Dict, Any


class DisplayFactory:
    @staticmethod
    def create(scheme: str, profile: Dict[str, Any], data_adapter=None):
        if scheme == 'cli_basic':
            from .cli_basic import CliBasicDisplay
            return CliBasicDisplay(profile, data_adapter)
        elif scheme == 'cli_table' or scheme == 'cli_interactive':
            from .cli_table import CliTableDisplay
            return CliTableDisplay(profile, data_adapter)
        elif scheme == 'web_gui':
            from .web_gui import WebGuiDisplay
            return WebGuiDisplay(profile, data_adapter)
        elif scheme == 'trace32':
            from .trace32_format import Trace32Display
            return Trace32Display(profile, data_adapter)
        else:
            from .cli_basic import CliBasicDisplay
            return CliBasicDisplay(profile, data_adapter)
    
    @staticmethod
    def get_supported_schemes():
        return ['cli_basic', 'cli_table', 'web_gui', 'trace32']