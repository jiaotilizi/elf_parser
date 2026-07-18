# ELF Parser - RTOS Runtime Analysis Tool

## Overview

ELF Parser is a Python-based tool for analyzing embedded firmware by parsing ELF files and memory dumps. It extracts RTOS runtime information (tasks, queues, timers, mutexes, semaphores, events) and provides multiple display schemes for visualizing the results.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Main Entry                                    │
│                        main.py / test_simple.py                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ Profile Loader  │         │  ELF Parser     │         │  Dump Reader    │
│ (profile_loader)│         │  (elf_parser)   │         │  (dump_reader)  │
│                 │         │                 │         │                 │
│  Load YAML      │         │  Parse ELF/DWARF│         │  Read memory    │
│  Configuration  │         │  Symbol lookup  │         │  from dump.bin  │
│                 │         │  Type analysis  │         │                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
          │                           │                           │
          └───────────────────────────┼───────────────────────────┘
                                      ▼
                            ┌─────────────────┐
                            │ Plugin Manager  │
                            │ (plugin_manager)│
                            │                 │
                            │  Load RTOS      │
                            │  Plugins        │
                            └─────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  RTOS Plugin    │         │  RTOS Plugin    │         │  Module Plugin  │
│  (ThreadX)      │         │  (FreeRTOS)     │         │  (Test Point)   │
│                 │         │                 │         │                 │
│  Parse Tasks    │         │  Parse Tasks    │         │  Parse TP       │
│  Mutex/Sem/Q    │         │  Queue/Mutex    │         │  Data           │
│  Events/Timers  │         │  Sem/Timer      │         │                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
                                      │
                                      ▼
                            ┌─────────────────┐
                            │   Data Adapter  │
                            │ (data_adapter)  │
                            │                 │
                            │  Normalize data │
                            │  Provide        │
                            │  Resource API   │
                            └─────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  CLI Basic      │         │ CLI Interactive │         │    Web GUI      │
│  (cli_basic)    │         │ (cli_interactive)│         │   (web_gui)     │
│                 │         │                 │         │                 │
│  Text output    │         │  Interactive    │         │  HTTP Server    │
│  JSON format    │         │  Navigation     │         │  Browser UI     │
│                 │         │  Tab panels     │         │                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
```

## Directory Structure

| Directory | Purpose |
|-----------|---------|
| `core/` | Core components (ELF parsing, dump reading, plugin management, profile loading) |
| `plugins/` | RTOS and module plugins (ThreadX, FreeRTOS, test_point, assert_info) |
| `display/` | Display schemes (CLI basic, CLI interactive, Web GUI) |
| `profiles/` | Target configuration files (chip, OS, memory regions, QEMU settings) |
| `tests/qemu_m4_threadx/` | Cortex-M4 ThreadX QEMU test scenario |
| `tests/qemu_m4_freertos/` | Cortex-M4 FreeRTOS QEMU test scenario |
| `tests/qemu_r52_threadx/` | Cortex-R52 ThreadX QEMU test scenario (ARMv8-R) |
| `tests/qemu_r52_freertos/` | Cortex-R52 FreeRTOS QEMU test scenario (ARMv8-R) |
| `tests/qemu_r52_bare/` | Cortex-R52 bare-metal QEMU test scenario |
| `tests/qemu_riscv_bare/` | RISC-V bare-metal QEMU test scenario |
| `tests/qemu_aarch64_bare/` | AArch64 bare-metal QEMU test scenario |
| `tests/unit/` | Unit tests for core modules |
| `tests/_common/` | Shared test utilities (QEMU runner, show_parsed_base) |
| `rtos/` | RTOS source code submodules (ThreadX, FreeRTOS) - **DO NOT MODIFY** |

## Installation

```bash
cd elf_parser
pip install -r requirements.txt
```

### Dependencies

| Package | Version | Description |
|---------|---------|-------------|
| Python | >=3.8 | Minimum Python version |
| pyelftools | >=0.28 | ELF/DWARF parsing |
| pyyaml | >=6.0 | YAML profile loading |
| flask | >=2.0 | Web GUI server (optional) |

## Usage

### Basic Usage

```bash
python3 main.py --elf firmware.elf --dump dump.bin --profile profiles/test/qemu_m4_threadx.yaml
```

### Command Line Options

```
--elf        Path to ELF file (required)
--dump       Path to memory dump file (required)
--profile    Path to profile YAML file (required)
--display    Display scheme: cli_basic, cli_interactive, web_gui (default: cli_interactive)
```

### Example Output

```
🧵 [Tasks]
--------------------------------------------------------------------------------
Name             | State           | Priority        | Stack Size      | Stack Used      
--------------------------------------------------------------------------------
tx_timer_thread  | TX_READY        | 0               | 0x00000400      | 0x00000080      
app_thread_0     | TX_DELAY        | 1               | 0x00000800      | 0x00000120      
```

## Profile Configuration

Profile YAML structure:

```yaml
chip:
  name: qemu_m4_threadx
  vendor: qemu
  arch: armv7e-m
  cpu: cortex-m4
  bits: 32

