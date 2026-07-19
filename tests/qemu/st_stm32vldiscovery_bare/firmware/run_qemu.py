#!/usr/bin/env python3
"""QEMU STM32VLDISCOVERY (Cortex-M3) bare metal: run and dump RAM."""
import os
import sys

_TEST_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

_COMMON_DIR = os.path.dirname(_TEST_DIR)
if _COMMON_DIR not in sys.path:
    sys.path.insert(0, _COMMON_DIR)

from _common.qemu_runner import runner_from_profile

SCENARIO_DIR = os.path.dirname(os.path.abspath(__file__))
ELF_FILENAME = 'output/img/test_firmware_stm32.elf'
DUMP_FILENAME = 'output/img/test_dump_stm32.bin'
PROFILE_NAME = 'qemu/st_stm32vldiscovery_bare'


def main():
    runner = runner_from_profile(
        profile_name=PROFILE_NAME,
        scenario_dir=SCENARIO_DIR,
        elf_filename=ELF_FILENAME,
        dump_filename=DUMP_FILENAME,
    )
    ok = runner.run_and_dump()
    if ok:
        print(f"\n  ★ 运行 python3 show_parsed.py 查看解析效果")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
