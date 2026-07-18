# 计划：完成 QEMU 真实 dump 的离线解析验证

## Summary

用户问"能否在qemu上跑固件和dump真实bin呢"——QEMU 真实运行 + dump.bin 已经成功生成（上一阶段完成），但离线解析工具因 **DWARF 多 CU 引用偏移** bug 无法正确解析 QEMU 版 ELF。本计划收尾这部分工作：完成 `elf_parser.py` 中剩余 5 个方法的 DWARF 引用修复，验证 QEMU 真实 dump 能被工具正确解析，并补齐 QEMU 专用测试用例。

## Current State Analysis

### 已验证的事实（本次探索得到）

1. **QEMU 真实 dump 数据正确**（直接读 `test_dump_qemu.bin` 字节验证）：
   - `g_system_ticks = 5234567` ✅ (代码 `simulate_runtime()` 末尾赋值)
   - `g_error_count = 9` ✅ (3+2+3+1 条 assert)
   - `g_system_status = 0xff` ✅ (`trigger_crash_assert()` 末尾赋值)
   - `g_active_assert_idx = 2` ✅
   - `g_trace_write_idx = 20` ✅ (写入 20 条 trace)
   - `g_string_pool_used = 378` ✅
   - dump 大小 4096 字节，非零 767 字节（18.7%）

2. **DWARF 多 CU bug 确认**（直接 dump DWARF 验证）：
   - QEMU 版 ELF 有 **2 个 CU**：`CU[0] cu_offset=0x0`，`CU[1] cu_offset=0x23`
   - 所有变量 `DW_AT_type` 用 `DW_FORM_ref4`（CU 相对偏移），必须 `+cu_offset` 才是绝对偏移
   - 例如 `g_system_ticks` 的 type val=`0x61`，真实绝对偏移=`0x84`（uint32_t typedef 的 DIE）
   - 原版 `test_firmware_bss.elf` 只有 1 个 CU（cu_offset=0），所以老代码恰好正确

