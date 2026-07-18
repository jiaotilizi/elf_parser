# 续作计划：多架构 QEMU 并行测试场景（Phase 1.4 修复 + Phase 2-6）

## Context

本计划承接已批准的 [multi_arch_qemu_scenarios.md](file:///Users/yangtao/Documents/.trae/documents/multi_arch_qemu_scenarios.md)，处理因上下文中断而遗留的 Phase 1.4 半完成状态，并继续推进 Phase 2-6。原计划定义了 7 个平行 QEMU 测试场景（3 M4 变体 + R52 + AArch64 + RISC-V + BSS 模拟），目标是验证离线解析器对**多架构（含 64 位指针）**和 **RTOS 任务/同步原语**的解析泛用性。

## 已完成进度

| Phase | 子项 | 状态 | 证据 |
|---|---|---|---|
| 0 | 工具链安装 | ✅ | `arm-none-eabi-gcc 16.1.0`、`aarch64-elf-gcc 16.1.0`、`riscv64-elf-gcc 16.1.0` 均已安装 |
| 1.1 | 解析器 64 位指针修复 | ✅ | [core/elf_parser.py](file:///Users/yangtao/Documents/core/elf_parser.py) 指针分支已按 `byte_size` 选 4/8 字节；[core/dump_reader.py](file:///Users/yangtao/Documents/core/dump_reader.py#L117-L124) 新增 `read_pointer_by_size` |
| 1.3 | 目录重构 | ✅ | `firmware/_common/`、`firmware/qemu_m4_bare/`、`firmware/bss_simulated/`、`tests/{unit,bss_simulated,qemu_m4_bare,qemu_m4_freertos,qemu_m4_threadx,qemu_r52_bare,qemu_aarch64_bare,qemu_riscv_bare}/` 均已建立（含 `__init__.py`） |
| 1.4 | profile 拆分 + 路径更新 | ⚠️ 半完成 | YAML 已创建但 `qemu_m4_bare.yaml` 被截断；6 个文件路径/profile 名未更新；旧 `test_firmware_real.yaml` 未删 |
| 1.2 | universality 合成测试 | ❌ 未做 | `tests/unit/test_elf_parser_universality.py` 不存在 |
| 1.5 | 现有测试验证 | ❌ 未验证 | 当前 36 测试中 20 个 skip（路径错） |
| 2-6 | 后续所有阶段 | ❌ 未开始 | — |

当前测试输出：`Ran 36 tests in 0.014s — OK (skipped=20)`。20 个 skip 全部因路径/profile 名错误导致找不到 ELF/dump 文件。

## Phase 1.4 修复清单（必须先做，解锁后续）

### 1.4.1 修复截断的 `profiles/test/qemu_m4_bare.yaml`

当前文件结尾停在 `ram_size:`，需补全为：

```yaml
chip:
  name: qemu_m4_bare
  vendor: qemu
  description: QEMU mps2-an386 Cortex-M4 bare-metal
  arch: armv7e-m
  cpu: cortex-m4
  bits: 32
os:
  name: baremetal
  version: none
  description: Bare-metal firmware on QEMU
qemu:
  binary: qemu-system-arm
  machine: mps2-an386
  cpu: cortex-m4
  kernel_arg: -kernel
  ram_base: 0x20000000
  ram_size: 4096
  run_seconds: 2.0
memory:
- name: ram
  start_addr: 536870912
  size: 4096
modules:
- assert_info
- test_point
```

`536870912 = 0x20000000`。

### 1.4.2 修复 `tests/qemu_m4_bare/test_qemu_m4_bare.py`

三处修改：
- **L26**：`'firmware', 'qemu_real', ...` → `'firmware', 'qemu_m4_bare', ...`
- **L27**：同上
- **L38**：`load_profile('test/test_firmware_real')` → `load_profile('test/qemu_m4_bare')`

### 1.4.3 修复 `tests/bss_simulated/test_bss_firmware.py`

两处修改：
- **L20**：路径缺一级 `..`，应改为 `os.path.join(os.path.dirname(__file__), '..', '..', 'firmware', 'bss_simulated', 'test_firmware_bss.elf')`
- **L21**：同上
- **L27**：`load_profile('test/test_firmware_real')` → `load_profile('test/bss_simulated')`

### 1.4.4 修复 `firmware/qemu_m4_bare/run_qemu_dump.py`

- **L23**：`os.path.join(BASE_DIR, 'qemu_real', ...)` → `os.path.join(BASE_DIR, 'qemu_m4_bare', ...)`
- **L24**：同上

### 1.4.5 修复 `firmware/qemu_m4_bare/show_qemu_parsed.py`

- **L12-13**：`'firmware', 'qemu_real', ...` → `'firmware', 'qemu_m4_bare', ...`
- **L30**：`load_profile('test/test_firmware_real')` → `load_profile('test/qemu_m4_bare')`

### 1.4.6 修复 `firmware/bss_simulated/show_bss_parsed.py`

- **L13-14**：`BASE_DIR` 当前是 `dirname(dirname(dirname(__file__)))` = `firmware/`，但 `ELF_PATH` 拼成 `firmware/firmware/bss_simulated/...`（多了一级）。应改为 `BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`（上两级到 `Documents/`），然后 `ELF_PATH = os.path.join(BASE_DIR, 'firmware', 'bss_simulated', ...)`
- **L24**：profile 名 → `test/bss_simulated`

### 1.4.7 修复 `firmware/bss_simulated/generate_bss_dump.py`

- **L17-19**：`BASE_DIR = dirname(abspath(__file__))` 已是 `firmware/bss_simulated/`，`ELF_PATH`/`DUMP_PATH` 用 `os.path.join(BASE_DIR, 'test_firmware_bss.elf')` 正确。**实际无需改**，但需验证 `BASE_DIR` 没有被误改成多一级。

### 1.4.8 修复 `tests/unit/test_core.py`（可选但推荐）

- **L7**：`sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))` 当前添加 `tests/`，但 `core` 在 `Documents/`。改为 `os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))` 加 `Documents/`。当前通过 `python3 -m unittest discover -s tests` 运行时 cwd 已在 sys.path 故未暴露，但直接运行单文件会失败。

### 1.4.9 删除旧 profile

- 删除 `profiles/test/test_firmware_real.yaml`（确认无其他文件引用后）

## Phase 1.2 — 创建 universality 合成测试

新建 `tests/unit/test_elf_parser_universality.py`，**不依赖 QEMU**：

构造一个合成的 ELF + dump 组合，专门验证 64 位指针解析路径：
- 用 `tempfile` 构造一个含 8 字节指针的合成 dump（在偏移 0 写 `0x00000000deadbeef`）
- 通过 mock 或合成 DWARF 类型信息调用 `_read_typed_value` 的 pointer 分支
- 断言返回 `'<ptr 0x00000000deadbeef>'`（16 hex 宽，证明未截断）

或更实用的方式：构造一个最小 ELF（用 `aarch64-elf-gcc` 编译一个含 `char* ptr;` 的小程序），加上对应 dump，断言 `parse_struct_auto` 返回 `<ptr 0x...>` 且宽度为 16。这能在无 QEMU 环境下验证 Section A 修复。**优选**：在 Phase 3.2 AArch64 场景中专门加 `test_pointer_size_is_8`，universality 测试用合成 dump + mock DIE 即可，避免依赖外部工具链。

具体合成测试方案（无外部依赖）：
```python
# 用 unittest.mock 构造 type_info 字典，直接调用 ELFParser._read_typed_value
from unittest.mock import MagicMock
parser = ELFParser.__new__(ELFParser)  # 跳过 __init__
parser._address_size = 8
# 写 8 字节到临时 dump
dump_data = (0xdeadbeef).to_bytes(8, 'little')
# type_info 模拟 8 字节 pointer
type_info = {'kind': 'pointer', 'byte_size': 8, 'name': None, 'ref_type': {'kind': 'base', 'name': 'long'}}
result = parser._read_typed_value(addr=0x0, type_info=type_info, dump_reader=mock_reader)
assert result == '<ptr 0x00000000deadbeef>'
```

3-5 个测试用例：
- 32 位指针返回 8 hex 宽
- 64 位指针返回 16 hex 宽
- 64 位 char* 自动解引用为字符串
- 0 值指针返回 `'<ptr 0x00000000>'` 而非 None
- 异常 byte_size（如 2）走 fallback 路径不崩

## Phase 1.5 — 验证

```bash
cd /Users/yangtao/Documents
python3 -m unittest discover -s tests -p 'test_*.py'
```
期望：所有测试通过（无 skip，或仅 skip 因 QEMU 未装的环境性问题），含新增 universality 测试。

## Phase 2 — 共享基础设施

详见原计划 [multi_arch_qemu_scenarios.md Phase 2](file:///Users/yangtao/Documents/.trae/documents/multi_arch_qemu_scenarios.md#phase-2--共享基础设施1-2-小时)。要点：

- **2.1** `firmware/_common/qemu_runner.py`：提取现有 `firmware/qemu_m4_bare/run_qemu_dump.py` 的 `QMPConnection` 类为参数化 `QemuRunner`。支持 `run_and_dump()`（单区域）和 `run_and_dump_multi_region(regions)`（RISC-V 多区域 pmemsave 拼接）。`runner_from_profile(profile_name, scenario_dir)` 从 YAML `qemu:` 块构造。
- **2.2** `firmware/_common/show_parsed_base.py`：`ShowParsedBase` 基类提供 banner/scalar/struct_array 渲染。`firmware/_common/build_helpers.py`：编译/链接辅助。
- **2.3** 重构 `qemu_m4_bare/run_qemu_dump.py` + `show_qemu_parsed.py` 用基类（变 ~10 行 shim）；验证重新生成的 dump 与现有 `test_dump_qemu.bin` 字节一致。

## Phase 3 — 3 个裸机新架构

详见原计划 [Phase 3](file:///Users/yangtao/Documents/.trae/documents/multi_arch_qemu_scenarios.md#phase-3--3-个裸机新架构3-4-小时可并行)。每场景含：`startup.S` / `linker.ld` / `main.c`（薄包装 `#include "../_common/test_firmware_bss.c"`）/ `profile YAML` / `run_qemu.py` / `show_parsed.py` / 10 测试。

| 场景 | QEMU 机器/CPU | RAM 基址 | Flash | 工具链 | 启动特点 |
|---|---|---|---|---|---|
| qemu_r52_bare | `mps3-an536`/`cortex-r52` | 0x20000000 | 无 | `arm-none-eabi-gcc -mcpu=cortex-r52 -mthumb` | R-profile 无向量表，`_start` 设 SP → 清 .bss → 调 main |
| qemu_aarch64_bare | `virt`/`cortex-a53` | 0x40000000 | 无 | `aarch64-elf-gcc -march=armv8-a -mcpu=cortex-a53 -fno-pic -mno-red-zone` | **验证 64 位指针修复** |
| qemu_riscv_bare | `sifive_e`/`sifive-e31` | 0x80000000 | 0x20000000 | `riscv64-elf-gcc -march=rv32imac_zicsr -mabi=ilp32` | **需多区域 dump**（rodata 在 flash） |

执行顺序：R52 → AArch64 → RISC-V。

每场景 10 测试：elf_exists / elf_header（class+machine+entry 范围）/ bss_in_ram / scalar_values / assert_info_expansion / record_details / test_point_expansion / trace_buffer_expansion / char_pointer_deref / auto_vs_manual_read。AArch64 额外加 `test_pointer_size_is_8`。

## Phase 4 — FreeRTOS on M4

详见原计划 [Phase 4](file:///Users/yangtao/Documents/.trae/documents/multi_arch_qemu_scenarios.md#phase-4--freertos-on-m44-6-小时)。
- `git clone --depth 1 --branch V11.3.0 https://github.com/FreeRTOS/FreeRTOS-Kernel.git firmware/qemu_m4_freertos/rtos`
- 复用 `rtos/portable/GCC/ARM_CM4F/port.c`，写 `FreeRTOSConfig.h` + `startup.S`（PendSV/SVC/SysTick 别名到 `vPort*Handler`）
- `main.c`：4 任务 + mutex + counting sem + queue + event group；run 2s 后 dump
- ram_size 64KB（覆盖 heap_4 + 任务栈）
- 验证 `TCB_t`（`pcTaskName`/`uxPriority`/`pxTopOfStack`）、`List_t`、`Queue_t` 自动恢复
- 10 测试断言**结构性属性**（非精确动态值，避免 flaky）
- 如 `plugins/rtos/freertos/freertos_11p0.py` 不兼容 V11.3.0，加 `freertos_11p3.py`

## Phase 5 — ThreadX on M4

详见原计划 [Phase 5](file:///Users/yangtao/Documents/.trae/documents/multi_arch_qemu_scenarios.md#phase-5--threadx-on-m44-6-小时)。
- `git clone --depth 1 https://github.com/eclipse-threadx/threadx.git firmware/qemu_m4_threadx/rtos`
- 复用 `rtos/ports/cortex-m4/gnu/`
- 写 `tx_user.h` + `startup.S`（PendSV→`__tx_PendSVHandler`）
- 验证 `TX_THREAD`（`tx_thread_name` char*/`tx_thread_state`/`tx_thread_priority`）、`TX_MUTEX`/`TX_SEMAPHORE`/`TX_QUEUE` 自动恢复
- 兼容 `plugins/rtos/threadx/threadx_6p5.py`

## Phase 6 — 端到端回归

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```
期望 70+ 测试全通过。每场景 `show_parsed.py` 人工检查。`main.py --profile test/qemu_m4_freertos --elf ... --dump ...` 端到端加载 RTOS 插件打印任务列表。

## 执行策略

1. **先做 Phase 1.4 修复 + 1.2 universality + 1.5 验证**（约 30 分钟，解锁基线）
2. **再做 Phase 2 共享基础设施**（约 1-2 小时，为后续场景铺路）
3. **Phase 3 三个裸机架构**（约 3-4 小时，可并行尝试但顺序执行更稳）
4. **Phase 4 + 5 RTOS**（各 4-6 小时，最复杂）
5. **Phase 6 回归**（约 1 小时）

每 Phase 完成后立即运行测试验证，可分批暂停。

## 假设与决策

1. **不重写原计划**：本续作计划只补充 Phase 1.4 修复细节和 Phase 1.2 实现方案，其他细节沿用原计划。
2. **路径层级修复用 `os.path.dirname` 链**：保持现有风格不引入 `pathlib`。
3. **universality 测试用 mock**：避免依赖 aarch64 工具链，让单测可在任意环境运行。
4. **先修后建**：Phase 1.4 修复完成 + 1.5 验证通过后，才进入 Phase 2，避免在破损基线上叠新代码。
5. **保留 `qemu:` 块为可选**：仅 `test/qemu_*.yaml` 有，nxp/unisoc profile 不受影响。
6. **删除 `test_firmware_real.yaml` 时机**：Phase 1.4 所有引用更新完毕后，删除前最后一步。
