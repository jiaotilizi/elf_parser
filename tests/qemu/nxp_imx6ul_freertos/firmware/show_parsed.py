#!/usr/bin/env python3
"""Show parsed result for NXP i.MX6UL + FreeRTOS firmware."""
import os
import sys

_TEST_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

from _common.show_parsed_base import ShowParsedBase


class ShowNxpImx6ulFreeRTOS(ShowParsedBase):
    BANNER_TITLE = 'NXP i.MX6UL (Cortex-A7) + FreeRTOS Crash Dump 自动恢复'
    BANNER_LINES = [
        '  芯片 : NXP i.MX6UL (Cortex-A7, ARMv7-A)',
        '  RTOS : FreeRTOS V11.3.0',
        '  平台 : QEMU virt machine',
    ]
    FOOTER_LINES = [
        '★ 验证要点: ARMv7-A 架构下 FreeRTOS TCB/Queue 解析',
    ]


def main():
    scenario_dir = os.path.dirname(os.path.abspath(__file__))
    elf_filename = 'output/img/test_firmware_nxp_imx6ul_freertos.elf'
    dump_filename = 'output/img/test_dump_nxp_imx6ul_freertos.bin'
    profile_name = 'qemu/nxp_imx6ul_freertos'

    show = ShowNxpImx6ulFreeRTOS(
        scenario_dir=scenario_dir,
        elf_filename=elf_filename,
        dump_filename=dump_filename,
        profile_name=profile_name,
    )
    return show.run()


if __name__ == '__main__':
    sys.exit(main())
