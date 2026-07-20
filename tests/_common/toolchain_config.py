#!/usr/bin/env python3
"""跨平台工具链配置：根据操作系统自动识别并配置交叉编译工具链路径。

默认配置：
- Windows: 使用 MSYS2 UCRT64 的工具链
- macOS: 使用 Homebrew 或系统默认路径
- Linux: 使用系统默认路径

可通过环境变量覆盖：
  ARM_TOOLCHAIN_PATH: ARM 工具链路径（arm-none-eabi-gcc）
  AARCH64_TOOLCHAIN_PATH: AArch64 工具链路径（aarch64-none-elf-gcc）
  RISCV_TOOLCHAIN_PATH: RISC-V 工具链路径（riscv64-elf-gcc）
  QEMU_PATH: QEMU 二进制路径
"""
import os
import platform
import subprocess
from typing import Optional, Dict


def get_os_type() -> str:
    """返回操作系统类型: 'windows', 'macos', 'linux'."""
    sys_type = platform.system()
    if sys_type == 'Windows':
        return 'windows'
    elif sys_type == 'Darwin':
        return 'macos'
    else:
        return 'linux'


def find_executable(name: str, default_paths: Optional[list] = None) -> str:
    """在 PATH 中查找可执行文件，Windows 自动追加 .exe 后缀。"""
    os_type = get_os_type()
    
    if os.path.isabs(name) and os.path.exists(name):
        return name
    
    if os_type == 'windows' and not name.endswith('.exe'):
        if os.path.isabs(name + '.exe') and os.path.exists(name + '.exe'):
            return name + '.exe'
    
    for path in os.environ.get('PATH', '').split(os.pathsep):
        if not path:
            continue
        candidate = os.path.join(path, name)
        if os.path.exists(candidate):
            return candidate
        if os_type == 'windows':
            candidate_exe = candidate + '.exe'
            if os.path.exists(candidate_exe):
                return candidate_exe
    
    if default_paths:
        for default_path in default_paths:
            candidate = os.path.join(default_path, name)
            if os.path.exists(candidate):
                return candidate
            if os_type == 'windows':
                candidate_exe = candidate + '.exe'
                if os.path.exists(candidate_exe):
                    return candidate_exe
    
    return name


# 默认工具链路径配置
_DEFAULT_TOOLCHAIN_PATHS: Dict[str, Dict[str, str]] = {
    'windows': {
        'arm': r'C:\msys64\ucrt64\bin',
        'aarch64': r'D:\ProgramFiles\ARM\aarch64\bin',
        'riscv': r'C:\msys64\ucrt64\bin',
        'qemu': r'C:\msys64\ucrt64\bin',
    },
    'macos': {
        'arm': '/opt/homebrew/bin',
        'aarch64': '/opt/homebrew/bin',
        'riscv': '/opt/homebrew/bin',
        'qemu': '/opt/homebrew/bin',
    },
    'linux': {
        'arm': '/usr/bin',
        'aarch64': '/usr/bin',
        'riscv': '/usr/bin',
        'qemu': '/usr/bin',
    },
}


def get_toolchain_paths() -> Dict[str, str]:
    """返回当前平台的工具链路径配置。"""
    os_type = get_os_type()
    return _DEFAULT_TOOLCHAIN_PATHS.get(os_type, _DEFAULT_TOOLCHAIN_PATHS['linux'])


# ── 工具链二进制路径 ──────────────────────────────────────────

def get_arm_toolchain_prefix() -> str:
    """返回 ARM 工具链前缀 (arm-none-eabi-)。"""
    env_path = os.environ.get('ARM_TOOLCHAIN_PATH')
    if env_path:
        return os.path.join(env_path, 'arm-none-eabi-')
    
    paths = get_toolchain_paths()
    return os.path.join(paths['arm'], 'arm-none-eabi-')


def get_aarch64_toolchain_prefix() -> str:
    """返回 AArch64 工具链前缀 (aarch64-none-elf-)。"""
    env_path = os.environ.get('ARCH64_TOOLCHAIN_PATH') or os.environ.get('AARCH64_TOOLCHAIN_PATH')
    if env_path:
        return os.path.join(env_path, 'aarch64-none-elf-')
    
    paths = get_toolchain_paths()
    return os.path.join(paths['aarch64'], 'aarch64-none-elf-')


