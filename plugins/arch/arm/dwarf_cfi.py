"""
DWARF Call Frame Information (CFI) parser for register recovery and stack
unwinding from static memory dumps.

Parses the .debug_frame section of an ELF file to build an index of
Frame Description Entries (FDEs) keyed by PC address range.  Each FDE
encodes, for every instruction in a function, where each register was
saved (if at all) and how to compute the Canonical Frame Address (CFA).

This is the standard-compliant replacement for hardcoded stack offsets,
FP-chain walking, and BSP-specific symbol lookups.

Design constraints:
  - Registers whose CFI rule is REGISTER, SAME_VALUE, or UNDEFINED
    cannot be recovered from a static dump and are returned as None.
  - Only OFFSET rules (register saved at CFA + offset) are recoverable.
  - DWARF expressions are not evaluated (returned as None with a note).
  - The CIE augmentation string must be 'armcc+' (ARM compiler).
"""

import bisect
import logging
import struct
from typing import Dict, List, Optional, Tuple, Any

from elftools.elf.elffile import ELFFile
from elftools.dwarf.callframe import CIE, FDE, CFARule, RegisterRule

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CFI register rule types
# ---------------------------------------------------------------------------
class CFIRuleType:
    UNDEFINED = 'UNDEFINED'   # register has no recoverable value
    SAME_VALUE = 'SAME_VALUE'  # register not modified (still in CPU reg)
    OFFSET = 'OFFSET'          # register saved at CFA + offset
    REGISTER = 'REGISTER'      # register saved in another register
    EXPRESSION = 'EXPRESSION'  # register saved at complex DWARF expression


class CFIState:
    """Snapshot of CFI register rules at a specific PC.

    Fields:
        pc: int          - program counter this state is valid for
        cfa_rule: dict   - {'reg': int, 'offset': int} or None
        registers: dict  - reg_name (str) -> {'type': str, 'offset': int|None}
    """

    __slots__ = ('pc', 'cfa_rule', 'registers')

    def __init__(self, pc: int, cfa_rule: Optional[Dict], registers: Dict[str, Dict]):
        self.pc = pc
        self.cfa_rule = cfa_rule
        self.registers = registers

    def compute_cfa(self, sp: int) -> Optional[int]:
        """Compute the Canonical Frame Address given the current SP.

        CFA = reg_value + offset.  The reg is the DWARF register number
        (e.g. 13 = SP on ARM).  The offset is in bytes.
        """
        if not self.cfa_rule:
            return None
        reg = self.cfa_rule.get('reg')
        offset = self.cfa_rule.get('offset', 0)
        # DWARF reg 13 = SP on ARM
        if reg == 13:
            return sp + offset
        # For other registers, we cannot compute CFA from static dump
        return None

    def get_register_value(self, sp: int, reg_name: str,
                           dump_reader) -> Optional[int]:
        """Attempt to read a register value from the dump using CFI rules.

        Returns:
            int value if recoverable, None if not.
        """
        rule = self.registers.get(reg_name)
        if not rule:
            return None

        rule_type = rule.get('type')
        if rule_type != CFIRuleType.OFFSET:
            return None

        cfa = self.compute_cfa(sp)
        if cfa is None:
            return None

        addr = cfa + rule['offset']
        try:
            return dump_reader.read_uint32(addr)
        except Exception as e:
            logger.debug("CFI read %s at 0x%08x failed: %s", reg_name, addr, e)
            return None

    def get_return_address(self, sp: int, dump_reader,
                           return_reg: int = 14) -> Optional[int]:
        """Read the return address (LR / R14) using CFI rules."""
        return self.get_register_value(sp, str(return_reg), dump_reader)


