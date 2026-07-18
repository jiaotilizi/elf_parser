# QEMU 真实固件运行与 RAM Dump 方案

## Context（背景）

当前项目的 dump 文件 (`test_dump_bss.bin`) 是用 Python 脚本 (`generate_bss_dump.py`) **模拟**固件运行时行为生成的——Python 脚本硬编码了变量赋值逻辑，然后写入二进制文件。这不是真实的内存 dump。

用户希望用 QEMU 真实运行 ARM Cortex-M4 固件，在触发 crash 后从 QEMU 的虚拟 RAM 中 dump 出真实的内存内容，然后用现有的离线分析工具解析。这样可以验证工具能处理真实硬件行为产生的 dump（包括编译器优化、栈布局、对齐填充等 Python 模拟无法覆盖的细节）。

**关键约束已验证：**
- QEMU 11.0 已安装，`mps2-an386` 机器支持 Cortex-M4
- MPS2-AN386 内存映射：FLASH=0x00000000 (4MB), RAM=0x20000000 (4MB)
- 固件 `test_firmware_bss.c` 是 freestanding 的，只依赖 `stdint.h`，无 UART/semihosting 依赖
- `main()` 流程：`firmware_init()` → `simulate_runtime()` → `trigger_crash_assert()`（设 `g_system_status=0xFF`，进 `while(1)`）

## 实现方案

### 1. 创建 Cortex-M4 启动文件 `firmware/qemu/startup_qemu.s`

Cortex-M4 复位时需要向量表（位于 Flash 起始地址 0x00000000）：
- Word 0: 初始 SP（=0x20040000，RAM 顶部）
- Word 1: Reset_Handler 地址

Reset_Handler 负责：
- 复制 `.data` 段从 Flash LMA 到 RAM VMA
- 清零 `.bss` 段
- 调用 `main()`
- `main` 返回后进入死循环

包含 Default_Handler 处理所有其他异常（NMI、HardFault 等），防止异常触发时跑飞。

### 2. 创建 QEMU 专用链接脚本 `firmware/qemu/linker_qemu.ld`

