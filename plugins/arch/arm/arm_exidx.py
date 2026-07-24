"""
ARM Exception Index Table (.ARM.exidx) parser for EHABI stack unwinding.

Parses .ARM.exidx and .ARM.extab sections to provide stack unwinding
capability without relying on frame pointers. This is the ARM EABI
standard mechanism for exception handling and stack unwinding.

Reference: ARM IHI 0038B - Exception Handling ABI for the ARM Architecture
           (Section 9: Exception Index Table)

Key concepts:
  - .ARM.exidx: Sorted table of (function_addr, unwind_descriptor) pairs.
    Each entry is 8 bytes.
  - .ARM.extab: Extended unwind table containing bytecode programs for
    functions whose unwind info cannot fit in a 4-byte inline descriptor.

Unwind procedure:
  1. Given PC, find the exidx entry whose function_addr <= PC.
  2. Decode the unwind descriptor to determine where LR (and other saved
     registers) are stored on the stack.
  3. Read LR from the stack to get the caller's PC.
  4. Compute the caller's SP from the VSP adjustment.

Note: This parser handles the common ARM EHABI unwind opcodes.  Uncommon
or vendor-specific opcodes (VFP, FPA, Intel MMX) are skipped gracefully.
"""

import bisect
import logging
import struct
from typing import Dict, List, Optional, Tuple, Any

from elftools.elf.elffile import ELFFile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EHABI unwind opcode constants
# ---------------------------------------------------------------------------
class _Op:
    """Mnemonic constants for ARM EHABI unwind opcodes."""
    # 0x00-0x7F: vsp = vsp + ((op & 0x7F) << 2) + 4
    VSP_ADJUST_LO = 0x00
    VSP_ADJUST_HI = 0x7F

    # 0x80-0x8F: pop r4..r(4+N)  where N = op & 0x0F (0..12)
    POP_R4_R4N_LO = 0x80
    POP_R4_R4N_HI = 0x8F

    POP_LR = 0x90          # pop {r14}

    # 0xA0-0xA7: vsp = vsp + (op & 0x07) * 4
    VSP_ADJUST_SMALL_LO = 0xA0
    VSP_ADJUST_SMALL_HI = 0xA7

    POP_R4 = 0xA8          # pop {r4}
    POP_R4_R5 = 0xA9       # pop {r4,r5}
    POP_R4_R6 = 0xAA       # pop {r4,r5,r6}
    POP_R4_R7 = 0xAB       # pop {r4,r5,r6,r7}

    FINISH = 0xB0          # end of unwind opcodes

    POP_MASK = 0xB1        # pop with 16-bit mask (r4..r15, single precision)
    POP_MASK_DOUBLE = 0xB2  # pop with 16-bit mask (double precision)

    VSP_ADJUST_ULEB = 0xB3  # vsp = vsp + uleb128

    # 0xB8: Pop FPA registers (deprecated)
    # 0xC0-0xC5: Intel wireless MMX pop
    # 0xC8: Pop VFP double precision
    # 0xC9: Pop VFP single precision
    # 0xD0: Pop VFP registers


# ---------------------------------------------------------------------------
# Unwind info data class
# ---------------------------------------------------------------------------
class ExidxUnwindInfo:
    """Parsed unwind information for a function.

    Attributes:
        can_unwind: Whether this function has valid unwind info.
        saved_registers: List of (reg_num, offset_from_current_sp) tuples.
            reg_num is the DWARF register number (e.g., 14 = LR).
            offset_from_current_sp is the byte offset from the current SP
            where the register is saved on the stack.
        sp_adjust: Total bytes to add to current SP to get caller's SP.
    """
    __slots__ = ('can_unwind', 'saved_registers', 'sp_adjust')

    def __init__(self):
        self.can_unwind: bool = True
        self.saved_registers: List[Tuple[int, int]] = []
        self.sp_adjust: int = 0

    def get_lr_offset(self) -> Optional[int]:
        """Return the offset of LR (R14) from current SP, or None."""
        for reg_num, offset in self.saved_registers:
            if reg_num == 14:
                return offset
        return None


