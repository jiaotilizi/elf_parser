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

from plugins.arch.base import ArchPlugin

logger = logging.getLogger(__name__)


class ArmV7MArchPlugin(ArchPlugin):
    def __init__(self):
        super().__init__(
            name='armv7_m',
            version='1.0',
            arch_name='armv7-m',
            description='ARMv7-M architecture plugin (Cortex-M0/M3/M4/M7)'
        )

    def get_register_info(self) -> Dict[str, Any]:
        return {
            'registers': {f'r{i}': 4 for i in range(16)},
            'frame_pointer_reg': 'r7',
            'link_reg': 'lr',
            'stack_reg': 'sp',
            'program_counter_reg': 'pc',
            'flags_reg': 'xpsr',
        }

    def extract_registers(self, sp: int, frame_offsets: Dict[str, int],
                          dump_reader, is_32bit: bool) -> Dict[str, int]:
        registers = {}
        for reg_name, offset in frame_offsets.items():
            addr = sp + offset
            try:
                if is_32bit:
                    registers[reg_name] = dump_reader.read_uint32(addr)
                else:
                    registers[reg_name] = dump_reader.read_uint64(addr)
            except Exception as e:
                logger.debug(f"Failed to read register {reg_name} at 0x{addr:08x}: {e}")
                registers[reg_name] = 0
        return registers

    def get_fpu_register_info(self) -> Dict[str, Any]:
        return {
            'registers': {f'S{i}': 4 for i in range(32)} | {'FPSCR': 4},
        }

    def extract_fpu_registers(self, sp: int, fpu_offsets: Dict[str, int],
                              dump_reader, is_32bit: bool) -> Dict[str, Any]:
        registers = {}
        for reg_name, offset in fpu_offsets.items():
            addr = sp + offset
            try:
                if is_32bit:
                    registers[reg_name] = dump_reader.read_uint32(addr)
                else:
                    registers[reg_name] = dump_reader.read_uint64(addr)
            except Exception as e:
                logger.debug(f"Failed to read FPU register {reg_name} at 0x{addr:08x}: {e}")
                registers[reg_name] = 0
        return registers

    def get_mpu_register_map(self) -> Dict[str, int]:
        return {
            'MPU_TYPE': 0xE000ED90,
            'MPU_CTRL': 0xE000ED94,
            'MPU_RNR': 0xE000ED98,
            'MPU_RBAR': 0xE000ED9C,
            'MPU_RASR': 0xE000EDA0,
        }

    def get_mpu_info(self, dump_reader) -> Dict[str, Any]:
        mpu_map = self.get_mpu_register_map()
        try:
            mpu_type = dump_reader.read_uint32(mpu_map['MPU_TYPE'])
            mpu_ctrl = dump_reader.read_uint32(mpu_map['MPU_CTRL'])

            region_count = mpu_type & 0xFF
            enabled = (mpu_ctrl & 0x01) != 0

            regions = []
            if enabled and region_count > 0:
                for i in range(region_count):
                    dump_reader.write_uint32(mpu_map['MPU_RNR'], i)
                    rbar = dump_reader.read_uint32(mpu_map['MPU_RBAR'])
                    rasr = dump_reader.read_uint32(mpu_map['MPU_RASR'])

                    base_addr = (rbar & 0xFFFFFFE0) << 5
                    size = 1 << ((rasr & 0x000003F0) >> 4)
                    region_enabled = (rasr & 0x01) != 0
                    permissions = self._decode_mpu_permissions(rasr)

                    regions.append({
                        'number': i,
                        'base_addr': base_addr,
                        'size': size,
                        'enabled': region_enabled,
                        'permissions': permissions,
                    })

            return {
                'enabled': enabled,
                'region_count': region_count,
                'regions': regions,
            }
        except Exception as e:
            logger.debug(f"Failed to read MPU info: {e}")
            return {}

    def _decode_mpu_permissions(self, rasr: int) -> str:
        ap = (rasr >> 24) & 0x03
        xn = (rasr >> 28) & 0x01

        perm_map = {
            0b00: 'No access',
            0b01: 'PRW',
            0b10: 'PRW UR',
            0b11: 'PRW URW',
        }

        result = perm_map.get(ap, 'Unknown')
        if xn:
            result += ' (XN)'
        return result

    def get_interrupt_controller_register_map(self) -> Dict[str, int]:
        return {
            'NVIC_ISER0': 0xE000E100,
            'NVIC_ISER1': 0xE000E104,
            'NVIC_ISER2': 0xE000E108,
            'NVIC_ICER0': 0xE000E180,
            'NVIC_ICER1': 0xE000E184,
            'NVIC_ICER2': 0xE000E188,
            'NVIC_ISPR0': 0xE000E200,
            'NVIC_ISPR1': 0xE000E204,
            'NVIC_ISPR2': 0xE000E208,
            'NVIC_ICPR0': 0xE000E280,
            'NVIC_ICPR1': 0xE000E284,
            'NVIC_ICPR2': 0xE000E288,
            'NVIC_IPR0': 0xE000E400,
            'NVIC_ICSR': 0xE000ED04,
            'NVIC_AIRCR': 0xE000ED0C,
        }

    def get_interrupt_info(self, dump_reader) -> Dict[str, Any]:
        ic_map = self.get_interrupt_controller_register_map()
        try:
            icsr = dump_reader.read_uint32(ic_map['NVIC_ICSR'])
            aircr = dump_reader.read_uint32(ic_map['NVIC_AIRCR'])

            current_interrupt = icsr & 0x1FF
            active_interrupt = (icsr >> 12) & 0x1FF
            pending_interrupt = (icsr >> 24) & 0x1FF
            priority_group = (aircr >> 8) & 0x07

            iser0 = dump_reader.read_uint32(ic_map['NVIC_ISER0'])
            iser1 = dump_reader.read_uint32(ic_map['NVIC_ISER1'])
            iser2 = dump_reader.read_uint32(ic_map['NVIC_ISER2'])

            ispr0 = dump_reader.read_uint32(ic_map['NVIC_ISPR0'])
            ispr1 = dump_reader.read_uint32(ic_map['NVIC_ISPR1'])
            ispr2 = dump_reader.read_uint32(ic_map['NVIC_ISPR2'])

            enabled_interrupts = []
            for i in range(96):
                if i < 32:
                    if iser0 & (1 << i):
                        enabled_interrupts.append(i)
                elif i < 64:
                    if iser1 & (1 << (i - 32)):
                        enabled_interrupts.append(i)
                else:
                    if iser2 & (1 << (i - 64)):
                        enabled_interrupts.append(i)

            pending_interrupts = []
            for i in range(96):
                if i < 32:
                    if ispr0 & (1 << i):
                        pending_interrupts.append(i)
                elif i < 64:
                    if ispr1 & (1 << (i - 32)):
                        pending_interrupts.append(i)
                else:
                    if ispr2 & (1 << (i - 64)):
                        pending_interrupts.append(i)

            interrupt_priorities = {}
            for i in range(32):
                addr = ic_map['NVIC_IPR0'] + i * 4
                ipr = dump_reader.read_uint32(addr)
                for j in range(4):
                    irq = i * 4 + j
                    priority = (ipr >> (j * 8)) & 0xFF
                    if priority != 0:
                        interrupt_priorities[irq] = priority

            return {
                'current_interrupt': current_interrupt if current_interrupt != 0 else None,
                'active_interrupt': active_interrupt if active_interrupt != 0 else None,
                'pending_interrupt': pending_interrupt if pending_interrupt != 0 else None,
                'enabled_interrupts': enabled_interrupts,
                'pending_interrupts': pending_interrupts,
                'interrupt_priorities': interrupt_priorities,
                'priority_group': priority_group,
            }
        except Exception as e:
            logger.debug(f"Failed to read interrupt info: {e}")
            return {}

    def unwind_stack(self, sp: int, fp: int, dump_reader, elf_parser,
                     is_32bit: bool, max_frames: int = 20,
                     start_pc: Optional[int] = None) -> List[Dict]:
        frames = []
        current_fp = fp
        current_sp = sp

        for _ in range(max_frames):
            if not current_fp or current_fp < current_sp:
                break

            try:
                if is_32bit:
                    prev_fp = dump_reader.read_uint32(current_fp)
                    return_addr = dump_reader.read_uint32(current_fp + 4)
                else:
                    prev_fp = dump_reader.read_uint64(current_fp)
                    return_addr = dump_reader.read_uint64(current_fp + 8)

                if not return_addr:
                    break

                func_info = elf_parser.find_function_by_address(return_addr)
                func_name = func_info.get('name', '') if func_info else ''
                func_offset = return_addr - func_info.get('address', return_addr) if func_info else 0

                frames.append({
                    'pc': return_addr,
                    'function': func_name if func_name else 'unknown',
                    'offset': func_offset,
                    'fp': current_fp,
                    'sp': current_sp,
                })

                current_sp = current_fp + (8 if is_32bit else 16)
                current_fp = prev_fp

            except Exception as e:
                logger.debug(f"Stack unwind failed at fp=0x{current_fp:08x}: {e}")
                break

        return frames

    def get_supported_archs(self) -> List[str]:
        return ['armv7-m', 'armv7m', 'cortex-m0', 'cortex-m3', 'cortex-m4', 'cortex-m7']

    def matches_arch(self, arch_name: str) -> bool:
        if not arch_name:
            return False
        arch_lower = arch_name.lower()
        return any(support in arch_lower for support in self.get_supported_archs())