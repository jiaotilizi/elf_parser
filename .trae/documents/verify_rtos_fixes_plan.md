# RTOS Display 修复验证计划

## 摘要

已确认 7 个修复全部在代码中到位，现在需要运行全部 5 个 RTOS 场景的 display 命令，验证输出结果与预期一致。

## 当前状态

所有 7 个修复点已确认在代码中：

| # | 问题 | 文件 | 状态 |
|---|------|------|------|
| 1 | 任务列表为空/不完整 | `plugins/rtos/base.py:232-243` | ✅ 已修复 |
| 2 | 任务名乱码/缺失 | `plugins/rtos/freertos/freertos_v11p3p0.py:227-235` | ✅ 已修复 |
| 3 | 信号量计数错误 | `plugins/rtos/threadx/threadx_v6p5p1.py:234-248` | ✅ 已修复 |
| 4 | thread_8/9 缺失 | 固件问题，无需修改 | ✅ 无需修复 |
| 5 | xQueueRegistry 出现在队列列表 | `plugins/rtos/freertos/freertos_v11p3p0.py:452-455` | ✅ 已修复 |
| 6 | Mutex 未出现在 Semaphore 列表 | `plugins/rtos/freertos/freertos_v11p3p0.py:292-295` | ✅ 已修复 |
| 7 | 定时器列表包含内部结构 | `plugins/rtos/freertos/freertos_v11p3p0.py:571-576` | ✅ 已修复 |

## 验证结果（最终）

### 步骤 1：FreeRTOS mps2_an386 ✅

**结果：** 12 个任务、4 信号量+2 互斥量(=6)、2 队列、2 定时器、2 事件
**状态：** 通过。无重复任务、无定时器地址、无 xQueueRegistry

### 步骤 2：FreeRTOS mps3_an536 ✅

**结果：** 10 个任务、4 信号量+2 互斥量(=6)、2 队列、0 定时器、2 事件
**状态：** 通过。固件未创建 Tmr Svc（无定时器），10 个任务正确

### 步骤 3：ThreadX mps2_an386 ✅

**结果：** 9 个任务(固件限制)、2 信号量(count=0 已修正)、2 互斥量、2 队列、2 事件、2 定时器、1 块池、1 字节池
**状态：** 通过。信号量警告已触发但值已修正为 0

### 步骤 4：ThreadX mps3_an536 ✅

**结果：** 11 个任务、2 信号量(count=1/0)、2 互斥量、2 队列、2 事件、2 定时器、1 块池、1 字节池
**状态：** 通过

### 步骤 5：ThreadX nxp_imx6ul ✅

**结果：** 11 个任务、2 信号量(count=1/0)、2 互斥量、2 队列、2 事件、2 定时器、1 块池、1 字节池
**状态：** 通过

## 验证结果汇总

| 场景 | 任务 | 信号量 | 互斥量 | 队列 | 事件 | 定时器 | 状态 |
|------|------|--------|--------|------|------|--------|------|
| mps2_an386_freertos | 12 | 4 | 2 | 2 | 2 | 2 | ✅ |
| mps3_an536_freertos | 10 | 4 | 2 | 2 | 2 | 0 | ✅ |
| mps2_an386_threadx | 9 | 2 | 2 | 2 | 2 | 2 | ✅ |
| mps3_an536_threadx | 11 | 2 | 2 | 2 | 2 | 2 | ✅ |
| nxp_imx6ul_threadx | 11 | 2 | 2 | 2 | 2 | 2 | ✅ |

## 验证期间发现并修复的额外问题

### 问题 8：FreeRTOS 任务重复和垃圾数据

**根因：**
- `xDelayedTaskList1` 与 `pxReadyTasksLists[8]` 地址重叠，导致任务被重复枚举
- `uxTopUsedPriority` 在 Flash 区域（不在 RAM dump 中），读取失败后回退到 32 个优先级遍历
- 超过 `uxTopUsedPriority` 的优先级槽位包含垃圾数据，导致定时器地址被误解析为 TCB

**修复：** `plugins/rtos/freertos/freertos_v11p3p0.py` `_get_tasks` 方法
- 添加 `uxTopUsedPriority` 读取失败时的 ELF 回退机制
- 添加 `uxNumberOfItems` 合理性检查（> 255 视为垃圾数据）
- 添加 TCB 地址去重逻辑

## 假设与决策

- 所有修复代码已确认在磁盘上，无需再修改
- 测试固件和 dump 文件已存在且为最新版本
- Python 3.8+ 环境和依赖已安装
- 如果某个场景验证失败，需要进一步排查该场景的具体问题

## 执行方式

5 个场景的命令可以并行运行（互相独立），然后逐个分析输出结果。