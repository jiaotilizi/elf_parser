"""Show parsed output for QEMU Cortex-R52 + ThreadX real-run dump."""
import os
import sys

_TEST_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

from _common.show_parsed_base import ShowParsedBase

SCENARIO_DIR = os.path.dirname(os.path.abspath(__file__))


class QemuR52ThreadXShow(ShowParsedBase):
    BANNER_TITLE = 'Offline memory analysis - QEMU Cortex-R52 + ThreadX V6.5.1 crash dump auto-recovery'
    BANNER_LINES = [
        f'  ELF  : output/img/sample_threadx.elf (ThreadX V6.5.1 on mps3-an536)',
        f'  Dump : output/img/threadx_ram_dump.bin (RAM 4MB after 3s runtime)',
        f'  Arch : ARMv8-R (Cortex-R52, 32-bit ARM state)',
        f'  OS   : ThreadX V6.5.1 with 10 threads + mutex + sem + queue + event flag + timer',
        f'  Key  : validates TX_THREAD struct DWARF parsing + RTOS plugin thread enumeration',
    ]
    FOOTER_LINES = [
        'OK: ThreadX QEMU real-run dump works',
        'OK: TX_THREAD struct in DWARF verified',
        'OK: _tx_thread_current_ptr non-null after scheduler start',
        'OK: same parser / same DWARF / with RTOS - universality verified',
    ]


def main():
    show = QemuR52ThreadXShow(
        scenario_dir=SCENARIO_DIR,
        elf_filename='output/img/sample_threadx.elf',
        dump_filename='output/img/threadx_ram_dump.bin',
        profile_name='qemu/mps3_an536_threadx',
    )
    return show.run()


if __name__ == '__main__':
    sys.exit(main())
