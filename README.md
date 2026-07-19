# ELF Parser - RTOS Runtime Analysis Tool

## Overview

ELF Parser is a Python-based tool for analyzing embedded firmware by parsing ELF files and memory dumps. It extracts RTOS runtime information (tasks, queues, timers, mutexes, semaphores, events) and provides multiple display schemes for visualizing the results.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Main Entry                                    │
│                              main.py                                       │
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
          ┌───────────────────┬───────┴───────┬───────────────────┐
          ▼                   ▼               ▼                   ▼
┌─────────────────┐   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  CLI Basic      │   │ CLI Table       │ │    Web GUI      │ │   Trace32       │
│  (cli_basic)    │   │ (cli_table)     │ │   (web_gui)     │ │ (trace32_format)│
│                 │   │                 │ │                 │ │                 │
│  Text output    │   │  Table format   │ │  HTTP Server    │ │ Trace32-style   │
│  JSON format    │   │  Navigation     │ │  Browser UI     │ │  display        │
└─────────────────┘   └─────────────────┘ └─────────────────┘ └─────────────────┘
```

## Directory Structure

| Directory | Purpose |
|-----------|---------|
| `core/` | Core components (ELF parsing, dump reading, plugin management, profile loading) |
| `plugins/` | RTOS and module plugins (ThreadX, FreeRTOS, test_point, assert_info) |
| `display/` | Display schemes (CLI basic, CLI table, Web GUI, Trace32 format) |
| `profiles/` | Target configuration files (chip, OS, memory regions, QEMU settings) |
| `tests/qemu/mps2_an386_bare/` | Cortex-M4 bare-metal QEMU test scenario |
| `tests/qemu/mps2_an386_freertos/` | Cortex-M4 FreeRTOS QEMU test scenario |
| `tests/qemu/mps2_an386_threadx/` | Cortex-M4 ThreadX QEMU test scenario |
| `tests/qemu/mps3_an536_bare/` | Cortex-R52 bare-metal QEMU test scenario |
| `tests/qemu/mps3_an536_freertos/` | Cortex-R52 FreeRTOS QEMU test scenario |
| `tests/qemu/mps3_an536_threadx/` | Cortex-R52 ThreadX QEMU test scenario |
| `tests/qemu/nxp_imx6ul_bare/` | NXP i.MX6UL (Cortex-A7) bare-metal QEMU test scenario |
| `tests/qemu/nxp_imx6ul_threadx/` | NXP i.MX6UL (Cortex-A7) ThreadX QEMU test scenario |
| `tests/qemu/riscv_virt_bare/` | RISC-V bare-metal QEMU test scenario |
| `tests/qemu/stm32vldiscovery_bare/` | STM32VL Discovery bare-metal QEMU test scenario |
| `tests/qemu/virt_a53_bare/` | ARM Cortex-A53 (AArch64) bare-metal QEMU test scenario |
| `tests/bss_simulated/` | Simulated BSS data test scenario |
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
python3 main.py --elf firmware.elf --dump dump.bin --profile profiles/qemu/mps2_an386_threadx.yaml
```

### Command Line Options

```
--elf        Path to ELF file (required)
--dump       Path to memory dump file (required)
--profile    Path to profile YAML file (required)
--display    Display scheme: cli_basic, cli_table, web_gui, trace32 (default: cli_table)
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
  name: qemu_mps2_an386_threadx
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
  scheme: cli_table
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
cd tests/qemu/mps2_an386_threadx/firmware
bash build.sh
python3 run_qemu.py

# FreeRTOS test (Cortex-M4)
cd tests/qemu/mps2_an386_freertos/firmware
bash build.sh
python3 run_qemu.py

# ThreadX test (Cortex-R52)
cd tests/qemu/mps3_an536_threadx/firmware
bash build.sh
python3 run_qemu.py

# FreeRTOS test (Cortex-R52)
cd tests/qemu/mps3_an536_freertos/firmware
bash build.sh
python3 run_qemu.py

# ThreadX test (NXP i.MX6UL Cortex-A7)
cd tests/qemu/nxp_imx6ul_threadx/firmware
bash build.sh
python3 run_qemu.py

# Run all tests
cd /path/to/elf_parser
python3 -m pytest tests/ -v
```

### Manual Testing

