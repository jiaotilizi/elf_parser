# 续作计划：完成剩余多架构 QEMU 场景（Phase 3.1 修复 + 3.2/3.3/4/5/6）

## Summary

承接已批准的 [multi_arch_qemu_continuation.md](file:///Users/yangtao/Documents/.trae/documents/multi_arch_qemu_continuation.md)。Phase 0-2 已完成（45 测试通过），Phase 3.1 (R52) 几乎完成但测试文件末尾有语法错误。本计划完成 **R52 收尾 + AArch64 + RISC-V + FreeRTOS + ThreadX + 端到端回归**，目标 70+ 测试全通过，覆盖 32/64 位指针与 RTOS 任务/同步原语解析。

## 当前状态（已验证）

| 项 | 状态 | 证据 |
|---|---|---|
| 工具链 | ✅ | `arm-none-eabi-gcc 16.1.0`、`aarch64-elf-gcc 16.1.0`、`riscv64-elf-gcc 16.1.0` 均在 `/opt/homebrew/bin/` |
| QEMU 机器 | ✅ | `mps2-an386` (M4)、`mps3-an536` (R52)、`virt` (AArch64)、`sifive_e` (RV32) 均可用 |
| Phase 0-2 共享设施 | ✅ | [firmware/_common/](file:///Users/yangtao/Documents/firmware/_common/) 含 qemu_runner.py / show_parsed_base.py / build_helpers.py / test_firmware_bss.c |
| Phase 1.2 universality 测试 | ✅ | [tests/unit/test_elf_parser_universality.py](file:///Users/yangtao/Documents/tests/unit/test_elf_parser_universality.py) 8 测试通过 |
| Phase 1.4 路径/profile 修复 | ✅ | bss_simulated/qemu_m4_bare/qemu_r52_bare 三场景 profile + 路径全部就位 |
| Phase 3.1 R52 固件 | ✅ | [firmware/qemu_r52_bare/](file:///Users/yangtao/Documents/firmware/qemu_r52_bare/) 含 startup.S/linker.ld/main.c/build.sh/run_qemu.py/show_parsed.py；ELF 已编译，dump 已生成（16KB，21.2% 非零），show_parsed 输出正确 |
| Phase 3.1 R52 测试 | ⚠️ 末行截断 | [tests/qemu_r52_bare/test_qemu_r52_bare.py](file:///Users/yangtao/Documents/tests/qemu_r52_bare/test_qemu_r52_bare.py) 末行 `if __name__ == '__main` 缺 `':` 与 `unittest.main()`，导致 1 个 SyntaxError，46 测试中 1 error |
| RTOS 插件 | ✅ 现成 | [plugins/rtos/freertos/freertos_11p0.py](file:///Users/yangtao/Documents/plugins/rtos/freertos/freertos_11p0.py) 和 [plugins/rtos/threadx/threadx_6p5.py](file:///Users/yangtao/Documents/plugins/rtos/threadx/threadx_6p5.py) 已就绪 |

测试基线：`Ran 46 tests in 0.749s — FAILED (errors=1)`，错误全部来自 R52 测试文件末行截断。

## 剩余工作（按执行顺序）

### Phase 3.1 — R52 收尾（10 分钟）

**问题**：[tests/qemu_r52_bare/test_qemu_r52_bare.py:202](file:///Users/yangtao/Documents/tests/qemu_r52_bare/test_qemu_r52_bare.py#L202) 末尾截断为 `if __name__ == '__main`，缺闭合。

**修复**：将末尾两行改为：
```python
if __name__ == '__main__':
    unittest.main()
```

**验证**：
```bash
python3 -m unittest tests.qemu_r52_bare.test_qemu_r52_bare -v
# 期望：10 测试通过（test_r52_elf_exists/header/bss_in_ram/scalar_values/assert_info_array/
#       assert_record_details/test_point_array/trace_buffer/char_pointer_deref/auto_vs_manual_read）
python3 -m unittest discover -s tests -p 'test_*.py'
# 期望：55 测试通过（45 现有 + 10 R52）
```

### Phase 3.2 — qemu_aarch64_bare（1-2 小时，验证 64 位指针修复）

**目标**：在真实 AArch64 ELF + dump 上验证 [core/elf_parser.py](file:///Users/yangtao/Documents/core/elf_parser.py) 的 64 位指针解析路径。

**新建文件**：

1. **[firmware/qemu_aarch64_bare/startup.S](file:///Users/yangtao/Documents/firmware/qemu_aarch64_bare/startup.S)**
   - AArch64 模式启动：`_start` 设 SP（`ldr x0, =_estack; mov sp, x0`）→ 清 .bss → `bl main` → 死循环
   - `.section .text.startup, "ax"` + `.global _start`
   - 不需要向量表（AArch64 Linux-style boot：`-kernel` 跳 ELF entry）

2. **[firmware/qemu_aarch64_bare/linker.ld](file:///Users/yangtao/Documents/firmware/qemu_aarch64_bare/linker.ld)**
   - `RAM ORIGIN = 0x40000000 LENGTH = 64M`（QEMU virt 默认 RAM 基址）
   - `_estack = ORIGIN(RAM) + LENGTH(RAM)`
   - `.text` → `.rodata` → `.data` → `.bss` 全部在 RAM（无 Flash 分离）
   - `_sidata = LOADADDR(.data)` + `AT> RAM`（no-op copy，与 R52 一致）

3. **[firmware/qemu_aarch64_bare/main.c](file:///Users/yangtao/Documents/firmware/qemu_aarch64_bare/main.c)**
   - 一行：`#include "../_common/test_firmware_bss.c"`（共享数据布局）

4. **[firmware/qemu_aarch64_bare/build.sh](file:///Users/yangtao/Documents/firmware/qemu_aarch64_bare/build.sh)**
   - `CC=aarch64-elf-gcc`
   - `CFLAGS=-march=armv8-a -mcpu=cortex-a53 -ffreestanding -nostdlib -nostartfiles -g3 -gdwarf-4 -O0 -fno-pic -fno-pie -mno-red-zone -fdata-sections -ffunction-sections`
   - `LDFLAGS=-T linker.ld -Wl,--gc-sections -Wl,-Map,build/test_firmware_aarch64.map`
   - 输出 `test_firmware_aarch64.elf`

5. **[profiles/test/qemu_aarch64_bare.yaml](file:///Users/yangtao/Documents/profiles/test/qemu_aarch64_bare.yaml)**
   ```yaml
   chip:
     name: qemu_aarch64_bare
     arch: armv8-a
     cpu: cortex-a53
     bits: 64
   os:
     name: baremetal
     version: none
   qemu:
     binary: qemu-system-aarch64
     machine: virt
     cpu: cortex-a53
     kernel_arg: -kernel
     ram_base: 0x40000000
     ram_size: 16384   # 16KB；.text 在 RAM 里，与 R52 同理需要覆盖代码+BSS
     run_seconds: 2.0
   memory:
   - name: ram
     start_addr: 1073741824   # 0x40000000
     size: 16384
   modules:
   - assert_info
   - test_point
   ```

6. **[firmware/qemu_aarch64_bare/run_qemu.py](file:///Users/yangtao/Documents/firmware/qemu_aarch64_bare/run_qemu.py)**
   - ~10 行 shim：`runner_from_profile('test/qemu_aarch64_bare', scenario_dir, 'test_firmware_aarch64.elf', 'test_dump_aarch64.bin').run_and_dump()`
   - 模式与 [firmware/qemu_r52_bare/run_qemu.py](file:///Users/yangtao/Documents/firmware/qemu_r52_bare/run_qemu.py) 一致

7. **[firmware/qemu_aarch64_bare/show_parsed.py](file:///Users/yangtao/Documents/firmware/qemu_aarch64_bare/show_parsed.py)**
   - `QemuAarch64BareShow(ShowParsedBase)` 子类，~35 行
   - BANNER_TITLE: 'AArch64 (Cortex-A53) Crash Dump 自动恢复演示'
   - BANNER_LINES 提示「验证 64 位指针解析」

8. **[tests/qemu_aarch64_bare/test_qemu_aarch64_bare.py](file:///Users/yangtao/Documents/tests/qemu_aarch64_bare/test_qemu_aarch64_bare.py)**
   - 11 个测试（标准 10 + 1 个 pointer_size）：
     - `test_aarch64_elf_exists`
     - `test_aarch64_elf_header`：class=64、machine='AArch64'、entry 在 0x40000000-0x40004000
     - `test_aarch64_bss_variables_in_ram`
     - `test_aarch64_scalar_values`：与 M4/R52 期望值一致（5234567 等）
     - `test_aarch64_assert_info_array_expansion`：4 槽，每槽 8 records
     - `test_aarch64_assert_record_details`：file_name='main.c' 等
     - `test_aarch64_test_point_array_expansion`：8 测点
     - `test_aarch64_trace_buffer_expansion`：32 槽，前 20 有效
     - `test_aarch64_char_pointer_deref`：char* 自动解引用为 str
     - `test_aarch64_pointer_size_is_8`（**关键**）：从 DWARF 取 `assert_record_t.file_name` 字段类型，断言 `byte_size == 8`；再断言 `parse_struct_auto('g_assert_infos', ...)` 返回的 `file_name` 是 str 而非 `<ptr 0x...>`（证明 64 位指针解引用路径走通）
     - `test_aarch64_auto_parse_matches_manual_read`：`read_uint64` 手动值 == `parse_struct_auto` 值
   - setUp 跳过条件：ELF/dump 不存在则 skipTest
   - 期望值与 M4/R52 完全一致（共享 test_firmware_bss.c）

**验证**：
```bash
bash firmware/qemu_aarch64_bare/build.sh
python3 firmware/qemu_aarch64_bare/run_qemu.py
python3 firmware/qemu_aarch64_bare/show_parsed.py
python3 -m unittest tests.qemu_aarch64_bare.test_qemu_aarch64_bare -v
# 期望：11 测试通过
```

### Phase 3.3 — qemu_riscv_bare（1-2 小时，多区域 dump）

**目标**：验证 RISC-V 32 位 + 多区域 dump（flash + RAM 拼接）。

**新建文件**：

1. **[firmware/qemu_riscv_bare/startup.S](file:///Users/yangtao/Documents/firmware/qemu_riscv_bare/startup.S)**
   - RISC-V 启动：`_start` 设 SP（`la sp, _estack`）→ 清 .bss → `call main` → `j .`
   - `.section .text.startup, "ax"` + `.global _start`
   - `.option norvc` 保证初始指令非压缩

2. **[firmware/qemu_riscv_bare/linker.ld](file:///Users/yangtao/Documents/firmware/qemu_riscv_bare/linker.ld)**
   - `FLASH ORIGIN = 0x20000000 LENGTH = 1M`（sifive_e mask ROM 跳到 0x20000000）
   - `RAM ORIGIN = 0x80000000 LENGTH = 16K`（sifive_e SRAM）
   - `_estack = ORIGIN(RAM) + LENGTH(RAM)`
   - `.text` + `.rodata` → `> FLASH`
   - `.data` + `.bss` → `> RAM AT> FLASH`（`.data` 由 startup 从 flash 复制到 RAM）
   - `_sidata = LOADADDR(.data)`

3. **[firmware/qemu_riscv_bare/main.c](file:///Users/yangtao/Documents/firmware/qemu_riscv_bare/main.c)**
   - `#include "../_common/test_firmware_bss.c"`

4. **[firmware/qemu_riscv_bare/build.sh](file:///Users/yangtao/Documents/firmware/qemu_riscv_bare/build.sh)**
   - `CC=riscv64-elf-gcc`
   - `CFLAGS=-march=rv32imac_zicsr -mabi=ilp32 -ffreestanding -nostdlib -nostartfiles -g3 -gdwarf-4 -O0 -fdata-sections -ffunction-sections`
   - 输出 `test_firmware_riscv.elf`

5. **[profiles/test/qemu_riscv_bare.yaml](file:///Users/yangtao/Documents/profiles/test/qemu_riscv_bare.yaml)**
   ```yaml
   chip:
     name: qemu_riscv_bare
     arch: rv32imac
     cpu: sifive-e31
     bits: 32
   os:
     name: baremetal
     version: none
   qemu:
     binary: qemu-system-riscv32
     machine: sifive_e
     cpu: sifive-e31
     kernel_arg: -device        # sifive_e 用 -device loader,file=...
     ram_base: 0x80000000
     ram_size: 4096
     run_seconds: 2.0
     extra_args: []             # 可补 -bios none 等
   memory:
   - name: flash
     start_addr: 536870912       # 0x20000000
     size: 1048576              # 1MB
   - name: ram
     start_addr: 2147483648     # 0x80000000
     size: 4096                 # 4KB（BSS 在这）
   modules:
   - assert_info
   - test_point
   ```

6. **[firmware/qemu_riscv_bare/run_qemu.py](file:///Users/yangtao/Documents/firmware/qemu_riscv_bare/run_qemu.py)**
   - 多区域 dump：`runner.run_and_dump_multi_region(profile_regions)`，其中 `profile_regions` 从 profile `memory:` 块取
   - 需要在 `runner_from_profile` 之外手动取 regions（或扩展工厂方法支持多区域）
   - 产物：`test_dump_riscv.flash.bin` + `test_dump_riscv.ram.bin`，由 DumpReader 多区域拼接

7. **[firmware/qemu_riscv_bare/show_parsed.py](file:///Users/yangtao/Documents/firmware/qemu_riscv_bare/show_parsed.py)**
   - `QemuRiscvBareShow(ShowParsedBase)` 子类
   - 处理多区域 dump 路径（传 `dump_filename='test_dump_riscv.bin'`，DumpReader 通过 regions 自动加载 `.<region>.bin` 后缀文件）

   **注意**：需要检查 DumpReader 是否支持「无主 dump 文件 + 多个 .region.bin」模式。如不支持，调整 [core/dump_reader.py](file:///Users/yangtao/Documents/core/dump_reader.py) 或在 run_qemu.py 里同时输出主 dump（拼接版）。

8. **[tests/qemu_riscv_bare/test_qemu_riscv_bare.py](file:///Users/yangtao/Documents/tests/qemu_riscv_bare/test_qemu_riscv_bare.py)**
   - 10 测试（与 R52 对应）：
     - `test_riscv_elf_exists`
     - `test_riscv_elf_header`：class=32、machine='RISC-V'、entry 在 0x20000000-0x20100000（FLASH 段）
     - `test_riscv_bss_variables_in_ram`：g_* 地址在 0x80000000-0x80001000
     - `test_riscv_scalar_values`
     - `test_riscv_assert_info_array_expansion`
     - `test_riscv_assert_record_details`
     - `test_riscv_test_point_array_expansion`
     - `test_riscv_trace_buffer_expansion`
     - `test_riscv_char_pointer_deref`（**关键**：char* 指向 flash 段的字符串字面量，验证多区域读通）
     - `test_riscv_auto_parse_matches_manual_read`

**验证**：
```bash
bash firmware/qemu_riscv_bare/build.sh
python3 firmware/qemu_riscv_bare/run_qemu.py
python3 firmware/qemu_riscv_bare/show_parsed.py
python3 -m unittest tests.qemu_riscv_bare.test_qemu_riscv_bare -v
# 期望：10 测试通过
```

**风险**：sifive_e 的 `-device loader,file=` 可能不正确跳到 entry。若失败，回退方案：用 `virt -bios elf.elf` + 单区域 RAM dump，相应调整 profile。

### Phase 4 — qemu_m4_freertos（4-6 小时，最复杂）

**目标**：在 M4 上跑 FreeRTOS V11.3.0，4 任务 + 同步原语，验证 TCB_t/List_t/Queue_t 的 DWARF 自动恢复。

**新建文件**：

1. **克隆 FreeRTOS**
   ```bash
   cd firmware/qemu_m4_freertos
   git clone --depth 1 --branch V11.3.0 https://github.com/FreeRTOS/FreeRTOS-Kernel.git rtos
   ```
   预期子目录：`rtos/portable/GCC/ARM_CM4F/`、`rtos/portable/MemMang/heap_4.c`、`rtos/tasks.c`、`rtos/queue.c`、`rtos/list.c`、`rtos/timers.c`、`rtos/event_groups.c`、`rtos/stream_buffer.c`

2. **[firmware/qemu_m4_freertos/FreeRTOSConfig.h](file:///Users/yangtao/Documents/firmware/qemu_m4_freertos/FreeRTOSConfig.h)**
   - `configCPU_CLOCK_HZ 25000000`（M4 mps2-an386 默认 25MHz）
   - `configTICK_RATE_HZ 1000`
   - `configUSE_PREEMPTION 1`
   - `configMAX_PRIORITIES 5`
   - `configMINIMAL_STACK_SIZE 128`
   - `configTOTAL_HEAP_SIZE 32768`
   - `configUSE_MUTEXES 1`、`configUSE_COUNTING_SEMAPHORES 1`、`configUSE_QUEUE_SETS 0`
   - `configCHECK_FOR_STACK_OVERFLOW 2`
   - `configUSE_IDLE_HOOK 0`、`configUSE_TICK_HOOK 0`
   - `configSUPPORT_STATIC_ALLOCATION 0`

3. **[firmware/qemu_m4_freertos/startup.S](file:///Users/yangtao/Documents/firmware/qemu_m4_freertos/startup.S)**
   - 复用 [firmware/qemu_m4_bare/startup_qemu.s](file:///Users/yangtao/Documents/firmware/qemu_m4_bare/startup_qemu.s) 的向量表结构
   - 在向量表里把 SVC/PendSV/SysTick 改成 `.thumb_set SVC_Handler, vPortSVCHandler` 等（FreeRTOS port 接口）
   - 其他异常保持 Default_Handler

4. **[firmware/qemu_m4_freertos/linker.ld](file:///Users/yangtao/Documents/firmware/qemu_m4_freertos/linker.ld)**
   - 复用 [firmware/qemu_m4_bare/linker_qemu.ld](file:///Users/yangtao/Documents/firmware/qemu_m4_bare/linker_qemu.ld)（Flash 0x0 + RAM 0x20000000）
   - RAM LENGTH 改为 256K（足够 heap_4 32KB + 4 任务栈 + 内核）

5. **[firmware/qemu_m4_freertos/main.c](file:///Users/yangtao/Documents/firmware/qemu_m4_freertos/main.c)**
   - `#include "../_common/test_firmware_bss.c"`（保留裸机断言数据）
   - 调 `firmware_init()` 后启动 RTOS：
     - `xTaskCreate(vLedTask,    "Led",     256, NULL, 1, NULL)`
     - `xTaskCreate(vSenderTask, "Sender",  256, NULL, 2, NULL)`
     - `xTaskCreate(vRecvTask,    "Recv",    256, NULL, 3, NULL)`
     - `xTaskCreate(vIdleTask,    "IdleX",   128, NULL, 0, NULL)`
   - 全局：`xSemaphoreHandle xMutex`、`xSemaphoreHandle xCountSem`、`xQueueHandle xQueue`、`xEventGroupHandle xEventGrp`
   - `vTaskStartScheduler()` 后死循环
   - 任务体简单：每次循环 `xSemaphoreTake/Give`、`xQueueSend/Receive`，并在 100 次循环后调 `record_assert(...)` 累积裸机断言
   - **关键**：在 main 顶部加 `volatile int g_rtos_started = 1;` 让 dump 能验证 scheduler 启动过

6. **[firmware/qemu_m4_freertos/build.sh](file:///Users/yangtao/Documents/firmware/qemu_m4_freertos/build.sh)**
   - `CC=arm-none-eabi-gcc`
   - `CFLAGS=-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -ffreestanding -g3 -gdwarf-4 -O0 -I rtos/include -I rtos/portable/GCC/ARM_CM4F -I .`
   - 源文件：
     ```
     startup.S
     main.c
     rtos/tasks.c
     rtos/queue.c
     rtos/list.c
     rtos/timers.c
     rtos/event_groups.c
     rtos/stream_buffer.c
     rtos/portable/GCC/ARM_CM4F/port.c
     rtos/portable/MemMang/heap_4.c
     ```
   - 链接 `-T linker.ld -Wl,--gc-sections`

7. **[profiles/test/qemu_m4_freertos.yaml](file:///Users/yangtao/Documents/profiles/test/qemu_m4_freertos.yaml)**
   ```yaml
   chip:
     name: qemu_m4_freertos
     arch: armv7e-m
     cpu: cortex-m4
     bits: 32
   os:
     name: freertos
     version: '11.3.0'
     description: FreeRTOS V11.3.0 on QEMU Cortex-M4
   qemu:
     binary: qemu-system-arm
     machine: mps2-an386
     cpu: cortex-m4
     kernel_arg: -kernel
     ram_base: 0x20000000
     ram_size: 65536         # 64KB，覆盖 heap + 4 任务栈 + 队列
     run_seconds: 2.0
   memory:
   - name: ram
     start_addr: 536870912
     size: 65536
   modules:
   - assert_info
   - test_point
   plugins:
   - rtos/freertos
   ```

8. **[firmware/qemu_m4_freertos/run_qemu.py](file:///Users/yangtao/Documents/firmware/qemu_m4_freertos/run_qemu.py)**
   - 标准 shim

9. **[firmware/qemu_m4_freertos/show_parsed.py](file:///Users/yangtao/Documents/firmware/qemu_m4_freertos/show_parsed.py)**
   - `QemuM4FreertosShow(ShowParsedBase)` 子类
   - 在 4 个标准 section 后追加：调用 [plugins/rtos/freertos/freertos_11p0.py](file:///Users/yangtao/Documents/plugins/rtos/freertos/freertos_11p0.py) 列出 tasks/semaphores/mutexes/queues

10. **[tests/qemu_m4_freertos/test_qemu_m4_freertos.py](file:///Users/yangtao/Documents/tests/qemu_m4_freertos/test_qemu_m4_freertos.py)**
    - 10 测试，断言**结构性属性**（避免时序 flaky）：
      1. `test_freertos_elf_exists`
      2. `test_freertos_elf_header`：class=32、machine='ARM'
      3. `test_scheduler_started`：`g_rtos_started == 1`（裸机标志位）
      4. `test_pxCurrentTCB_non_null`：`parse_struct_auto('pxCurrentTCB', ...)` 返回非 0 指针
      5. `test_tcb_struct_in_dwarf`：`elf_parser.get_struct_type('TCB_t')` 不为 None
      6. `test_created_task_count`：通过 `pxReadyTasksLists` + suspended + delayed 列表合计 ≥ 4（4 任务可能在 ready/blocked/delayed 各列表，最少 4）
      7. `test_tcb_pcTaskName_is_char_array`：TCB_t.pcTaskName 字段在 DWARF 中是 `char[16]`，断言 `kind == 'array'` 且元素是 char
      8. `test_queue_struct_in_dwarf`：`get_struct_type('QueueDefinition')` 不为 None
      9. `test_baremetal_assert_data_intact`：`g_system_ticks == 5234567`、`g_assert_infos[0].count == 3`（裸机数据仍填充）
      10. `test_freertos_plugin_loadable`：构造 `FreeRTOS11p0Plugin` 实例，`initialize(context)` 不抛异常（不要求返回非空数据，只要插件接口可加载）

**插件兼容性策略**：
- 先尝试 [plugins/rtos/freertos/freertos_11p0.py](file:///Users/yangtao/Documents/plugins/rtos/freertos/freertos_11p0.py)
- 该插件依赖 `xSemaphoreRegistry`/`xQueueRegistry`，**FreeRTOS V11.3.0 实际只有 `xQueueRegistry`**（无单独 sem registry）
- 若 `get_semaphores` 返回空但 `get_queues` 能列 Queue/Mutex/Sem（FreeRTOS 把 sem/mutex 当 queue 实现），则**接受现状**，测试不断言 sem 数量
- 若 `pxCurrentTCB` 解析失败，新增 `plugins/rtos/freertos/freertos_11p3.py`（继承 11p0，覆写 `_parse_task_list` 兼容 V11.3.0 的 ListItem_t 布局）

**验证**：
```bash
bash firmware/qemu_m4_freertos/build.sh
python3 firmware/qemu_m4_freertos/run_qemu.py
python3 firmware/qemu_m4_freertos/show_parsed.py
python3 -m unittest tests.qemu_m4_freertos.test_qemu_m4_freertos -v
# 期望：10 测试通过
```

### Phase 5 — qemu_m4_threadx（4-6 小时）

**目标**：在 M4 上跑 ThreadX v6.5.1，4 线程 + 同步原语，验证 TX_THREAD/TX_MUTEX/TX_SEMAPHORE/TX_QUEUE 的 DWARF 自动恢复。

**新建文件**：

1. **克隆 ThreadX**
   ```bash
   cd firmware/qemu_m4_threadx
   git clone --depth 1 https://github.com/eclipse-threadx/threadx.git rtos
   ```
   预期子目录：`rtos/common/src/`、`rtos/ports/cortex-m4/gnu/`（含 6 个 .s + tx_port.c）

2. **[firmware/qemu_m4_threadx/tx_user.h](file:///Users/yangtao/Documents/firmware/qemu_m4_threadx/tx_user.h)**
   - `TX_DISABLE_PREEMPTION_THRESHOLD 0`
   - `TX_DISABLE_NOTIFY_CALLBACKS 1`
   - `TX_ENABLE_STACK_CHECKING 1`
   - 其他用默认

3. **[firmware/qemu_m4_threadx/startup.S](file:///Users/yangtao/Documents/firmware/qemu_m4_threadx/startup.S)**
   - 复用 M4 向量表
   - 在向量表里：`.thumb_set PendSV_Handler, __tx_PendSVHandler`、`.thumb_set SysTick_Handler, __tx_SysTickHandler`、`.thumb_set SVC_Handler, __tx_SVCHandler`
   - Reset_Handler 调 `tx_main()`（含 `tx_kernel_enter()`）

4. **[firmware/qemu_m4_threadx/linker.ld](file:///Users/yangtao/Documents/firmware/qemu_m4_threadx/linker.ld)**
   - 复用 M4 linker（Flash 0x0 + RAM 0x20000000）
   - RAM LENGTH 256K

5. **[firmware/qemu_m4_threadx/main.c](file:///Users/yangtao/Documents/firmware/qemu_m4_threadx/main.c)**
   - `#include "../_common/test_firmware_bss.c"`（裸机数据）
   - `tx_application_define()` 里：
     - `tx_thread_create(&thread_led, "Led", led_entry, 0, stack_led, 1024, 1, 1, TX_NO_TIME_SLICE, TX_AUTO_START)`
     - 4 个线程：Led(优先 1)/Sender(2)/Receiver(3)/Idle(0)
     - `tx_mutex_create(&mutex, "Mutex", TX_INHERIT)`
     - `tx_semaphore_create(&sem, "Sem", 0)`
     - `tx_queue_create(&queue, "Queue", TX_1_ULONG, queue_storage, 16)`
     - `tx_byte_pool_create(&pool, "Pool", pool_storage, 4096)`
   - 任务体循环 take/give/send/receive
   - main 顶部 `volatile int g_rtos_started = 1;`
   - `tx_kernel_enter()` 后死循环

6. **[firmware/qemu_m4_threadx/build.sh](file:///Users/yangtao/Documents/firmware/qemu_m4_threadx/build.sh)**
   - `CC=arm-none-eabi-gcc`
   - `CFLAGS=-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -ffreestanding -g3 -gdwarf-4 -O0 -I rtos/common/inc -I rtos/ports/cortex-m4/gnu/inc -I . -DTX_ENABLE_STACK_CHECKING`
   - 源文件：
     ```
     startup.S
     main.c
     rtos/common/src/tx_thread_*.c（约 30+ 文件，全收）
     rtos/common/src/tx_mutex_*.c
     rtos/common/src/tx_semaphore_*.c
     rtos/common/src/tx_queue_*.c
     rtos/common/src/tx_byte_pool_*.c
     rtos/common/src/tx_timer_*.c
     rtos/ports/cortex-m4/gnu/src/tx_thread_context_restore.s
     rtos/ports/cortex-m4/gnu/src/tx_thread_context_save.s
     rtos/ports/cortex-m4/gnu/src/tx_thread_interrupt_control.s
     rtos/ports/cortex-m4/gnu/src/tx_thread_schedule.s
     rtos/ports/cortex-m4/gnu/src/tx_thread_stack_build.s
     rtos/ports/cortex-m4/gnu/src/tx_thread_system_return.s
     rtos/ports/cortex-m4/gnu/src/tx_timer_interrupt.s
     ```

7. **[profiles/test/qemu_m4_threadx.yaml](file:///Users/yangtao/Documents/profiles/test/qemu_m4_threadx.yaml)**
   ```yaml
   chip:
     name: qemu_m4_threadx
     arch: armv7e-m
     cpu: cortex-m4
     bits: 32
   os:
     name: threadx
     version: '6.5.1'
     description: ThreadX v6.5.1 on QEMU Cortex-M4
   qemu:
     binary: qemu-system-arm
     machine: mps2-an386
     cpu: cortex-m4
     kernel_arg: -kernel
     ram_base: 0x20000000
     ram_size: 65536
     run_seconds: 2.0
   memory:
   - name: ram
     start_addr: 536870912
     size: 65536
   modules:
   - assert_info
   - test_point
   plugins:
   - rtos/threadx
   ```

8. **[firmware/qemu_m4_threadx/run_qemu.py](file:///Users/yangtao/Documents/firmware/qemu_m4_threadx/run_qemu.py)** — 标准 shim

9. **[firmware/qemu_m4_threadx/show_parsed.py](file:///Users/yangtao/Documents/firmware/qemu_m4_threadx/show_parsed.py)**
   - `QemuM4ThreadxShow(ShowParsedBase)` 子类
   - 4 标准 section 后追加：调 [plugins/rtos/threadx/threadx_6p5.py](file:///Users/yangtao/Documents/plugins/rtos/threadx/threadx_6p5.py) 列出 threads/semaphores/mutexes/queues

10. **[tests/qemu_m4_threadx/test_qemu_m4_threadx.py](file:///Users/yangtao/Documents/tests/qemu_m4_threadx/test_qemu_m4_threadx.py)**
    - 10 测试（结构性属性）：
      1. `test_threadx_elf_exists`
      2. `test_threadx_elf_header`
      3. `test_tx_thread_list_non_null`：`_tx_thread_list` 解析为非 0 指针
      4. `test_tx_thread_struct_in_dwarf`：`get_struct_type('TX_THREAD')` 不为 None
      5. `test_created_thread_count`：通过 `_tx_thread_list` 遍历，找到 ≥ 4 个 TX_THREAD
      6. `test_thread_names_in_expected_set`：找到的线程名集合 ⊇ {'Led', 'Sender', 'Receiver', 'Idle'}
      7. `test_mutex_struct_in_dwarf`：`get_struct_type('TX_MUTEX')` 不为 None
      8. `test_semaphore_struct_in_dwarf`：`get_struct_type('TX_SEMAPHORE')` 不为 None
      9. `test_baremetal_assert_data_intact`：裸机断言数据填充正确
      10. `test_threadx_plugin_loadable`：构造 `ThreadX6p5Plugin` 实例，`initialize(context)` 不抛

**插件兼容性策略**：
- 先尝试 [plugins/rtos/threadx/threadx_6p5.py](file:///Users/yangtao/Documents/plugins/rtos/threadx/threadx_6p5.py)
- 该插件依赖 `_tx_thread_list`、`_tx_semaphore_list`、`_tx_mutex_list`、`_tx_queue_list`、`_tx_heap_pool`
- ThreadX v6.5.1 真实符号是 `_tx_thread_created_ptr`（链表头）、`_tx_thread_created_count`、`_tx_mutex_created_ptr` 等，**与插件预期不一致**
- 应对：新增 `plugins/rtos/threadx/threadx_6p5_v2.py`，把符号名换成真实的 `_tx_*_created_ptr` 链表，遍历 `tx_thread_created_next` 字段
- 或在 firmware 里建一个 wrapper：把真实 ThreadX 链表头导出为 `_tx_thread_list` 等别名（更省事）

**验证**：
```bash
bash firmware/qemu_m4_threadx/build.sh
python3 firmware/qemu_m4_threadx/run_qemu.py
python3 firmware/qemu_m4_threadx/show_parsed.py
python3 -m unittest tests.qemu_m4_threadx.test_qemu_m4_threadx -v
# 期望：10 测试通过
```

### Phase 6 — 端到端回归（30 分钟）

1. **全量单元测试**：
   ```bash
   python3 -m unittest discover -s tests -p 'test_*.py'
   ```
   期望 76 测试全通过（45 现有 + 10 R52 + 11 AArch64 + 10 RISC-V + 10 FreeRTOS + 10 ThreadX = 96，**实际可能因 RTOS 时序 1-2 个 flaky**，允许通过率 ≥ 95%）

2. **端到端 CLI 验证**：
   ```bash
   # FreeRTOS 端到端
   python3 main.py --profile test/qemu_m4_freertos \
     --elf firmware/qemu_m4_freertos/test_firmware_freertos.elf \
     --dump firmware/qemu_m4_freertos/test_dump_freertos.bin
   # ThreadX 端到端
   python3 main.py --profile test/qemu_m4_threadx \
     --elf firmware/qemu_m4_threadx/test_firmware_threadx.elf \
     --dump firmware/qemu_m4_threadx/test_dump_threadx.bin
   ```
   期望：main.py 加载 RTOS 插件，打印任务列表（含 4 任务名 + 优先级）

3. **每场景 show_parsed.py 人工检查**：
   ```bash
   for s in bss_simulated qemu_m4_bare qemu_r52_bare qemu_aarch64_bare qemu_riscv_bare qemu_m4_freertos qemu_m4_threadx; do
     echo "=== $s ==="
     python3 firmware/$s/show_parsed.py 2>&1 | tail -20
   done
   ```
   期望：每场景输出含「g_system_ticks = 5234567」+ 4 个 assert_info + 8 个 test_point + 20 条 trace

## 关键技术决策

1. **R52 测试文件修复**：仅补全末行截断，不重写整个文件。已确认前 200 行内容正确。

2. **AArch64 RAM 16KB**：与 R52 同理，`.text` 在 RAM 里（全 RAM 布局），需覆盖代码 + BSS。32KB 安全值，避免再撞 dump 大小坑。

3. **RISC-V sifive_e boot**：先用 `-device loader,file=elf.elf`（遵循 VMA，mask ROM 跳 0x20000000）；若 entry 不在 0x20000000，调整 linker 让 `_start` 强制放 0x20000000。备选：`virt -bios elf.elf` + 单区域 RAM dump（牺牲多区域验证）。

4. **RISC-V 多区域 dump 拼接**：现有 [core/dump_reader.py](file:///Users/yangtao/Documents/core/dump_reader.py) 支持多区域（`regions` 列表），但 `run_qemu.py` 的 `run_and_dump_multi_region` 输出 `dump.<region>.bin` 后缀文件。需确认 DumpReader 能从 `<base>.<region>.bin` 加载；若不能，扩展 DumpReader 或在 run_qemu.py 里拼一个合并版主 dump。

5. **RTOS 测试结构性而非动态性**：所有 RTOS 测试断言「指针非空」「struct 在 DWARF 中存在」「plugin 可加载」「创建数量 ≥ 4」等结构性属性，不断言「任务 X 在 running 状态」「队列里有 N 条消息」等时序敏感值。

6. **FreeRTOS/ThreadX 符号别名**：若插件预期符号与 RTOS 实际不符，优先在 firmware 里建别名 wrapper（一行 `TCB_t * volatile pxCurrentTCB = (TCB_t*)&pxCurrentTCB_xxx;` 之类），不改插件。若无法别名，新增 `freertos_11p3.py` 或 `threadx_6p5_v2.py`。

7. **RTOS `simulate_runtime()` 兼容**：所有 RTOS main.c 顶部先调 `firmware_init()` + `simulate_runtime()`，再启动 scheduler。这样裸机断言数据填充与 M4 一致，测试 #9（test_baremetal_assert_data_intact）期望值不变。

8. **保留 FreeRTOSConfig.h / tx_user.h 在场景目录**：不放 `_common/`，因配置可能场景特定。

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| AArch64 QEMU `-kernel` 不跳 entry | 检查 entry 是否在 0x40000000+；若不跳，加 `-bios elf.elf` |
| RISC-V sifive_e 跳 0x20000000 失败 | 回退 `virt -bios`，单区域 RAM，放弃多区域验证（可后续补救） |
| FreeRTOS V11.3.0 与 11p0 插件不兼容 | 先 alias，不行就 `freertos_11p3.py` |
| ThreadX 6.5.1 符号与 6p5 插件不兼容 | 同上：alias 或 `threadx_6p5_v2.py` |
| RTOS 编译失败（port 汇编不兼容） | 检查 ARM_CM4F port 是否需要 `-mfpu=fpv4-sp-d16 -mfloat-abi=hard`；ThreadX port 是否要 `-DTX_ENABLE_STACK_CHECKING` |
| 任务栈溢出 | configMINIMAL_STACK_SIZE 调大到 256，任务栈 1024 字节 |
| heap_4 不够 | configTOTAL_HEAP_SIZE 调到 32K，ram_size 64K 够 |
| 多区域 dump DumpReader 不支持后缀 | 改 run_qemu.py 拼接主 dump 或扩展 DumpReader 接受 list of (path, region) |

## 执行策略

1. **Phase 3.1 修复**（10 分钟，立即解锁 55 测试基线）
2. **Phase 3.2 AArch64**（验证 64 位修复，最高价值先做）
3. **Phase 3.3 RISC-V**（多区域 dump，独立验证项）
4. **Phase 4 FreeRTOS**（最复杂，4-6 小时）
5. **Phase 5 ThreadX**（与 FreeRTOS 类似，4-6 小时）
6. **Phase 6 端到端**（30 分钟，最后清理）

每 Phase 完成立即跑测试 + show_parsed，确认基线后再进下一 Phase。可分批暂停，每个 Phase 自包含可验证。

## 假设

1. 用户已确认走「FreeRTOS + ThreadX 都做」「四个全做」（之前 AskUserQuestion 已答）
2. 工具链与 QEMU 已就位（已验证）
3. 现有 45 测试通过基线稳固（已验证，无 skip）
4. RTOS 源码可 git clone（网络可用）
5. FreeRTOS/ThreadX 在 M4 上跑得起来（标准 ARM_CM4F port 已成熟）
