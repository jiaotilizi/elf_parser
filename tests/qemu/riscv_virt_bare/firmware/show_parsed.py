"""Show parsed output for QEMU RISC-V (SiFive E) real-run dump."""
import os
import sys

_TEST_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

from _common.show_parsed_base import ShowParsedBase

SCENARIO_DIR = os.path.dirname(os.path.abspath(__file__))


class QemuRiscvBareShow(ShowParsedBase):
    BANNER_TITLE = 'Offline memory analysis - QEMU RISC-V (SiFive E) crash dump auto-recovery'
    BANNER_LINES = [
        f'  ELF  : output/img/test_firmware_riscv.elf (QEMU sifive_e build)',
        f'  Dump : output/img/test_dump_riscv.bin (multi-region: flash + ram concatenated)',
        f'  Arch : RV32IMAC (32-bit RISC-V)',
        f'  Key  : validates multi-region dump loading (char* into flash region)',
    ]
    FOOTER_LINES = [
        'OK: Cortex-A53 (AArch64) QEMU real-run dump works',
        'OK: RISC-V RV32 multi-region (flash + RAM) dump loads correctly',
        'OK: same parser / same DWARF / different ISA - universality verified',
    ]


def main():
    show = QemuRiscvBareShow(
        scenario_dir=SCENARIO_DIR,
        elf_filename='output/img/test_firmware_riscv.elf',
        dump_filename='output/img/test_dump_riscv.bin',
        profile_name='qemu/riscv_virt_bare',
    )
    return show.run()


if __name__ == '__main__':
    sys.exit(main())