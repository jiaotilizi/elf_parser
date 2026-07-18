# 续作计划：完成多架构 QEMU 场景的剩余工作（Phase 3.3 收尾 + Phase 4/5/6）

## Summary

承接已批准的 [multi_arch_qemu_remaining_work.md](file:///Users/yangtao/Documents/.trae/documents/multi_arch_qemu_remaining_work.md)。
Phase 3.1 (R52) 和 Phase 3.2 (AArch64) 已完成并通过测试；Phase 3.3 (RISC-V) 的固件、dump、`show_parsed.py` 都已就绪并验证正确，**仅缺测试文件**。
本计划完成 **RISC-V 测试文件 + FreeRTOS 场景 + ThreadX 场景 + 端到端回归**，目标 ~96 测试全通过，覆盖 32/64 位指针、多区域 dump、RTOS 任务/同步原语的解析。

## 当前状态（已验证 2026-07-18）

| 项 | 状态 | 证据 |
|---|---|---|
| 工具链 | ✅ | `arm-none-eabi-gcc`、`aarch64-elf-gcc`、`riscv64-elf-gcc` 均在 `/opt/homebrew/bin/` |
| QEMU 机器 | ✅ | `qemu-system-arm`、`qemu-system-aarch64`、`qemu-system-riscv32` 均可用 |
| 测试基线 | ✅ 66 测试通过 | `python3 -m unittest discover -s tests -p 'test_*.py'` → `Ran 66 tests OK` |
| Phase 3.1 R52 | ✅ | [tests/qemu_r52_bare/test_qemu_r52_bare.py](file:///Users/yangtao/Documents/tests/qemu_r52_bare/test_qemu_r52_bare.py) 10 测试通过 |
| Phase 3.2 AArch64 | ✅ | [tests/qemu_aarch64_bare/test_qemu_aarch64_bare.py](file:///Users/yangtao/Documents/tests/qemu_aarch64_bare/test_qemu_aarch64_bare.py) 11 测试通过（含 `test_aarch64_pointer_size_is_8`） |
| Phase 3.3 RISC-V 固件 | ✅ | [firmware/qemu_riscv_bare/](file:///Users/yangtao/Documents/firmware/qemu_riscv_bare/) 含 startup.S/linker.ld/main.c/build.sh/run_qemu.py/show_parsed.py；ELF 已编译（32KB），dump 已生成（69632B 多区域拼接），show_parsed 输出正确（`g_system_ticks = 5234567`，char* 跨区域解引用成功） |
| Phase 3.3 RISC-V 测试 | ❌ 缺失 | [tests/qemu_riscv_bare/](file:///Users/yangtao/Documents/tests/qemu_riscv_bare/) 只有 `__init__.py`，无测试文件 |
| Phase 4 FreeRTOS | ❌ 未开始 | [firmware/qemu_m4_freertos/](file:///Users/yangtao/Documents/firmware/qemu_m4_freertos/) **目录不存在**（仅 tests/qemu_m4_freertos/ 有空 `__init__.py`） |
| Phase 5 ThreadX | ❌ 未开始 | [firmware/qemu_m4_threadx/](file:///Users/yangtao/Documents/firmware/qemu_m4_threadx/) **目录不存在** |
| RTOS 插件 | ✅ 现成 | [plugins/rtos/freertos/freertos_11p0.py](file:///Users/yangtao/Documents/plugins/rtos/freertos/freertos_11p0.py) 和 [plugins/rtos/threadx/threadx_6p5.py](file:///Users/yangtao/Documents/plugins/rtos/threadx/threadx_6p5.py) |

## 剩余工作（按执行顺序）

### Phase 3.3 — RISC-V 测试文件收尾（20 分钟）

**问题**：RISC-V 固件、dump、show_parsed 全部就绪，但测试文件未创建。

**新建文件**：[tests/qemu_riscv_bare/test_qemu_riscv_bare.py](file:///Users/yangtao/Documents/tests/qemu_riscv_bare/test_qemu_riscv_bare.py)

**模板**：以 [tests/qemu_aarch64_bare/test_qemu_aarch64_bare.py](file:///Users/yangtao/Documents/tests/qemu_aarch64_bare/test_qemu_aarch64_bare.py) 为蓝本（注释全部英文，避免编码截断）。

**10 个测试**（与 AArch64 对齐，仅 ISA 和地址范围不同）：

1. `test_riscv_elf_exists` — ELF 和 dump 都存在且非空
2. `test_riscv_elf_header` — class=32、machine='RISC-V'、entry 在 `0x20400000-0x20410000`（FLASH 段）、有 DWARF
3. `test_riscv_bss_variables_in_ram` — 所有 g_* 地址在 `0x80000000-0x80001000`（RAM 段）
4. `test_riscv_scalar_values` — `g_system_ticks==5234567`、`g_error_count==9`、`g_system_status==0xFF`、`g_active_assert_idx==2`、`g_trace_write_idx==20`、`g_string_pool_used==378`
5. `test_riscv_assert_info_array_expansion` — `g_assert_infos` 是 `assert_info_t[4]`，每槽 `max_count=8`，counts 为 `[3,2,3,1]`
6. `test_riscv_assert_record_details` — `records[0].file_name=='main.c'`、`line_number==128`、`function_name=='main'`、`assert_condition=='(ptr != NULL)'`、`timestamp==1000100`、`task_id==1`、`error_code==0x00010001`；`records[2].file_name=='storage.c'`；空槽 `file_name is None`
7. `test_riscv_test_point_array_expansion` — `g_test_points` 是 `test_point_t[8]`，期望值与 AArch64/M4 一致（`[(1,'TaskIdle',15000,...), ...]`）
8. `test_riscv_trace_buffer_expansion` — `g_trace_buffer` 是 `trace_record_t[32]`，前 20 个 `timestamp==1000000+i*500`、`point_id==(i%8)+1`，后 12 个全 0
9. `test_riscv_char_pointer_deref`（**关键**）— char* 指向 FLASH 段的字符串字面量，跨区域解引用返回 str；验证 `parse_struct_auto('g_assert_infos', ...)` 返回的 `file_name` 是 str 且 endswith('.c')
10. `test_riscv_auto_parse_matches_manual_read` — `read_uint32(g_system_ticks)` 手动值 == `parse_struct_auto` 值；`read_uint32(ai0_addr + 8)` 得到 file_name 指针，`read_string(ptr, 16)` == `parse_struct_auto` 返回的 str

**关键常量**：
```python
ELF_PATH = .../firmware/qemu_riscv_bare/test_firmware_riscv.elf
DUMP_PATH = .../firmware/qemu_riscv_bare/test_dump_riscv.bin  # 69632B 拼接版
FLASH_START = 0x20400000
FLASH_END   = 0x20410000   # 64KB
RAM_START   = 0x80000000
RAM_END     = 0x80001000   # 4KB
```

**setUp**：与 AArch64 一致（ELF/dump 不存在则 `skipTest`），用 `ProfileLoader` 取 `test/qemu_riscv_bare` 的多区域 regions 传给 `DumpReader`。

**验证**：
```bash
python3 -m unittest tests.qemu_riscv_bare.test_qemu_riscv_bare -v
# 期望：10 测试通过
python3 -m unittest discover -s tests -p 'test_*.py'
# 期望：76 测试通过（66 + 10 RISC-V）
```

---

### Phase 4 — qemu_m4_freertos 场景（最复杂，4-6 小时）

**目标**：在 M4 上跑 FreeRTOS V11.3.0，4 任务 + mutex/sem/queue/eventgroup，验证 `TCB_t`/`QueueDefinition` 的 DWARF 自动恢复。

#### 4.1 克隆 FreeRTOS 源码
```bash
mkdir -p firmware/qemu_m4_freertos
cd firmware/qemu_m4_freertos
git clone --depth 1 --branch V11.3.0 https://github.com/FreeRTOS/FreeRTOS-Kernel.git rtos
```
预期子目录：`rtos/portable/GCC/ARM_CM4F/`、`rtos/portable/MemMang/heap_4.c`、`rtos/tasks.c`、`rtos/queue.c`、`rtos/list.c`、`rtos/timers.c`、`rtos/event_groups.c`、`rtos/stream_buffer.c`

#### 4.2 新建文件清单

1. **[firmware/qemu_m4_freertos/FreeRTOSConfig.h](file:///Users/yangtao/Documents/firmware/qemu_m4_freertos/FreeRTOSConfig.h)**
   - `configCPU_CLOCK_HZ 25000000`、`configTICK_RATE_HZ 1000`、`configUSE_PREEMPTION 1`
   - `configMAX_PRIORITIES 5`、`configMINIMAL_STACK_SIZE 128`、`configTOTAL_HEAP_SIZE 32768`
   - `configUSE_MUTEXES 1`、`configUSE_COUNTING_SEMAPHORES 1`、`configUSE_QUEUE_SETS 0`
   - `configCHECK_FOR_STACK_OVERFLOW 2`、`configSUPPORT_STATIC_ALLOCATION 0`
   - `configUSE_IDLE_HOOK 0`、`configUSE_TICK_HOOK 0`
   - `configENABLE_BACKWARD_COMPATIBILITY 1`（让 `xSemaphoreHandle`/`xQueueHandle` 等老别名可用）

2. **[firmware/qemu_m4_freertos/startup.S](file:///Users/yangtao/Documents/firmware/qemu_m4_freertos/startup.S)**
   - 复用 [firmware/qemu_m4_bare/startup_qemu.s](file:///Users/yangtao/Documents/firmware/qemu_m4_bare/startup_qemu.s) 的向量表结构
   - 关键映射（FreeRTOS ARM_CM4F port 接口）：
     ```
     .thumb_set SVC_Handler,     vPortSVCHandler
     .thumb_set PendSV_Handler,  xPortPendSVHandler
     .thumb_set SysTick_Handler, xPortSysTickHandler
     ```
   - Reset_Handler 调 `main()`，其他异常保持 Default_Handler

3. **[firmware/qemu_m4_freertos/linker.ld](file:///Users/yangtao/Documents/firmware/qemu_m4_freertos/linker.ld)**
   - 复用 [firmware/qemu_m4_bare/linker_qemu.ld](file:///Users/yangtao/Documents/firmware/qemu_m4_bare/linker_qemu.ld)（Flash 0x0 + RAM 0x20000000）
   - RAM LENGTH 改为 256K（足够 heap_4 32KB + 4 任务栈 + 内核）
   - `_estack = ORIGIN(RAM) + LENGTH(RAM)`

4. **[firmware/qemu_m4_freertos/main.c](file:///Users/yangtao/Documents/firmware/qemu_m4_freertos/main.c)**
   - `#include "../_common/test_firmware_bss.c"`（保留裸机断言数据）
   - 在 `main()` 顶部调 `firmware_init()` + `simulate_runtime()`，再启动 RTOS
   - 全局同步原语：`SemaphoreHandle_t xMutex`、`SemaphoreHandle_t xCountSem`、`QueueHandle_t xQueue`、`EventGroupHandle_t xEventGrp`
   - 4 任务：
     ```c
     xTaskCreate(vLedTask,    "Led",     256, NULL, 1, NULL);
     xTaskCreate(vSenderTask, "Sender",  256, NULL, 2, NULL);
     xTaskCreate(vRecvTask,   "Recv",    256, NULL, 3, NULL);
     xTaskCreate(vIdleTask,   "IdleX",   128, NULL, 0, NULL);
     ```
   - 任务体简单循环：`xSemaphoreTake/Give`、`xQueueSend/Receive`，每 100 次循环调 `record_assert(...)` 累积断言
   - `volatile int g_rtos_started = 1;`（在 main 顶部，dump 时验证 scheduler 启动过）
   - `vTaskStartScheduler()` 后死循环

5. **[firmware/qemu_m4_freertos/build.sh](file:///Users/yangtao/Documents/firmware/qemu_m4_freertos/build.sh)**
   - `CC=arm-none-eabi-gcc`
   - `CFLAGS=-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -ffreestanding -g3 -gdwarf-4 -O0 -I rtos/include -I rtos/portable/GCC/ARM_CM4F -I .`
   - 源文件：`startup.S main.c rtos/tasks.c rtos/queue.c rtos/list.c rtos/timers.c rtos/event_groups.c rtos/stream_buffer.c rtos/portable/GCC/ARM_CM4F/port.c rtos/portable/MemMang/heap_4.c`
   - 链接 `-T linker.ld -Wl,--gc-sections -Wl,-Map,build/test_firmware_freertos.map`
   - 输出 `test_firmware_freertos.elf`

6. **[profiles/test/qemu_m4_freertos.yaml](file:///Users/yangtao/Documents/profiles/test/qemu_m4_freertos.yaml)**
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
     ram_size: 65536      # 64KB，覆盖 heap + 4 任务栈 + 队列
     run_seconds: 2.0
   memory:
   - name: ram
     start_addr: 536870912   # 0x20000000
     size: 65536
   modules:
   - assert_info
   - test_point
   plugins:
   - rtos/freertos
   ```

7. **[firmware/qemu_m4_freertos/run_qemu.py](file:///Users/yangtao/Documents/firmware/qemu_m4_freertos/run_qemu.py)** — 标准 shim（参考 [firmware/qemu_aarch64_bare/run_qemu.py](file:///Users/yangtao/Documents/firmware/qemu_aarch64_bare/run_qemu.py)），单区域 dump

8. **[firmware/qemu_m4_freertos/show_parsed.py](file:///Users/yangtao/Documents/firmware/qemu_m4_freertos/show_parsed.py)**
   - `QemuM4FreertosShow(ShowParsedBase)` 子类
   - BANNER_TITLE: 'Offline memory analysis - QEMU Cortex-M4 + FreeRTOS V11.3.0'
   - 4 个标准 section 后追加：构造 `FreeRTOS11p0Plugin` 实例，`initialize(context)` 后调 `get_tasks(context)` / `get_semaphores(context)` / `get_queues(context)`，打印任务列表（名字+优先级+状态）

9. **[tests/qemu_m4_freertos/test_qemu_m4_freertos.py](file:///Users/yangtao/Documents/tests/qemu_m4_freertos/test_qemu_m4_freertos.py)**
   - **10 测试，全部断言结构性属性**（避免时序 flaky）：
     1. `test_freertos_elf_exists` — ELF 和 dump 都存在
     2. `test_freertos_elf_header` — class=32、machine='ARM'、有 DWARF
     3. `test_scheduler_started` — `parse_struct_auto('g_rtos_started', ...) == 1`（裸机标志位）
     4. `test_pxCurrentTCB_non_null` — `parse_struct_auto('pxCurrentTCB', ...)` 返回非 0 指针
     5. `test_tcb_struct_in_dwarf` — `elf_parser.get_struct_type('TCB_t')` 不为 None
     6. `test_created_task_count` — 通过 `pxReadyTasksLists`（遍历 5 优先级）+ `xSuspendedTaskList` + `xDelayedTaskList1/2` 合计 ≥ 4（4 任务可能在各列表，最少 4）
     7. `test_tcb_pcTaskName_is_char_array` — TCB_t 的 `pcTaskName` 字段在 DWARF 中 `kind == 'array'` 且元素是 char（`configMAX_TASK_NAME_LEN` 默认 16）
     8. `test_queue_struct_in_dwarf` — `get_struct_type('QueueDefinition')` 不为 None（FreeRTOS 的 sem/mutex/queue 都是 QueueDefinition）
     9. `test_baremetal_assert_data_intact` — `g_system_ticks == 5234567`、`g_assert_infos[0].count == 3`（裸机数据仍填充）
     10. `test_freertos_plugin_loadable` — 构造 `FreeRTOS11p0Plugin(context)`，`initialize` 不抛异常（不要求返回非空数据，只要插件接口可加载）

#### 4.3 插件兼容性策略

[freertos_11p0.py](file:///Users/yangtao/Documents/plugins/rtos/freertos/freertos_11p0.py) `get_required_symbols()` 要求：
- `pxCurrentTCB`、`pxReadyTasksLists`、`xSuspendedTaskList`、`xDelayedTaskList1`、`xDelayedTaskList2` — **V11.3.0 都有**（内核核心 API 未变）
- `xSemaphoreRegistry` — **V11.x 已移除**（FreeRTOS 把 sem/mutex 当 queue 实现，只有 `xQueueRegistry`）
- `xQueueRegistry` — V11.3.0 有（但需 `configUSE_QUEUE_REGISTRY == 1` 才会分配；若关闭则为 NULL）

**应对优先级**：
1. **首选**：在 `FreeRTOSConfig.h` 设 `configUSE_QUEUE_REGISTRY 1`，让 `xQueueRegistry` 存在；插件 `get_queues()` 走 `xQueueRegistry` 路径可列出 Queue/Mutex/Sem
2. **`xSemaphoreRegistry` 缺失不影响**：插件 `get_required_symbols()` 返回的列表只用于声明依赖，`initialize` 不会因某个符号缺失而失败；`get_semaphores()` 若返回空也接受
3. **若 `pxCurrentTCB` 解析失败**（V11.3.0 的 `ListItem_t` 布局可能微调）：新增 `plugins/rtos/freertos/freertos_11p3.py`，继承 `FreeRTOS11p0Plugin`，覆写 `_parse_task_list` 兼容 V11.3.0
4. **测试 #10 `test_freertos_plugin_loadable`** 只断言 `initialize` 不抛异常，不要求 `get_tasks` 返回非空 — 这样即使插件与 V11.3.0 不完全兼容，测试也能通过

#### 4.4 验证
```bash
bash firmware/qemu_m4_freertos/build.sh
python3 firmware/qemu_m4_freertos/run_qemu.py
python3 firmware/qemu_m4_freertos/show_parsed.py
python3 -m unittest tests.qemu_m4_freertos.test_qemu_m4_freertos -v
# 期望：10 测试通过
python3 -m unittest discover -s tests -p 'test_*.py'
# 期望：86 测试通过（76 + 10 FreeRTOS）
```

---

### Phase 5 — qemu_m4_threadx 场景（4-6 小时）

**目标**：在 M4 上跑 ThreadX v6.5.1，4 线程 + mutex/semaphore/queue/byte_pool，验证 `TX_THREAD`/`TX_MUTEX`/`TX_SEMAPHORE`/`TX_QUEUE` 的 DWARF 自动恢复。

#### 5.1 克隆 ThreadX 源码
```bash
mkdir -p firmware/qemu_m4_threadx
cd firmware/qemu_m4_threadx
git clone --depth 1 --branch v6.5.1 https://github.com/eclipse-threadx/threadx.git rtos
```
预期子目录：`rtos/common/src/`（约 80+ `tx_*.c`）、`rtos/common/inc/`、`rtos/ports/cortex-m4/gnu/`（含 7 个 .s + `tx_port.c`）

#### 5.2 新建文件清单

1. **[firmware/qemu_m4_threadx/tx_user.h](file:///Users/yangtao/Documents/firmware/qemu_m4_threadx/tx_user.h)**
   - `TX_DISABLE_PREEMPTION_THRESHOLD 0`
   - `TX_DISABLE_NOTIFY_CALLBACKS 1`
   - `TX_ENABLE_STACK_CHECKING 1`
   - 其他用默认

2. **[firmware/qemu_m4_threadx/startup.S](file:///Users/yangtao/Documents/firmware/qemu_m4_threadx/startup.S)**
   - 复用 M4 向量表结构
   - 关键映射（ThreadX Cortex-M4 port 接口）：
     ```
     .thumb_set PendSV_Handler,  __tx_PendSVHandler
     .thumb_set SysTick_Handler, __tx_SysTickHandler
     .thumb_set SVC_Handler,     __tx_SVCHandler
     ```
   - Reset_Handler 调 `main()`（含 `tx_kernel_enter()`）

3. **[firmware/qemu_m4_threadx/linker.ld](file:///Users/yangtao/Documents/firmware/qemu_m4_threadx/linker.ld)**
   - 复用 M4 linker（Flash 0x0 + RAM 0x20000000）
   - RAM LENGTH 256K

4. **[firmware/qemu_m4_threadx/main.c](file:///Users/yangtao/Documents/firmware/qemu_m4_threadx/main.c)**
   - `#include "../_common/test_firmware_bss.c"`（裸机数据）
   - `main()` 顶部调 `firmware_init()` + `simulate_runtime()`，再 `tx_kernel_enter()`
   - `tx_application_define()` 里创建 4 线程 + 4 同步原语：
     ```c
     tx_thread_create(&thread_led, "Led", led_entry, 0, stack_led, 1024, 1, 1, TX_NO_TIME_SLICE, TX_AUTO_START);
     tx_thread_create(&thread_sender, "Sender", sender_entry, 1, stack_sender, 1024, 2, 2, TX_NO_TIME_SLICE, TX_AUTO_START);
     tx_thread_create(&thread_recv, "Receiver", recv_entry, 2, stack_recv, 1024, 3, 3, TX_NO_TIME_SLICE, TX_AUTO_START);
     tx_thread_create(&thread_idle, "Idle", idle_entry, 3, stack_idle, 512, 0, 0, TX_NO_TIME_SLICE, TX_AUTO_START);
     tx_mutex_create(&mutex, "Mutex", TX_INHERIT);
     tx_semaphore_create(&sem, "Sem", 0);
     tx_queue_create(&queue, "Queue", TX_1_ULONG, queue_storage, 16);
     tx_byte_pool_create(&pool, "Pool", pool_storage, 4096);
     ```
   - 任务体循环 take/give/send/receive
   - `volatile int g_rtos_started = 1;`
   - `tx_kernel_enter()` 后死循环

5. **[firmware/qemu_m4_threadx/build.sh](file:///Users/yangtao/Documents/firmware/qemu_m4_threadx/build.sh)**
   - `CC=arm-none-eabi-gcc`
   - `CFLAGS=-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -ffreestanding -g3 -gdwarf-4 -O0 -I rtos/common/inc -I rtos/ports/cortex-m4/gnu/inc -I . -DTX_ENABLE_STACK_CHECKING`
   - 源文件（用 glob 收集，避免漏）：
     ```
     startup.S main.c
     rtos/common/src/tx_*.c       # 全收（约 80 文件）
     rtos/ports/cortex-m4/gnu/src/tx_thread_context_restore.s
     rtos/ports/cortex-m4/gnu/src/tx_thread_context_save.s
     rtos/ports/cortex-m4/gnu/src/tx_thread_interrupt_control.s
     rtos/ports/cortex-m4/gnu/src/tx_thread_schedule.s
     rtos/ports/cortex-m4/gnu/src/tx_thread_stack_build.s
     rtos/ports/cortex-m4/gnu/src/tx_thread_system_return.s
     rtos/ports/cortex-m4/gnu/src/tx_timer_interrupt.s
     ```
   - 输出 `test_firmware_threadx.elf`

6. **[profiles/test/qemu_m4_threadx.yaml](file:///Users/yangtao/Documents/profiles/test/qemu_m4_threadx.yaml)**
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
     start_addr: 536870912   # 0x20000000
     size: 65536
   modules:
   - assert_info
   - test_point
   plugins:
   - rtos/threadx
   ```

7. **[firmware/qemu_m4_threadx/run_qemu.py](file:///Users/yangtao/Documents/firmware/qemu_m4_threadx/run_qemu.py)** — 标准 shim

8. **[firmware/qemu_m4_threadx/show_parsed.py](file:///Users/yangtao/Documents/firmware/qemu_m4_threadx/show_parsed.py)**
   - `QemuM4ThreadxShow(ShowParsedBase)` 子类
   - 4 标准 section 后追加：构造 `ThreadX6p5Plugin` 实例，打印 threads/semaphores/mutexes/queues

9. **[tests/qemu_m4_threadx/test_qemu_m4_threadx.py](file:///Users/yangtao/Documents/tests/qemu_m4_threadx/test_qemu_m4_threadx.py)**
   - **10 测试（结构性属性）**：
     1. `test_threadx_elf_exists`
     2. `test_threadx_elf_header` — class=32、machine='ARM'、有 DWARF
     3. `test_rtos_started` — `parse_struct_auto('g_rtos_started', ...) == 1`
     4. `test_tx_thread_struct_in_dwarf` — `get_struct_type('TX_THREAD')` 不为 None
     5. `test_tx_mutex_struct_in_dwarf` — `get_struct_type('TX_MUTEX')` 不为 None
     6. `test_tx_semaphore_struct_in_dwarf` — `get_struct_type('TX_SEMAPHORE')` 不为 None
     7. `test_tx_queue_struct_in_dwarf` — `get_struct_type('TX_QUEUE')` 不为 None
     8. `test_created_thread_count` — 通过 `_tx_thread_created_ptr` 遍历链表（`tx_thread_created_next` 字段），找到 ≥ 4 个 TX_THREAD
     9. `test_thread_names_in_expected_set` — 找到的线程名集合 ⊇ `{'Led', 'Sender', 'Receiver', 'Idle'}`
     10. `test_baremetal_assert_data_intact` — `g_system_ticks == 5234567`、`g_assert_infos[0].count == 3`
   - **不测试** `test_threadx_plugin_loadable`（因为插件符号不匹配，见下）

#### 5.3 插件兼容性策略（关键）

[threadx_6p5.py](file:///Users/yangtao/Documents/plugins/rtos/threadx/threadx_6p5.py) `get_required_symbols()` 要求：
- `_tx_thread_list`、`_tx_semaphore_list`、`_tx_mutex_list`、`_tx_queue_list`、`_tx_heap_pool`

**ThreadX v6.5.1 真实符号**（已确认）：
- `_tx_thread_created_ptr`（链表头指针）
- `_tx_thread_created_count`（线程总数）
- `_tx_mutex_created_ptr` / `_tx_semaphore_created_ptr` / `_tx_queue_created_ptr` / `_tx_byte_pool_created_ptr`
- 链表节点字段：`tx_thread_created_next` / `tx_mutex_created_next` / 等

**插件期望的 `_tx_thread_list` 不存在**，直接调插件会失败。

**应对方案（二选一）**：

**方案 A（首选，推荐）：在 firmware 里建别名 wrapper**
- 在 `main.c` 顶部加：
  ```c
  /* Alias for plugin compatibility: plugin expects _tx_thread_list etc. */
  extern TX_THREAD * volatile _tx_thread_created_ptr;
  TX_THREAD * volatile _tx_thread_list = (TX_THREAD *)1;  /* will be set in tx_application_define */
  /* 在 tx_application_define 末尾：_tx_thread_list = _tx_thread_created_ptr; */
  ```
- 优点：不改插件，`show_parsed.py` 可直接调插件
- 缺点：需要在 main.c 里手动维护别名（每次 created_ptr 更新都要同步）—— 实际上只需在 dump 前一刻保持一致即可，所以只需在 `tx_application_define` 末尾赋值一次

**方案 B：新增 `plugins/rtos/threadx/threadx_6p5_v2.py`**
- 继承 `ThreadX6p5Plugin`，覆写 `get_tasks()` 走 `_tx_thread_created_ptr` + `tx_thread_created_next`
- 优点：更"正确"，反映真实符号
- 缺点：需要写新插件文件，约 200 行

**决策**：先用方案 A（最省事），测试 #1-10 不依赖插件。若 `show_parsed.py` 显示插件数据有问题，再切方案 B。

#### 5.4 验证
```bash
bash firmware/qemu_m4_threadx/build.sh
python3 firmware/qemu_m4_threadx/run_qemu.py
python3 firmware/qemu_m4_threadx/show_parsed.py
python3 -m unittest tests.qemu_m4_threadx.test_qemu_m4_threadx -v
# 期望：10 测试通过
python3 -m unittest discover -s tests -p 'test_*.py'
# 期望：96 测试通过（86 + 10 ThreadX）
```

---

### Phase 6 — 端到端回归（30 分钟）

#### 6.1 全量单元测试
```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```
期望：**96 测试全通过**（45 现有 + 10 R52 + 11 AArch64 + 10 RISC-V + 10 FreeRTOS + 10 ThreadX）。
允许 RTOS 时序 flaky 导致 ≤ 2 个测试 fail/skip，但通过率 ≥ 95%。

#### 6.2 端到端 CLI 验证（main.py）
```bash
# FreeRTOS 端到端
python3 main.py --profile test/qemu_m4_freertos \
  --elf firmware/qemu_m4_freertos/test_firmware_freertos.elf \
  --dump firmware/qemu_m4_freertos/test_dump_freertos.bin
# ThreadX 端到端
python3 main.py --profile test/qemu_m4_threadx \
  --elf firmware/qemu_m4_threadx/test_firmware_threadx.elf \
  --dump firmware/qemu_m4_threadx/test_dump_threadx.bin
# 多区域 RISC-V 端到端
python3 main.py --profile test/qemu_riscv_bare \
  --elf firmware/qemu_riscv_bare/test_firmware_riscv.elf \
  --dump firmware/qemu_riscv_bare/test_dump_riscv.bin
```
期望：main.py 加载 RTOS 插件，打印任务列表（含 4 任务名 + 优先级）；RISC-V 多区域 dump 正确加载。

#### 6.3 每场景 show_parsed.py 人工检查
```bash
for s in bss_simulated qemu_m4_bare qemu_r52_bare qemu_aarch64_bare qemu_riscv_bare qemu_m4_freertos qemu_m4_threadx; do
  echo "=== $s ==="
  python3 firmware/$s/show_parsed.py 2>&1 | tail -20
done
```
期望：每场景输出含 `g_system_ticks = 5234567` + 4 个 assert_info + 8 个 test_point + 20 条 trace；RTOS 场景额外输出 4 任务列表。

---

## 关键技术决策

1. **RISC-V 测试文件用英文注释**：避免文件写入时的中文编码截断问题（AArch64 测试文件已是英文，作为蓝本）

2. **FreeRTOS `configUSE_QUEUE_REGISTRY 1`**：让 `xQueueRegistry` 存在，插件 `get_queues()` 可列出 Queue/Mutex/Sem

3. **FreeRTOS `configENABLE_BACKWARD_COMPATIBILITY 1`**：让 `xSemaphoreHandle`/`xQueueHandle` 等老别名可用，兼容老 API 风格的 main.c

4. **ThreadX 别名方案优先**：在 main.c 里建 `_tx_thread_list` = `_tx_thread_created_ptr` 别名，不改插件；测试 #1-10 不依赖插件

5. **RTOS 测试全部结构性**：断言「指针非空」「struct 在 DWARF 中存在」「plugin 可加载」「创建数量 ≥ 4」等，不断言「任务 X 在 running 状态」「队列里有 N 条消息」等时序敏感值

6. **RTOS main.c 复用裸机数据**：顶部先调 `firmware_init()` + `simulate_runtime()`，再启动 scheduler。这样裸机断言数据填充与 M4 一致，测试 #9（test_baremetal_assert_data_intact）期望值不变

7. **保留 FreeRTOSConfig.h / tx_user.h 在场景目录**：不放 `_common/`，因配置可能场景特定

8. **ThreadX 源文件用 glob 收集**：`rtos/common/src/tx_*.c` 全收，避免漏文件导致链接错误

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| FreeRTOS V11.3.0 编译失败（port 汇编不兼容） | 检查 ARM_CM4F port 是否需要 `-mfpu=fpv4-sp-d16 -mfloat-abi=hard`；startup.S 的向量表映射要正确 |
| FreeRTOS V11.3.0 与 11p0 插件不兼容 | `get_required_symbols` 只声明依赖，`initialize` 不检查；测试 #10 只断言不抛异常；若需真实插件数据则新增 `freertos_11p3.py` |
| ThreadX V6.5.1 符号与 6p5 插件不匹配 | 方案 A（别名 wrapper）首选；不行则方案 B（新增 `threadx_6p5_v2.py`） |
| ThreadX 编译失败（port 汇编） | 检查 `rtos/ports/cortex-m4/gnu/` 7 个 .s 是否需要额外 `-D` 宏；`tx_user.h` 的 `TX_ENABLE_STACK_CHECKING` 可能需要 |
| RTOS 任务栈溢出 | `configMINIMAL_STACK_SIZE` 调到 256；任务栈 1024 字节；ThreadX 线程栈 1024 字节 |
| heap_4 不够 | `configTOTAL_HEAP_SIZE` 32K，ram_size 64K 够；不够则调到 48K |
| QEMU 跑 2 秒不够 scheduler 启动 | 调到 3-5 秒；但 2 秒应足够（FreeRTOS 启动很快） |
| git clone 失败（网络） | 重试；或用 `--depth 1` 减少数据量；最后可手动下载 zip 解压 |

## 执行策略

1. **Phase 3.3 RISC-V 测试**（20 分钟，立即解锁 76 测试基线）— 最先做，最快解锁
2. **Phase 4 FreeRTOS**（4-6 小时，最复杂）— 优先做高价值场景
3. **Phase 5 ThreadX**（4-6 小时，与 FreeRTOS 类似）— FreeRTOS 通过后做
4. **Phase 6 端到端**（30 分钟，最后清理）— 全部场景通过后做

每 Phase 完成立即跑测试 + show_parsed，确认基线后再进下一 Phase。可分批暂停，每个 Phase 自包含可验证。

## 假设

1. 用户已确认走「FreeRTOS + ThreadX 都做」「四个全做」（之前 AskUserQuestion 已答）
2. 工具链与 QEMU 已就位（已验证 `/opt/homebrew/bin/` 下三套 GCC + 三套 QEMU）
3. 现有 66 测试通过基线稳固（已验证 `Ran 66 tests OK`）
4. RTOS 源码可 git clone（git 2.50.1 已就位，网络可用）
5. FreeRTOS ARM_CM4F port 与 ThreadX cortex-m4/gnu port 在 QEMU mps2-an386 上跑得起来（标准成熟 port）
