"""展示 BSS 段固件的 dump 被自动解析恢复的效果。

通过 _common/show_parsed_base.py 的 ShowParsedBase 基类渲染，
本文件只指定场景特定的 banner/footer。
"""
import os
import sys

# 让脚本能 import 到 _common/ 模块（在 firmware/ 下）
_FIRMWARE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FIRMWARE_DIR not in sys.path:
    sys.path.insert(0, _FIRMWARE_DIR)

from _common.show_parsed_base import ShowParsedBase

SCENARIO_DIR = os.path.dirname(os.path.abspath(__file__))


class BssSimulatedShow(ShowParsedBase):
    BANNER_TITLE = '离线内存分析 — BSS 段固件 Crash Dump 自动恢复演示'
    BANNER_LINES = [
        f'  ELF  : test_firmware_bss.elf',
        f'  Dump : test_dump_bss.bin',
        f'  原理 : 用 DWARF 调试信息 + RAM dump，自动展开所有结构体',
    ]
    FOOTER_LINES = [
        '所有结构体 100% 由 parse_struct_auto 从 DWARF 信息自动恢复，',
        '没有任何手动字段偏移！',
    ]


def main():
    show = BssSimulatedShow(
        scenario_dir=SCENARIO_DIR,
        elf_filename='test_firmware_bss.elf',
        dump_filename='test_dump_bss.bin',
        profile_name='bss_simulated',
    )
    return show.run()


if __name__ == '__main__':
    sys.exit(main())
