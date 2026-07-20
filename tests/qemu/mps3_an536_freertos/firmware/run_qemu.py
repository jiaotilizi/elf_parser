#!/usr/bin/env python3
import os
import sys

_TEST_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

_COMMON_DIR = os.path.dirname(_TEST_DIR)
if _COMMON_DIR not in sys.path:
    sys.path.insert(0, _COMMON_DIR)

from _common.qemu_runner import runner_from_profile

SCENARIO_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    runner = runner_from_profile(
        profile_name='qemu/mps3_an536_freertos',
        scenario_dir=SCENARIO_DIR,
        elf_filename='output/img/test_firmware_freertos.elf',
        dump_filename='output/img/test_dump_freertos.bin',
    )
    ok = runner.run_and_dump()
    if ok:
        print(f"\n  Run: python3 show_parsed.py")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())