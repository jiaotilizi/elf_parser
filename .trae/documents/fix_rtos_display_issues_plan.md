# RTOS Display 问题修复计划

## 背景
通过运行 5 个 RTOS 场景的 display，发现 7 个问题。通过深入调试，已确认每个问题的根因。

## 问题 1：FreeRTOS 任务列表为空（mps3_an536）/ 不完整（mps2_an386）

**根因：** `_walk_doubly_linked_list` 在 `plugins/rtos/base.py:232-234` 使用 `pxIndex` 作为链表遍历起点，但 FreeRTOS 中 `pxIndex` 是调度器轮转指针，不是链表头。正确起点是 `xListEnd.pxNext`（List_t offset 12）。

当 `pxIndex` 指向 `xListEnd` 时（mps3_an536），`first_item_addr == list_end_addr` 直接返回空列表。

**修复：** 修改起始点从 `pxIndex`(offset 4) 改为 `xListEnd.pxNext`(offset 12)，`list_end_addr` 改为 `xListEnd` 地址(offset 8)。

**文件：** `plugins/rtos/base.py` 第 232-239 行

## 问题 2：FreeRTOS 任务名乱码/缺失

**根因：** `_parse_tcb` 在 `freertos_v11p3p0.py:228-232` 名字校验过严：包含 `\xff` 就返回 None 拒绝整个 TCB。FreeRTOS `pcTaskName` 是固定 16 字节数组，剩余字节可能含 0xFF。

**修复：** 改拒绝为清理（sanitize）：截断 `\x00`/`\xff` 后内容，保留可打印 ASCII。

**文件：** `plugins/rtos/freertos/freertos_v11p3p0.py` 第 228-232 行

## 问题 3：ThreadX mps2_an386 信号量计数错误

**根因：** dump 中 `tx_semaphore_count`(offset=8) 值为 5420073，非预期 1。mps3_an536 同 offset 数据正确(count=1)。这是 dump 数据异常，插件无防御性检查。

**修复：** 添加合理性检查：count > 0xFFFF 时记录警告并设为 0。

**文件：** `plugins/rtos/threadx/threadx_v6p5p1.py` 第 234-236 行

## 问题 4：ThreadX mps2_an386 缺少 thread_8/9

**根因：** **固件问题，非插件 bug。** thread_8/9 的 TCB 首字段为 0（未初始化），`tx_thread_create` 失败。byte_pool_0 仅 9120 字节，需要 10x1024=10240 字节栈空间，内存不足。

**修复：** 无需修改插件代码。

## 问题 5：FreeRTOS xQueueRegistry 出现在队列列表

**根因：** `_get_queues` 名字匹配 `'Queue' in s['name']` 匹配到 `xQueueRegistry`。

**修复：** 添加 `'Registry' not in s['name']` 过滤。

**文件：** `plugins/rtos/freertos/freertos_v11p3p0.py` 第 449-451 行

## 问题 6：FreeRTOS Mutex 未出现在 Semaphore 列表

**根因：** `_get_semaphores` 只匹配 `'Sem'`/`'sem'`，不匹配 `'Mutex'`。FreeRTOS 中 Mutex 是 Semaphore 的一种。

**修复：** 添加 `'Mutex' in s['name']` 匹配。

**文件：** `plugins/rtos/freertos/freertos_v11p3p0.py` 第 289-292 行

## 问题 7：FreeRTOS 定时器列表包含内部结构

**根因：** `_parse_timer_list` 包含所有 timer 结构，包括无名、period=0 的内部结构。

**修复：** 过滤掉无名字且 period=0 的 timer。

**文件：** `plugins/rtos/freertos/freertos_v11p3p0.py` 第 563-567 行

## 修改文件清单

1. `plugins/rtos/base.py` — `_walk_doubly_linked_list` 修复链表遍历起点
2. `plugins/rtos/freertos/freertos_v11p3p0.py` — 5 处修改
3. `plugins/rtos/threadx/threadx_v6p5p1.py` — 信号量计数合理性检查

## 验证步骤

```bash
cd /Users/yangtao/Documents/elf_parser

# 1. FreeRTOS mps2_an386
python3 main.py --elf tests/qemu/mps2_an386_freertos/firmware/output/img/test_firmware_freertos.elf \
  --dump tests/qemu/mps2_an386_freertos/firmware/output/img/test_dump_freertos.bin \
  --profile qemu/mps2_an386_freertos --display cli_table

# 2. FreeRTOS mps3_an536
python3 main.py --elf tests/qemu/mps3_an536_freertos/firmware/output/img/test_firmware_freertos.elf \
  --dump tests/qemu/mps3_an536_freertos/firmware/output/img/test_dump_freertos.bin \
  --profile qemu/mps3_an536_freertos --display cli_table

# 3. ThreadX mps2_an386
python3 main.py --elf tests/qemu/mps2_an386_threadx/firmware/output/img/sample_threadx.elf \
  --dump tests/qemu/mps2_an386_threadx/firmware/output/img/threadx_ram_dump.bin \
  --profile qemu/mps2_an386_threadx --display cli_table

# 4. ThreadX mps3_an536
python3 main.py --elf tests/qemu/mps3_an536_threadx/firmware/output/img/sample_threadx.elf \
  --dump tests/qemu/mps3_an536_threadx/firmware/output/img/threadx_ram_dump.bin \
  --profile qemu/mps3_an536_threadx --display cli_table

# 5. ThreadX nxp_imx6ul
python3 main.py --elf tests/qemu/nxp_imx6ul_threadx/firmware/output/img/test_firmware_nxp_imx6ul_threadx.elf \
  --dump tests/qemu/nxp_imx6ul_threadx/firmware/output/img/test_dump_nxp_imx6ul_threadx.bin \
  --profile qemu/nxp_imx6ul_threadx --display cli_table
```

### 预期结果：

| 场景 | 线程 | 信号量 | 互斥量 | 队列 | 事件标志 | 定时器 |
|------|------|--------|--------|------|----------|--------|
| mps2_an386_freertos | 12个 | 6个(含Mutex) | 2个 | 2个(无Registry) | 2个 | 2个(无内部) |
| mps3_an536_freertos | 11个 | 6个(含Mutex) | 2个 | 2个(无Registry) | 2个 | 0个 |
| mps2_an386_threadx | 9个(固件限制) | 2个(count合理) | 2个 | 2个 | 2个 | 2个 |
| mps3_an536_threadx | 11个 | 2个 | 2个 | 2个 | 2个 | 2个 |
| nxp_imx6ul_threadx | 11个 | 2个 | 2个 | 2个 | 2个 | 2个 |
