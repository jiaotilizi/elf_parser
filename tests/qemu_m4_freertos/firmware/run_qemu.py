#!/usr/bin/env python3
"""QEMU mps2-an386 (Cortex-M4) + FreeRTOS V11.3.0: run firmware and dump RAM.

Uses ../_common/qemu_runner.py QemuRunner driven by profile YAML.
"""
import os
import sys

_TEST_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

from _common.qemu_runner import runner_from_profile

SCENARIO_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    runner = runner_from_profile(
        profile_name='test/qemu_m4_freertos',
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