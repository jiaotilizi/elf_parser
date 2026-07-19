#!/usr/bin/env python3
"""通用 QEMU 运行器：通过 QMP 启动 QEMU、运行固件、dump 内存。

支持两种模式：
  - 单区域 dump（run_and_dump）：典型场景如 Cortex-M 的 RAM-only dump
  - 多区域 dump（run_and_dump_multi_region）：典型场景如 RISC-V 的 flash + RAM 拼接

由 profile YAML 的 `qemu:` 块驱动，不硬编码场景细节：
  ```yaml
  qemu:
    binary: qemu-system-arm
    machine: mps2-an386
    cpu: cortex-m4
    kernel_arg: -kernel     # 或 -device loader,file=
    ram_base: 0x20000000
    ram_size: 4096
    run_seconds: 2.0
    extra_args: []          # 可选，追加到 QEMU 命令行
  ```

通过 `runner_from_profile(profile_name, scenario_dir)` 工厂构造。
"""
import os
import sys
import json
import time
import socket
import signal
import subprocess
from typing import Dict, List, Optional, Any

# 让脚本能 import 到 core 模块（在 elf_parser/ 下）
_ELF_PARSER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ELF_PARSER_DIR not in sys.path:
    sys.path.insert(0, _ELF_PARSER_DIR)

from core.profile_loader import ProfileLoader


class QMPConnection:
    """简单的 QMP (QEMU Machine Protocol) 客户端。"""

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.sock.settimeout(5.0)
        self._buffer = b''

    def _recv_json(self) -> dict:
        """读取一行 JSON。"""
        while b'\r\n' not in self._buffer and b'\n' not in self._buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("QMP 连接关闭")
            self._buffer += chunk
        if b'\r\n' in self._buffer:
            line, self._buffer = self._buffer.split(b'\r\n', 1)
        else:
            line, self._buffer = self._buffer.split(b'\n', 1)
        return json.loads(line.decode())

    def execute(self, cmd: str, arguments: dict = None) -> dict:
        """执行 QMP 命令，跳过事件通知，返回 return/error 字典。"""
        msg = {"execute": cmd}
        if arguments:
            msg["arguments"] = arguments
        self.sock.sendall((json.dumps(msg) + '\r\n').encode())
        while True:
            resp = self._recv_json()
            if 'return' in resp or 'error' in resp:
                return resp
            # 事件通知，继续读

    def handshake(self):
        """QMP 握手：读取 banner + 发送 qmp_capabilities。"""
        banner = self._recv_json()
        if 'QMP' not in banner:
            raise RuntimeError(f"意外的 QMP banner: {banner}")
        self.execute("qmp_capabilities")


