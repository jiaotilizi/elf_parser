from .base import DisplayBase, ResourceMetadata
from typing import Dict, List, Any


class Trace32Display(DisplayBase):
    STATE_MAP = {
        0: 'Ready',
        1: 'Completed',
        2: 'Terminated',
        3: 'Suspended',
        4: 'Queue Susp',
        5: 'Sema Susp',
        6: 'Mutex Susp',
        7: 'Event Flag',
        8: 'Block Susp',
        9: 'Byte Susp',
        10: 'Time Susp',
        11: 'Mem Susp',
        12: 'Delay',
        13: 'Queue Susp',
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
        print("magic____|name________|count|prio_|owner_______|suspended___")
        
        for item in data:
            magic = self._format_hex(item.get('address', 0))
            name = item.get('name', '')[:10]
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
            
            print(f"{magic} |{name:<10}|{count_str}|{prio_str}|{owner:<11}|{suspended_str}")

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