#!/usr/bin/env python3
"""QEMU mps3-an536 (Cortex-R52) + ThreadX v6.5.1: run firmware and dump RAM.

Uses _common/qemu_runner.py QemuRunner driven by profile YAML.
"""
import os
import sys

_TEST_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

from _common.qemu_runner import runner_from_profile

SCENARIO_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    runner = runner_from_profile(
        profile_name='qemu/mps3_an536_threadx',
        scenario_dir=SCENARIO_DIR,
        elf_filename='output/img/sample_threadx.elf',
        dump_filename='output/img/threadx_ram_dump.bin',
    )
    ok = runner.run_and_dump()
    if ok:
        print(f"\n  Run: python3 firmware/qemu_r52_threadx/show_parsed.py")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())