def get_riscv_toolchain_prefix() -> str:
    """返回 RISC-V 工具链前缀 (riscv64-elf-)。"""
    env_path = os.environ.get('RISCV_TOOLCHAIN_PATH')
    if env_path:
        return os.path.join(env_path, 'riscv64-elf-')
    
    paths = get_toolchain_paths()
    return os.path.join(paths['riscv'], 'riscv64-elf-')


def get_qemu_binary(name: str) -> str:
    """返回 QEMU 二进制路径。"""
    env_path = os.environ.get('QEMU_PATH')
    if env_path:
        candidate = os.path.join(env_path, name)
        if os.path.exists(candidate):
            return candidate
    
    paths = get_toolchain_paths()
    return find_executable(name, [paths['qemu']])


# ── 便捷函数 ──────────────────────────────────────────────────

def get_arm_gcc() -> str:
    """返回 arm-none-eabi-gcc 路径。"""
    prefix = get_arm_toolchain_prefix()
    gcc = prefix + 'gcc'
    if get_os_type() == 'windows' and not gcc.endswith('.exe'):
        gcc += '.exe'
    if os.path.exists(gcc):
        return gcc
    return find_executable('arm-none-eabi-gcc')


def get_arm_objcopy() -> str:
    """返回 arm-none-eabi-objcopy 路径。"""
    prefix = get_arm_toolchain_prefix()
    objcopy = prefix + 'objcopy'
    if get_os_type() == 'windows' and not objcopy.endswith('.exe'):
        objcopy += '.exe'
    if os.path.exists(objcopy):
        return objcopy
    return find_executable('arm-none-eabi-objcopy')


def get_aarch64_gcc() -> str:
    """返回 aarch64-none-elf-gcc 路径。"""
    prefix = get_aarch64_toolchain_prefix()
    gcc = prefix + 'gcc'
    if get_os_type() == 'windows' and not gcc.endswith('.exe'):
        gcc += '.exe'
    if os.path.exists(gcc):
        return gcc
    return find_executable('aarch64-none-elf-gcc')


def get_aarch64_objcopy() -> str:
    """返回 aarch64-none-elf-objcopy 路径。"""
    prefix = get_aarch64_toolchain_prefix()
    objcopy = prefix + 'objcopy'
    if get_os_type() == 'windows' and not objcopy.endswith('.exe'):
        objcopy += '.exe'
    if os.path.exists(objcopy):
        return objcopy
    return find_executable('aarch64-none-elf-objcopy')


def get_riscv_gcc() -> str:
    """返回 riscv64-elf-gcc 路径。"""
    prefix = get_riscv_toolchain_prefix()
    gcc = prefix + 'gcc'
    if get_os_type() == 'windows' and not gcc.endswith('.exe'):
        gcc += '.exe'
    if os.path.exists(gcc):
        return gcc
    return find_executable('riscv64-elf-gcc')


def get_riscv_objcopy() -> str:
    """返回 riscv64-elf-objcopy 路径。"""
    prefix = get_riscv_toolchain_prefix()
    objcopy = prefix + 'objcopy'
    if get_os_type() == 'windows' and not objcopy.endswith('.exe'):
        objcopy += '.exe'
    if os.path.exists(objcopy):
        return objcopy
    return find_executable('riscv64-elf-objcopy')


def get_qemu_arm() -> str:
    """返回 qemu-system-arm 路径。"""
    return get_qemu_binary('qemu-system-arm')


def get_qemu_aarch64() -> str:
    """返回 qemu-system-aarch64 路径。"""
    return get_qemu_binary('qemu-system-aarch64')


def get_qemu_riscv64() -> str:
    """返回 qemu-system-riscv64 路径。"""
    return get_qemu_binary('qemu-system-riscv64')


def print_toolchain_info():
    """打印当前工具链配置信息。"""
    os_type = get_os_type()
    print(f"=== 工具链配置 ({os_type}) ===")
    print(f"ARM GCC:        {get_arm_gcc()}")
    print(f"ARM objcopy:    {get_arm_objcopy()}")
    print(f"AArch64 GCC:    {get_aarch64_gcc()}")
    print(f"AArch64 objcopy:{get_aarch64_objcopy()}")
    print(f"RISC-V GCC:     {get_riscv_gcc()}")
    print(f"RISC-V objcopy: {get_riscv_objcopy()}")
    print(f"QEMU ARM:       {get_qemu_arm()}")
    print(f"QEMU AArch64:   {get_qemu_aarch64()}")
    print(f"QEMU RISC-V:    {get_qemu_riscv64()}")
    print()


if __name__ == '__main__':
    print_toolchain_info()
