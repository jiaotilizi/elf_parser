#!/usr/bin/env python3
"""QEMU virt Cortex-A53 (AArch64) 裸机固件：运行并 dump RAM。

通过 ../_common/qemu_runner.py 的 QemuRunner 由 profile 驱动。
"""
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


def main():
    runner = runner_from_profile(
        profile_name='test/qemu_aarch64_bare',
        scenario_dir=SCENARIO_DIR,
        elf_filename='output/img/test_firmware_aarch64.elf',
        dump_filename='output/img/test_dump_aarch64.bin',
    )
    ok = runner.run_and_dump()
    if ok:
        print(f"\n  ★ 运行 python3 show_parsed.py 查看解析效果")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())