"""展示 QEMU 真实运行固件后的 dump 被自动解析恢复的效果。

通过 ../_common/show_parsed_base.py 的 ShowParsedBase 基类渲染，
本文件只指定场景特定的 banner/footer。
"""
import os
import sys

_TEST_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

from _common.show_parsed_base import ShowParsedBase

SCENARIO_DIR = os.path.dirname(os.path.abspath(__file__))


class QemuM4BareShow(ShowParsedBase):
    BANNER_TITLE = '离线内存分析 — QEMU 真实运行 Crash Dump 自动恢复演示'
    BANNER_LINES = [
        f'  ELF  : output/img/test_firmware_qemu.elf (QEMU mps2-an386 编译)',
        f'  Dump : output/img/test_dump_qemu.bin (QEMU pmemsave 真实 dump)',
        f'  原理 : 固件在 QEMU 中真实运行 → trigger_crash_assert →',
        f'         QEMU pmemsave 导出 RAM → DWARF 自动解析',
    ]
    FOOTER_LINES = [
        '★ 这是 QEMU 真实运行产生的 dump（非 Python 模拟）！',
        '★ 所有结构体 100% 由 parse_struct_auto 从 DWARF 信息自动恢复',
        '★ 证明离线分析工具能处理真实硬件行为产生的 dump',
    ]


def main():
    show = QemuM4BareShow(
        scenario_dir=SCENARIO_DIR,
        elf_filename='output/img/test_firmware_qemu.elf',
        dump_filename='output/img/test_dump_qemu.bin',
        profile_name='qemu/arm_mps2_an386_bare',
    )
    return show.run()


if __name__ == '__main__':
    sys.exit(main())