基于现有 [firmware/linker.ld](file:///Users/yangtao/Documents/firmware/linker.ld) 修改：
- `FLASH` ORIGIN 改为 `0x00000000`（MPS2 的 ssram1）
- `RAM` ORIGIN 保持 `0x20000000`（MPS2 的 ssram23，与现有 profile 一致）
- 添加 `.isr_vector` 段（向量表）放在 Flash 最前面
- 导出 `_estack`（初始 SP）、`_sidata`/`_sdata`/`_edata`、`_sbss`/`_ebss` 符号供启动文件使用

**不修改原 `linker.ld`** — 保留它给现有测试使用。

### 3. 编译 QEMU 版固件

```bash
arm-none-eabi-gcc -c -g -O0 -mcpu=cortex-m4 -mthumb \
    firmware/qemu/startup_qemu.s -o build/startup_qemu.o
arm-none-eabi-gcc -c -g -O0 -mcpu=cortex-m4 -mthumb \
    firmware/test_firmware_bss.c -o build/test_firmware_bss_qemu.o
arm-none-eabi-gcc -g -O0 -mcpu=cortex-m4 -mthumb -nostdlib \
    -T firmware/qemu/linker_qemu.ld \
    build/startup_qemu.o build/test_firmware_bss_qemu.o \
    -o firmware/test_firmware_qemu.elf
```

### 4. 创建 QEMU 运行 + dump 脚本 `firmware/qemu/run_qemu_dump.py`

用 Python + subprocess 控制 QEMU 和 GDB：

1. 启动 QEMU：`qemu-system-arm -machine mps2-an386 -nographic -S -gdb tcp::1234 -kernel test_firmware_qemu.elf`
   - `-S` 暂停在复位
   - `-gdb tcp::1234` 启动 GDB server
2. 用 `arm-none-eabi-gdb` 批处理连接：
   - `target remote :1234`
   - 在 `trigger_crash_assert` 函数设断点（或直接在 `main` 末尾的 `while(1)` 处）
   - `continue` 运行到断点
   - `dump binary memory test_dump_qemu.bin 0x20000000 0x20001000` 导出 RAM
   - `detach` + `quit`
3. 关闭 QEMU

### 5. 更新测试 profile

现有 [profiles/test/test_firmware_real.yaml](file:///Users/yangtao/Documents/profiles/test/test_firmware_real.yaml) 内存配置已匹配：
```yaml
memory:
  - name: ram
    start_addr: 0x20000000
    size: 0x1000
```
**无需修改** — QEMU dump 的地址范围与现有 profile 完全一致。

### 6. 创建 QEMU dump 解析脚本 `firmware/qemu/show_qemu_parsed.py`

基于现有 [firmware/show_bss_parsed.py](file:///Users/yangtao/Documents/firmware/show_bss_parsed.py)，改为：
- 读取 `test_firmware_qemu.elf`（DWARF 来自真实 QEMU 版固件）
- 读取 `test_dump_qemu.bin`（真实 QEMU dump）
- 用 `parse_struct_auto()` 自动展开所有结构体
- 显示解析结果

### 7. 添加测试 `tests/test_qemu_firmware.py`

验证 QEMU 真实 dump 的解析：
- `test_qemu_elf_exists` — QEMU 编译产物存在
- `test_qemu_dump_exists` — QEMU dump 文件存在
- `test_qemu_elf_header` — ELF 头（class=32, machine=ARM, entry=0x00000000）
- `test_qemu_code_symbols_in_flash` — 代码符号在 0x00000000 段
- `test_qemu_bss_variables_in_ram` — BSS 变量在 0x20000000 段
- `test_qemu_assert_info_expansion` — g_assert_infos 数组自动展开
- `test_qemu_test_points_expansion` — g_test_points 数组自动展开
- `test_qemu_trace_buffer_expansion` — g_trace_buffer 环形缓冲区
- `test_qemu_system_status_crashed` — g_system_status == 0xFF（crash 已触发）
- `test_qemu_trace_write_idx` — g_trace_write_idx 在合理范围

## 关键文件清单

**新建：**
- `firmware/qemu/startup_qemu.s` — Cortex-M4 启动汇编
- `firmware/qemu/linker_qemu.ld` — QEMU 链接脚本
- `firmware/qemu/run_qemu_dump.py` — QEMU 运行 + GDB dump 脚本
- `firmware/qemu/show_qemu_parsed.py` — QEMU dump 解析展示
- `tests/test_qemu_firmware.py` — QEMU 测试用例

**生成物（运行时产生）：**
- `firmware/test_firmware_qemu.elf` — QEMU 版编译产物
- `firmware/test_dump_qemu.bin` — 真实 QEMU RAM dump

**不修改：**
- 现有 `firmware/linker.ld`、`firmware/test_firmware_bss.elf`、`test_dump_bss.bin` 保留
- 现有 `profiles/test/test_firmware_real.yaml` 内存配置已匹配
- 现有 `core/elf_parser.py`、`core/dump_reader.py` 等核心代码无需改动

## 验证方式

1. **编译验证**：`arm-none-eabi-gcc` 成功生成 `test_firmware_qemu.elf`，`arm-none-eabi-readelf` 能看到正确的段地址
2. **QEMU 运行验证**：QEMU 启动后能通过 GDB 控制执行到 `trigger_crash_assert` 断点
3. **Dump 验证**：`test_dump_qemu.bin` 大小 = 0x1000 字节，内容不全为 0（证明固件确实运行并填充了 BSS）
4. **解析验证**：`show_qemu_parsed.py` 能正确展开所有结构体，字段值与预期一致
5. **测试验证**：`python3 -m unittest tests.test_qemu_firmware` 全部通过
6. **全量回归**：`python3 -m unittest discover -s tests` 全部通过（现有 26 个 + 新增 QEMU 测试）

## 技术风险与应对

| 风险 | 应对 |
|-----|------|
| QEMU `-kernel` 对 Cortex-M 向量表处理不确定 | 启动文件中显式定义 `.isr_vector` 段，放在 Flash 最前 |
| GDB 连接失败 | 使用 `arm-none-eabi-gdb` 而非主机 GDB，确保 ARM 架构支持 |
| 固件在 QEMU 中跑飞（HardFault） | startup 文件包含 Default_Handler 捕获所有异常 |
| `while(1)` 无法到达 | 用断点而非超时控制执行；检查 simulate_runtime 是否有未处理的边界 |
| BSS 段大小超 0x1000 | `arm-none-eabi-size` 预检，如超限则扩大 profile 的 size |
