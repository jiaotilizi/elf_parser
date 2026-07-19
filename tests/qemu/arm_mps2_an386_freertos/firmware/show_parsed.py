"""Show parsed output for QEMU Cortex-M4 + FreeRTOS V11.3.0 real-run dump."""
import os
import sys

_TEST_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

from _common.show_parsed_base import ShowParsedBase

SCENARIO_DIR = os.path.dirname(os.path.abspath(__file__))


class QemuM4FreertosShow(ShowParsedBase):
    BANNER_TITLE = 'Offline memory analysis - QEMU Cortex-M4 + FreeRTOS V11.3.0 crash dump auto-recovery'
    BANNER_LINES = [
        f'  ELF  : output/img/test_firmware_freertos.elf (FreeRTOS V11.3.0 on mps2-an386)',
        f'  Dump : output/img/test_dump_freertos.bin (RAM 64KB after 3s runtime)',
        f'  Arch : ARMv7E-M (Cortex-M4, 32-bit)',
        f'  OS   : FreeRTOS V11.3.0 with 4 tasks + mutex + sem + queue + event group',
        f'  Key  : validates TCB_t/QueueDefinition DWARF parsing + RTOS plugin task enumeration',
    ]
    FOOTER_LINES = [
        'OK: FreeRTOS QEMU real-run dump works',
        'OK: TCB_t struct in DWARF verified',
        'OK: pxCurrentTCB non-null after scheduler start',
        'OK: same parser / same DWARF / with RTOS - universality verified',
    ]


def main():
    show = QemuM4FreertosShow(
        scenario_dir=SCENARIO_DIR,
        elf_filename='output/img/test_firmware_freertos.elf',
        dump_filename='output/img/test_dump_freertos.bin',
        profile_name='qemu/arm_mps2_an386_freertos',
    )
    return show.run()


if __name__ == '__main__':
    sys.exit(main())