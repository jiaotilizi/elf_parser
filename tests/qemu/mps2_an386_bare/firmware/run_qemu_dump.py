#!/usr/bin/env python3
"""QEMU mps2-an386 Cortex-M4 裸机固件：运行并 dump RAM。

通过 ../_common/qemu_runner.py 的 QemuRunner 由 profile 驱动，
本文件只是 ~10 行 shim。

流程：
  1. 启动 QEMU (mps2-an386, Cortex-M4) 加载固件，QMP 通过 unix socket
  2. 等待固件运行（main → trigger_crash_assert → while(1)）
  3. 通过 QMP 的 pmemsave 命令 dump RAM
  4. 关闭 QEMU
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
ELF_FILENAME = 'output/img/test_firmware_qemu.elf'
DUMP_FILENAME = 'output/img/test_dump_qemu.bin'
PROFILE_NAME = 'qemu/mps2_an386_bare'


def main():
    runner = runner_from_profile(
        profile_name=PROFILE_NAME,
        scenario_dir=SCENARIO_DIR,
        elf_filename=ELF_FILENAME,
        dump_filename=DUMP_FILENAME,
    )
    ok = runner.run_and_dump()
    if ok:
        print(f"\n  ★ 运行 python3 show_qemu_parsed.py 查看解析效果")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())