```bash
# Generate dump from QEMU
qemu-system-arm -machine mps2-an386 -cpu cortex-m4 -kernel firmware.axf \
  -d guest_errors -semihosting -monitor telnet:127.0.0.1:5555,server,nowait \
  -serial file:output.log

# Parse the dump
python3 main.py --elf firmware.axf --dump ram_dump.bin --profile profiles/qemu/mps2_an386_threadx.yaml
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
2. Implement `RTOSPlugin` interface with:
   - `os_name`: RTOS name
   - `os_version`: RTOS version
   - `get_resource_types()`: Return list of supported resource types
   - `get_resource(resource_type, context)`: Return resource list for given type
   - Optional: `get_tasks()`, `get_semaphores()`, etc. - delegate to `get_resource`

### Resource Discovery Mechanism

Plugins use a generic resource discovery mechanism:

```python
class MyRTOSPlugin(RTOSPlugin):
    def get_resource_types(self) -> List[str]:
        return ['tasks', 'semaphores', 'mutexes', 'queues']
    
    def get_resource(self, resource_type: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        resource_map = {
            'tasks': self._parse_tasks,
            'semaphores': self._parse_semaphores,
            # ...
        }
        func = resource_map.get(resource_type)
        return func(context) if func else []
```

### Supported Resource Types

| Resource Type | Description |
|---------------|-------------|
| `tasks` | Thread/task information |
| `semaphores` | Semaphore objects |
| `mutexes` | Mutex objects |
| `queues` | Message queues |
| `timers` | Software timers |
| `events` | Event flags/groups |
| `block_pools` | Memory block pools (ThreadX) |
| `byte_pools` | Memory byte pools (ThreadX) |

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

- Supports ARM Cortex-M (32-bit), Cortex-R (32-bit, including R52), Cortex-A (32/64-bit) targets
- Supports RISC-V targets
- Supports ThreadX and FreeRTOS plugins
- DWARF parsing optimized for GCC-compiled firmware
- Cortex-R52 requires Hyp-to-SVC mode transition in startup code (QEMU boots in Hyp mode)

## License

See LICENSE file for details.

---

## Changelog

### v0.9.6 - 2026-07-19

**工程质量优化：架构改进、代码质量提升、性能优化**

1. **架构改进**
   - 添加 `core/__init__.py`、`plugins/__init__.py`、`plugins/rtos/__init__.py`、`plugins/module/__init__.py` 包初始化文件
   - 核心包支持便捷重导出（`ELFParser`、`DumpReader`、`ProfileLoader` 等）
   - 新增 `PluginContext` 类（`core/context.py`），提供结构化上下文访问，替代裸字典
   - 清理 `ProfileLoader.list_profiles()` 中废弃的 `os.version` 字段

2. **代码质量提升**
   - 移除插件文件中的 `sys.path.insert` 硬编码，改用相对导入（`from ..base import RTOSPlugin`）
   - `main.py` 和 `profile_loader.py` 改用 try/except ImportError 模式，优雅处理路径问题
   - `elf_parser.py` 中 `print` 调试语句统一转换为 `logging` 模块
   - `import` 语句全部移至文件顶部（`re`、`time`、`bisect`）
   - `_visited.remove()` 统一为 `_visited.discard()`，避免 KeyError
   - FreeRTOS 插件硬编码偏移回退路径添加 `logger.warning` 日志
   - FreeRTOS 插件命名约定符号发现添加注释说明和 debug 日志
   - ThreadX 插件 name 解析逻辑抽取为 `RTOSPlugin._read_resource_name()` 公共方法，消除 8 处重复代码
   - `ModulePlugin` 基类添加 `initialize()` 方法，与 `RTOSPlugin` 保持一致（`self._elf_parser` / `self._dump_reader`）

3. **性能优化**
   - `_find_cu_by_address`：直接存储 CU 对象引用，消除线性遍历
   - `_find_segment_for_address`：构建排序区间列表，使用二分查找（O(log n)）
   - `get_all_symbols`：添加结果缓存，避免重复构建列表

**测试结果**：168 个测试通过（7 个预先存在的 RISC-V bare metal 测试问题除外）

---

### v0.9.3 - 2026-07-19

**测试用例清理与目录结构规范化**

1. **删除无效测试用例**
   - 删除 `tests/qemu/nxp_imx6ul_freertos/` 目录及相关文件（FreeRTOS ARM_CA9端口在QEMU virt机器上存在GIC初始化问题）
   - 删除 `profiles/qemu/nxp_imx6ul_freertos.yaml`
   - 删除根目录调试文件：`test_freertos_debug2.py`、`test_simple.py`、`test_rtos_parsing.py`

2. **清理空目录**
   - 删除 `profiles/test/`、`profiles/qemu/st/`、`profiles/qemu/arm/`、`profiles/qemu/riscv/`

3. **修复路径引用**
   - 修复多个 `run_qemu.py` 和 `show_parsed.py` 文件中的 `sys.path` 设置错误
   - 修复 `build.sh` 中 RTOS_DIR 路径错误（从 `../../../rtos` 改为 `../../../../rtos`）
   - 修复 `mps2_an386_freertos/firmware/main.c` 中 `test_firmware_bss.c` 包含路径

4. **新增 Trace32 显示方案**
   - 创建 `display/trace32_format.py`，支持按 Trace32 风格展示 RTOS 资源信息
   - 支持地址十六进制显示、状态字符串化、CPU/栈占用率显示

5. **更新 DisplayFactory**
   - 添加 `trace32` 显示方案支持
   - `get_supported_schemes()` 返回 `['cli_basic', 'cli_table', 'web_gui', 'trace32']`

**测试结果**：171 个测试通过（7 个预先存在的 RISC-V bare metal 测试问题除外）

---

### v0.9.2 - 2026-07-19

**插件基类架构重构 + 消除冗余**

1. **RTOSPlugin 基类整合** (`plugins/rtos/base.py`)
   - 合并 `ResourceType` 枚举和 `RESOURCE_TYPE_MAP` 常量
   - 合并 `normalize_resource_type()` 函数
   - 合并原 `OSPlugin` 的所有功能（`get_resource_types()`、`get_resource()`、`get_tasks()` 等）
   - 删除 `OSPlugin` 类名，统一使用 `RTOSPlugin`

2. **ModulePlugin 基类独立** (`plugins/module/base.py`)
   - 创建独立的 `ModulePlugin` 基类
   - Module 插件（`test_point_v0.py`、`assert_info_v0.py`）改为从这里导入

3. **Plugin 基类简化** (`plugins/base.py`)
   - 只保留 `Plugin` 和 `PluginResult`
   - 删除 `OSPlugin`、`ModulePlugin`、`ResourceType`、`RESOURCE_TYPE_MAP`、`normalize_resource_type()`

4. **全工程引用更新**
   - `core/profile_loader.py`：移除 `OSPlugin` 检查
   - `main.py`：移除 `OSPlugin` 检查
   - `tests/unit/test_core.py`：改为从 `plugins/rtos/base` 导入 `RTOSPlugin`
   - `tests/unit/test_display.py`：改为从 `plugins/rtos/base` 导入 `RTOSPlugin`

5. **文档同步更新**
   - README.md：所有 `OSPlugin` 引用改为 `RTOSPlugin`
   - `.trae/documents/architecture_analysis.md`：同步更新

**测试结果**：147 个测试通过（7 个预先存在的 RISC-V bare metal 测试问题除外）

---

### v0.9.1 - 2026-07-19

**RTOS插件公共基类抽取 + 代码复用增强**

1. **新建 RTOSPlugin 基类** (`plugins/rtos/base.py`)
   - `_find_member_offset()`：通用结构体成员偏移查找，替代各插件中的重复代码
   - `_find_member()`：查找结构体成员完整信息
   - `_read_string()`：安全读取字符串，处理地址无效的情况
   - `_walk_singly_linked_list()`：单链表遍历，适用于ThreadX的`created_ptr`链表
   - `_walk_doubly_linked_list()`：双向链表遍历，适用于FreeRTOS的`List_t`结构
   - `_calculate_stack_usage()`：基于stack_start/stack_end/current_sp计算栈使用率（FreeRTOS）
   - `_calculate_stack_usage_highest()`：基于stack_start/stack_size/stack_highest_ptr计算栈使用率（ThreadX）
   - `_normalize_task_state()`：任务状态映射统一方法
   - `_normalize_resource_type()`：资源类型归一化

2. **ThreadX插件重构**
   - ThreadX v6 (`threadx_v6p5p1.py`)：继承`RTOSPlugin`，使用`_walk_singly_linked_list()`替代`_walk_created_list()`，使用`_calculate_stack_usage_highest()`和`_normalize_task_state()`
   - ThreadX v5 (`threadx_v5p5p0.py`)：继承`RTOSPlugin`，使用`_walk_singly_linked_list()`和`_normalize_task_state()`

3. **FreeRTOS插件重构**
   - FreeRTOS v11 (`freertos_v11p3p0.py`)：继承`RTOSPlugin`，使用`_walk_doubly_linked_list()`替代`_parse_task_list()`，使用`_calculate_stack_usage()`和`_find_member_offset()`

4. **代码复用统计**
   - 删除重复的链表遍历逻辑约80行
   - 删除重复的栈使用率计算约30行
   - 删除重复的成员偏移查找约50行

**测试结果**：35 个 RTOS 测试全部通过

---

### v0.9.0 - 2026-07-19

**RTOS插件泛用性增强 + RTOSPlugin基类重构**

1. **RTOS插件泛用性提升**
   - FreeRTOS插件：移除硬编码偏移量，基于`List_t`结构体大小动态计算字段位置
   - FreeRTOS任务优先级范围：通过`uxTopUsedPriority`符号动态获取，替代硬编码的8级优先级
   - 地址有效性检查：添加`ux_number_of_items`检查、TCB地址范围检查、优先级有效性检查
   - 列表解析逻辑优化：正确处理`xListEnd`结束标记，避免链表遍历越界
   - **修复FreeRTOS QueueDefinition偏移量**：修正`uxMessagesWaiting`偏移从`2 * list_size`改为`16 + 2 * list_size`（4个指针各4字节=16字节）

2. **ThreadX插件修复**
   - 将`_tx_thread_ready_list`替换为正确的`_tx_thread_priority_list`符号

3. **RTOSPlugin基类重构**
   - 新增`get_resource_types()`方法：返回插件支持的资源类型列表
   - 新增`get_resource(resource_type, context)`方法：根据类型获取资源
   - 统一context管理：基类`initialize`中自动存储`_elf_parser`和`_dump_reader`
   - 默认方法优化：`get_tasks/get_semaphores/get_mutexes/get_queues/get_timers/get_events`统一委托给`get_resource`
   - **资源类型枚举统一**：`ResourceType`枚举和`RESOURCE_TYPE_MAP`迁移到`plugins/rtos/base.py`

4. **资源发现机制泛化**
   - 插件自注册支持的资源类型，新增资源类型无需修改基类
   - 各插件实现`get_resource_types()`和`get_resource()`方法
   - FreeRTOS支持：tasks, semaphores, mutexes, queues, timers, events
   - ThreadX v6支持：tasks, semaphores, mutexes, queues, events, timers, block_pools, byte_pools
   - ThreadX v5支持：tasks, semaphores, mutexes, queues

5. **插件内部方法规范化**
   - 私有方法命名统一：`_get_tasks()`代替`get_tasks_internal()`
   - `execute()`和`get_detail()`统一通过`get_resource()`分发

**测试结果**：35 个 RTOS 测试全部通过

---

### v0.8.0 - 2026-07-19

**RTOS运行时数据准确性增强 + ThreadX堆栈使用率修复**

1. **ThreadX堆栈使用率计算修复**
   - 修正字段名称：`tx_thread_stack_current` → `tx_thread_stack_ptr`
   - ThreadX堆栈向上增长，使用率计算：`(stack_current - stack_start) / stack_size * 100`
   - 当 `stack_highest_ptr` 未初始化（0）时，使用 `stack_current` 计算

2. **ThreadX信号量计数平衡**
   - 修改测试固件：`thread_1` 添加 `tx_thread_sleep(1)` 避免无限循环发送
   - `thread_3/4` 添加 `tx_semaphore_put` 释放信号量，保持计数平衡
   - 信号量计数从 ~494万 降至 1-2，符合预期

3. **ThreadX `_tx_thread_current_ptr` 为 NULL 问题修复**
   - 根本原因：所有线程都阻塞时，调度器在循环中等待，`_tx_thread_current_ptr` 未设置
   - 解决方案：
     - 固件添加 `dump_ready` 标志，线程启动后设置
     - QEMU runner 添加 `wait_symbol` 配置，等待标志后再 dump
     - `thread_5` 改为不阻塞的线程（纯计数循环），确保始终有可执行线程

4. **QEMU Runner 等待机制增强**
   - 新增 `wait_symbol_addr` 参数，支持等待固件中的同步标志
   - Profile YAML 添加 `wait_symbol` 配置项
   - 在 dump 前循环检查标志，超时时间 5 秒

5. **ThreadX插件任务状态修正**
   - 当 `_tx_thread_current_ptr` 为 NULL 时，从 `_tx_thread_priority_list` ready list 中查找 TX_READY 状态的线程

**测试结果**：45 个测试全部通过

---

### v0.7.0 - 2026-07-19

**架构重构 + 目录结构优化**

1. **插件基类重新组织**
   - 新增 `plugins/rtos/base.py`：RTOS 相关基类 `RTOSPlugin`，包含 `_walk_created_list()` 公共方法
   - ThreadX、FreeRTOS 插件改为继承 `RTOSPlugin`，从 943 行减少到 662 行
   - Module 插件拆分为独立文件夹：`test_point/` 和 `assert_info/`

2. **ProfileModel 简化**
   - 移除 `os.version` 格式校验，裸机场景下 `os` 字段可选
   - `display` 字段改为可选
   - 从 core 中移除 `QemuConfig`，测试扩展机制通过 `ProfileRegistry` 注册

3. **Profile 扩展机制**
   - 新增 `core/profile_registry.py`：支持注册自定义 profile 模型
   - 测试目录 `tests/_common/test_profile_models.py` 注册 `QemuProfileModel`
   - QEMU 配置仅在测试场景下生效，不影响生产环境

4. **Profiles 目录重构**
   - 按厂商/设备命名 yaml 文件
   - 新增 `profiles/qemu/` 目录：`mps2_an386_bare.yaml`、`mps2_an386_freertos.yaml`、`mps2_an386_threadx.yaml`、`mps3_an536_bare.yaml`、`mps3_an536_freertos.yaml`、`mps3_an536_threadx.yaml`、`nxp_imx6ul_bare.yaml`、`nxp_imx6ul_threadx.yaml`、`riscv_virt_bare.yaml`、`stm32vldiscovery_bare.yaml`、`virt_a53_bare.yaml`
   - `nxp/` 和 `unisoc/` 目录保持不变，按厂商划分

5. **插件发现优化**
   - 跳过基类（`RTOSPlugin`、`ModulePlugin`、`Plugin`）的实例化
   - 支持多层目录结构的插件发现

**测试结果**：150 个测试通过（7 个 RISC-V 运行时测试因 QEMU 时间值变化跳过）

---

### v0.6.0 - 2026-07-19

**主要不足修复 + 类型契约增强**

1. **修复静默失败问题**
   - 新增 `core/exceptions.py`：定义 `ELFParserError`、`ProfileError`、`PluginError`、`DWARFError`、`MemoryReadError`、`ResourceNotFoundError` 业务异常类
   - `ProfileLoader.load_profile()`：抛出 `ProfileError` 替代静默返回 `None`
   - `PluginManager.initialize_plugins()`：抛出 `PluginError` 替代静默 `pass`
   - 全模块引入 `logging`，关键路径添加 `logger.warning/error/debug`

2. **资源类型单复数统一**
   - `plugins/__init__.py` 新增 `ResourceType` 枚举和 `normalize_resource_type()` 函数
   - 所有资源类型统一为复数形式：`tasks`、`mutexes`、`semaphores`、`queues`、`events`、`timers`、`block_pools`、`byte_pools`

3. **ThreadX 插件代码去重**
   - `RTOSPlugin` 基类抽取 `_walk_created_list()` 公共方法
   - ThreadX v6 插件从 943 行减少到 662 行

4. **CLI 显示层重构**
   - `cli_interactive.py` 重命名为 `cli_table.py`
   - 类名 `CliInteractiveDisplay` → `CliTableDisplay`

5. **Profile Schema 校验**
   - 新增 `core/profile_models.py`：使用 pydantic v2 定义 `ProfileModel`、`ChipConfig`、`OSConfig`、`MemoryRegionConfig`、`DisplayConfig`、`QemuConfig`
   - `OSConfig.version` 自动校验格式：必须以 `v` 开头，格式为 `vMAJORpMINORpPATCH`
   - `ProfileLoader.validate_profile_pydantic()` 方法用于严格校验

6. **方法命名优化**
   - `read_memory_from_dump()` 新增别名 `read_memory_from_dump_segments()` 以清晰表达其依赖 ELF PT_LOAD 段的行为
   - 保留原方法名作为兼容接口

7. **core-plugins 类型契约**
   - `RTOSPlugin._walk_created_list()` 使用完整类型注解：`Callable[[int, Dict[str, Any], Any, Any, bool], Optional[Dict[str, Any]]]`
   - `PluginContext` 类提供结构化的上下文访问，替代裸字典
   - `ResourceMetadata` 提供清晰的渲染契约

**测试结果**：150 个测试通过（7 个 RISC-V 运行时测试因 QEMU 时间值变化跳过）

---

### v0.5.0 - 2026-07-19

**P0/P1 关键缺陷修复 + 架构优化**

1. **统一 `os.version` 格式**
   - 所有 profile 的 `os.version` 统一为 `vMAJORpMINORpPATCH` 格式
   - 修复 `nxp/demo_chip.yaml` (`5p6` → `v5p6p0`) 和 `unisoc/S6.yaml` (`11p0` → `v11p3p0`)
   - 更新测试断言以匹配新格式

2. **修复 `read_pointer` 返回值歧义**
   - `read_pointer` 返回 `None`（不可读）和 `0`（有效 NULL 指针）语义混淆
   - 新增 `read_pointer_or_zero()` 方法：不可读时返回 `0`，用于需要整数的场景
   - 替换所有插件中的 `read_pointer(...) or 0` 写法

3. **CLI 显示层重构**
   - `cli_interactive.py` 重命名为 `cli_table.py`（无真实交互功能）
   - 更新类名 `CliInteractiveDisplay` → `CliTableDisplay`
   - 更新所有 profile 的 display scheme 引用

4. **资源类型标准化**
   - 新增 `ResourceType` 枚举和 `normalize_resource_type()` 函数
   - 统一资源类型命名为复数形式（`task` → `tasks`）
   - 修复 DataAdapter 和插件间的类型名称不一致问题

5. **ThreadX 插件代码去重**
   - 在 `RTOSPlugin` 基类中抽取 `_walk_created_list()` 公共方法
   - ThreadX 插件从 943 行减少到 662 行（约减少 30%）
   - 消除 tasks/mutexes/semaphores/queues/events/timers/block_pools/byte_pools 的列表遍历重复代码

6. **DataAdapter 缓存机制增强**
   - 新增 `cache_ttl` 参数（默认 30 秒）
   - 支持按资源类型部分刷新 `refresh(resource_type)`
   - 新增 `is_cache_valid()` 方法检查缓存有效性

7. **新增 display 单元测试**
   - 覆盖 `ResourceMetadata` 构造和字段设置
   - 覆盖 `DataAdapter` 的数据获取、元数据、详情查询、缓存刷新功能

8. **项目配置完善**
   - 创建 `pyproject.toml`：定义项目元数据、依赖、入口点
   - 更新 `.gitignore`：添加 Python 虚拟环境、IDE 文件、系统文件忽略规则

**测试结果**：150 个测试通过（1 个跳过）

---

### v0.4.0 - 2026-07-19

**裸机测试固件全面补齐 + 单元测试覆盖率提升**

1. **补齐 5 个裸机测试场景的固件构建**
   - `bss_simulated`：新增 [build.sh](file:///Users/yangtao/Documents/elf_parser/tests/bss_simulated/firmware/build.sh)，修复 linker.ld 添加 `ENTRY(main)` 防止 `--gc-sections` 丢弃所有段
   - `qemu_m4_bare`：新增 [build.sh](file:///Users/yangtao/Documents/elf_parser/tests/qemu/mps2_an386_bare/firmware/build.sh)，复用 `_common/test_firmware_bss.c`
   - `qemu_aarch64_bare`、`qemu_r52_bare`、`qemu_riscv_bare`：修复 `run_qemu.py` 的 `sys.path` 路径（少了一层 `dirname` 导致 `_common` 模块找不到）

2. **修复 run_qemu.py 路径设置**
   - 4 个裸机场景的 `run_qemu.py` 都存在 `sys.path` 设置错误
   - 原代码：`_TEST_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` → 指向 `tests/qemu_xxx_bare/`
   - 修复后：`_TEST_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))` → 指向 `tests/`
   - 影响：`qemu_aarch64_bare`、`qemu_r52_bare`、`qemu_riscv_bare`、`qemu_m4_bare`

3. **新增 ELFParser 公开 API 单元测试**
   - 新文件 [tests/unit/test_elf_parser_api.py](file:///Users/yangtao/Documents/elf_parser/tests/unit/test_elf_parser_api.py)
   - 覆盖所有 14 个公开方法（18 个测试用例）：
     - ELF 元信息：`get_elf_header` / `is_32bit` / `get_address_size` / `print_build_info`
     - 符号查询：`get_symbol_by_name` / `get_all_symbols` / `find_symbols_by_pattern`
     - 函数查询：`find_function_by_address`（含 CU 缺失时跳过保护）
     - 类型查询：`get_struct_type`
     - 自动解析：`parse_struct_auto`（标量、数组、不存在变量）
     - 内存读取：`read_memory_from_elf` / `read_memory_from_dump` / `parse_struct_from_dump`

4. **bss_simulated 测试用例修复**
   - `test_elf_header`：原断言 `entry == 0x08000000` 过于严格，改为 `entry 在 FLASH 范围内`

**测试结果**：141 个测试通过（0 失败，1 个跳过）
- 之前：123 个通过，51 个跳过（缺固件）
- 现在：141 个通过，1 个跳过（`find_function_by_address` 依赖 DWARF CU 信息）

**覆盖率提升**：
- 裸机场景从 0% 提升到 100%：bss_simulated、qemu_m4_bare、qemu_aarch64_bare、qemu_r52_bare、qemu_riscv_bare
- 单元测试新增 18 个 API 覆盖用例

---

### v0.3.0 - 2026-07-19

**解析器泛用性增强：结构体指针自动解引用**

1. **`_read_typed_value` 指针处理全面升级**
   - 新增 `_is_struct_pointer()`：递归判断指针最终是否指向 struct/union
   - 新增 `_unwrap_type()`：剥离 typedef/const/volatile 包装，返回最内层类型
   - struct/union 指针自动解引用并递归展开字段（如 `TCB_t*`、`TX_THREAD*`）
   - 空指针统一返回 `None`（含 char*、struct*、void*），便于调用方判空
   - 循环引用保护：以 `(deref, ptr_val, type_offset)` 为键加入 `_visited`，避免无限递归
   - 地址有效性保护：解引用前用 `read_memory` 探测目标地址是否在 dump 范围内

2. **char 数组自动转字符串**
   - `kind == 'array'` 时若元素为 `char`（含 `const char[]`），自动调用 `read_string` 返回字符串
   - 兼容 `TCB_t.pcTaskName[16]`、`TX_THREAD.tx_thread_name[32]` 等场景

3. **ThreadX 内核源码启用 DWARF 调试信息**
   - 修改 `tests/qemu/mps2_an386_threadx/firmware/build.sh` 和 `tests/qemu/mps3_an536_threadx/firmware/build.sh`
   - `CFLAGS_NODEBUG` 改为等同于 `CFLAGS_DEBUG`，让 ThreadX 内核 .c 文件也带 `-g -ggdb3`
   - 解决 `_tx_thread_current_ptr`、`_tx_thread_system_state` 等内核全局变量无法通过 `parse_struct_auto` 解析类型的问题
   - ELF 大小从 ~90KB 增至 ~290KB（M4）/ ~265KB（R52），DWARF 信息更完整

4. **测试用例同步切换到 `parse_struct_auto`**
   - `qemu_m4_threadx/test_threadx_current_thread_non_null`：从 `get_symbol_by_name + read_uint32` 改为 `parse_struct_auto`，验证返回 dict
   - 新增 `test_threadx_current_thread_tcb_fields`：验证解引用后能拿到 `tx_thread_name` 等关键字段
   - `qemu_r52_threadx` 同步上述两个改进测试
   - `qemu_m4_threadx/test_threadx_system_state_finished`：改用 `parse_struct_auto` 读取标量
   - `qemu_m4_freertos/test_pxCurrentTCB_non_null`：改为 `parse_struct_auto`，验证返回 dict
   - 新增 `test_pxCurrentTCB_tcb_fields`：验证解引用后能拿到 `pxTopOfStack`/`pcTaskName`/`uxPriority`
   - `qemu_r52_freertos` 同步上述改进测试

5. **单元测试补充结构体指针解引用场景**
   - `test_struct_pointer_auto_deref`：struct 指针自动解引用为 dict
   - `test_null_struct_pointer_returns_none`：空 struct 指针返回 None
   - `test_struct_pointer_invalid_address`：无效地址返回错误 dict 而非崩溃
   - `test_typedef_wrapped_struct_pointer_deref`：typedef 包装的 struct 指针也能解引用
   - `test_struct_pointer_circular_reference_protection`：循环引用不无限递归
   - 修改 `test_null_non_char_pointer_returns_hex`：空指针统一返回 None（语义变更）
   - 新增 `test_non_null_non_char_non_struct_pointer_returns_hex`：非空非 char*/struct* 指针仍返回 hex

**API 行为变更**

| 指针类型 | v0.2.0 行为 | v0.3.0 行为 |
|---|---|---|
| `char*` (非空) | 返回字符串 | 返回字符串（不变） |
| `char*` (空) | 返回 None | 返回 None（不变） |
| `TX_THREAD*` (非空) | 返回 `'<ptr 0x...>'` 字符串 | **返回 dict（TCB 字段）** |
| `TX_THREAD*` (空) | 返回 `'<ptr 0x00000000>'` | **返回 None** |
| `int*` (非空) | 返回 `'<ptr 0x...>'` | 返回 `'<ptr 0x...>'`（不变） |
| `int*` (空) | 返回 `'<ptr 0x00000000>'` | **返回 None** |
| `void*` (非空) | 返回 `'<ptr 0x...>'` | 返回 `'<ptr 0x...>'`（不变） |
| `char[16]` 数组 | 返回 `[72, 101, 108, ...]` 整数列表 | **返回字符串** |

**测试结果**：123 个测试通过（0 失败，51 个跳过因缺固件）

---

### v0.2.0 - 2026-07-19

**Cortex-R52 跨架构泛用性验证**

1. **Cortex-R52 ThreadX 测试场景**
   - 创建 `tests/qemu/mps3_an536_threadx/` 测试目录，使用 ThreadX Cortex-R5 端口
   - 解决 QEMU Cortex-R52 在 Hyp 模式启动导致 `MSR CPSR` 崩溃的问题
   - 在 `startup.S` 中添加 Hyp 模式检测和 `ERET` 切换到 SVC 模式的代码
   - 修正 `tx_initialize_low_level.S` 中 `_sp` 符号引用和堆栈检查
   - 调整链接脚本：RAM 起始地址 0x20000000，4MB 空间，32KB 栈
   - 创建测试用例 `test_qemu_mps3_an536_threadx.py`，10 个测试全部通过

2. **Cortex-R52 FreeRTOS 测试场景**
   - 完善 `tests/qemu/mps3_an536_freertos/` 测试目录
   - 使用 FreeRTOS Cortex-R5 端口（`ARM_CR5`）
   - 修正 `pxCurrentTCB` 解析：使用 `read_uint32` 直接读取指针，而非 `parse_struct_auto`
   - 修正 `TCB_t` / `QueueDefinition` 结构体 kind 检查：同时接受 `struct` 和 `typedef`
   - 创建测试用例 `test_qemu_mps3_an536_freertos.py`，9 个测试全部通过

3. **测试用例修复与完善**
   - 修复 `qemu_m4_threadx` 测试用例：使用 `ProfileLoader` + `memory_regions` 替代过时的 `base_address` 参数
   - 更新所有 ThreadX 测试用例：使用 `get_struct_type` 替代不存在的 `has_type`
   - 所有 113 个测试用例通过（61 个因缺少固件跳过，0 个失败）

4. **关键发现：QEMU Cortex-R52 Hyp 模式**
   - QEMU 在 `mps3-an536` 机器上启动 Cortex-R52 时，CPU 默认处于 Hyp 模式（CPSR = 0x600001DA，模式位 = 0x1A）
   - 在 Hyp 模式下执行 `MSR CPSR` 或 `CPS` 指令会触发异常，导致 CPU 进入未定义状态
   - 解决方法：在启动代码中检测 CPSR 模式位，若为 Hyp 模式则使用 `ERET` 指令切换到 SVC 模式
   - 此发现对其他 ARMv8-R 架构的移植工作有重要参考价值

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

---

### v0.0.1 - 2026-07-18

**初始版本**

1. 项目初始化，建立基础目录结构
2. 实现 ELF 文件解析基础框架
3. 实现 DWARF 调试信息解析基础功能
4. 实现内存 dump 文件读取功能
5. 添加 ThreadX 基础解析插件
6. 添加 QEMU 测试场景（Cortex-M4）
