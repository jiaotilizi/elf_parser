#!/usr/bin/env python3
"""QEMU sifive_e (RISC-V RV32) bare-metal firmware: run and dump multi-region.

RISC-V sifive_e memory has two regions we need:
  - FLASH 0x20000000 (1MB): code + rodata (char* string literals live here)
  - RAM   0x80000000 (16KB): data + bss (g_* globals live here)

QemuRunner.run_and_dump_multi_region() generates per-region dump files:
  <dump_path>.flash.bin and <dump_path>.ram.bin

DumpReader expects a single concatenated dump file with regions in the same
order as the profile's `memory:` list. This script concatenates them.
"""
import os
import sys

_TEST_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)

_COMMON_DIR = os.path.dirname(_TEST_DIR)
if _COMMON_DIR not in sys.path:
    sys.path.insert(0, _COMMON_DIR)

from _common.qemu_runner import QemuRunner, runner_from_profile
from core.profile_loader import ProfileLoader

SCENARIO_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    loader = ProfileLoader()
    profile = loader.load_profile('qemu/riscv_bare')
    regions = loader.get_memory_regions(profile)

    runner = runner_from_profile(
        profile_name='qemu/riscv_bare',
        scenario_dir=SCENARIO_DIR,
        elf_filename='output/img/test_firmware_riscv.elf',
        dump_filename='output/img/test_dump_riscv.bin',
    )

    print(f"  Regions: {[(r['name'], hex(r['start_addr']), r['size']) for r in regions]}")
    ok = runner.run_and_dump_multi_region(regions)
    if not ok:
        return 1

    dump_path = runner.dump_path
    with open(dump_path, 'wb') as out_f:
        for region in regions:
            region_path = f"{dump_path}.{region['name']}.bin"
            if not os.path.exists(region_path):
                print(f"  Warning: missing region file {region_path}", file=sys.stderr)
                continue
            with open(region_path, 'rb') as in_f:
                out_f.write(in_f.read())
            print(f"  Concat: {os.path.basename(region_path)} -> {os.path.basename(dump_path)}")

    total_size = os.path.getsize(dump_path)
    expected = sum(r['size'] for r in regions)
    print(f"\n  Final dump: {dump_path} ({total_size} bytes, expected {expected})")
    if total_size != expected:
        print(f"  Warning: size mismatch ({total_size} != {expected})", file=sys.stderr)

    print(f"\n  Next: python3 show_parsed.py")
    return 0


if __name__ == '__main__':
    sys.exit(main())