class QemuRunner:
    """参数化的 QEMU 运行器，由 profile 的 qemu: 块构造。

    典型用法：
        runner = QemuRunner(
            qemu_binary='qemu-system-arm',
            machine='mps2-an386',
            cpu='cortex-m4',
            kernel_arg='-kernel',
            elf_path='/path/to/fw.elf',
            dump_path='/path/to/dump.bin',
            ram_base=0x20000000,
            ram_size=4096,
            run_seconds=2.0,
        )
        runner.run_and_dump()

    多区域场景（如 RISC-V flash + RAM）：
        runner.run_and_dump_multi_region([
            {'name': 'flash', 'start_addr': 0x20000000, 'size': 0x100000},
            {'name': 'ram',   'start_addr': 0x80000000, 'size': 0x1000},
        ])
        # 输出文件是 dump_path（单区域）或 dump_path + '.<region>.bin'（多区域）
    """

    def __init__(
        self,
        *,
        qemu_binary: str,
        machine: str,
        cpu: str,
        kernel_arg: str,
        elf_path: str,
        dump_path: str,
        ram_base: int,
        ram_size: int,
        run_seconds: float = 2.0,
        extra_args: Optional[List[str]] = None,
        qmp_socket: Optional[str] = None,
        wait_symbol_addr: Optional[int] = None,
    ):
        self.qemu_binary = qemu_binary
        self.machine = machine
        self.cpu = cpu
        self.kernel_arg = kernel_arg
        self.elf_path = elf_path
        self.dump_path = dump_path
        self.ram_base = ram_base
        self.ram_size = ram_size
        self.run_seconds = run_seconds
        self.extra_args = extra_args or []
        self.qmp_socket = qmp_socket or '/tmp/qemu-qmp.sock'
        self.wait_symbol_addr = wait_symbol_addr

    # ── 命令构造 ──────────────────────────────────────────────
    def build_qemu_cmd(self) -> List[str]:
        """构造 QEMU 命令行。kernel_arg 决定 ELF 加载方式。"""
        cmd = [
            self.qemu_binary,
            '-machine', self.machine,
            '-nographic',
            '-serial', 'null',
            '-qmp', f'unix:{self.qmp_socket},server,nowait',
        ]
        # kernel_arg 可能是 '-kernel'（Cortex-M/A 直接加载到 VMA）或
        # '-device' + 'loader,file=...'（RISC-V sifive_e 模式）
        if self.kernel_arg == '-kernel':
            cmd += ['-kernel', self.elf_path]
        elif self.kernel_arg == '-device':
            cmd += ['-device', f'loader,file={self.elf_path}']
        else:
            # 兼容直接传入的字符串（如 '-bios'）
            cmd += [self.kernel_arg, self.elf_path]

        # CPU 显式指定时加入
        if self.cpu:
            cmd += ['-cpu', self.cpu]

        # 追加场景特定参数（如 RISC-V 的 `-device loader` 之外的额外参数）
        cmd += self.extra_args
        return cmd

    # ── 单区域 dump ───────────────────────────────────────────
    def run_and_dump(self, verbose: bool = True) -> bool:
        """启动 QEMU → 运行 run_seconds → pmemsave 单区域 RAM → 退出。

        成功返回 True，dump 写入 self.dump_path。
        """
        return self._run_and_dump_regions(
            regions=[{'name': 'ram', 'start_addr': self.ram_base, 'size': self.ram_size}],
            dump_path=self.dump_path,
            verbose=verbose,
        )

    # ── 多区域 dump ────────────────────────────────────────────
    def run_and_dump_multi_region(
        self,
        regions: List[Dict[str, int]],
        verbose: bool = True,
    ) -> bool:
        """启动 QEMU → 运行 run_seconds → 对每个区域 pmemsave → 退出。

        每个区域输出到 self.dump_path + '.<region_name>.bin'。
        regions: [{'name': 'flash', 'start_addr': 0x..., 'size': 0x...}, ...]
        """
        ok = True
        for region in regions:
            region_path = f"{self.dump_path}.{region['name']}.bin"
            if not self._run_and_dump_regions(
                regions=[region],
                dump_path=region_path,
                verbose=verbose,
            ):
                ok = False
        return ok

    def _run_and_dump_regions(
        self,
        regions: List[Dict[str, int]],
        dump_path: str,
        verbose: bool = True,
    ) -> bool:
        """内部：启动 QEMU，dump 一组区域到指定路径。

        注意：当前实现是「每次启动 QEMU 跑一遍只 dump 一个区域」的简化版。
        如果要支持「一次启动 dump 多区域」，可扩展为在握手后循环 pmemsave。
        """
        if not os.path.exists(self.elf_path):
            print(f"✗ ELF 不存在: {self.elf_path}", file=sys.stderr)
            return False

        # 清理旧 socket
        if os.path.exists(self.qmp_socket):
            os.remove(self.qmp_socket)

        qemu_cmd = self.build_qemu_cmd()
        if verbose:
            cpu_label = self.cpu or 'default'
            print(f"  QEMU : {self.machine} (CPU={cpu_label})")
            print(f"  ELF  : {os.path.basename(self.elf_path)}")

        qemu_proc = subprocess.Popen(
            qemu_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        time.sleep(0.5)

        if qemu_proc.poll() is not None:
            stderr = qemu_proc.stderr.read().decode()
            print(f"✗ QEMU 启动失败:\n{stderr}", file=sys.stderr)
            return False

        # 连接 QMP
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connected = False
        for _ in range(20):
            try:
                sock.connect(self.qmp_socket)
                connected = True
                break
            except (FileNotFoundError, ConnectionRefusedError):
                time.sleep(0.1)

        if not connected:
            print("✗ 无法连接 QMP", file=sys.stderr)
            qemu_proc.send_signal(signal.SIGTERM)
            return False

        try:
            qmp = QMPConnection(sock)
            qmp.handshake()
            if verbose:
                print(f"  QMP  : 握手成功")

            status = qmp.execute("query-status")
            if verbose:
                print(f"  状态 : {status.get('return', {}).get('status', 'unknown')}")

            # 让固件运行
            if verbose:
                print(f"  运行 : 等待 {self.run_seconds}s ...")
            time.sleep(self.run_seconds)

            # 如果配置了等待标志，循环检查直到标志变为非零
            if hasattr(self, 'wait_symbol_addr') and self.wait_symbol_addr is not None:
                if verbose:
                    print(f"  等待 : 检查地址 0x{self.wait_symbol_addr:x} ...")
                for _ in range(50):
                    result = qmp.execute("pmemsave", {
                        "val": self.wait_symbol_addr,
                        "size": 4,
                        "filename": "/tmp/qemu_wait_check.bin"
                    })
                    if 'error' not in result:
                        with open('/tmp/qemu_wait_check.bin', 'rb') as f:
                            val = int.from_bytes(f.read(4), 'little')
                            if val != 0:
                                if verbose:
                                    print(f"  等待 : 标志已设置 (0x{val:x})")
                                break
                    time.sleep(0.1)
                else:
                    if verbose:
                        print(f"  等待 : 超时，继续执行")

            # 暂停 VM
            qmp.execute("stop")
            if verbose:
                print(f"  暂停 : VM 已停止")

            # 每个区域 pmemsave 到独立文件
            for region in regions:
                start = region['start_addr']
                size = region['size']
                name = region.get('name', 'region')
                if len(regions) == 1:
                    out_path = dump_path
                else:
                    out_path = f"{dump_path}.{name}.bin"
                if verbose:
                    print(f"  Dump : {name} [{start:#x} - {start+size:#x}] -> {os.path.basename(out_path)}")
                result = qmp.execute("pmemsave", {
                    "val": start,
                    "size": size,
                    "filename": out_path,
                })
                if 'error' in result:
                    print(f"✗ pmemsave {name} 失败: {result['error']}", file=sys.stderr)
                    return False
                time.sleep(0.3)

            qmp.execute("quit")

        except Exception as e:
            print(f"✗ QMP 错误: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return False
        finally:
            sock.close()
            try:
                qemu_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                qemu_proc.send_signal(signal.SIGTERM)
                qemu_proc.wait(timeout=3)
            if os.path.exists(self.qmp_socket):
                os.remove(self.qmp_socket)

        # 验证 dump 文件
        for region in regions:
            name = region.get('name', 'region')
            if len(regions) == 1:
                out_path = dump_path
            else:
                out_path = f"{dump_path}.{name}.bin"
            if not os.path.exists(out_path):
                print(f"✗ Dump 文件未生成: {out_path}", file=sys.stderr)
                return False
            size = os.path.getsize(out_path)
            with open(out_path, 'rb') as f:
                data = f.read()
            non_zero = sum(1 for b in data if b != 0)
            if verbose:
                print(f"  {name:5s}: {size} bytes ({size:#x}), 非零 {non_zero}/{len(data)} ({100*non_zero/max(len(data),1):.1f}%)")
            if non_zero == 0:
                print(f"✗ {name} dump 全为 0，固件可能未运行", file=sys.stderr)
                return False

        if verbose:
            print(f"\n{'='*60}")
            print(f"✓ QEMU dump 生成成功！")
        return True


def runner_from_profile(
    profile_name: str,
    scenario_dir: str,
    elf_filename: str,
    dump_filename: str,
) -> QemuRunner:
    """从 profile YAML 的 qemu: 块构造 QemuRunner。

    参数：
      profile_name: 如 'qemu/arm_mps2_an386_bare'
      scenario_dir: 场景目录（含 ELF 和 dump），如 '.../firmware/qemu_m4_bare'
      elf_filename: ELF 文件名（不含路径），如 'test_firmware_qemu.elf'
      dump_filename: dump 文件名（不含路径），如 'test_dump_qemu.bin'
    """
    loader = ProfileLoader()
    profile = loader.load_profile(profile_name)
    if profile is None:
        raise FileNotFoundError(f"profile '{profile_name}' 未找到")
    qemu_cfg = profile.get('qemu')
    if not qemu_cfg:
        raise ValueError(f"profile '{profile_name}' 缺少 qemu: 块")

    elf_path = os.path.join(scenario_dir, elf_filename)
    dump_path = os.path.join(scenario_dir, dump_filename)

    # 解析 ram_base：YAML 可能写 '0x20000000' 或十进制
    ram_base_str = str(qemu_cfg.get('ram_base', '0x20000000'))
    ram_base = int(ram_base_str, 0) if ram_base_str.startswith('0x') else int(ram_base_str)

    wait_symbol = qemu_cfg.get('wait_symbol')
    wait_symbol_addr = None
    if wait_symbol:
        try:
            from core.elf_parser import ELFParser
            elf_parser = ELFParser(elf_path)
            sym = elf_parser.get_symbol_by_name(wait_symbol)
            if sym:
                wait_symbol_addr = sym['address']
                print(f"  等待符号: {wait_symbol} @ 0x{wait_symbol_addr:x}")
        except Exception as e:
            print(f"  警告: 无法获取等待符号地址: {e}")

    return QemuRunner(
        qemu_binary=qemu_cfg.get('binary', 'qemu-system-arm'),
        machine=qemu_cfg['machine'],
        cpu=qemu_cfg.get('cpu', ''),
        kernel_arg=qemu_cfg.get('kernel_arg', '-kernel'),
        elf_path=elf_path,
        dump_path=dump_path,
        ram_base=ram_base,
        ram_size=int(qemu_cfg.get('ram_size', 4096)),
        run_seconds=float(qemu_cfg.get('run_seconds', 2.0)),
        extra_args=qemu_cfg.get('extra_args', []),
        wait_symbol_addr=wait_symbol_addr,
    )
