# 移除特例化处理 - 修复计划

## 背景

上轮修复过程中引入了 3 处特例化处理（0xFFFF 阈值、255 阈值、ELF 回退），且代码中还存在多处历史遗留的特例化代码（硬编码偏移量、魔术值检查）。用户要求所有修复都必须是泛用性方案，不能为了让测试用例通过而特例化。

## 审查结论

### 泛用性修复（保留）

| 修复 | 文件 | 判断 |
|------|------|------|
| `_walk_doubly_linked_list` 使用 `xListEnd.pxNext` | base.py | ✅ 正确 FreeRTOS List_t 语义 |
| 任务名 sanitization（截断 \x00/\xff、过滤不可打印字符） | freertos_v11p3p0.py | ✅ FreeRTOS pcTaskName 是固定 16 字节 char 数组 |
| TCB 地址去重 | freertos_v11p3p0.py | ✅ 通用防御措施 |
| 定时器内部结构过滤（无名+period=0） | freertos_v11p3p0.py | ✅ 定时器守护进程内部实现产物 |
| 基于命名的资源发现 | freertos_v11p3p0.py | ✅ FreeRTOS 固有特性，DWARF 类型系统无法区分 |

### 特例化处理（需移除/重做）

| # | 问题 | 文件:行号 | 类型 |
|---|------|----------|------|
| 1 | ThreadX 信号量 count > 0xFFFF 阈值 | threadx_v6p5p1.py:239-245 | 本次引入 |
| 2 | FreeRTOS uxNumberOfItems > 255 阈值 | freertos_v11p3p0.py:147,158 | 本次引入 |
| 3 | FreeRTOS uxTopUsedPriority ELF 回退 | freertos_v11p3p0.py:134-141 | 本次引入 |
| 4 | FreeRTOS 硬编码偏移量 56/60/64/68 | freertos_v11p3p0.py:371-375,450-453,524-527 | 历史遗留 |
| 5 | FreeRTOS 魔术值检查 65535 / 0xFFFFFFFF | freertos_v11p3p0.py:381-382,457-460,534-535 | 历史遗留 |
| 6 | FreeRTOS period_ticks > 1000000 阈值 | freertos_v11p3p0.py:663 | 历史遗留 |
| 7 | FreeRTOS 硬编码 ListItem_t size=20 回退 | freertos_v11p3p0.py:646-648 | 历史遗留 |

这些特例化代码的共同问题：
- 使用任意阈值（0xFFFF、255、1000000）掩盖底层问题
- 使用硬编码偏移量替代 DWARF 类型信息
- 使用魔术值（65535、0xFFFFFFFF）静默修正数据

## 修改方案

### 核心设计：用 ELF 符号大小推导 configMAX_PRIORITIES

FreeRTOS 的 `pxReadyTasksLists` 声明为 `List_t pxReadyTasksLists[configMAX_PRIORITIES]`，其 ELF 符号大小 = `configMAX_PRIORITIES * sizeof(List_t)`。`sizeof(List_t)` 可从 DWARF 获取。用此方法替代不可靠的 `uxTopUsedPriority`（运行时变量，可能不在 dump 中）。

### 修改 1：ThreadX 信号量 — 移除 0xFFFF 阈值

**文件：** `plugins/rtos/threadx/threadx_v6p5p1.py`

移除第 239-245 行的阈值检查，改为直接报告原始值：

```python
# 修改前
elif member_name == 'tx_semaphore_count':
    raw_count = dump_reader.read_uint32(sem_addr + member_offset)
    if raw_count is not None and raw_count > 0xFFFF:
        logger.warning(...)
        result['count'] = 0
    else:
        result['count'] = raw_count if raw_count is not None else 0

# 修改后
elif member_name == 'tx_semaphore_count':
    result['count'] = dump_reader.read_uint32(sem_addr + member_offset) or 0
```

**理由：** dump 中的垃圾数据问题应在 dump 采集层面解决，插件应如实报告原始值。

### 修改 2：新增 `_get_config_max_priorities` 辅助方法

**文件：** `plugins/rtos/freertos/freertos_v11p3p0.py`

在 `FreeRTOSV11Plugin` 类中新增方法，从 `pxReadyTasksLists` 的 ELF 符号大小推导 `configMAX_PRIORITIES`：

```python
def _get_config_max_priorities(self, elf_parser) -> int:
    """从 pxReadyTasksLists 的 ELF 符号大小推导 configMAX_PRIORITIES。
    
    pxReadyTasksLists 是 List_t[configMAX_PRIORITIES] 数组，
    符号大小 = configMAX_PRIORITIES * sizeof(List_t)。
    当无法推导时返回 32（FreeRTOS 常见最大值），并记录 WARNING。
    """
    ready_lists_sym = elf_parser.get_symbol_by_name('pxReadyTasksLists')
    if not ready_lists_sym:
        return 32
    
    list_struct = elf_parser.get_struct_type('List_t')
    if not list_struct:
        return 32
    
    list_size = list_struct.get('byte_size', 0)
    if list_size <= 0:
        return 32
    
    symbol_size = ready_lists_sym.get('size', 0)
    if symbol_size <= 0:
        return 32
    
    max_priorities = symbol_size // list_size
    if max_priorities <= 0:
        return 32
    
    return max_priorities
```