3. **已部分修复**（[elf_parser.py](file:///Users/yangtao/Documents/core/elf_parser.py)）：
   - `_resolve_type_ref` 方法已添加（L141-154），逻辑正确
   - 第三遍变量索引已用 `_resolve_type_ref`（L134）
   - **未修复**的 5 个方法仍用老模式（直接 `die_by_offset.get(type_attr.value)`）：
     - `_parse_typedef_die` L188-192
     - `_parse_pointer_die` L216-220
     - `_parse_const_die` L252-256
     - `_parse_array_die` L275-279
     - `_parse_member` L388-393

### 关键文件清单

| 文件 | 角色 | 状态 |
|------|------|------|
| [core/elf_parser.py](file:///Users/yangtao/Documents/core/elf_parser.py) | DWARF 解析核心 | 5 个方法待替换 |
| [firmware/qemu/show_qemu_parsed.py](file:///Users/yangtao/Documents/firmware/qemu/show_qemu_parsed.py) | QEMU 解析展示脚本 | 已写好，待 elf_parser 修复后运行 |
| [firmware/qemu/run_qemu_dump.py](file:///Users/yangtao/Documents/firmware/qemu/run_qemu_dump.py) | QEMU 运行+dump 脚本 | 已稳定，可重跑生成 dump |
| [firmware/test_firmware_qemu.elf](file:///Users/yangtao/Documents/firmware/test_firmware_qemu.elf) | QEMU 版固件 | 已编译完成（2 个 CU） |
| [firmware/test_dump_qemu.bin](file:///Users/yangtao/Documents/firmware/test_dump_qemu.bin) | QEMU 真实 dump | 已生成（4096 字节，数据正确） |
| [tests/test_bss_firmware.py](file:///Users/yangtao/Documents/tests/test_bss_firmware.py) | BSS 固件测试（11 个） | 已稳定，需回归通过 |
| [tests/test_core.py](file:///Users/yangtao/Documents/tests/test_core.py) | 通用核心测试（15 个） | 已稳定，需回归通过 |
| [profiles/test/test_firmware_real.yaml](file:///Users/yangtao/Documents/profiles/test/test_firmware_real.yaml) | 测试 profile | RAM `0x20000000` size `0x1000` |

## Proposed Changes

### Step 1：修复 `_parse_typedef_die` 中的 DWARF 引用

**文件**：[core/elf_parser.py](file:///Users/yangtao/Documents/core/elf_parser.py#L176-L202)

**What/Why**：把直接 `die_by_offset.get(type_attr.value)` 改为 `self._resolve_type_ref(die, die_by_offset)`，让 typedef 解析在多 CU 场景下能找到被引用的真实类型 DIE。

**How**（替换 L188-192）：
```python
ref_die = self._resolve_type_ref(die, die_by_offset)
if ref_die:
    info['ref_type_offset'] = ref_die.offset
    # 递归解析被 typedef 的真实类型，把 byte_size 和 members 提升上来
    ref_info = self._parse_any_die(ref_die, die_by_offset)
    if ref_info:
        info['ref_type'] = ref_info
        info['byte_size'] = ref_info.get('byte_size', 0)
        # typedef 直接继承被引用类型的 members，这样上层可当作结构体使用
        if 'members' in ref_info:
            info['members'] = ref_info['members']
```

### Step 2：修复 `_parse_pointer_die`

**文件**：[core/elf_parser.py](file:///Users/yangtao/Documents/core/elf_parser.py#L204-L226)

**How**（替换 L216-220）：
```python
ref_die = self._resolve_type_ref(die, die_by_offset)
if ref_die:
    info['ref_type_offset'] = ref_die.offset
    info['ref_type'] = self._parse_any_die(ref_die, die_by_offset)
    # 如果最终指向 char（可能经过 const_type 修饰），给个友好名字
    if self._is_char_pointer(info):
        info['name'] = 'char*'
```

### Step 3：修复 `_parse_const_die`

**文件**：[core/elf_parser.py](file:///Users/yangtao/Documents/core/elf_parser.py#L243-L263)

**How**（替换 L252-256）：
```python
ref_die = self._resolve_type_ref(die, die_by_offset)
if ref_die:
    info['ref_type_offset'] = ref_die.offset
    info['ref_type'] = self._parse_any_die(ref_die, die_by_offset)
    if info['ref_type']:
        info['byte_size'] = info['ref_type'].get('byte_size', 0)
        if info['ref_type'].get('name'):
            info['name'] = 'const ' + info['ref_type']['name']
```

### Step 4：修复 `_parse_array_die`

**文件**：[core/elf_parser.py](file:///Users/yangtao/Documents/core/elf_parser.py#L265-L298)

**How**（替换 L275-279）：
```python
ref_die = self._resolve_type_ref(die, die_by_offset)
if ref_die:
    info['element_type_offset'] = ref_die.offset
    info['element_type'] = self._parse_any_die(ref_die, die_by_offset)
```

### Step 5：修复 `_parse_member`

**文件**：[core/elf_parser.py](file:///Users/yangtao/Documents/core/elf_parser.py#L354-L404)

**How**（替换 L388-393）：
```python
if 'DW_AT_type' in die.attributes:
    ref_die = self._resolve_type_ref(die, die_by_offset)
    if ref_die:
        member['type_offset'] = ref_die.offset
        type_info = self._parse_any_die(ref_die, die_by_offset)
        if type_info:
            member['type'] = type_info
            member['type_name'] = type_info.get('name') or type_info.get('kind')
            if type_info.get('byte_size'):
                member['byte_size'] = type_info['byte_size']
```

### Step 6：运行 `show_qemu_parsed.py` 验证 QEMU 真实 dump 解析

**命令**：`python3 firmware/qemu/show_qemu_parsed.py`

**预期**：4 个区块全部正确打印——系统状态 6 个标量、g_assert_infos[4] 的 9 条记录、g_test_points[8] 的 8 个测点、g_trace_buffer[32] 的 20 条 trace。所有 char* 自动解引用为字符串。

### Step 7：回归测试——确认原 26 个测试无回归

**命令**：`python3 -m unittest discover -s tests`

**预期**：26 个测试全部通过（原版 ELF 只有 1 个 CU，`_resolve_type_ref` 对单 CU 也兼容——`cu_offset=0` 时 val 不变）。

### Step 8：创建 `tests/test_qemu_firmware.py`

**文件**：新建 `tests/test_qemu_firmware.py`，参照 [test_bss_firmware.py](file:///Users/yangtao/Documents/tests/test_bss_firmware.py) 结构。

**用例清单（10 个）**：
1. `test_qemu_elf_exists`：ELF/dump 文件存在且非空
2. `test_qemu_elf_header`：ARM 32 位、entry 在 Flash（`0x0` 段而非 `0x08000000`），有 debug_info
3. `test_qemu_bss_variables_in_ram`：所有 `g_*` 符号地址都在 `0x20000000`~`0x20001000`
4. `test_qemu_scalar_values`：6 个标量与 `simulate_runtime()` 赋值一致（ticks=5234567, err=9, status=0xff, active=2, twi=20, spu=378）
5. `test_qemu_assert_info_array_expansion`：4 个 assert_info_t，counts=[3,2,3,1]
6. `test_qemu_assert_record_details`：抽查几条记录的 file/line/func/cond/task/err
7. `test_qemu_test_point_array_expansion`：8 个 test_point_t，全部字段与代码一致
8. `test_qemu_trace_buffer_expansion`：32 条 trace，前 20 条有数据，后 12 条为 0
9. `test_qemu_char_pointer_deref`：所有 char* 字段都是字符串，非指针 hex 值
10. `test_qemu_auto_parse_matches_manual_read`：手动 `read_uint32` 与 `parse_struct_auto` 结果一致

### Step 9：全量测试验证

**命令**：`python3 -m unittest discover -s tests`

**预期**：26（原）+ 10（新 QEMU）= 36 个测试全部通过。

## Assumptions & Decisions

1. **不动 `run_qemu_dump.py` 和 QEMU 二进制**：dump 已生成且数据正确，无需重跑。
2. **`_resolve_type_ref` 已正确实现**：本次探索验证过逻辑——`attr.form.startswith('DW_FORM_ref') and attr.form != 'DW_FORM_ref_addr'` 判断正确，单 CU 时 `cu_offset=0` 自动兼容。
3. **测试用例的期望值来源**：直接来自 [test_firmware_bss.c](file:///Users/yangtao/Documents/firmware/test_firmware_bss.c) 的 `simulate_runtime()` 函数体（已逐一对照）。
4. **测试 profile 复用**：`test/test_firmware_real` 的 RAM 配置（`0x20000000`, `0x1000`）对 QEMU 版同样适用。
5. **不动 `test_bss_firmware.py`**：保持原版 ELF 测试不变，作为多 CU 修复的单 CU 兼容性回归基线。

## Verification Steps

1. 修复 5 个方法后运行 `python3 firmware/qemu/show_qemu_parsed.py`——目视确认所有结构体展开正确
2. 运行 `python3 -m unittest discover -s tests`——36 个测试全部通过
3. 用 `python3 -c "from core.elf_parser import ELFParser; ..."` 快速检查 `_var_type_cache` 不为空（修复后应非空且包含全部 10 个 `g_*` 全局变量）
