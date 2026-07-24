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
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

from plugins.base import Plugin

logger = logging.getLogger(__name__)


class ArchPlugin(Plugin, ABC):
    def __init__(self, name: str, version: str, arch_name: str, description: str = ""):
        super().__init__(name, version, description)
        self.arch_name = arch_name

    @abstractmethod
    def get_register_info(self) -> Dict[str, Any]:
        """返回架构寄存器定义

        返回: {
            'registers': {'r0': 4, 'r1': 4, ..., 'pc': 4, 'lr': 4},
            'frame_pointer_reg': 'r7',
            'link_reg': 'lr',
            'stack_reg': 'sp',
            'program_counter_reg': 'pc',
            'flags_reg': 'xpsr',
        }
        """
        pass

    @abstractmethod
    def extract_registers(self, sp: int, frame_offsets: Dict[str, int],
                          dump_reader, is_32bit: bool) -> Dict[str, int]:
        """从栈中提取寄存器值

        参数:
            sp: 栈指针值
            frame_offsets: 寄存器名到偏移的映射 (由RTOS插件提供)
            dump_reader: 内存读取器
            is_32bit: 是否32位

        返回:
            {'r0': 0x1234, 'r1': 0x5678, ..., 'pc': 0x0800ABCD}
        """
        pass

    def get_fpu_register_info(self) -> Dict[str, Any]:
        """返回FPU寄存器定义（默认无FPU）"""
        return {}

    def extract_fpu_registers(self, sp: int, fpu_offsets: Dict[str, int],
                              dump_reader, is_32bit: bool) -> Dict[str, Any]:
        """从栈中提取FPU寄存器值"""
        return {}

    def get_mpu_register_map(self) -> Dict[str, int]:
        """返回MPU寄存器地址映射"""
        return {}

    def get_mpu_info(self, dump_reader) -> Dict[str, Any]:
        """读取MPU配置信息"""
        return {}

    def get_interrupt_controller_register_map(self) -> Dict[str, int]:
        """返回中断控制器寄存器地址映射"""
        return {}

    def get_interrupt_info(self, dump_reader) -> Dict[str, Any]:
        """读取中断控制器状态"""
        return {}

    @abstractmethod
    def unwind_stack(self, sp: int, fp: int, dump_reader, elf_parser,
                     is_32bit: bool, max_frames: int = 20,
                     start_pc: Optional[int] = None) -> List[Dict]:
        """展开调用栈

        参数:
            sp: 当前栈指针
            fp: 当前帧指针
            dump_reader: 内存读取器
            elf_parser: ELF解析器（用于符号查找）
            is_32bit: 是否32位
            max_frames: 最大展开帧数
            start_pc: 起始PC（用于CFI/exidx展开）。None时回退到FP链展开。

        返回: [
            {'pc': 0x0800ABCD, 'function': 'tx_main', 'offset': 0x10, 'fp': 0x20001000},
            {'pc': 0x08001234, 'function': 'app_init', 'offset': 0x24, 'fp': 0x20000FF0},
        ]
        """
        pass

    def get_supported_archs(self) -> List[str]:
        """返回支持的架构名称列表"""
        return [self.arch_name]

    def matches_arch(self, arch_name: str) -> bool:
        """判断是否匹配给定的架构名称"""
        return arch_name in self.get_supported_archs()