**理由：** `configMAX_PRIORITIES` 是编译时常量，从符号大小推导是精确的。32 作为回退值是 FreeRTOS 的常见最大值，且有 WARNING 日志。

### 修改 3：`_get_tasks` — 用符号大小替代 uxTopUsedPriority + 移除 255 阈值

**文件：** `plugins/rtos/freertos/freertos_v11p3p0.py`

**3a.** 替换 `max_priorities` 计算（第 130-143 行），移除 `uxTopUsedPriority` 读取和 ELF 回退：

```python
# 修改前
max_priorities = 32
ux_top_used_priority_sym = elf_parser.get_symbol_by_name('uxTopUsedPriority')
if ux_top_used_priority_sym:
    ux_top_used_priority = dump_reader.read_uint32(...)
    if ux_top_used_priority is None:
        ux_top_used_priority = elf_parser.read_memory_from_elf(...)
        ...
    if ux_top_used_priority is not None and ux_top_used_priority < max_priorities:
        max_priorities = ux_top_used_priority + 1

# 修改后
max_priorities = self._get_config_max_priorities(elf_parser)
```

**3b.** 移除 `MAX_REASONABLE_LIST_ITEMS = 255` 和 `if ux_number_of_items > MAX_REASONABLE_LIST_ITEMS: continue`（第 145-158 行）。`_walk_doubly_linked_list` 已有 `visited` 集合防循环。

**3c.** 保留 TCB 地址去重逻辑（第 203-213 行）— 这是泛用性防御措施。

### 修改 4：`_get_task_state` — 用符号大小替代硬编码 32

**文件：** `plugins/rtos/freertos/freertos_v11p3p0.py` 第 64 行

```python
# 修改前
for priority in range(32):

# 修改后
for priority in range(self._get_config_max_priorities(elf_parser)):
```

同时移除 `list_size` 的硬编码回退值 20（第 62 行）— 如果 `List_t` 不存在，返回 `'UNKNOWN'`。

### 修改 5：`_parse_tcb_with_context` — 用符号大小替代 uxTopUsedPriority

**文件：** `plugins/rtos/freertos/freertos_v11p3p0.py` 第 219-224 行

```python
# 修改前
max_priorities = 32
ux_top_used_priority_sym = elf_parser.get_symbol_by_name('uxTopUsedPriority')
...

# 修改后
max_priorities = self._get_config_max_priorities(elf_parser)
```

### 修改 6：移除硬编码偏移量 — `_parse_semaphore`、`_parse_mutex`、`_parse_queue`

**文件：** `plugins/rtos/freertos/freertos_v11p3p0.py`

**6a. `_parse_semaphore`（第 370-375 行）：** 移除硬编码偏移量 56/60/64，改为优雅降级（返回 None）。同时移除 `result['count'] == 65535` 魔术值检查（第 381-382 行）。

**6b. `_parse_mutex`（第 450-453 行）：** 同样移除硬编码偏移量 56/68，改为优雅降级。同时移除 `result['count'] == 65535` 和 `result['owner'] == 0xffffffff` 魔术值检查（第 457-460 行）。

**6c. `_parse_queue`（第 524-527 行）：** 同样移除硬编码偏移量 56/60/64，改为优雅降级。同时移除 `result['messages_count'] == 65535` 魔术值检查（第 534-535 行）。

**理由：** 当 DWARF 类型信息缺失时，使用硬编码偏移量会产生错误结果，不如优雅降级。`16 + 2 * list_size` 的偏移量计算基于 `sizeof(List_t)` 从 DWARF 获取，这是结构性的（基于 FreeRTOS QueueDefinition 结构体布局），不是魔术值。

### 修改 7：移除 `_parse_timer` 的特例化处理

**文件：** `plugins/rtos/freertos/freertos_v11p3p0.py`

**7a.** 移除 `period_ticks > 1000000` 阈值（第 663-664 行）。

**7b.** 移除硬编码 `ListItem_t size=20` 回退（第 646-648 行），改为优雅降级。

## 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `plugins/rtos/threadx/threadx_v6p5p1.py` | 移除 0xFFFF 阈值 |
| `plugins/rtos/freertos/freertos_v11p3p0.py` | 新增 `_get_config_max_priorities`；移除 255 阈值/ELF 回退/硬编码偏移量/魔术值检查/period 阈值 |

## 验证步骤

修改后重新运行全部 5 个场景的 display 验证。

## 预期影响

- **mps2_an386 ThreadX：** 信号量 count 将显示原始值（5420073），不再静默修正为 0。这是预期行为 — dump 数据有问题，插件如实报告。
- **mps2_an386 FreeRTOS：** 不再使用 uxTopUsedPriority ELF 回退，改用符号大小推导。如果符号大小推导失败，回退到 32。
- **所有场景：** 当 DWARF 类型信息缺失时，semaphore/mutex/queue 解析将优雅降级（返回 None，不出现在输出中），而不是使用硬编码偏移量产生错误结果。
