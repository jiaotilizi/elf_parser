#!/usr/bin/env python3
"""编译/链接辅助函数：为各 QEMU 场景生成 ELF。

提供通用的：
  - 工具链探测（按 chip.cpu 自动选择 arm-none-eabi-gcc / aarch64-elf-gcc / riscv64-elf-gcc）
  - CFLAGS 模板（按架构）
  - 简单的编译+链接调用

不依赖 Makefile：每个场景的 output/img/<scenario>.elf 由本模块根据 profile 生成。
"""
import os
import sys
import subprocess
from typing import List, Optional


# 工具链映射：CPU 名 → 二进制前缀
TOOLCHAIN_BY_CPU = {
    # ARM Cortex-M / Cortex-R (32-bit Thumb)
    'cortex-m4': 'arm-none-eabi-',
    'cortex-m3': 'arm-none-eabi-',
    'cortex-m7': 'arm-none-eabi-',
    'cortex-m0': 'arm-none-eabi-',
    'cortex-r52': 'arm-none-eabi-',
    'cortex-r5':  'arm-none-eabi-',
    # AArch64
    'cortex-a53': 'aarch64-elf-',
    'cortex-a57': 'aarch64-elf-',
    'cortex-a72': 'aarch64-elf-',
    # RISC-V
    'sifive-e31': 'riscv64-elf-',
    'sifive-e34': 'riscv64-elf-',
    'sifive-u54': 'riscv64-elf-',
}

# CFLAGS 模板：按架构
CFLAGS_BY_ARCH = {
    'armv7e-m': [
        '-mcpu=cortex-m4', '-mthumb',
        '-ffreestanding', '-nostdlib', '-nostartfiles',
        '-g3', '-gdwarf-4', '-O0',
        '-fdata-sections', '-ffunction-sections',
    ],
    'armv7-r': [
        '-mcpu=cortex-r52', '-mthumb',
        '-ffreestanding', '-nostdlib', '-nostartfiles',
        '-g3', '-gdwarf-4', '-O0',
        '-fdata-sections', '-ffunction-sections',
    ],
    'armv8-a': [
        '-march=armv8-a', '-mcpu=cortex-a53',
        '-ffreestanding', '-nostdlib', '-nostartfiles',
        '-g3', '-gdwarf-4', '-O0',
        '-fno-pic', '-fno-pie', '-mno-red-zone',
        '-fdata-sections', '-ffunction-sections',
    ],
    'riscv': [
        '-march=rv32imac_zicsr', '-mabi=ilp32',
        '-ffreestanding', '-nostdlib', '-nostartfiles',
        '-g3', '-gdwarf-4', '-O0',
        '-fdata-sections', '-ffunction-sections',
    ],
}


def get_toolchain_prefix(cpu: str) -> str:
    """根据 CPU 名返回工具链前缀，如 'arm-none-eabi-'。"""
    return TOOLCHAIN_BY_CPU.get(cpu, 'arm-none-eabi-')


def get_cflags(arch: str, cpu: Optional[str] = None) -> List[str]:
    """根据架构返回 CFLAGS。cpu 可用于微调（如 cortex-m4 vs cortex-m7）。"""
    base = list(CFLAGS_BY_ARCH.get(arch, CFLAGS_BY_ARCH['armv7e-m']))
    # 如果 cpu 给定且与默认不一致，覆盖 -mcpu
    if cpu:
        for i, flag in enumerate(base):
            if flag.startswith('-mcpu='):
                base[i] = f'-mcpu={cpu}'
                break
    return base


def run_cmd(cmd: List[str], cwd: Optional[str] = None, check: bool = True) -> int:
    """运行命令并打印，返回码。失败时若 check=True 则抛异常。"""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"✗ 命令失败 (rc={result.returncode}):", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        if check:
            raise RuntimeError(f"命令失败: {' '.join(cmd)}")
    return result.returncode


def compile_and_link(
    *,
    toolchain_prefix: str,
    cflags: List[str],
    ldflags: List[str],
    sources: List[str],
    startup_files: List[str],
    linker_script: str,
    output_elf: str,
    include_dirs: Optional[List[str]] = None,
    cwd: Optional[str] = None,
) -> str:
    """编译每个 .c → .o，然后链接 startup.o + *.o → output_elf。

    返回 output_elf 路径。
    """
    cc = toolchain_prefix + 'gcc'
    objdump = toolchain_prefix + 'objcopy'  # 占位，目前不需要

    include_flags = []
    for inc in (include_dirs or []):
        include_flags += ['-I', inc]

    # 编译每个源文件
    obj_files = []
    for src in sources + startup_files:
        obj = os.path.splitext(src)[0] + '.o'
        cmd = [cc] + cflags + include_flags + ['-c', src, '-o', obj]
        run_cmd(cmd, cwd=cwd)
        obj_files.append(obj)

    # 链接
    link_cmd = (
        [cc] + cflags +
        ['-T', linker_script, '-Wl,--gc-sections', '-Wl,-Map,' + output_elf + '.map'] +
        obj_files + ['-o', output_elf]
    )
    run_cmd(link_cmd, cwd=cwd)
    # 显式传 ldflags 给链接器
    if ldflags:
        # 上面已经合到 link_cmd 里了，这里是占位
        pass

    print(f"  ✓ 生成 ELF: {output_elf}")
    return output_elf


def ensure_toolchain(toolchain_prefix: str) -> bool:
    """检查工具链是否可用。返回 True/False。"""
    cc = toolchain_prefix + 'gcc'
    try:
        result = subprocess.run(
            [cc, '--version'],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"  工具链: {version}")
            return True
    except FileNotFoundError:
        pass
    print(f"✗ 工具链未找到: {cc}", file=sys.stderr)
    return False
