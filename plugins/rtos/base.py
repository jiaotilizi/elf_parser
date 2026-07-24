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
from enum import Enum
from typing import Dict, List, Optional, Any

from plugins.base import Plugin

logger = logging.getLogger(__name__)


class ResourceType(str, Enum):
    TASKS = 'tasks'
    MUTEXES = 'mutexes'
    SEMAPHORES = 'semaphores'
    QUEUES = 'queues'
    EVENTS = 'events'
    TIMERS = 'timers'
    BLOCK_POOLS = 'block_pools'
    BYTE_POOLS = 'byte_pools'
    TEST_POINTS = 'test_points'
    ASSERT_INFO = 'assert_info'


RESOURCE_TYPE_MAP = {
    'task': ResourceType.TASKS,
    'mutex': ResourceType.MUTEXES,
    'semaphore': ResourceType.SEMAPHORES,
    'queue': ResourceType.QUEUES,
    'event': ResourceType.EVENTS,
    'timer': ResourceType.TIMERS,
    'block_pool': ResourceType.BLOCK_POOLS,
    'byte_pool': ResourceType.BYTE_POOLS,
    'test_point': ResourceType.TEST_POINTS,
}


def normalize_resource_type(resource_type: str) -> str:
    if not resource_type:
        return resource_type
    try:
        return ResourceType(resource_type).value
    except ValueError:
        return RESOURCE_TYPE_MAP.get(resource_type, resource_type)


class RTOSPlugin(Plugin):
    def __init__(self, name: str, version: str, os_name: str, os_version: str, description: str = ""):
        super().__init__(name, version, description)
        self.os_name = os_name
        self.os_version = os_version
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        self._elf_parser = context.get('elf_parser')
        self._dump_reader = context.get('dump_reader')
        self._profile = context.get('profile')
        self._context = context
        return True
    
    def get_resource_types(self) -> List[str]:
        return []
    
    def get_resource(self, resource_type: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        normalized_type = normalize_resource_type(resource_type)
        return []
    
    def get_tasks(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('tasks', context)
    
    def get_semaphores(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('semaphores', context)
    
    def get_mutexes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('mutexes', context)
    
    def get_queues(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('queues', context)
    
    def get_timers(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('timers', context)
    
    def get_events(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.get_resource('events', context)
    
    def get_heap_info(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {}
    
    def get_display_config(self) -> Dict[str, Any]:
        return {
            'display_type': 'tree',
            'title': f"{self.os_name} {self.os_version}",
            'view_config': {
                'expand_level': 2,
                'show_address': True,
            }
        }

    def get_stack_frame_layout(self, arch_name: str) -> Optional[Dict[str, int]]:
        """返回寄存器在栈上的偏移映射

        这是RTOS与Arch的唯一耦合点，但只是数据(偏移表)，不是代码依赖。
        栈帧布局由RTOS的port汇编代码定义。

        Args:
            arch_name: 架构名称（如 'armv7-m', 'armv7-r'）

        Returns:
            寄存器名到偏移的映射，如 {'r0': 36, 'r1': 40, ..., 'pc': 60}
        """
        return None

    def get_fpu_frame_layout(self, arch_name: str) -> Optional[Dict[str, int]]:
        """返回FPU寄存器在栈上的偏移映射"""
        return None

    def get_smp_info(self, elf_parser, dump_reader) -> Dict[str, Any]:
        """获取SMP信息

        Returns:
            {
                'is_smp': False,
                'core_count': 1,
                'current_threads': [thread_addr, ...]  # 每个core的当前线程
            }
        """
        return {'is_smp': False, 'core_count': 1, 'current_threads': [None]}

    def enhance_threads_with_arch(self, tasks: List[Dict], context: Dict) -> None:
        """使用arch插件增强任务信息(寄存器+调用栈)

        此方法在tasks基本解析完成后调用，原地修改task dict。
        如果context中没有arch_plugin，则静默跳过(优雅降级)。

        Args:
            tasks: 任务列表
            context: 分析上下文
        """
        arch_plugin = context.get('arch_plugin')
        if not arch_plugin:
            return

        arch_name = context['profile'].get('arch', '') or context['profile'].get('chip', {}).get('arch', '')
        frame_offsets = self.get_stack_frame_layout(arch_name)
        if not frame_offsets:
            return

        is_32bit = context['elf_parser'].is_32bit()
        dump_reader = context['dump_reader']
        elf_parser = context['elf_parser']
        reg_info = arch_plugin.get_register_info()
        fp_reg = reg_info.get('frame_pointer_reg', 'r7')

        smp_info = context.get('_smp_info', {})
        current_threads = smp_info.get('current_threads', [None])

        task_by_addr = {t['address']: t for t in tasks}

        for task in tasks:
            sp = task.get('stack_current', 0)
            if not sp:
                continue
            try:
                registers = arch_plugin.extract_registers(
                    sp, frame_offsets, dump_reader, is_32bit)
                task['registers'] = registers

                fp = registers.get(fp_reg, 0)
                start_pc = registers.get('pc', 0)
                task['backtrace'] = arch_plugin.unwind_stack(
                    sp, fp, dump_reader, elf_parser, is_32bit,
                    start_pc=start_pc if start_pc else None)

                fpu_offsets = self.get_fpu_frame_layout(arch_name)
                if fpu_offsets:
                    fpu_registers = arch_plugin.extract_fpu_registers(
                        sp, fpu_offsets, dump_reader, is_32bit)
                    task['fpu_registers'] = fpu_registers

            except Exception as e:
                logger.debug("Thread %s arch analysis failed: %s",
                            task.get('name', '?'), e)
                task['registers'] = {}
                task['backtrace'] = []

        for core_id, thread_addr in enumerate(current_threads):
            if thread_addr and thread_addr in task_by_addr:
                task_by_addr[thread_addr]['running_on_core'] = core_id