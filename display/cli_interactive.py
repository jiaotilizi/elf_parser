from .base import DisplayBase
from typing import Dict, List, Any
import re


class CliInteractiveDisplay(DisplayBase):
    def __init__(self, profile: Dict[str, Any], data_adapter=None):
        super().__init__(profile, data_adapter)
        self.show_hex = self.options.get('show_hex', True)
        self.show_address = self.options.get('show_address', True)
        self.max_rows = self.options.get('max_rows', 50)
        self.current_panel = 'tasks'
        self.panels = [
            ('tasks', 'Tasks'),
            ('mutexes', 'Mutexes'),
            ('semaphores', 'Semaphores'),
            ('queues', 'Queues'),
            ('events', 'Events'),
            ('timers', 'Timers'),
            ('block_pools', 'Block Pools'),
            ('byte_pools', 'Byte Pools'),
            ('test_points', 'Test Points'),
        ]
    
    def _format_hex(self, value: int) -> str:
        if value is None:
            return '-'
        if value < 0:
            return str(value)
        return f"0x{value:08X}"
    
    def _format_state(self, state: int) -> str:
        state_map = {
            0: 'Ready',
            1: 'Running',
            2: 'Suspended',
            3: 'Sleep',
            4: 'Queue Susp',
            5: 'Sema Susp',
            6: 'Mutex Susp',
            7: 'Event Susp',
        }
        return state_map.get(state, f"Unknown({state})")
    
    def _parse_jump_mark(self, mark_str: str) -> Dict:
        match = re.match(r'\[0x([0-9A-Fa-f]+)\|(.+)\]', mark_str)
        if match:
            return {
                'address': int(match.group(1), 16),
                'name': match.group(2)
            }
        return None
    
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
    
    def show_rtos_tasks(self, tasks: List[Dict]):
        print("\n--- ThreadX Tasks ---")
        header = ['magic', 'state', 'prio', 'runcount', 'name']
        rows = []
        for task in tasks:
            rows.append([
                self._format_hex(task.get('magic')),
                self._format_state(task.get('state', 0)),
                str(task.get('priority', 0)),
                str(task.get('run_count', 0)),
                task.get('name', '')[:24],
            ])
        self._print_table(header, rows)
    
    def show_rtos_mutexes(self, mutexes: List[Dict]):
        print("\n--- ThreadX Mutexes ---")
        header = ['magic', 'name', 'count', 'prio', 'owner', 'suspended']
        rows = []
        for mutex in mutexes:
            owner_info = mutex.get('owner')
            if owner_info and isinstance(owner_info, dict):
                owner_str = f"[0x{owner_info.get('address', 0):08X}|{owner_info.get('name', '')}]"
            elif owner_info:
                owner_str = f"0x{owner_info:08X}"
            else:
                owner_str = "-"
            rows.append([
                self._format_hex(mutex.get('magic')),
                mutex.get('name', '')[:16],
                str(mutex.get('count', 0)),
                str(mutex.get('priority', 0)),
                owner_str[:20],
                str(mutex.get('suspended_count', 0)),
            ])
        self._print_table(header, rows)
    
    def show_rtos_semaphores(self, semaphores: List[Dict]):
        print("\n--- ThreadX Semaphores ---")
        header = ['magic', 'name', 'count', 'suspended']
        rows = []
        for sem in semaphores:
            rows.append([
                self._format_hex(sem.get('magic')),
                sem.get('name', '')[:20],
                str(sem.get('count', 0)),
                str(sem.get('suspended_count', 0)),
            ])
        self._print_table(header, rows)
    
    def show_rtos_queues(self, queues: List[Dict]):
        print("\n--- ThreadX Queues ---")
        header = ['magic', 'name', 'entries', 'enqueued', 'suspended']
        rows = []
        for queue in queues:
            rows.append([
                self._format_hex(queue.get('magic')),
                queue.get('name', '')[:16],
                str(queue.get('max_entries', 0)),
                str(queue.get('enqueued_count', 0)),
                str(queue.get('suspended_count', 0)),
            ])
        self._print_table(header, rows)
    
    def show_rtos_events(self, events: List[Dict]):
        print("\n--- ThreadX Event Flags ---")
        header = ['magic', 'name', 'flags', 'suspended']
        rows = []
        for event in events:
            rows.append([
                self._format_hex(event.get('magic')),
                event.get('name', '')[:20],
                self._format_hex(event.get('flags', 0)),
                str(event.get('suspended_count', 0)),
            ])
        self._print_table(header, rows)
    
    def show_rtos_timers(self, timers: List[Dict]):
        print("\n--- ThreadX Timers ---")
        header = ['magic', 'name', 'period', 'ticks_remaining', 'active']
        rows = []
        for timer in timers:
            active_str = 'Yes' if timer.get('active', False) else 'No'
            rows.append([
                self._format_hex(timer.get('magic')),
                timer.get('name', '')[:20],
                str(timer.get('period_ticks', 0)),
                str(timer.get('ticks_remaining', 0)),
                active_str,
            ])
        self._print_table(header, rows)
    
    def show_rtos_block_pools(self, pools: List[Dict]):
        print("\n--- ThreadX Block Memory Pools ---")
        header = ['magic', 'name', 'total_blocks', 'available_blocks']
        rows = []
        for pool in pools:
            rows.append([
                self._format_hex(pool.get('magic')),
                pool.get('name', '')[:20],
                str(pool.get('total_blocks', 0)),
                str(pool.get('available_blocks', 0)),
            ])
        self._print_table(header, rows)
    
    def show_rtos_byte_pools(self, pools: List[Dict]):
        print("\n--- ThreadX Byte Memory Pools ---")
        header = ['magic', 'name', 'total_bytes', 'available_bytes']
        rows = []
        for pool in pools:
            rows.append([
                self._format_hex(pool.get('magic')),
                pool.get('name', '')[:20],
                str(pool.get('total_bytes', 0)),
                str(pool.get('available_bytes', 0)),
            ])
        self._print_table(header, rows)
    
    def show_test_points(self, test_points: List[Dict]):
        print("\n--- Test Points ---")
        header = ['cpu', 'timestamp', 'type', 'id', 'data']
        rows = []
        for tp in test_points[:self.max_rows]:
            rows.append([
                str(tp.get('cpu', 0)),
                str(tp.get('timestamp', '')),
                tp.get('type', '')[:16],
                str(tp.get('id', 0)),
                str(tp.get('data', '')),
            ])
        self._print_table(header, rows)
    
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
            if isinstance(value, int):
                value_str = self._format_hex(value)
            elif isinstance(value, dict):
                if 'address' in value and 'name' in value:
                    value_str = f"[0x{value['address']:08X}|{value['name']}]"
                else:
                    value_str = str(value)
            else:
                value_str = str(value)
            print(f"  {key}: {value_str}")
    
    def run(self):
        if not self.data_adapter:
            print("Error: Data adapter not provided")
            return
        
        try:
            rtos_data = self.data_adapter.get_rtos_data()
            
            if rtos_data.get('tasks'):
                self.show_rtos_tasks(rtos_data['tasks'])
            if rtos_data.get('mutexes'):
                self.show_rtos_mutexes(rtos_data['mutexes'])
            if rtos_data.get('semaphores'):
                self.show_rtos_semaphores(rtos_data['semaphores'])
            if rtos_data.get('queues'):
                self.show_rtos_queues(rtos_data['queues'])
            if rtos_data.get('events'):
                self.show_rtos_events(rtos_data['events'])
            if rtos_data.get('timers'):
                self.show_rtos_timers(rtos_data['timers'])
            if rtos_data.get('block_pools'):
                self.show_rtos_block_pools(rtos_data['block_pools'])
            if rtos_data.get('byte_pools'):
                self.show_rtos_byte_pools(rtos_data['byte_pools'])
            
            test_points = self.data_adapter.get_test_points()
            if test_points:
                self.show_test_points(test_points)
                
            print("\n--- Navigation ---")
            print("  Press Enter to select, Tab to switch panel, Q to quit")
            
        except Exception as e:
            print(f"Error during display: {e}")