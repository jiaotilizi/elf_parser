from abc import ABC, abstractmethod
from typing import Dict, List, Any


class DisplayBase(ABC):
    def __init__(self, profile: Dict[str, Any], data_adapter=None):
        self.profile = profile
        self.data_adapter = data_adapter
        self.options = profile.get('display', {}).get('options', {})
    
    @abstractmethod
    def show_rtos_tasks(self, tasks: List[Dict]):
        pass
    
    @abstractmethod
    def show_rtos_mutexes(self, mutexes: List[Dict]):
        pass
    
    @abstractmethod
    def show_rtos_semaphores(self, semaphores: List[Dict]):
        pass
    
    @abstractmethod
    def show_rtos_queues(self, queues: List[Dict]):
        pass
    
    @abstractmethod
    def show_rtos_events(self, events: List[Dict]):
        pass
    
    @abstractmethod
    def show_rtos_timers(self, timers: List[Dict]):
        pass
    
    @abstractmethod
    def show_rtos_block_pools(self, pools: List[Dict]):
        pass
    
    @abstractmethod
    def show_rtos_byte_pools(self, pools: List[Dict]):
        pass
    
    @abstractmethod
    def show_test_points(self, test_points: List[Dict]):
        pass
    
    @abstractmethod
    def show_detail(self, resource_type: str, address: int):
        pass
    
    @abstractmethod
    def run(self):
        pass