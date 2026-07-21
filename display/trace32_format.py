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
from .base import DisplayBase, ResourceMetadata
from typing import Dict, List, Any


class Trace32Display(DisplayBase):
    STATE_MAP = {
        0: 'Ready',
        1: 'Completed',
        2: 'Terminated',
        3: 'Suspended',
        4: 'Sleep',
        5: 'Queue Susp',
        6: 'Sema Susp',
        7: 'Event Flag',
        8: 'Block Mem',
        9: 'Byte Mem',
        10: 'I/O Susp',
        11: 'File Susp',
        12: 'Net Susp',
        13: 'Mutex Susp',
    }

    def __init__(self, profile: Dict[str, Any], data_adapter=None):
        super().__init__(profile, data_adapter)

    def _format_hex(self, value: int) -> str:
        if value is None or value == 0:
            return '00000000'
        return f"{value:08X}"

    def _format_decimal(self, value, width: int = 8) -> str:
        if value is None:
            value = 0
        return f"{value:{width}.1f}"

    def _get_nested_value(self, item: Dict, field_name: str):
        keys = field_name.split('.')
        value = item
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return ''
        return value

    def show_tasks(self, data: List[Dict]):
        print("\nThreadX.Task")
        print("=" * 78)
        print("magic____|state_______|prio|runcount|name___________________")
        
        for item in data:
            magic = self._format_hex(item.get('address', 0))
            state_code = item.get('state', 0)
            state = self.STATE_MAP.get(state_code, f'Unknown({state_code})')
            state = state[:11].ljust(11)
            prio = f"{item.get('priority', 0):>3}."
            runcount = item.get('run_count', 0)
            runcount_str = f"{runcount:>7}. "
            name = item.get('name', '')[:27]
            
            print(f"{magic} |{state}|{prio}|{runcount_str}|{name}")

    def show_semaphores(self, data: List[Dict]):
        print("\nThreadX.Semaphore")
        print("=" * 78)
        print("magic____count_suspended_name")
        
        for item in data:
            magic = self._format_hex(item.get('address', 0))
            count = item.get('count', 0)
            count_str = f"{count:>7}. "
            suspended = item.get('suspended_count', 0)
            suspended_str = f"{suspended:>7}. "
            name = item.get('name', '')[:40]
            
            print(f"{magic}{count_str}{suspended_str}{name}")

    def show_mutexes(self, data: List[Dict]):
        print("\nThreadX.Mutex")
        print("=" * 78)
        print("magic____|count|prio_|owner_______|suspended___|name________")
        
        for item in data:
            magic = self._format_hex(item.get('address', 0))
            count = item.get('inherit_count', 0)
            count_str = f"{count:>4}."
            prio = item.get('priority', 0)
            prio_str = f"{prio:>4}."
            owner_info = item.get('owner_info', {})
            owner = owner_info.get('name', '-') if owner_info else '-'
            if owner == '':
                owner = '-'
            owner = owner[:11]
            suspended = item.get('suspended_count', 0)
            suspended_str = f"{suspended:>7}. "
            name = item.get('name', '')[:10]
            
            print(f"{magic} |{count_str}|{prio_str}|{owner:<11}|{suspended_str}|{name:<10}")

    def show_queues(self, data: List[Dict]):
        print("\nThreadX.Queue")
        print("=" * 78)
        print("magic____capacity_msgsize_enqueued_suspended_name")
        
        for item in data:
            magic = self._format_hex(item.get('address', 0))
            capacity = item.get('max_messages', 0)
            capacity_str = f"{capacity:>7}. "
            msgsize = item.get('message_size', 0)
            msgsize_str = f"{msgsize:>7}. "
            enqueued = item.get('messages', 0)
            enqueued_str = f"{enqueued:>7}. "
            suspended = item.get('suspended_count', 0)
            suspended_str = f"{suspended:>7}. "
            name = item.get('name', '')[:40]
            
            print(f"{magic}{capacity_str}{msgsize_str}{enqueued_str}{suspended_str}{name}")

    def show_events(self, data: List[Dict]):
        print("\nThreadX.Event")
        print("=" * 78)
        print("magic_____current_suspended_name")
        
        for item in data:
            magic = self._format_hex(item.get('address', 0))[:8] + ' '
            current = f"{item.get('flags', 0):08X}"
            suspended = item.get('suspended_count', 0)
            suspended_str = f"{suspended:>7}. "
            name = item.get('name', '')[:40]
            
            print(f"{magic}{current} {suspended_str}{name}")

    def show_timers(self, data: List[Dict]):
        print("\nThreadX.Timer")
        print("=" * 78)
        print("magic____remain__reinit_function__name")
        
        for item in data:
            magic = self._format_hex(item.get('address', 0))
            remain = item.get('ticks_remaining', 0)
            remain_str = f"{remain:>7}. "
            reinit = item.get('period_ticks', 0)
            reinit_str = f"{reinit:>7}. "
            func = self._format_hex(item.get('expiration_function', 0))
            name = item.get('name', '')[:30]
            
            print(f"{magic}{remain_str}{reinit_str}  {func} {name}")

    def show_block_pools(self, data: List[Dict]):
        print("\nThreadX.BlockMemory")
        print("=" * 78)
        print("magic____available_total_blocksize_name")
        
        for item in data:
            magic = self._format_hex(item.get('address', 0))
            available = item.get('available_blocks', 0)
            available_str = f"{available:>7}. "
            total = item.get('total_blocks', 0)
            total_str = f"{total:>7}. "
            blocksize = item.get('block_size', 0)
            blocksize_str = f"{blocksize:>7}. "
            name = item.get('name', '')[:40]
            
            print(f"{magic}{available_str}{total_str}{blocksize_str}{name}")

    def show_byte_pools(self, data: List[Dict]):
        print("\nThreadX.ByteMemory")
        print("=" * 78)
        print("magic____available_total_name")
        
        for item in data:
            magic = self._format_hex(item.get('address', 0))
            available = item.get('available_bytes', 0)
            available_str = f"{available:>7}. "
            total = item.get('total_bytes', 0)
            total_str = f"{total:>7}. "
            name = item.get('name', '')[:50]
            
            print(f"{magic}{available_str}{total_str}{name}")

    def show_stack(self, data: List[Dict]):
        print("\nThreadX.Stack")
        print("=" * 110)
        print("____________________________name|low______high____|sp__________%|lowest___spare____max_|0____10____20____30____40____50____60____70____80____90____100|")
        
        for item in data:
            name = item.get('name', '')[:30].rjust(30)
            stack_start = item.get('stack_start', 0)
            stack_end = item.get('stack_end', 0)
            if stack_start > stack_end:
                low = stack_end
                high = stack_start
            else:
                low = stack_start
                high = stack_end
            
            sp = item.get('stack_current', 0) or item.get('stack_ptr', 0)
            
            stack_size = item.get('stack_size', 0)
            if stack_size <= 0:
                stack_size = abs(high - low)
            
            stack_high_water = item.get('stack_high_water', 0)
            if stack_high_water > 0 and stack_size > 0:
                used = stack_size - stack_high_water
                usage = used / stack_size * 100
            else:
                usage = item.get('stack_usage', 0)
            
            lowest = low if low > 0 else 0
            spare = stack_high_water if stack_high_water > 0 else 0
            
            progress_bar = ''
            usage_int = int(usage)
            segments = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
            char_counts = [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5]
            
            for i in range(len(segments) - 1):
                start = segments[i]
                end = segments[i + 1]
                count = char_counts[i]
                if usage_int >= end:
                    progress_bar += '#' * count
                elif usage_int >= start:
                    ratio = (usage_int - start) / (end - start)
                    filled = int(ratio * count)
                    progress_bar += '#' * filled + '-' * (count - filled)
                else:
                    progress_bar += '-' * count
            
            print(f"{name}|{low:08X} {high:08X}|{sp:08X} {usage:>4.1f}%|{lowest:08X} {spare:08X} {usage_int:>3}%|{progress_bar}|")

    def show_resource(self, resource_type: str, data: List[Dict], metadata: ResourceMetadata):
        if resource_type == 'tasks':
            self.show_tasks(data)
        elif resource_type == 'semaphores':
            self.show_semaphores(data)
        elif resource_type == 'mutexes':
            self.show_mutexes(data)
        elif resource_type == 'queues':
            self.show_queues(data)
        elif resource_type == 'events':
            self.show_events(data)
        elif resource_type == 'timers':
            self.show_timers(data)
        elif resource_type == 'block_pools':
            self.show_block_pools(data)
        elif resource_type == 'byte_pools':
            self.show_byte_pools(data)
        elif resource_type == 'stack':
            self.show_stack(data)

    def show_detail(self, resource_type: str, address: int):
        pass

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