# ---------------------------------------------------------------------------
# ARM DWARF register name mapping
# ---------------------------------------------------------------------------
_ARM_REG_NAMES = {
    0: 'r0', 1: 'r1', 2: 'r2', 3: 'r3',
    4: 'r4', 5: 'r5', 6: 'r6', 7: 'r7',
    8: 'r8', 9: 'r9', 10: 'r10', 11: 'r11',
    12: 'r12', 13: 'sp', 14: 'lr', 15: 'pc',
    16: 's0', 17: 's1', 18: 's2', 19: 's3',
    20: 's4', 21: 's5', 22: 's6', 23: 's7',
    24: 's8', 25: 's9', 26: 's10', 27: 's11',
    28: 's12', 29: 's13', 30: 's14', 31: 's15',
    32: 's16', 33: 's17', 34: 's18', 35: 's19',
    36: 's20', 37: 's21', 38: 's22', 39: 's23',
    40: 's24', 41: 's25', 42: 's26', 43: 's27',
    44: 's28', 45: 's29', 46: 's30', 47: 's31',
    256: 'cpsr',
}


def _dw_reg_name(reg_num: int) -> str:
    """Convert DWARF register number to ARM register name."""
    return _ARM_REG_NAMES.get(reg_num, f'r{reg_num}')


