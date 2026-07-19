"""展示 QEMU Cortex-R52 真实运行固件后的 dump 被自动解析恢复的效果。"""
import os
import sys

_TEST_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

from _common.show_parsed_base import ShowParsedBase

SCENARIO_DIR = os.path.dirname(os.path.abspath(__file__))


class QemuR52BareShow(ShowParsedBase):
    BANNER_TITLE = '离线内存分析 — QEMU Cortex-R52 Crash Dump 自动恢复演示'
    BANNER_LINES = [
        f'  ELF  : output/img/test_firmware_r52.elf (QEMU mps3-an536 编译)',
        f'  Dump : output/img/test_dump_r52.bin (QEMU pmemsave 真实 dump)',
        f'  原理 : R-profile ARMv7-R 固件在 QEMU 中真实运行 →',
        f'         QEMU pmemsave 导出 RAM → DWARF 自动解析',
    ]
    FOOTER_LINES = [
        '★ 这是 Cortex-R52 QEMU 真实运行产生的 dump',
        '★ 验证解析器在 R-profile ARMv7-R 上同样工作',
        '★ 与 M4 (ARMv7-E) 输出结构完全一致',
    ]


def main():
    show = QemuR52BareShow(
        scenario_dir=SCENARIO_DIR,
        elf_filename='output/img/test_firmware_r52.elf',
        dump_filename='output/img/test_dump_r52.bin',
        profile_name='qemu/arm_mps3_an536_bare',
    )
    return show.run()


if __name__ == '__main__':
    sys.exit(main())