# ---------------------------------------------------------------------------
# ArmExidxEntry
# ---------------------------------------------------------------------------
class _ArmExidxEntry:
    """A single .ARM.exidx table entry."""
    __slots__ = ('function_addr', 'unwind_word', 'is_inline')

    def __init__(self, function_addr: int, unwind_word: int, is_inline: bool):
        self.function_addr = function_addr
        self.unwind_word = unwind_word
        self.is_inline = is_inline


# ---------------------------------------------------------------------------
# ArmExidxParser
# ---------------------------------------------------------------------------
class ArmExidxParser:
    """Parser for .ARM.exidx and .ARM.extab sections.

    Usage:
        parser = ArmExidxParser(elffile)
        if parser.is_available:
            info = parser.get_unwind_info(pc)
            if info:
                lr_offset = info.get_lr_offset()
                if lr_offset is not None:
                    caller_pc = dump_reader.read_uint32(sp + lr_offset)
                    caller_sp = sp + info.sp_adjust
    """

    EXIDX_CANTUNWIND = 0x00000001

    def __init__(self, elffile: ELFFile):
        self._entries: List[_ArmExidxEntry] = []
        self._extab_data: bytes = b''
        self._extab_base: int = 0
        self._parsed: bool = False
        self._parse(elffile)

    # ------------------------------------------------------------------
    # Section parsing
    # ------------------------------------------------------------------

    def _parse(self, elffile: ELFFile) -> None:
        """Parse .ARM.exidx and .ARM.extab sections."""
        exidx = elffile.get_section_by_name('.ARM.exidx')
        if not exidx:
            logger.debug("No .ARM.exidx section found; EHABI unwind disabled")
            return

        exidx_data = exidx.data()
        exidx_base = exidx.header.sh_addr
        entry_size = 8

        entries: List[_ArmExidxEntry] = []
        for i in range(0, len(exidx_data), entry_size):
            word0, word1 = struct.unpack_from('<II', exidx_data, i)

            # Word 0 bit 31 = 1: can't unwind sentinel
            if word0 & 0x80000000:
                entries.append(_ArmExidxEntry(0, word1, True))
                continue

            # Word 0: prel31 offset to function start
            # Prel31 = signed 31-bit offset from the entry address
            entry_addr = exidx_base + i
            # Sign-extend from bit 30
            offset = word0 & 0x7FFFFFFF
            if word0 & 0x40000000:
                offset |= 0x80000000  # negative
            func_addr = (entry_addr + offset) & 0xFFFFFFFF

            # Word 1 bit 31 = 1: inline compact descriptor
            # Word 1 bit 31 = 0: prel31 offset to .ARM.extab entry
            is_inline = bool(word1 & 0x80000000)
            entries.append(_ArmExidxEntry(func_addr, word1, is_inline))

        entries.sort(key=lambda e: e.function_addr)
        self._entries = entries

        extab = elffile.get_section_by_name('.ARM.extab')
        if extab:
            self._extab_data = extab.data()
            self._extab_base = extab.header.sh_addr

        self._parsed = True
        logger.debug("ArmExidxParser: %d entries indexed", len(self._entries))

    # ------------------------------------------------------------------
    # Entry lookup
    # ------------------------------------------------------------------

    def _find_entry(self, pc: int) -> Optional[_ArmExidxEntry]:
        """Binary search for the exidx entry covering the given PC."""
        if not self._entries:
            return None
        addrs = [e.function_addr for e in self._entries]
        idx = bisect.bisect_right(addrs, pc) - 1
        if idx < 0:
            return None
        return self._entries[idx]

    # ------------------------------------------------------------------
    # Unwind info decoding
    # ------------------------------------------------------------------

    def get_unwind_info(self, pc: int) -> Optional[ExidxUnwindInfo]:
        """Get EHABI unwind information for a given PC.

        Returns:
            ExidxUnwindInfo or None if no entry covers this PC.
            If can_unwind is False, the function cannot be unwound.
        """
        entry = self._find_entry(pc)
        if not entry:
            return None

        if entry.function_addr == 0 and entry.is_inline:
            info = ExidxUnwindInfo()
            info.can_unwind = False
            return info

        if entry.is_inline:
            return self._decode_inline(entry.unwind_word)
        else:
            return self._decode_extab(entry.unwind_word & 0x7FFFFFFF)

    def _decode_inline(self, unwind_word: int) -> ExidxUnwindInfo:
        """Decode an inline compact unwind descriptor."""
        if unwind_word == self.EXIDX_CANTUNWIND:
            info = ExidxUnwindInfo()
            info.can_unwind = False
            return info

        info = ExidxUnwindInfo()
        encoding = (unwind_word >> 28) & 0x0F

        if encoding in (0x8, 0x9):
            # Standard compact model (0x8 = ARM, 0x9 = Thumb)
            # Bits 27-24: index of first saved register
            # Bits 23-16: number of saved registers (not including LR)
            # Bit 15: POP {LR} flag
            # Bits 14-0: SP adjustment (bytes to add to SP to get caller's SP)
            first_reg = (unwind_word >> 24) & 0x0F
            reg_count = (unwind_word >> 16) & 0xFF
            pop_lr = (unwind_word >> 15) & 0x01
            sp_adjust = unwind_word & 0x7FFF

            # Registers are saved sequentially from SP + sp_adjust upward
            offset = sp_adjust
            for i in range(reg_count):
                info.saved_registers.append((first_reg + i, offset))
                offset += 4
            if pop_lr:
                info.saved_registers.append((14, offset))
                offset += 4

            info.sp_adjust = offset

        elif encoding in (0xA, 0xB):
            # Additional compact models:
            # 0xA: vfpv3/neon, 0xB: reserved/other
            # These are complex and rarely needed for basic stack unwinding.
            info.can_unwind = False
            logger.debug(
                "Inline compact model 0x%X (word=0x%08X) not fully supported; "
                "marking as cannot-unwind", encoding, unwind_word)
        else:
            info.can_unwind = False

        return info

    def _decode_extab(self, extab_offset: int) -> Optional[ExidxUnwindInfo]:
        """Decode a .ARM.extab entry at the given prel31 offset."""
        if not self._extab_data:
            return None

        # extab_offset is relative to .ARM.extab section base
        try:
            data_offset = (extab_offset - self._extab_base) & 0xFFFFFFFF
        except OverflowError:
            return None

        if data_offset < 0 or data_offset + 4 > len(self._extab_data):
            return None

        data = self._extab_data[data_offset:]

        # Header: first byte = number of extra words (0-3)
        num_extra = data[0] & 0x03
        header_size = 4 + num_extra * 4

        if len(data) < header_size:
            return None

        opcodes = data[header_size:]
        info = ExidxUnwindInfo()
        if len(opcodes) == 0:
            return info

        self._decode_opcodes(opcodes, info)
        return info

    def _decode_opcodes(self, opcodes: bytes, info: ExidxUnwindInfo) -> None:
        """Decode an EHABI unwind opcode sequence.

        The opcode sequence describes how to reverse the function prologue.
        Starting with VSP = current SP, each opcode either adjusts VSP
        upward or pops registers from VSP.  The final VSP is the caller's SP.

        Registers are "popped" by reading from VSP and incrementing VSP.
        This gives us the offset of each register from the current SP.
        """
        vsp = 0  # virtual offset from current SP
        i = 0
        n = len(opcodes)

        while i < n:
            op = opcodes[i]
            i += 1

            if op == _Op.FINISH:
                break

            elif op == _Op.POP_LR:
                info.saved_registers.append((14, vsp))
                vsp += 4

            elif op == _Op.POP_R4:
                info.saved_registers.append((4, vsp))
                vsp += 4

            elif op == _Op.POP_R4_R5:
                info.saved_registers.append((4, vsp))
                info.saved_registers.append((5, vsp + 4))
                vsp += 8

            elif op == _Op.POP_R4_R6:
                info.saved_registers.append((4, vsp))
                info.saved_registers.append((5, vsp + 4))
                info.saved_registers.append((6, vsp + 8))
                vsp += 12

            elif op == _Op.POP_R4_R7:
                for r in range(4, 8):
                    info.saved_registers.append((r, vsp + (r - 4) * 4))
                vsp += 16

            elif _Op.POP_R4_R4N_LO <= op <= _Op.POP_R4_R4N_HI:
                count = (op & 0x0F) + 1
                for r in range(4, 4 + count):
                    info.saved_registers.append((r, vsp + (r - 4) * 4))
                vsp += count * 4

            elif _Op.VSP_ADJUST_SMALL_LO <= op <= _Op.VSP_ADJUST_SMALL_HI:
                vsp += (op & 0x07) * 4

            elif _Op.VSP_ADJUST_LO <= op <= _Op.VSP_ADJUST_HI:
                vsp += ((op & 0x7F) << 2) + 4

            elif op == _Op.POP_MASK:
                if i + 1 >= n:
                    break
                mask = opcodes[i] | (opcodes[i + 1] << 8)
                i += 2
                for r in range(4, 16):
                    if mask & (1 << (r - 4)):
                        info.saved_registers.append((r, vsp))
                        vsp += 4

            elif op == _Op.POP_MASK_DOUBLE:
                # Double precision: each register pair occupies 8 bytes.
                # We skip decoding these since they are VFP registers (D0-D15),
                # not core registers needed for stack unwinding.
                if i + 1 >= n:
                    break
                mask = opcodes[i] | (opcodes[i + 1] << 8)
                i += 2
                for r in range(4, 16):
                    if mask & (1 << (r - 4)):
                        vsp += 8  # double precision = 8 bytes per reg

            elif op == _Op.VSP_ADJUST_ULEB:
                value = 0
                shift = 0
                while i < n:
                    b = opcodes[i]
                    i += 1
                    value |= (b & 0x7F) << shift
                    if (b & 0x80) == 0:
                        break
                    shift += 7
                vsp += value

            else:
                # Unknown opcode — stop decoding.  The unwind info gathered
                # so far may still be useful (e.g., LR offset may have been
                # decoded before the unknown opcode).
                logger.debug("Unknown EHABI opcode 0x%02X at offset %d", op, i - 1)
                break

        info.sp_adjust = vsp

    # ------------------------------------------------------------------
    # Unwind API
    # ------------------------------------------------------------------

    def unwind_frame(self, pc: int, sp: int,
                     dump_reader) -> Optional[Tuple[int, int]]:
        """Unwind one stack frame using EHABI unwind info.

        Args:
            pc: Current program counter.
            sp: Current stack pointer.
            dump_reader: DumpReader for reading memory.

        Returns:
            (caller_pc, caller_sp) or None if unwinding fails.
        """
        info = self.get_unwind_info(pc)
        if not info or not info.can_unwind:
            return None

        lr_offset = info.get_lr_offset()
        if lr_offset is None:
            return None

        try:
            caller_pc = dump_reader.read_uint32(sp + lr_offset)
        except Exception as e:
            logger.debug("EHABI unwind: failed to read LR at SP+0x%X: %s",
                         lr_offset, e)
            return None

        if not caller_pc:
            return None

        caller_sp = sp + info.sp_adjust
        return (caller_pc, caller_sp)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        return self._parsed and len(self._entries) > 0

    def get_entry_count(self) -> int:
        return len(self._entries)

    def has_entry_for(self, pc: int) -> bool:
        """Check if there is an exidx entry covering the given PC."""
        entry = self._find_entry(pc)
        if not entry:
            return False
        if entry.function_addr == 0 and entry.is_inline:
            return False
        return True