# ---------------------------------------------------------------------------
# DwarfCFIParser
# ---------------------------------------------------------------------------
class DwarfCFIParser:
    """Parse .debug_frame section and provide CFI-based register recovery.

    Usage:
        parser = DwarfCFIParser(elffile)
        state = parser.get_cfi_state(pc)
        if state:
            lr = state.get_return_address(sp, dump_reader)
            r4 = state.get_register_value(sp, 'r4', dump_reader)
    """

    def __init__(self, elffile: ELFFile):
        self._fde_index: List[Tuple[int, int, FDE]] = []  # (start, end, fde)
        self._return_address_register: int = 14  # default: LR (R14)
        self._code_alignment_factor: int = 1
        self._data_alignment_factor: int = -4
        self._cie_cache: Dict[int, CIE] = {}
        self._parsed: bool = False
        self._parse(elffile)

    def _parse(self, elffile: ELFFile) -> None:
        """Parse .debug_frame and build FDE address index."""
        if not elffile.has_dwarf_info():
            logger.warning("No DWARF info in ELF; CFI parsing disabled")
            return

        dwarfinfo = elffile.get_dwarf_info()
        if not dwarfinfo.has_CFI():
            logger.warning("No .debug_frame section; CFI parsing disabled")
            return

        fde_entries: List[Tuple[int, int, FDE]] = []
        cie_list: Dict[int, CIE] = {}

        cie_idx = 0
        for entry in dwarfinfo.CFI_entries():
            if isinstance(entry, CIE):
                cie_list[cie_idx] = entry
                cie_idx += 1
            elif isinstance(entry, FDE):
                header = entry.header
                init_loc = header.get('initial_location', 0)
                addr_range = header.get('address_range', 0)
                if init_loc == 0 and addr_range == 0:
                    continue
                cie_offset = header.get('CIE_pointer', 0)
                fde_entries.append((init_loc, init_loc + addr_range, entry))
                if cie_offset not in cie_list:
                    try:
                        cie = entry.cie
                        cie_list[cie_offset] = cie
                    except Exception:
                        pass

        fde_entries.sort(key=lambda x: x[0])
        self._fde_index = fde_entries
        self._cie_cache = cie_list
        self._parsed = True

        # Extract CIE parameters from the first CIE
        if cie_list:
            cie = next(iter(cie_list.values()))
            hdr = cie.header
            self._return_address_register = hdr.get('return_address_register', 14)
            self._code_alignment_factor = hdr.get('code_alignment_factor', 1)
            self._data_alignment_factor = hdr.get('data_alignment_factor', -4)

        logger.debug("DwarfCFIParser: %d FDEs indexed", len(fde_entries))

    def _find_fde(self, pc: int) -> Optional[FDE]:
        """Binary search for the FDE covering the given PC."""
        if not self._fde_index:
            return None
        starts = [e[0] for e in self._fde_index]
        idx = bisect.bisect_right(starts, pc) - 1
        if idx < 0:
            return None
        start, end, fde = self._fde_index[idx]
        if start <= pc < end:
            return fde
        return None

    def get_cfi_state(self, pc: int) -> Optional[CFIState]:
        """Get the CFI register rules for a given PC.

        Args:
            pc: Program counter value.

        Returns:
            CFIState with CFA rule and register rules, or None if no FDE
            covers this PC.
        """
        fde = self._find_fde(pc)
        if not fde:
            return None

        try:
            decoded = fde.get_decoded()
            table = decoded.table
        except Exception as e:
            logger.debug("CFI decode failed for PC=0x%08x: %s", pc, e)
            return None

        # Find the row that covers this PC
        # The table rows have 'pc' keys; we need the last row with pc <= target_pc
        best_row = None
        for row in table:
            row_pc = row.get('pc', 0)
            if row_pc <= pc:
                best_row = row
            else:
                break

        if best_row is None:
            return None

        return self._row_to_cfi_state(best_row)

    def _row_to_cfi_state(self, row: Dict) -> CFIState:
        """Convert a decoded table row to a CFIState."""
        cfa_rule = None
        cfa_obj = row.get('cfa')
        if cfa_obj and isinstance(cfa_obj, CFARule):
            cfa_rule = {
                'reg': cfa_obj.reg,
                'offset': cfa_obj.offset,
            }

        registers: Dict[str, Dict] = {}
        for key, val in row.items():
            if key in ('pc', 'cfa'):
                continue
            if isinstance(val, RegisterRule):
                try:
                    rule_type = val.type  # e.g. 'UNDEFINED', 'OFFSET', 'SAME_VALUE', 'REGISTER'
                except AttributeError:
                    rule_type = str(val)
                rule_info = {'type': rule_type, 'offset': None}
                if rule_type == CFIRuleType.OFFSET:
                    try:
                        rule_info['offset'] = val.arg
                    except AttributeError:
                        pass
                elif rule_type == CFIRuleType.REGISTER:
                    try:
                        rule_info['reg'] = val.arg
                    except AttributeError:
                        pass
                # key is DWARF register number (int or str)
                reg_name = _dw_reg_name(int(key)) if isinstance(key, (int, str)) and str(key).isdigit() else str(key)
                registers[reg_name] = rule_info

        return CFIState(
            pc=row.get('pc', 0),
            cfa_rule=cfa_rule,
            registers=registers,
        )

    def unwind_frame(self, pc: int, sp: int,
                     dump_reader) -> Optional[Tuple[int, int]]:
        """Unwind one stack frame using CFI rules.

        Args:
            pc: Current program counter.
            sp: Current stack pointer.
            dump_reader: DumpReader for reading memory.

        Returns:
            (caller_pc, caller_sp) or None if unwinding fails.
        """
        state = self.get_cfi_state(pc)
        if not state:
            return None

        # Read return address
        ret_reg = str(self._return_address_register)
        caller_pc = state.get_register_value(sp, ret_reg, dump_reader)
        if not caller_pc:
            return None

        # Compute caller's SP from CFA
        # CFA = SP_at_call + offset_after_prologue
        # caller_SP = CFA (approximately, since CFA = SP before call)
        cfa = state.compute_cfa(sp)
        if cfa is None:
            return None

        # The CFA is typically the caller's SP value
        # (before the callee pushed anything)
        return (caller_pc, cfa)

    def get_all_register_values(self, pc: int, sp: int,
                                dump_reader) -> Dict[str, Optional[int]]:
        """Attempt to read all recoverable register values from the dump.

        Args:
            pc: Current program counter.
            sp: Current stack pointer.
            dump_reader: DumpReader for reading memory.

        Returns:
            Dict mapping register name to value (int) or None if unrecoverable.
        """
        state = self.get_cfi_state(pc)
        if not state:
            return {}

        result: Dict[str, Optional[int]] = {}
        for reg_name in state.registers:
            result[reg_name] = state.get_register_value(sp, reg_name, dump_reader)

        return result

    def has_entry_for(self, pc: int) -> bool:
        """Check if there is a CFI entry covering the given PC."""
        return self._find_fde(pc) is not None

    @property
    def is_available(self) -> bool:
        return self._parsed and len(self._fde_index) > 0

    def get_fde_count(self) -> int:
        return len(self._fde_index)