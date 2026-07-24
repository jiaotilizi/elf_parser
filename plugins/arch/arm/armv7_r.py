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
from plugins.arch.arm.dwarf_cfi import DwarfCFIParser
from plugins.arch.arm.arm_exidx import ArmExidxParser

logger = logging.getLogger(__name__)

# ARM instruction decoding for IRQ prologue analysis
_ARM_INST_STMFD = 0xE92D0000
_ARM_INST_STMDB = 0xE9AD0000
_ARM_INST_PUSH = 0xE52D0000
_ARM_INST_MRS_R0_SPSR = 0xE10F0000
_ARM_INST_LDR = 0xE59D0000
_ARM_INST_ADD = 0xE28D0000
_ARM_INST_SUB = 0xE24D0000

# ARM register list for bitmask decoding
_ARM_REGS = ['r0', 'r1', 'r2', 'r3', 'r4', 'r5', 'r6', 'r7',
             'r8', 'r9', 'r10', 'r11', 'r12', 'sp', 'lr', 'pc']


class ArmV7RArchPlugin(ArchPlugin):
    def __init__(self):
        super().__init__(
            name='armv7_r',
            version='1.0',
            arch_name='armv7-r',
            description='ARMv7-R architecture plugin (Cortex-R4/R5/R5F/R7/R8)'
        )

    # ------------------------------------------------------------------
    # Register info
    # ------------------------------------------------------------------

    def get_register_info(self) -> Dict[str, Any]:
        return {
            'registers': {f'r{i}': 4 for i in range(16)},
            'frame_pointer_reg': 'r11',
            'link_reg': 'lr',
            'stack_reg': 'sp',
            'program_counter_reg': 'pc',
            'flags_reg': 'cpsr',
        }

    # ------------------------------------------------------------------
    # Task stack register extraction (RTOS frame layout)
    # ------------------------------------------------------------------

    def extract_registers(self, sp: int, frame_offsets: Dict[str, int],
                          dump_reader, is_32bit: bool) -> Dict[str, int]:
        """Extract registers from task stack using RTOS-provided frame offsets.

        The frame_offsets dict is provided by the RTOS plugin's
        get_stack_frame_layout() and describes where each register is stored
        on the task's stack during a context switch.

        Args:
            sp: Task stack pointer (tx_thread_stack_ptr)
            frame_offsets: {reg_name: byte_offset} from RTOS plugin
            dump_reader: DumpReader for memory access
            is_32bit: True for 32-bit ARM

        Returns:
            Dict of register_name -> value
        """
        registers = {}
        for reg_name, offset in frame_offsets.items():
            addr = sp + offset
            try:
                if is_32bit:
                    registers[reg_name] = dump_reader.read_uint32(addr)
                else:
                    registers[reg_name] = dump_reader.read_uint64(addr)
            except Exception as e:
                logger.debug("Failed to read register %s at 0x%08x: %s",
                             reg_name, addr, e)
                registers[reg_name] = 0
        return registers

    # ------------------------------------------------------------------
    # IRQ context recovery (architecture-only, no RTOS/BSP dependency)
    # ------------------------------------------------------------------

    def _find_irq_handler(self, elf_parser, dump_reader) -> Optional[int]:
        """Find the IRQ handler function address.

        Strategy (in priority order):
        1. Search ELF symbol table for known IRQ handler names
        2. Read ARM vector table IRQ entry (handles both direct and indirect vectors)

        ARM vector table locations: 0x00000000, 0xFFFF0000, 0x92000000 (Unisoc)
        ARM indirect vectors: each entry is LDR PC, [PC, #0x18] = 0xE59FF018
        The actual handler addresses follow at offset 0x20.

        Returns:
            Handler function address, or None if not found.
        """
        candidates = [
            '_tx_thread_irq_handler',
            '__irq_handler',
            'IRQ_Handler',
            'irq_handler',
            '_irq_handler',
            'InterruptHandler',
        ]
        for name in candidates:
            sym = elf_parser.get_symbol_by_name(name)
            if sym and sym.get('address'):
                return sym['address']

        vector_bases = [0x00000000, 0xFFFF0000, 0x92000000]
        for vector_base in vector_bases:
            try:
                reset_val = dump_reader.read_uint32(vector_base + 0x00)
                if reset_val is None:
                    continue

                if reset_val == 0xE59FF018:
                    handler_addr = dump_reader.read_uint32(vector_base + 0x20 + 6 * 4)
                else:
                    handler_addr = dump_reader.read_uint32(vector_base + 0x18)

                if handler_addr and handler_addr != 0xFFFFFFFF:
                    return handler_addr
            except Exception:
                continue

        return None

    def _decode_irq_prologue(self, elf_parser, handler_addr: int) -> Dict[str, int]:
        """Decode the IRQ handler prologue to determine register save layout.

        Handles both ARM (32-bit) and Thumb-2 (32-bit) instruction sets.
        When entering IRQ mode on ARM, the CPU automatically saves:
        - R0-R3, R12, LR_irq (R14_irq), PC, CPSR onto the IRQ stack (8 words = 32 bytes)
        
        The handler prologue then typically saves additional registers using:
        - ARM: STMFD SP!, {reg_list} (0xE92Dxxxx)
        - Thumb-2: STMFD SP!, {reg_list} (0xE92D4xxx)
        - Thumb-16: PUSH {reg_list} (0xB4xx)

        Args:
            elf_parser: ELF parser instance
            handler_addr: Address of IRQ handler function

        Returns:
            Dict of register_name -> byte_offset from IRQ SP (after all pushes).
            Empty dict if prologue cannot be decoded.
        """
        layout: Dict[str, int] = {}
        offset = 0

        for i in range(20):
            try:
                inst = elf_parser.read_memory_from_elf(handler_addr + i * 4, 4)
                if len(inst) < 4:
                    break
                inst_val = int.from_bytes(inst, 'little')
            except Exception:
                break

            if (inst_val & 0xFFFF0000) == _ARM_INST_STMFD:
                reg_list = inst_val & 0x0000FFFF
                for bit in range(16):
                    if reg_list & (1 << bit):
                        layout[_ARM_REGS[bit]] = offset
                        offset += 4
            elif (inst_val & 0xFFFF0000) == _ARM_INST_STMDB:
                reg_list = inst_val & 0x0000FFFF
                for bit in range(16):
                    if reg_list & (1 << bit):
                        layout[_ARM_REGS[bit]] = offset
                        offset += 4
            elif (inst_val & 0xFFFF0000) == _ARM_INST_PUSH:
                reg_list = inst_val & 0x0000FFFF
                for bit in range(16):
                    if reg_list & (1 << bit):
                        layout[_ARM_REGS[bit]] = offset
                        offset += 4

            elif (inst_val & 0xFFF00000) == 0xE92D0000:
                reg_list = inst_val & 0x000FFFFF
                for bit in range(16):
                    if reg_list & (1 << bit):
                        layout[_ARM_REGS[bit]] = offset
                        offset += 4

            elif (inst_val & 0xFF00FF00) == 0xB4000000:
                t1 = inst_val & 0x00FF
                t2 = (inst_val >> 16) & 0x00FF
                
                if t1 & 0xF0 == 0xB0:
                    reg_list = t1 & 0x0F
                    for bit in range(4):
                        if reg_list & (1 << bit):
                            layout[_ARM_REGS[bit]] = offset
                            offset += 2
                    if t1 & 0x10:
                        layout['lr'] = offset
                        offset += 2
                
                if t2 & 0xF0 == 0xB0:
                    reg_list = t2 & 0x0F
                    for bit in range(4):
                        if reg_list & (1 << bit):
                            layout[_ARM_REGS[bit]] = offset
                            offset += 2
                    if t2 & 0x10:
                        layout['lr'] = offset
                        offset += 2

            elif (inst_val & 0xFFFF0000) == _ARM_INST_MRS_R0_SPSR:
                pass
            elif (inst_val & 0xFF9F0000) == _ARM_INST_LDR:
                pass
            elif (inst_val & 0xFF9F0000) == _ARM_INST_ADD:
                pass
            elif (inst_val & 0xFF9F0000) == _ARM_INST_SUB:
                pass
            else:
                pass

        if layout:
            logger.debug("Decoded IRQ prologue: saved %d registers", len(layout))
        else:
            logger.debug("No register saves found in IRQ prologue at 0x%08X", handler_addr)

        return layout

    def find_irq_sp(self, dump_reader, elf_parser) -> Optional[int]:
        """Find the IRQ stack pointer by analyzing memory and ELF info.

        Strategy:
        1. Search for known IRQ stack symbols (arch-agnostic)
        2. Search memory for valid stack frame patterns

        This method does NOT depend on any RTOS-specific symbols.

        Returns:
            IRQ SP value, or None if cannot be determined.
        """
        irq_stack_syms = [
            '__IRQ_STACK_TOP',
            '__irq_stack_top',
            '_irq_stack_top',
            'irq_stack_top',
            '__IRQ_STACK_BASE',
            '_irq_stack_base',
            '__irq_sp',
            'g_irq_sp',
        ]
        for name in irq_stack_syms:
            sym = elf_parser.get_symbol_by_name(name)
            if sym and sym.get('address'):
                return sym['address']

        return None

    def extract_irq_registers(self, irq_sp: int, dump_reader,
                              is_32bit: bool, elf_parser=None) -> Dict[str, Optional[int]]:
        """Extract registers saved by the IRQ handler on the IRQ stack.

        ARM IRQ entry sequence:
        1. CPU automatically saves R0-R3, R12, LR_irq, PC, CPSR (8 registers = 32 bytes)
           at the OLD SP (before handler prologue)
        2. Handler prologue pushes additional registers (r4, r5, r6, r8, r9, r10, lr)

        The IRQ SP provided is typically AFTER the handler's prologue has run.
        So the layout is (from lowest address to highest):
        - Handler-saved registers (at IRQ SP + offset)
        - CPU-autosaved registers (at IRQ SP + total_handler_size + offset)

        Uses instruction decoding to dynamically determine the register
        save layout from the IRQ handler prologue.  No hardcoded offsets.
        No RTOS or BSP dependency.

        Args:
            irq_sp: IRQ mode stack pointer.
            dump_reader: DumpReader for memory access.
            is_32bit: True for 32-bit ARM.
            elf_parser: ELF parser (required for prologue decoding).

        Returns:
            Dict of register_name -> value, or empty dict if layout cannot be
            determined.
        """
        if elf_parser is None or not irq_sp:
            return {}

        handler_addr = self._find_irq_handler(elf_parser, dump_reader)
        if not handler_addr:
            return {}

        layout = self._decode_irq_prologue(elf_parser, handler_addr)
        if not layout:
            return {}

        registers: Dict[str, Optional[int]] = {}

        total_handler_size = len(layout) * 4

        for reg_name, offset in layout.items():
            addr = irq_sp + offset
            try:
                if is_32bit:
                    registers[reg_name] = dump_reader.read_uint32(addr)
                else:
                    registers[reg_name] = dump_reader.read_uint64(addr)
            except Exception as e:
                logger.debug("Failed to read IRQ register %s at 0x%08x: %s",
                             reg_name, addr, e)

        cpu_auto_save_offset = total_handler_size
        cpu_auto_saved = ['r0', 'r1', 'r2', 'r3', 'r12', 'lr_irq', 'pc', 'cpsr']
        for i, reg_name in enumerate(cpu_auto_saved):
            addr = irq_sp + cpu_auto_save_offset + i * 4
            try:
                if is_32bit:
                    val = dump_reader.read_uint32(addr)
                else:
                    val = dump_reader.read_uint64(addr)
                registers[reg_name] = val
            except Exception as e:
                logger.debug("Failed to read CPU-autosaved register %s at 0x%08x: %s",
                             reg_name, addr, e)

        spsr_addr = irq_sp + cpu_auto_save_offset + 8 * 4
        try:
            if is_32bit:
                registers['spsr'] = dump_reader.read_uint32(spsr_addr)
            else:
                registers['spsr'] = dump_reader.read_uint64(spsr_addr)
        except Exception as e:
            logger.debug("Failed to read SPSR at 0x%08x: %s", spsr_addr, e)

        return registers

    def find_current_register_values(self, irq_sp: int, dump_reader,
                                     elf_parser, is_32bit: bool) -> Dict[str, Optional[int]]:
        """Recover current CPU register values from the dump.

        Strategy (no RTOS/BSP dependency):
        1. Extract IRQ entry registers from the IRQ stack using prologue decoding
        2. Use DWARF CFI of the interrupted function to recover additional registers

        Args:
            irq_sp: IRQ mode stack pointer.
            dump_reader: DumpReader for memory access.
            elf_parser: ELF parser.
            is_32bit: True for 32-bit ARM.

        Returns:
            Dict of register_name -> value or None.
        """
        registers: Dict[str, Optional[int]] = {}

        irq_regs = self.extract_irq_registers(irq_sp, dump_reader, is_32bit, elf_parser)
        for reg_name, val in irq_regs.items():
            if val is not None:
                registers[reg_name] = val

        lr_val = irq_regs.get('lr')
        if lr_val is None or lr_val == 0:
            return registers

        interrupted_pc = lr_val - 4

        cfi = self._get_cfi_parser(elf_parser)
        if cfi and cfi.is_available:
            state = cfi.get_cfi_state(interrupted_pc)
            if state:
                for reg_name in state.registers:
                    val = state.get_register_value(irq_sp, reg_name, dump_reader)
                    if val is not None:
                        registers[reg_name] = val

        return registers

    # ------------------------------------------------------------------
    # DWARF CFI-based stack unwinding
    # ------------------------------------------------------------------

    def _get_cfi_parser(self, elf_parser) -> Optional[DwarfCFIParser]:
        """Create a DwarfCFIParser from the ELF parser's underlying ELF file.

        Cached per plugin instance.  Returns None if the ELF parser backend
        does not expose a raw ELF file (e.g. dwarffi).
        """
        if not hasattr(self, '_cfi_parser'):
            elffile = elf_parser._get_elffile()
            if elffile is None:
                self._cfi_parser = None
            else:
                try:
                    self._cfi_parser = DwarfCFIParser(elffile)
                except Exception as e:
                    logger.debug("Failed to init CFI parser: %s", e)
                    self._cfi_parser = None
        return self._cfi_parser

    def _get_exidx_parser(self, elf_parser) -> Optional[ArmExidxParser]:
        """Create an ArmExidxParser from the ELF parser's underlying ELF file.

        Cached per plugin instance.  Returns None if the ELF parser backend
        does not expose a raw ELF file, or if .ARM.exidx is not present.
        """
        if not hasattr(self, '_exidx_parser'):
            elffile = elf_parser._get_elffile()
            if elffile is None:
                self._exidx_parser = None
            else:
                try:
                    self._exidx_parser = ArmExidxParser(elffile)
                    if not self._exidx_parser.is_available:
                        self._exidx_parser = None
                except Exception as e:
                    logger.debug("Failed to init .ARM.exidx parser: %s", e)
                    self._exidx_parser = None
        return self._exidx_parser

    def unwind_stack(self, sp: int, fp: int, dump_reader, elf_parser,
                     is_32bit: bool, max_frames: int = 20,
                     start_pc: Optional[int] = None) -> List[Dict]:
        """Unwind the call stack using DWARF CFI (.debug_frame).

        Falls back to .ARM.exidx (EHABI), then to frame-pointer-based
        unwinding if neither CFI source is available.

        CFI and exidx parsers are created directly from the ELF parser's
        underlying ELF file, with no dependency on architecture-specific
        methods in the generic ELF parser base class.

        Args:
            sp: Current stack pointer.
            fp: Current frame pointer (used as fallback).
            dump_reader: DumpReader for memory access.
            elf_parser: ELF parser (must expose _get_elffile() for CFI/exidx).
            is_32bit: True for 32-bit ARM.
            max_frames: Maximum number of frames to unwind.
            start_pc: Starting PC for the first frame.  If None, the
                method falls back to FP-chain unwinding (CFI/exidx
                require a known PC to begin).

        Returns:
            List of frame dicts: [{'pc': int, 'function': str, 'offset': int,
                                   'fp': int, 'sp': int}, ...]
        """
        # CFI and exidx require a known starting PC
        if start_pc:
            # Priority 1: DWARF CFI (.debug_frame)
            cfi = self._get_cfi_parser(elf_parser)
            if cfi and cfi.is_available:
                return self._unwind_with_cfi(sp, start_pc, dump_reader,
                                             elf_parser, cfi, max_frames)

            # Priority 2: .ARM.exidx (EHABI)
            exidx = self._get_exidx_parser(elf_parser)
            if exidx and exidx.is_available:
                return self._unwind_with_exidx(sp, start_pc, dump_reader,
                                               elf_parser, exidx, max_frames)

        # Priority 3: Frame pointer chain (always available as fallback)
        return self._unwind_with_fp(fp, sp, dump_reader, elf_parser,
                                    is_32bit, max_frames)

    def _unwind_with_cfi(self, sp: int, start_pc: int, dump_reader,
                         elf_parser, cfi, max_frames: int) -> List[Dict]:
        """Unwind stack using DWARF CFI.

        Starting from start_pc (the interrupted instruction), reads the
        saved LR from the stack using CFI rules, looks up the CFI for
        the caller's PC, and repeats.
        """
        frames: List[Dict] = []
        current_sp = sp
        current_pc = start_pc

        for _ in range(max_frames):
            if not current_sp or not current_pc:
                break

            state = cfi.get_cfi_state(current_pc)
            if not state:
                break

            # Read return address (LR) from the stack using CFI
            lr_val = state.get_return_address(current_sp, dump_reader)
            if not lr_val:
                break

            # Look up the function containing this PC
            func_info = elf_parser.find_function_by_address(current_pc)
            func_name = func_info.get('name', '') if func_info else ''
            func_offset = (current_pc - func_info.get('address', current_pc)
                           if func_info else 0)

            frames.append({
                'pc': current_pc,
                'function': func_name if func_name else 'unknown',
                'offset': func_offset,
                'fp': 0,
                'sp': current_sp,
            })

            # Compute caller's SP from CFA
            caller_sp = state.compute_cfa(current_sp)
            if caller_sp is None or caller_sp <= current_sp:
                break
            current_sp = caller_sp
            current_pc = lr_val

        return frames

    def _unwind_with_exidx(self, sp: int, start_pc: int, dump_reader,
                           elf_parser, exidx, max_frames: int) -> List[Dict]:
        """Unwind stack using .ARM.exidx (EHABI).

        Uses the ARM EABI standard exception index table for unwinding.
        This works without frame pointers and without DWARF CFI.
        """
        frames: List[Dict] = []
        current_sp = sp
        current_pc = start_pc

        for _ in range(max_frames):
            if not current_sp or not current_pc:
                break

            result = exidx.unwind_frame(current_pc, current_sp, dump_reader)
            if not result:
                break

            caller_pc, caller_sp = result
            if not caller_pc or caller_sp <= current_sp:
                break

            func_info = elf_parser.find_function_by_address(current_pc)
            func_name = func_info.get('name', '') if func_info else ''
            func_offset = (current_pc - func_info.get('address', current_pc)
                           if func_info else 0)

            frames.append({
                'pc': current_pc,
                'function': func_name if func_name else 'unknown',
                'offset': func_offset,
                'fp': 0,
                'sp': current_sp,
            })

            current_sp = caller_sp
            current_pc = caller_pc

        return frames

    def _unwind_with_fp(self, fp: int, sp: int, dump_reader, elf_parser,
                        is_32bit: bool, max_frames: int) -> List[Dict]:
        """Fallback: frame-pointer-based stack unwinding.

        Used when neither DWARF CFI nor .ARM.exidx is available.
        Walks the frame pointer chain (R11 on ARM).

        Limitations:
        - Functions compiled without frame pointers (-fomit-frame-pointer)
          will break the chain.
        - Leaf functions may not set up a frame pointer.
        """
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
                func_offset = (return_addr - func_info.get('address', return_addr)
                               if func_info else 0)

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
                logger.debug("FP unwind failed at fp=0x%08x: %s",
                             current_fp, e)
                break

        return frames

    # ------------------------------------------------------------------
    # FPU
    # ------------------------------------------------------------------

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
                logger.debug("Failed to read FPU register %s at 0x%08x: %s",
                             reg_name, addr, e)
                registers[reg_name] = 0
        return registers

    # ------------------------------------------------------------------
    # MPU (not applicable for Cortex-R8 in this configuration)
    # ------------------------------------------------------------------

    def get_mpu_register_map(self) -> Dict[str, int]:
        return {}

    def get_mpu_info(self, dump_reader) -> Dict[str, Any]:
        return {}

    # ------------------------------------------------------------------
    # Interrupt controller (GIC on Cortex-R8 — implementation deferred)
    # ------------------------------------------------------------------

    def get_interrupt_controller_register_map(self) -> Dict[str, int]:
        return {}

    def get_interrupt_info(self, dump_reader) -> Dict[str, Any]:
        return {}

    # ------------------------------------------------------------------
    # Architecture identification
    # ------------------------------------------------------------------

    def get_supported_archs(self) -> List[str]:
        return ['armv7-r', 'armv7r', 'cortex-r4', 'cortex-r5',
                'cortex-r5f', 'cortex-r7', 'cortex-r8']

    def matches_arch(self, arch_name: str) -> bool:
        if not arch_name:
            return False
        arch_lower = arch_name.lower()
        return any(support in arch_lower
                   for support in self.get_supported_archs())