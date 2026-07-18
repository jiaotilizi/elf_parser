from .base import DisplayBase
from typing import Dict, List, Any
import json


class CliBasicDisplay(DisplayBase):
    def __init__(self, profile: Dict[str, Any], data_adapter=None):
        super().__init__(profile, data_adapter)
        self.show_hex = self.options.get('show_hex', True)
    
    def _print_section(self, title: str, data: List[Dict]):
        if not data:
            print(f"\n[{title}] Empty")
            return
        
        print(f"\n[{title}]")
        print("-" * 80)
        
        if self.show_hex:
            for item in data:
                print(json.dumps(item, indent=2, default=self._json_default))
        else:
            for item in data:
                print(item)
    
    def _json_default(self, obj):
        if isinstance(obj, int):
            if obj < 0:
                return obj
            return f"0x{obj:08X}"
        return str(obj)
    
    def show_rtos_tasks(self, tasks: List[Dict]):
        self._print_section("RTOS Tasks", tasks)
    
    def show_rtos_mutexes(self, mutexes: List[Dict]):
        self._print_section("RTOS Mutexes", mutexes)
    
    def show_rtos_semaphores(self, semaphores: List[Dict]):
        self._print_section("RTOS Semaphores", semaphores)
    
    def show_rtos_queues(self, queues: List[Dict]):
        self._print_section("RTOS Queues", queues)
    
    def show_rtos_events(self, events: List[Dict]):
        self._print_section("RTOS Events", events)
    
    def show_rtos_timers(self, timers: List[Dict]):
        self._print_section("RTOS Timers", timers)
    
    def show_rtos_block_pools(self, pools: List[Dict]):
        self._print_section("RTOS Block Pools", pools)
    
    def show_rtos_byte_pools(self, pools: List[Dict]):
        self._print_section("RTOS Byte Pools", pools)
    
    def show_test_points(self, test_points: List[Dict]):
        self._print_section("Test Points", test_points)
    
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
                
        except Exception as e:
            print(f"Error during display: {e}")