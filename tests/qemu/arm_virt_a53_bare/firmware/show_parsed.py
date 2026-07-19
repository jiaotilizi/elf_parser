"""展示 QEMU AArch64 (Cortex-A53) 真实运行固件后的 dump 被自动解析恢复的效果。"""
import os
import sys

_TEST_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

from _common.show_parsed_base import ShowParsedBase

SCENARIO_DIR = os.path.dirname(os.path.abspath(__file__))


class QemuAarch64BareShow(ShowParsedBase):
    BANNER_TITLE = '离线内存分析 — QEMU AArch64 (Cortex-A53) Crash Dump 自动恢复演示'
    BANNER_LINES = [
        f'  ELF  : output/img/test_firmware_aarch64.elf (QEMU virt 编译)',
        f'  Dump : output/img/test_dump_aarch64.bin (QEMU pmemsave 真实 dump)',
        f'  原理 : AArch64 ARMv8-A 固件在 QEMU 中真实运行 →',
        f'         QEMU pmemsave 导出 RAM → DWARF 自动解析',
        f'  关键 : 验证 64 位指针 (byte_size=8) 解析路径',
    ]
    FOOTER_LINES = [
        '★ 这是 Cortex-A53 (AArch64) QEMU 真实运行产生的 dump',
        '★ char* 字段在 DWARF 中 byte_size == 8，验证 64 位指针修复',
        '★ 与 32 位 (M4/R52) 输出结构完全一致',
    ]


def main():
    show = QemuAarch64BareShow(
        scenario_dir=SCENARIO_DIR,
        elf_filename='output/img/test_firmware_aarch64.elf',
        dump_filename='output/img/test_dump_aarch64.bin',
        profile_name='qemu/arm_virt_a53_bare',
    )
    return show.run()


if __name__ == '__main__':
    sys.exit(main())