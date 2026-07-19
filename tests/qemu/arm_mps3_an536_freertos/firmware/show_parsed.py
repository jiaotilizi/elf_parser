#!/usr/bin/env python3
import os
import sys

_TEST_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

from _common.show_parsed_base import show_parsed_from_scenario


def main():
    return show_parsed_from_scenario(
        scenario_dir=os.path.dirname(os.path.abspath(__file__)),
        profile_name='qemu/arm_mps3_an536_freertos',
        elf_filename='output/img/test_firmware_freertos.elf',
        dump_filename='output/img/test_dump_freertos.bin',
    )


if __name__ == '__main__':
    sys.exit(main())