os:
  name: threadx
  version: v6p5p1

memory:
- name: flash
  start_addr: 0x08000000
  size: 262144
  offset_in_dump: 0
- name: ram
  start_addr: 0x20000000
  size: 65536
  offset_in_dump: 262144

display:
  scheme: cli_interactive
  options:
    show_hex: true
    max_rows: 50
```

### Memory Regions

The `memory` section supports multiple regions with:
- `name`: Region identifier
- `start_addr`: Virtual address start
- `size`: Region size in bytes
- `offset_in_dump`: Offset in dump file where this region starts

## Testing

### Run QEMU Test Scenarios

```bash
# ThreadX test (Cortex-M4)
cd tests/qemu_m4_threadx/firmware
bash build.sh
python3 run_qemu.py

# FreeRTOS test (Cortex-M4)
cd tests/qemu_m4_freertos/firmware
bash build.sh
python3 run_qemu.py

# ThreadX test (Cortex-R52)
cd tests/qemu_r52_threadx/firmware
bash build.sh
python3 run_qemu.py

# FreeRTOS test (Cortex-R52)
cd tests/qemu_r52_freertos/firmware
bash build.sh
python3 run_qemu.py

# Run parser tests
cd tests/qemu_r52_threadx
python3 test_qemu_r52_threadx.py

# Run all tests
cd /path/to/elf_parser
python3 -m unittest discover -s tests -p "test_*.py"
```

### Manual Testing

```bash
# Generate dump from QEMU
qemu-system-arm -machine mps2-an386 -cpu cortex-m4 -kernel firmware.axf \
  -d guest_errors -semihosting -monitor telnet:127.0.0.1:5555,server,nowait \
  -serial file:output.log

# Parse the dump
python3 main.py --elf firmware.axf --dump ram_dump.bin --profile profiles/test/qemu_m4_threadx.yaml
```

## Version Management

### Build Information API

The ELF parser can extract and display build information:

```python
from core.elf_parser import ELFParser

