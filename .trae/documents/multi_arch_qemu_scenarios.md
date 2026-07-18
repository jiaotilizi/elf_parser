# 计划：多架构 QEMU 并行测试场景

## Context

用户希望扩展现有 QEMU 测试场景，从单一 Cortex-M4 裸机扩展到 **7 个平行场景**：3 个 M4 变体（bare/FreeRTOS/ThreadX）+ R52 裸机 + AArch64 裸机 + RISC-V 裸机 + 现有 BSS 模拟。目标：验证离线解析器对**多架构（含 64 位指针）**和 **RTOS 任务/同步原语**的解析泛用性。同时按要求把 `tests/` 重构为**平行目录**（单元测试与各固件场景同级）。

## 现状与已确认环境

- ✅ `arm-none-eabi-gcc 16.1.0` 已支持 Cortex-R52（`-mcpu=cortex-r52`）
- ❌ `aarch64-elf-gcc` / `riscv64-elf-gcc` 未装（brew 有 bottled 16.1.0）→ **Phase 0 安装**
- ✅ QEMU 机器：`mps3-an536` (R52)、`virt+cortex-a53` (AArch64, RAM@0x40000000)、`sifive_e` (RV32, flash@0x20000000/ram@0x80000000)
- ✅ FreeRTOS V11.3.0 / ThreadX v6.5.1 在 GitHub
- ⚠️ **解析器 bug**：[elf_parser.py:444](file:///Users/yangtao/Documents/core/elf_parser.py#L444) 硬编码 `read_uint32` 读指针，AArch64/RV64 的 8 字节指针会截断。`dump_reader.py` 已有 `read_uint64`/`read_pointer(addr, is_32bit)`。

## 目标目录结构

### `firmware/` — 每场景一目录
```
firmware/
├── _common/                       ← 共享基础设施（NEW）
│   ├── qemu_runner.py             ← 通用 QMP 运行器（参数化）
│   ├── show_parsed_base.py        ← 展示脚本基类
│   ├── build_helpers.py           ← 编译/链接辅助
│   └── test_firmware_bss.c        ← MOVED from firmware/common/
├── bss_simulated/                 ← 现有，保留
├── qemu_m4_bare/                  ← RENAMED from qemu_real
├── qemu_m4_freertos/              ← NEW：M4 + FreeRTOS V11.3.0
│   ├── rtos/                      ← git clone FreeRTOS-Kernel
│   ├── FreeRTOSConfig.h
│   └── ...
├── qemu_m4_threadx/               ← NEW：M4 + ThreadX v6.5.1
│   ├── rtos/                      ← git clone eclipse-threadx/threadx
│   ├── tx_user.h
│   └── ...
├── qemu_r52_bare/                  ← NEW：Cortex-R52 裸机
├── qemu_aarch64_bare/             ← NEW：AArch64 裸机（64 位指针）
└── qemu_riscv_bare/                ← NEW：RISC-V RV32 裸机
```
每场景目录统一含：`startup.S` / `linker.ld` / `main.c` / `run_qemu.py` / `show_parsed.py` / `build/` / `<scenario>.elf` / `<scenario>_dump.bin`。

### `tests/` — 平行子目录（用户明确要求）
```
tests/
├── __init__.py
├── unit/                          ← MOVED test_core.py
│   ├── __init__.py
│   ├── test_core.py
│   └── test_elf_parser_universality.py   ← NEW：64 位指针合成测试
├── bss_simulated/                 ← MOVED test_bss_firmware.py
├── qemu_m4_bare/                  ← MOVED+RENAMED test_qemu_firmware.py
├── qemu_m4_freertos/              ← NEW
├── qemu_m4_threadx/               ← NEW
├── qemu_r52_bare/                 ← NEW
├── qemu_aarch64_bare/             ← NEW
└── qemu_riscv_bare/               ← NEW
```
每场景 10 个测试，沿用现有 [test_qemu_firmware.py](file:///Users/yangtao/Documents/tests/test_qemu_firmware.py) 模式（class attrs ELF_PATH/DUMP_PATH、setUp skipTest）。

### `profiles/test/` — 每场景一 YAML
```
profiles/test/
├── bss_simulated.yaml             ← 拆自 test_firmware_real.yaml
├── qemu_m4_bare.yaml              ← 拆自 test_firmware_real.yaml
├── qemu_m4_freertos.yaml          ← NEW（ram_size 64KB，覆盖 RTOS 堆）
├── qemu_m4_threadx.yaml
├── qemu_r52_bare.yaml             ← RAM@0x20000000
├── qemu_aarch64_bare.yaml         ← RAM@0x40000000
└── qemu_riscv_bare.yaml            ← RAM@0x80000000 + Flash@0x20000000（多区域）
```
YAML 新增可选 `qemu:` 块（binary/machine/cpu/ram_base/ram_size/run_seconds/kernel_arg/extra_args），让 `qemu_runner.py` 完全由 profile 驱动，不硬编码。

## 关键改动

### A. 解析器泛用性修复（最高优先级，先做）

**文件**：[core/elf_parser.py](file:///Users/yangtao/Documents/core/elf_parser.py#L443-L454)

替换 `_read_typed_value` 指针分支（L443-454）：
```python
if kind == 'pointer':
    ptr_size = type_info.get('byte_size', self._address_size)
    if ptr_size == 4:
        ptr_val = dump_reader.read_uint32(address)
    elif ptr_size == 8:
        ptr_val = dump_reader.read_uint64(address)
    else:
        raw = dump_reader.read_memory(address, ptr_size)
        ptr_val = int.from_bytes(raw, 'little') if raw else 0
    hex_width = 16 if ptr_size == 8 else 8
    if self._is_char_pointer(type_info):
        if ptr_val == 0:
            return None
        try:
            return dump_reader.read_string(ptr_val)
        except Exception:
            return f'<ptr 0x{ptr_val:0{hex_width}x}>'
    return f'<ptr 0x{ptr_val:0{hex_width}x}>'
```

**文件**：[core/dump_reader.py](file:///Users/yangtao/Documents/core/dump_reader.py) — 加便捷方法：
```python
def read_pointer_by_size(self, address, byte_size=4):
    if byte_size == 4: return self.read_uint32(address)
    if byte_size == 8: return self.read_uint64(address)
    raw = self.read_memory(address, byte_size)
    return int.from_bytes(raw, 'little') if raw else None
```

**测试**：`tests/unit/test_elf_parser_universality.py` — 构造含已知 8 字节指针值的合成 dump，断言 `parse_struct_auto` 返回 `<ptr 0x00000000deadbeef>`（16 hex 宽），无需 QEMU 即可验证修复。

### B. 共享 QEMU 基础设施

**文件**：`firmware/_common/qemu_runner.py`（NEW）

把 [firmware/qemu_real/run_qemu_dump.py](file:///Users/yangtao/Documents/firmware/qemu_real/run_qemu_dump.py) 的 `QMPConnection` 类和 `main()` 提取为参数化 `QemuRunner`：
```python
class QemuRunner:
    def __init__(self, *, qemu_binary, machine, cpu, kernel_arg,
                 elf_path, dump_path, ram_base, ram_size,
                 run_seconds=2.0, extra_args=None): ...
    def run_and_dump(self): ...   # Popen → QMP handshake → sleep → stop → pmemsave → quit
    def run_and_dump_multi_region(self, regions): ...  # RISC-V 需要：多区域 pmemsave 拼接
```
`runner_from_profile(profile_name, scenario_dir)` 从 YAML `qemu:` 块构造 runner。每场景 `run_qemu.py` 变 10 行 shim。

**文件**：`firmware/_common/show_parsed_base.py`（NEW）— `ShowParsedBase` 基类提供 banner/scalar/struct_array 渲染框架，子类只填变量列表。

**复用**：`DumpReader` 已支持多区域（[dump_reader.py:36-53](file:///Users/yangtao/Documents/core/dump_reader.py#L36-L53)），RISC-V 多区域直接走通。

## 各场景细节（5 个新场景）

共享 C 源码：所有裸机场景 `main.c` 都是 `#include "../_common/test_firmware_bss.c"` 的薄包装（保留 `simulate_runtime` + `trigger_crash_assert`），断言期望值与现有 M4 测试一致。

| 场景 | QEMU 机器/CPU | RAM 基址 | Flash | 工具链/CFLAGS | 启动文件特点 |
|---|---|---|---|---|---|
| **qemu_r52_bare** | `mps3-an536` / `cortex-r52` | 0x20000000 | 无（全 RAM） | `arm-none-eabi-gcc -mcpu=cortex-r52 -mthumb -ffreestanding -g3 -gdwarf-4` | R-profile 无向量表，`_start` 设 SP → 清 .bss → 调 main |
| **qemu_aarch64_bare** | `virt` / `cortex-a53` | 0x40000000 | 无 | `aarch64-elf-gcc -march=armv8-a -mcpu=cortex-a53 -ffreestanding -g3 -fno-pic` | AArch64 boot：`_start` 设 SP（x0=`_estack`）→ 清 .bss → bl main；**64 位指针验证 Section A 修复** |
| **qemu_riscv_bare** | `sifive_e` / `sifive-e31` | 0x80000000 | 0x20000000 | `riscv64-elf-gcc -march=rv32imac_zicsr -mabi=ilp32 -ffreestanding -g3` | RISC-V reset 跳到 0x20000000，`_start` 设 SP → 清 .bss → call main。**需多区域 dump**（rodata 在 flash） |

**R52 linker**：全 RAM 布局（`RAM ORIGIN=0x20000000 LENGTH=4M`），`_sidata=_sdata`（copy 为 no-op）
**AArch64 linker**：`RAM ORIGIN=0x40000000 LENGTH=64M`，`_estack=ORIGIN+LENGTH`
**RISC-V linker**：`FLASH ORIGIN=0x20000000 LENGTH=1M` + `RAM ORIGIN=0x80000000 LENGTH=4K`

每场景 10 个测试：elf_exists / elf_header（class+machine+entry 范围）/ bss_in_ram / scalar_values / assert_info_expansion / record_details / test_point_expansion / trace_buffer_expansion / char_pointer_deref / auto_vs_manual_read。AArch64 额外加 `test_pointer_size_is_8`。

## RTOS 场景（M4 上 FreeRTOS + ThreadX）

复用 M4 启动文件/linker，加 RTOS 层。`simulate_runtime()` 数据仍填充（裸机断言全部保留），RTOS 断言叠加。

### qemu_m4_freertos
- `git clone --depth 1 --branch V11.3.0 https://github.com/FreeRTOS/FreeRTOS-Kernel.git rtos`
- 复用现成 `rtos/portable/GCC/ARM_CM4F/port.c`（无需移植）
- 写 `FreeRTOSConfig.h` + `startup.S`（SVC/PendSV/SysTick 通过 `.thumb_set` 别名到 `vPortSVCHandler`/`xPortPendSVHandler`/`xPortSysTickHandler`）
- `main.c`：4 个任务（LED/Sender/Receiver/IdleX）+ mutex + counting sem + queue + event group；`run_seconds=2.0` 后 dump
- 验证 DWARF 自动恢复：`TCB_t`（含 `pcTaskName` char 数组、`uxPriority`、`pxTopOfStack`）、`List_t`、`Queue_t`
- ram_size 64KB（覆盖 heap_4 + 任务栈）
- 10 个测试：scheduler_running / current_tcb_parseable / tcb_priority / mutex_owner_resolvable / semaphore_count / queue_messages / 裸机数据完整等。**断言结构性属性而非精确动态值**（避免时序 flaky）
- 兼容现有 `plugins/rtos/freertos/freertos_11p0.py`；如版本不匹配则加 `freertos_11p3.py`

### qemu_m4_threadx
- `git clone --depth 1 https://github.com/eclipse-threadx/threadx.git rtos`
- 复用 `rtos/ports/cortex-m4/gnu/`（含 6 个 .s + tx_port.c）
- 写 `tx_user.h` + `startup.S`（PendSV→`__tx_PendSVHandler`、SysTick→`__tx_SysTickHandler`）
- `main.c`：4 个线程 + `TX_MUTEX`/`TX_SEMAPHORE`/`TX_QUEUE`/`TX_BYTE_POOL`
- 验证 DWARF 自动恢复：`TX_THREAD`（含 `tx_thread_name` char*、`tx_thread_state`、`tx_thread_priority`、`tx_thread_stack_ptr`）、`TX_MUTEX`（`tx_mutex_owner` 指针）、`TX_SEMAPHORE`（`tx_semaphore_count`）、`TX_QUEUE`
- 10 个测试：current_thread_resolvable / created_thread_count_is_4 / thread_priorities / mutex_owner / semaphore_count / queue_structure / 裸机数据完整等
- 兼容现有 `plugins/rtos/threadx/threadx_6p5.py`

## 分阶段执行

### Phase 0 — 工具链安装（15 分钟）
`brew install aarch64-elf-gcc riscv64-elf-gcc`，验证版本 16.1.0。

### Phase 1 — 解析器修复 + tests/ 重构（1-2 小时）
1. 应用 Section A 修复到 `core/elf_parser.py` + `core/dump_reader.py`
2. 加 `tests/unit/test_elf_parser_universality.py`（合成 8 字节指针测试）
3. 重构目录：`firmware/common/` → `firmware/_common/`；`firmware/qemu_real/` → `firmware/qemu_m4_bare/`；移动 `tests/test_*.py` 到平行子目录；加 `__init__.py`
4. 拆分 `test_firmware_real.yaml` → `bss_simulated.yaml` + `qemu_m4_bare.yaml`
5. 更新所有路径引用
6. **验证**：`python -m unittest discover -s tests -p 'test_*.py'` 全部通过（含新 universality 测试）

### Phase 2 — 共享基础设施（1-2 小时）
1. 创建 `firmware/_common/qemu_runner.py`（含多区域支持）
2. 创建 `firmware/_common/show_parsed_base.py`
3. 创建 `firmware/_common/build_helpers.py`
4. 重构 `qemu_m4_bare/run_qemu.py` + `show_parsed.py` + `bss_simulated/show_bss_parsed.py` 用基类
5. **验证**：`run_qemu.py` 重新生成 dump 字节一致；M4 测试通过

### Phase 3 — 3 个裸机新架构（3-4 小时，可并行）
顺序：**R52 → AArch64 → RISC-V**
- R52 是 M4 最小 delta（同 arm-none-eabi-gcc，同 Thumb-2）
- AArch64 早做以验证 Section A 修复
- RISC-V 最后（需多区域 dump）
每场景：startup.S + linker.ld + main.c + profile YAML + run_qemu.py + show_parsed.py + 10 测试。
**验证**：每场景 10 测试通过；show_parsed 输出可识别的 assert_info/test_point/trace_buffer。

### Phase 4 — FreeRTOS on M4（4-6 小时）
1. git clone FreeRTOS-Kernel V11.3.0
2. 写 `FreeRTOSConfig.h` / `startup.S` / `linker.ld` / `main.c`
3. 编译：main.c + tasks.c + queue.c + list.c + timers.c + event_groups.c + stream_buffer.c + portable/GCC/ARM_CM4F/port.c + portable/MemMang/heap_4.c
4. 运行 QEMU 生成 dump
5. 写 show_parsed.py + 10 测试
6. 验证 freertos 插件可用
**验证**：10 测试通过；show_parsed 列出 4 任务带正确名/优先级。

### Phase 5 — ThreadX on M4（4-6 小时）
1. git clone eclipse-threadx/threadx
2. 写 `tx_user.h` / `startup.S` / `linker.ld` / `main.c`
3. 编译：main.c + rtos/common/src/*.c（选择性）+ rtos/ports/cortex-m4/gnu/src/*.c + .s
4. 运行 QEMU 生成 dump
5. 写 show_parsed.py + 10 测试
6. 验证 threadx_6p5 插件可用
**验证**：10 测试通过；show_parsed 通过 created-thread 链表列出 4 线程。

### Phase 6 — 端到端回归 + 清理（1 小时）
1. `python -m unittest discover -s tests -p 'test_*.py'` — 全部 70+ 测试通过
2. 每场景 show_parsed.py 人工检查
3. 确认 `main.py --profile test/qemu_m4_freertos --elf ... --dump ...` 端到端工作（加载 RTOS 插件打印任务列表）

## 风险与决策

1. **AArch64 boot**：用 `-kernel elf.elf`（QEMU 加载 ELF 到 VMA 并跳转入口），避免 boot ROM/DTB。CFLAGS 加 `-fno-pic -fno-pie -mno-red-zone`。
2. **RISC-V boot**：`sifive_e` 用 `-device loader,file=elf.elf`（遵循 VMA），mask ROM 跳到 0x20000000。失败则回退 `virt` + `-bios elf.elf`。Profile 驱动让切换无代码改动。
3. **RISC-V rodata 在 flash**：多区域 profile + 多区域 pmemsave（`qemu_runner.py` 扩展 `run_and_dump_multi_region`），`DumpReader` 已支持多区域拼接。
4. **RTOS 测试时序 flaky**：断言结构性属性（指针非空、名字在预期集合、优先级匹配创建顺序、count 在合法范围），不断言精确动态状态。
5. **DWARF typedef 匿名结构**：`TX_THREAD`/`TCB_t` 等通过 typedef 命名，`_build_type_cache` L121 已处理。`parse_struct_auto` 用 `_var_type_cache` 走变量声明类型，更可靠。
6. **profile schema 演进**：`qemu:` 块可选，仅 `test/qemu_*.yaml` 有。其他 profile（nxp/unisoc）不受影响。
7. **现有 test_firmware_real.yaml 引用**：Phase 1 先拆分并更新引用，再删旧文件，避免测试中途断裂。
8. **FreeRTOS 版本插件匹配**：如 `freertos_11p0.py` 不兼容 V11.3.0，加 `freertos_11p3.py`（TCB 布局 11.0→11.3 未变，轻拷贝改版本号）。

## 验证总览

| Phase | 验证命令 | 期望 |
|---|---|---|
| 1 | `python -m unittest discover -s tests -p 'test_*.py'` | 现有 + universality 测试通过 |
| 2 | `python3 firmware/qemu_m4_bare/run_qemu.py && python3 firmware/qemu_m4_bare/show_parsed.py` | dump 字节一致，解析正常 |
| 3 | 每场景 `python -m unittest tests.qemu_<scenario>.test_qemu_<scenario>` | 10 测试通过 |
| 4 | `python -m unittest tests.qemu_m4_freertos.test_qemu_m4_freertos` | 10 测试通过 |
| 5 | `python -m unittest tests.qemu_m4_threadx.test_qemu_m4_threadx` | 10 测试通过 |
| 6 | `python -m unittest discover -s tests -p 'test_*.py'` | 70+ 测试全部通过 |

## 范围说明

总工作量约 14-20 小时，跨多个会话。每 Phase 自包含可验证，可分批执行：建议至少先做 Phase 0-3（工具链+解析器+3 裸机架构），后续再补 Phase 4-5（RTOS）。用户可按需在任一 Phase 后暂停。
