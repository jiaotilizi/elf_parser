#!/usr/bin/env python3
"""Show parsed result for NXP i.MX6UL bare-metal firmware."""
import os
import sys

_TEST_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

_COMMON_DIR = os.path.dirname(_TEST_DIR)
if _COMMON_DIR not in sys.path:
    sys.path.insert(0, _COMMON_DIR)

from _common.show_parsed_base import show_parsed_from_scenario

SCENARIO_DIR = os.path.dirname(os.path.abspath(__file__))
ELF_FILENAME = 'output/img/test_firmware_nxp_imx6ul.elf'
DUMP_FILENAME = 'output/img/test_dump_nxp_imx6ul.bin'
PROFILE_NAME = 'qemu/nxp_imx6ul_bare'


def main():
    show_parsed_from_scenario(
        scenario_dir=SCENARIO_DIR,
        elf_filename=ELF_FILENAME,
        dump_filename=DUMP_FILENAME,
        profile_name=PROFILE_NAME,
    )


if __name__ == '__main__':
    sys.exit(main())