parser = ELFParser('firmware.elf')
parser.print_build_info()
```

Output:
```
========================================
ELF Build Information
========================================
ELF Path: firmware.elf
Architecture: 32-bit
DWARF Version: DWARF4
Compiler: GCC
Compiler Version: 10.3.1
Producer: arm-none-eabi-gcc (15:10.3-2021.07-4) 10.3.1 20210621 (release)
========================================
```

## RTOS Plugin Development

### Adding a New RTOS Plugin

1. Create `plugins/rtos/<rtos_name>/<version>.py`
2. Implement `OSPlugin` interface with:
   - `os_name`: RTOS name
   - `os_version`: RTOS version
   - `execute(context)`: Return dict with resource lists (tasks, mutexes, etc.)
   - `get_detail(resource_type, address)`: Return detailed info

### Data Contract

Plugins should return data in this format:

```python
{
    'tasks': [
        {'name': 'task1', 'address': 0x20001000, 'state': 'READY', 'priority': 1}
    ],
    'mutexes': [...],
    'semaphores': [...],
    'queues': [...],
    'events': [...],
    'timers': [...],
}
```

## Display Scheme Development

### Adding a New Display

1. Create `display/<name>.py`
2. Implement `DisplayBase` interface with:
   - `show_resource(resource_type, data, metadata)`: Render resource list
   - `show_detail(resource_type, address)`: Render detailed view
   - `run()`: Start display

## Code Iteration Guidelines

1. **Architecture**: Follow existing plugin-based architecture
2. **Submodules**: DO NOT modify files in `rtos/` directory
3. **Testing**: Add test cases in `tests/` directory
4. **Documentation**: Update this README for each major change
5. **Dependencies**: Update `requirements.txt` when adding new packages
6. **Backward Compatibility**: Maintain backward compatibility with existing profiles

## Known Limitations

- Supports ARM Cortex-M (32-bit) and Cortex-R (32-bit, including R52) targets
- Supports ThreadX and FreeRTOS plugins
- DWARF parsing optimized for GCC-compiled firmware
- Cortex-R52 requires Hyp-to-SVC mode transition in startup code (QEMU boots in Hyp mode)

## License

See LICENSE file for details.

---

## Changelog

### v0.2.0 - 2026-07-19

**Cortex-R52 跨架构泛用性验证**

1. **Cortex-R52 ThreadX 测试场景**
   - 创建 `tests/qemu_r52_threadx/` 测试目录，使用 ThreadX Cortex-R5 端口
   - 解决 QEMU Cortex-R52 在 Hyp 模式启动导致 `MSR CPSR` 崩溃的问题
   - 在 `startup.S` 中添加 Hyp 模式检测和 `ERET` 切换到 SVC 模式的代码
   - 修正 `tx_initialize_low_level.S` 中 `_sp` 符号引用和堆栈检查
   - 调整链接脚本：RAM 起始地址 0x20000000，4MB 空间，32KB 栈
   - 创建测试用例 `test_qemu_r52_threadx.py`，10 个测试全部通过

2. **Cortex-R52 FreeRTOS 测试场景**
   - 完善 `tests/qemu_r52_freertos/` 测试目录
   - 使用 FreeRTOS Cortex-R5 端口（`ARM_CR5`）
   - 修正 `pxCurrentTCB` 解析：使用 `read_uint32` 直接读取指针，而非 `parse_struct_auto`
   - 修正 `TCB_t` / `QueueDefinition` 结构体 kind 检查：同时接受 `struct` 和 `typedef`
   - 创建测试用例 `test_qemu_r52_freertos.py`，9 个测试全部通过

3. **测试用例修复与完善**
   - 修复 `qemu_m4_threadx` 测试用例：使用 `ProfileLoader` + `memory_regions` 替代过时的 `base_address` 参数
   - 更新所有 ThreadX 测试用例：使用 `get_struct_type` 替代不存在的 `has_type`
   - 所有 113 个测试用例通过（61 个因缺少固件跳过，0 个失败）

4. **关键发现：QEMU Cortex-R52 Hyp 模式**
   - QEMU 在 `mps3-an536` 机器上启动 Cortex-R52 时，CPU 默认处于 Hyp 模式（CPSR = 0x600001DA，模式位 = 0x1A）
   - 在 Hyp 模式下执行 `MSR CPSR` 或 `CPS` 指令会触发异常，导致 CPU 进入未定义状态
   - 解决方法：在启动代码中检测 CPSR 模式位，若为 Hyp 模式则使用 `ERET` 指令切换到 SVC 模式
   - 此发现对其他 ARMv8-R 架构的移植工作有重要参考价值

**文件修改**

- [tests/qemu_r52_threadx/firmware/startup.S](file:///Users/yangtao/Documents/elf_parser/tests/qemu_r52_threadx/firmware/startup.S) - 添加 Hyp 模式切换
- [tests/qemu_r52_threadx/firmware/linker.ld](file:///Users/yangtao/Documents/elf_parser/tests/qemu_r52_threadx/firmware/linker.ld) - 内存布局调整
- [tests/qemu_r52_threadx/firmware/sample_threadx.c](file:///Users/yangtao/Documents/elf_parser/tests/qemu_r52_threadx/firmware/sample_threadx.c) - 调试变量
- [tests/qemu_r52_threadx/firmware/show_parsed.py](file:///Users/yangtao/Documents/elf_parser/tests/qemu_r52_threadx/firmware/show_parsed.py) - 显示脚本
- [tests/qemu_r52_threadx/test_qemu_r52_threadx.py](file:///Users/yangtao/Documents/elf_parser/tests/qemu_r52_threadx/test_qemu_r52_threadx.py) - 测试用例
- [tests/qemu_r52_freertos/test_qemu_r52_freertos.py](file:///Users/yangtao/Documents/elf_parser/tests/qemu_r52_freertos/test_qemu_r52_freertos.py) - 测试用例
- [tests/qemu_m4_threadx/test_qemu_m4_threadx.py](file:///Users/yangtao/Documents/elf_parser/tests/qemu_m4_threadx/test_qemu_m4_threadx.py) - API 兼容性修复
- [README.md](file:///Users/yangtao/Documents/elf_parser/README.md) - 文档更新

---

### v0.1.1 - 2026-07-19

**FreeRTOS插件修复**

1. **任务解析逻辑修复**
   - 修正 `List_t` 结构遍历方式：直接使用 List_t 大小而非指针数组
   - 修正 TCB 地址计算：从 ListItem_t 地址减去 `xStateListItem` 偏移
   - 修正任务名称读取：`pcTaskName` 是字符数组而非指针，直接从 TCB 读取
   - 添加无效任务过滤：优先级 >= 32、栈地址不在有效范围、名称含 `\xff` 的任务被过滤

2. **Profile配置修复**
   - 修正 `os.name` 为 `freertos`（而非 `freertos_v11p3p0`），与插件注册一致
   - 添加 `os.version` 字段
   - 修正内存区域配置，使用单一 RAM 区域

**线程同步操作增强**

1. **ThreadX测试固件**
   - 添加 thread 8/9，实现互斥锁优先级继承和队列通信
   - 添加 queue_1、semaphore_1、mutex_1（带优先级继承）、event_flags_1
   - 实现线程间复杂同步模式：事件标志触发、队列消息传递、互斥锁竞争

2. **FreeRTOS测试固件**
   - 添加 10 个任务，包含多种优先级（0-7）
   - 添加 2 个互斥锁（xMutex1/xMutex2）、2 个队列（xQueue1/xQueue2）
   - 添加二进制信号量（xBinarySem）和计数信号量（xCountSem）
   - 添加 2 个事件组（xEventGrp1/xEventGrp2）和 2 个定时器（xTimer1/xTimer2）
   - 实现复杂同步模式：互斥锁竞争、信号量同步、事件组等待、定时器触发

**测试用例完善**

1. **单元测试**
   - `test_core.py`: 17 个测试用例全部通过
   - `test_elf_parser_universality.py`: 8 个测试用例全部通过

2. **QEMU测试场景**
   - ThreadX: 成功解析 8 个线程、2 个信号量、2 个互斥锁、2 个队列、2 个事件标志、2 个定时器
   - FreeRTOS: 成功解析 12 个任务（IDLE、TimerT、Recv、Event1、Mutex1、Mutex2、Sem1、Sender、Event2、HighPri、Sem2、Tmr Svc）

**文件修改**

- [plugins/rtos/freertos/freertos_v11p3p0.py](file:///Users/yangtao/Documents/elf_parser/plugins/rtos/freertos/freertos_v11p3p0.py) - 修复任务解析逻辑
- [profiles/test/qemu_m4_freertos.yaml](file:///Users/yangtao/Documents/elf_parser/profiles/test/qemu_m4_freertos.yaml) - 修复OS配置
- [profiles/test/qemu_m4_threadx.yaml](file:///Users/yangtao/Documents/elf_parser/profiles/test/qemu_m4_threadx.yaml) - 修复内存区域配置
- [tests/qemu_m4_freertos/firmware/main.c](file:///Users/yangtao/Documents/elf_parser/tests/qemu_m4_freertos/firmware/main.c) - 丰富线程同步操作
- [tests/qemu_m4_freertos/firmware/FreeRTOSConfig.h](file:///Users/yangtao/Documents/elf_parser/tests/qemu_m4_freertos/firmware/FreeRTOSConfig.h) - 增加最大优先级数
- [tests/qemu_m4_threadx/firmware/sample_threadx.c](file:///Users/yangtao/Documents/elf_parser/tests/qemu_m4_threadx/firmware/sample_threadx.c) - 丰富线程同步操作
- [test_simple.py](file:///Users/yangtao/Documents/elf_parser/test_simple.py) - 修复 `is_32bit()` 调用

---

### v0.1.0 - 2026-07-19

**核心改进**

1. **CU/DIE递归处理优化**
   - 使用 `visited-set` 替代硬编码深度限制，避免结构体自引用导致的无限递归
   - 保留递归深度超过20层时的 debug 打印，方便排查深层嵌套问题

2. **CU/DIE性能优化**
   - 确认 `_cu_cache` 在初始化时构建一次，按 `low_pc` 排序
   - 添加 `_find_cu_by_address` 方法，使用 `bisect` 二分查找定位 CU
   - 在 `_build_cu_index` 和 `_build_type_cache` 中添加计时日志

3. **ARMCC编译器支持**
   - 在 `_build_cu_index` 中检测 `DW_AT_high_pc` 的 form，如果是 `DW_FORM_data1/2/4/8`，将其视为相对 `low_pc` 的偏移量

4. **显示层解耦方案**
   - 定义 `ResourceMetadata` 通用数据契约，包含 `resource_type`、`label`、`icon`、`fields`
   - `DataAdapter` 提供 `get_all_resource_types()`、`get_resource_data()`、`get_resource_metadata()` 三个通用接口
   - 显示层（CLI/Web）通过 metadata 动态渲染，不依赖具体 RTOS 结构

5. **DWARF版本和编译器信息**
   - 在 `ELFParser` 中存储 `_dwarf_version`、`_compiler_name`、`_compiler_version`、`_producer_string`
   - 通过解析 `DW_AT_producer` 识别编译器（GCC/ARMCC/IAR）和版本号
   - 添加 `print_build_info()` 方法，可打印完整的构建信息

6. **多区域dump支持**
   - 在 `DumpReader` 中支持 `offset_in_dump` 字段
   - Profile 支持配置多个内存区域（flash、ram等），每个区域可独立设置在dump文件中的偏移

7. **依赖管理**
   - 创建 `requirements.txt`，明确依赖包版本要求
   - Python >= 3.8, pyelftools >= 0.28, pyyaml >= 6.0, flask >= 2.0

8. **文档完善**
   - 创建完整的 `README.md`，包含架构图、目录结构、使用方法、测试方法
   - 添加 RTOS 插件开发指南和 Display Scheme 开发指南
   - 制定代码迭代规范

9. **子模块代码约束**
   - 确认 `rtos/` 目录下的代码未被修改
   - 所有测试代码放在 `tests/` 目录下

**文件修改**

- [core/elf_parser.py](file:///Users/yangtao/Documents/elf_parser/core/elf_parser.py) - 递归visited-set、CU二分查找、ARMCC high_pc、编译器信息解析
- [core/dump_reader.py](file:///Users/yangtao/Documents/elf_parser/core/dump_reader.py) - 多区域dump支持（offset_in_dump）
- [display/base.py](file:///Users/yangtao/Documents/elf_parser/display/base.py) - 通用数据契约 ResourceMetadata
- [display/data_adapter.py](file:///Users/yangtao/Documents/elf_parser/display/data_adapter.py) - 通用资源API
- [display/cli_basic.py](file:///Users/yangtao/Documents/elf_parser/display/cli_basic.py) - 插件无关渲染器
- [display/cli_interactive.py](file:///Users/yangtao/Documents/elf_parser/display/cli_interactive.py) - 插件无关渲染器
- [display/web_gui.py](file:///Users/yangtao/Documents/elf_parser/display/web_gui.py) - 插件无关渲染器
- [requirements.txt](file:///Users/yangtao/Documents/elf_parser/requirements.txt) - 依赖声明
- [README.md](file:///Users/yangtao/Documents/elf_parser/README.md) - 完整文档

---

### v0.0.3 - 2026-07-18

**Bug修复**

1. **QEMU锁死问题**：修正 `startup.S` 中的向量表和链接脚本符号（`_estack`、`_sdata`）
2. **ELF解析超时**：通过编译 ThreadX 核心时不生成 debug 信息，将 DIE 数量从 10,047 减少到 373
3. **任务名显示为空**：任务名存储在 flash 而非 RAM，添加 `read_memory_from_elf` 方法读取 flash 数据
4. **定时器解析错误**：修正 `TX_TIMER` 结构体处理，使用内嵌的 `TX_TIMER_INTERNAL` 而非指针
5. **编译单元方法缺失**：修正 `_build_cu_index`，使用 `cu.get_top_DIE()` 替代不存在的 `cu.get_low_pc()`

**功能增强**

1. **线程状态映射**：添加 `THREAD_STATE_MAP`，将数字状态码转换为可读状态名（`TX_READY`、`TX_DELAY` 等）
2. **多任务测试固件**：生成包含 8 个线程、2 个定时器、mutex、semaphore、queue、event flags 的测试固件
3. **编译优化**：在 `build.sh` 中拆分 `CFLAGS_DEBUG`（应用代码）和 `CFLAGS_NODEBUG`（ThreadX核心）

**文件修改**

- [tests/qemu_m4_threadx/firmware/sample_threadx.c](file:///Users/yangtao/Documents/elf_parser/tests/qemu_m4_threadx/firmware/sample_threadx.c) - 添加定时器和更多任务
- [tests/qemu_m4_threadx/firmware/build.sh](file:///Users/yangtao/Documents/elf_parser/tests/qemu_m4_threadx/firmware/build.sh) - 拆分debug编译选项
- [plugins/rtos/threadx/threadx_v6p5p1.py](file:///Users/yangtao/Documents/elf_parser/plugins/rtos/threadx/threadx_v6p5p1.py) - 修正定时器解析、任务状态映射
- [core/elf_parser.py](file:///Users/yangtao/Documents/elf_parser/core/elf_parser.py) - 添加 read_memory_from_elf、修复CU解析

---

### v0.0.2 - 2026-07-18

**架构调整**

1. **插件化架构**：重构为插件模式，RTOS插件独立于核心解析器
2. **显示层抽象**：定义 `DisplayBase` 基类，支持多种显示方案（CLI/Web）
3. **Profile系统**：使用 YAML 文件配置目标芯片、OS、内存区域等参数

**核心功能**

1. **ELF/DWARF解析**：使用 pyelftools 解析 ELF 文件和 DWARF 调试信息
2. **符号表提取**：提取全局变量和函数符号，建立地址索引
3. **结构体解析**：递归解析结构体类型，支持嵌套结构体、数组、指针
4. **内存dump读取**：支持从二进制dump文件中读取内存数据
5. **ThreadX插件**：实现 ThreadX v6.5.1 和 v5.6.0 的任务、mutex、semaphore、queue、event、timer 解析
6. **FreeRTOS插件**：实现 FreeRTOS v11.3.0 的任务、queue、mutex、semaphore、timer 解析

**显示方案**

1. **CLI Basic**：基础文本输出，JSON格式显示
2. **CLI Interactive**：交互式CLI，支持导航和详情查看
3. **Web GUI**：基于 Flask 的 Web 界面，支持浏览器访问

---

### v0.0.1 - 2026-07-18

**初始版本**

1. 项目初始化，建立基础目录结构
2. 实现 ELF 文件解析基础框架
3. 实现 DWARF 调试信息解析基础功能
4. 实现内存 dump 文件读取功能
5. 添加 ThreadX 基础解析插件
6. 添加 QEMU 测试场景（Cortex-M4）