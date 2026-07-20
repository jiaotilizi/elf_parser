# ELF Parser GUI 规划文档

## 1. 概述

本文档规划 ELF Parser 的图形用户界面（GUI）设计，目标是提供一个类似 Trace32 的嵌入式调试分析工具体验，支持离线 ELF/Dump 分析和跨资源导航。

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GUI Layer (Qt/PySide6)                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                        Main Window                            │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │                      Menu Bar                           │  │  │
│  │  │  File │ Device │ RTOS │ Module │ View │ Help            │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │                      Tool Bar                           │  │  │
│  │  │  [Open ELF] [Open Dump] [Refresh] [Save] [Settings]    │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  │  ┌────────────────────┬─────────────────────────────────────┐  │  │
│  │  │   Navigation Pane  │           Content Area              │  │  │
│  │  │  ┌───────────────┐ │  ┌───────────────────────────────┐ │  │  │
│  │  │  │ Resources     │ │  │   Resource Table / Detail     │ │  │  │
│  │  │  │ ───────────── │ │  │                               │ │  │  │
│  │  │  │ Tasks         │ │  │   - Clickable jump markers    │ │  │  │
│  │  │  │ Semaphores    │ │  │   - Detail views             │ │  │  │
│  │  │  │ Mutexes       │ │  │   - Cross-plugin navigation   │ │  │  │
│  │  │  │ Queues        │ │  │                               │ │  │  │
│  │  │  │ Events        │ │  │                               │ │  │  │
│  │  │  │ Timers        │ │  │                               │ │  │  │
│  │  │  │ Block Pools   │ │  │                               │ │  │  │
│  │  │  │ Byte Pools    │ │  │                               │ │  │  │
│  │  │  └───────────────┘ │  └───────────────────────────────┘ │  │  │
│  │  │  ┌───────────────┐ │                                   │  │  │
│  │  │  │ History Stack │ │                                   │  │  │
│  │  │  │ (Back/Forward)│ │                                   │  │  │
│  │  │  └───────────────┘ │                                   │  │  │
│  │  └────────────────────┴─────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │                    Command Line                         │  │  │
│  │  │  > load.elf test.elf                                   │  │  │
│  │  │  > load.mem test.bin                                    │  │  │
│  │  │  > display tasks                                        │  │  │
│  │  │  > jump 0x20001000                                     │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                      Application Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐       │
│  │  ELFParser  │  │  DumpReader  │  │   ProfileLoader     │       │
│  └──────┬───────┘  └──────┬───────┘  └────────┬────────────┘       │
│         │                 │                    │                     │
│         └─────────────────┼────────────────────┘                     │
│                           ▼                                         │
│              ┌─────────────────────┐                                │
│              │   PluginContext     │                                │
│              │  - Plugin registry  │                                │
│              │  - Navigation API   │                                │
│              │  - History stack    │                                │
│              └──────────┬──────────┘                                │
│                         │                                           │
│         ┌───────────────┼───────────────┐                          │
│         ▼               ▼               ▼                          │
│  ┌───────────┐  ┌───────────┐  ┌───────────────┐                 │
│  │ RTOS      │  │ Module    │  │  DataAdapter  │                 │
│  │ Plugin    │  │ Plugin    │  │               │                 │
│  └───────────┘  └───────────┘  └───────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

| 组件 | 职责 | 技术实现 |
|------|------|---------|
| MainWindow | 主窗口框架，菜单/工具栏/布局 | QMainWindow |
| DeviceSelectorDialog | Device 选择弹窗，下拉列表 | QDialog + QComboBox |
| ResourceTree | 左侧资源导航树 | QTreeWidget |
| ContentArea | 右侧内容展示区 | QStackedWidget |
| ResourceTable | 资源列表表格 | QTableWidget |
| DetailView | 资源详情视图 | QTabWidget |
| CommandLine | 命令行交互区 | QLineEdit + QTextEdit |
| PluginContext | 插件上下文管理 | Python Class |

## 3. 菜单系统设计

### 3.1 菜单结构

```
File
├── Open ELF...          (Ctrl+O)
├── Open Dump...         (Ctrl+Shift+O)
├── Load Profile...      (Ctrl+P)
├── Save Results...      (Ctrl+S)
├── Export as JSON...    (Ctrl+E)
├── Recent Files
│   ├── test_firmware.elf
│   ├── threadx_ram_dump.bin
│   └── ...
└── Exit                 (Ctrl+Q)

Device
├── Select Device...     (Ctrl+D)  → 打开 Device 选择弹窗
└── <当前 Device>
    ├── Refresh          (F5)
    └── Properties...

RTOS                     ← 动态加载，根据 Device 配置
├── Display Tasks        (F1)
├── Display Semaphores   (F2)
├── Display Mutexes      (F3)
├── Display Queues       (F4)
├── Display Events       (F5)
├── Display Timers       (F6)
├── Display Block Pools  (F7)
├── Display Byte Pools   (F8)
└── Show All Resources   (Ctrl+Shift+F)

Module                   ← 动态加载，根据 Device 配置
├── Display Test Points  (F9)
├── Display Assert Info  (F10)
└── <其他 Module>

View
├── Navigation Pane      (Ctrl+1)
├── Command Line         (Ctrl+2)
├── Tool Bar             (Ctrl+3)
├── Status Bar           (Ctrl+4)
├── Font Size
│   ├── Small
│   ├── Medium
│   └── Large
└── Theme
    ├── Light
    ├── Dark
    └── System

Help
├── About
├── Documentation
└── Check for Updates
```

### 3.2 Device 选择弹窗

**设计要点**：

1. **芯片选择**：从所有 profiles 中提取唯一芯片型号，以树形或两级下拉展示
2. **OS/Profile 选择**：选中芯片后，展示该芯片支持的所有 OS/Profile（如 MPS2 AN386 支持 FreeRTOS/ThreadX/Bare-metal）
3. **搜索框**：支持按芯片名称/型号/OS 过滤
4. **预览区**：选中后显示 Profile 详细信息（芯片、OS、内存区域、插件列表）
5. **加载按钮**：确认后加载对应插件，更新菜单栏

**数据结构**（基于 profile.yaml 实际结构）：

```python
class ChipInfo:
    name: str              # 芯片名称 (e.g., "MPS2 AN386")
    vendor: str            # 芯片厂商 (e.g., "arm")
    cpu: str               # CPU 型号 (e.g., "cortex-m4")
    arch: str              # 架构 (e.g., "armv7e-m")
    bits: int              # 位宽 (32/64)
    profiles: List[ProfileInfo]  # 该芯片支持的所有 Profile

class ProfileInfo:
    name: str              # Profile 名称 (e.g., "qemu_mps2_an386_freertos")
    description: str       # 描述 (e.g., "QEMU ARM MPS2 AN386 (Cortex-M4) + FreeRTOS V11.3.0")
    plugins: List[str]     # 插件列表 (e.g., ["rtos.freertos.freertos_v11p3p0", "module.assert_info.assert_info_v0"])
    memory_regions: List[Dict]  # 内存区域配置
```

**Profile 文件结构示例**（参考 profiles/qemu/mps2_an386_freertos.yaml）：

```yaml
chip:
  name: qemu_mps2_an386_freertos
  vendor: arm
  description: QEMU ARM MPS2 AN386 (Cortex-M4) + FreeRTOS V11.3.0
  arch: armv7e-m
  cpu: cortex-m4
  bits: 32
memory:
- name: ram
  start_addr: 536870912
  size: 65536
plugins:
- rtos.freertos.freertos_v11p3p0    # RTOS 插件
- module.assert_info.assert_info_v0  # Module 插件
- module.test_point.test_point_v0    # Module 插件
```

**芯片与 Profile 映射关系**：

| 芯片型号 | 支持的 OS/Profile | 插件 |
|---------|-------------------|------|
| MPS2 AN386 | FreeRTOS v11.3.0 | rtos.freertos.freertos_v11p3p0 |
| MPS2 AN386 | ThreadX v6.5.1 | rtos.threadx.threadx_v6p5p1 |
| MPS2 AN386 | Bare-metal | 无 |
| MPS3 AN536 | FreeRTOS v11.3.0 | rtos.freertos.freertos_v11p3p0 |
| MPS3 AN536 | ThreadX v6.5.1 | rtos.threadx.threadx_v6p5p1 |
| NXP i.MX6UL | ThreadX v6.5.1 | rtos.threadx.threadx_v6p5p1 |
| STM32VLDiscovery | Bare-metal | 无 |

**交互流程**：

```
用户点击 "Device > Select Device..."
        ↓
弹出 DeviceSelectorDialog
        ↓
用户从芯片列表选择芯片（如 "MPS2 AN386"）
        ↓
右侧显示该芯片支持的 OS/Profile 列表
        ↓
用户选择具体 Profile（如 "FreeRTOS v11.3.0"）
        ↓
预览区显示完整 Profile 信息（芯片、OS、内存、插件）
        ↓
用户点击 "Load" 按钮
        ↓
系统解析 Profile 的 plugins 字段，区分 RTOS 和 Module 插件
        ↓
加载插件到 PluginContext（rtos.* → RTOS 插件，module.* → Module 插件）
        ↓
更新 RTOS 菜单（根据 RTOS 插件支持的资源类型）
        ↓
更新 Module 菜单（根据 Module 插件列表）
        ↓
刷新 Navigation Pane（显示可用资源类型）
```

**插件分类规则**：

| 插件路径前缀 | 类型 | 菜单位置 |
|-------------|------|---------|
| `rtos.freertos.*` | RTOS 插件 | RTOS 菜单 |
| `rtos.threadx.*` | RTOS 插件 | RTOS 菜单 |
| `module.*` | Module 插件 | Module 菜单 |

## 4. 命令行系统设计

### 4.1 命令格式

命令行系统模仿 Trace32 的命令风格：

```
> load.elf <path>           # 加载 ELF/AXF 文件
> load.mem <path> [offset]  # 加载内存 dump 文件
> load.profile <name>       # 加载 Profile
> display <resource>        # 显示资源列表
  > display tasks
  > display semaphores
  > display mutexes
  > display queues
  > display events
  > display timers
> jump <address>            # 跳转到指定地址的资源详情
> search <pattern>          # 搜索符号
> info                      # 显示当前加载信息
> help [command]            # 显示帮助
> clear                     # 清屏
```

### 4.2 拖拽支持

命令行区域支持文件拖拽：
- 拖入 `.elf` / `.axf` 文件 → 自动执行 `load.elf <path>`
- 拖入 `.bin` / `.mem` 文件 → 自动执行 `load.mem <path>`

### 4.3 命令历史

- 支持上下箭头浏览历史命令
- 支持 `Ctrl+R` 搜索历史命令
- 历史记录持久化到配置文件

## 5. 跨资源导航设计

### 5.1 Jump Marker 数据格式

插件返回的数据中，可跳转字段携带 `jump_to` 标记：

```python
{
    'name': 'thread_0',
    'priority': 1,
    'state': 'READY',
    'tx_mutex_holder': {
        'value': 0x20001000,
        'jump_to': {
            'resource_type': 'mutexes',
            'address': 0x20001000
        },
        'display': '[0x20001000|mutex_0]'
    }
}
```

### 5.2 导航流程

```
用户在资源列表中点击带有 jump_to 标记的字段
        ↓
ContentArea 调用 DataAdapter.navigate(resource_type, address)
        ↓
PluginContext.navigate() 根据 resource_type 找到对应插件
        ↓
插件调用 get_detail(resource_type, address) 获取详情
        ↓
ContentArea 切换到 DetailView 显示详情
        ↓
历史栈记录当前位置，支持 Back/Forward
```

### 5.3 历史栈

```python
class NavigationHistory:
    def __init__(self):
        self._history = []
        self._index = -1
    
    def push(self, resource_type: str, address: int, data: Dict):
        """压入历史记录"""
        # 清除当前位置之后的记录
        self._history = self._history[:self._index + 1]
        self._history.append({
            'resource_type': resource_type,
            'address': address,
            'data': data
        })
        self._index = len(self._history) - 1
    
    def back(self) -> Optional[Dict]:
        """后退"""
        if self._index > 0:
            self._index -= 1
            return self._history[self._index]
        return None
    
    def forward(self) -> Optional[Dict]:
        """前进"""
        if self._index < len(self._history) - 1:
            self._index += 1
            return self._history[self._index]
        return None
```

## 6. 数据适配层设计

### 6.1 DataAdapter 接口

```python
class DataAdapter:
    # 资源数据获取
    def get_all_resource_types(self) -> List[str]:
        """获取所有可用资源类型"""
    
    def get_resource_data(self, resource_type: str) -> List[Dict]:
        """获取指定类型的资源列表"""
    
    def get_resource_metadata(self, resource_type: str) -> ResourceMetadata:
        """获取资源类型的元数据（字段定义、显示配置）"""
    
    # 导航接口
    def get_detail(self, resource_type: str, address: int) -> Optional[Dict]:
        """获取指定资源的详细信息"""
    
    def navigate(self, resource_type: str, address: int) -> Optional[Dict]:
        """导航到指定资源（跨插件）"""
    
    # 搜索接口
    def search_symbols(self, pattern: str) -> List[Dict]:
        """搜索符号"""
    
    def search_memory(self, address: int, length: int = 64) -> Optional[bytes]:
        """搜索内存"""
```

## 7. 阶段规划

### Phase 1：基础框架（v1.0）

| 里程碑 | 内容 | 时间 |
|--------|------|------|
| M1.1 | 主窗口框架（菜单、工具栏、布局） | 第 1 周 |
| M1.2 | Device 选择弹窗 | 第 1 周 |
| M1.3 | 命令行系统（基础命令） | 第 2 周 |
| M1.4 | 文件拖拽加载 | 第 2 周 |
| M1.5 | 资源列表显示（表格） | 第 3 周 |

### Phase 2：导航功能（v1.1）

| 里程碑 | 内容 | 时间 |
|--------|------|------|
| M2.1 | Jump Marker 数据格式定义 | 第 4 周 |
| M2.2 | RTOS 插件添加跳转标记 | 第 4 周 |
| M2.3 | 资源详情视图 | 第 5 周 |
| M2.4 | 历史栈（Back/Forward） | 第 5 周 |

### Phase 3：交互增强（v1.2）

| 里程碑 | 内容 | 时间 |
|--------|------|------|
| M3.1 | 主题切换（Light/Dark） | 第 6 周 |
| M3.2 | 命令历史搜索 | 第 6 周 |
| M3.3 | 资源导航树 | 第 7 周 |
| M3.4 | 导出功能（JSON/CSV） | 第 7 周 |

### Phase 4：高级特性（v1.3+）

| 里程碑 | 内容 | 时间 |
|--------|------|------|
| M4.1 | 实时调试连接（J-Link/OpenOCD） | 第 8 周 |
| M4.2 | 内存可视化 | 第 9 周 |
| M4.3 | 断点设置与追踪 | 第 10 周 |
| M4.4 | 性能分析（任务运行时间统计） | 第 11 周 |

## 8. 技术栈选择

### 8.1 推荐方案：Qt/PySide6

| 维度 | 理由 |
|------|------|
| 跨平台 | 支持 Windows/macOS/Linux，嵌入式开发者常用 |
| 桌面体验 | 原生窗口、菜单、对话框，体验优于 Web |
| 性能 | 本地渲染，处理大量数据更流畅 |
| 拖拽支持 | 原生支持文件拖拽 |
| 社区 | 大量 Qt/PySide6 资源和文档 |

### 8.2 备选方案：Web GUI（Flask + HTML/JS）

| 维度 | 理由 |
|------|------|
| 开发速度 | Web 技术栈开发更快 |
| 远程访问 | 支持远程调试 |
| 跨平台 | 只需浏览器 |

### 8.3 最终决策

- **优先采用 Qt/PySide6** 作为主 GUI 框架
- **保留 Web GUI** 作为轻量级备选方案
- Qt GUI 作为主要开发方向，Web GUI 保持维护

## 9. 依赖清单

| 依赖 | 版本 | 用途 |
|------|------|------|
| PySide6 | >= 6.5 | GUI 框架 |
| PySide6-QtCharts | >= 6.5 | 图表显示（性能分析） |
| PySide6-QtSvg | >= 6.5 | SVG 图标支持 |
| pyelftools | >= 0.28 | ELF/DWARF 解析 |
| pyyaml | >= 6.0 | YAML 配置解析 |
| flask | >= 2.0 | Web GUI 后端 |

## 10. 目录结构规划

```
elf_parser/
├── gui/                              # GUI 模块
│   ├── __init__.py
│   ├── main_window.py                # 主窗口
│   ├── device_selector.py            # Device 选择弹窗
│   ├── resource_tree.py              # 资源导航树
│   ├── content_area.py               # 内容展示区
│   ├── resource_table.py             # 资源列表表格
│   ├── detail_view.py                # 资源详情视图
│   ├── command_line.py               # 命令行交互区
│   ├── navigation_history.py         # 导航历史栈
│   └── styles/                       # 样式文件
│       ├── light.qss                 # 浅色主题
│       └── dark.qss                  # 深色主题
├── core/                             # 核心模块（不变）
├── plugins/                          # 插件模块（不变）
├── display/                          # 显示模块（不变）
└── main.py                           # 入口文件（新增 GUI 启动参数）
```

## 11. 启动方式

```bash
# CLI 模式（现有）
python main.py --elf test.elf --dump test.bin --profile xxx

# GUI 模式（新增）
python main.py --gui

# GUI + 预加载文件
python main.py --gui --elf test.elf --dump test.bin --profile xxx
```

## 12. 总结

本文档规划了 ELF Parser GUI 的完整设计，包括：

1. **主窗口框架**：菜单、工具栏、导航面板、内容区、命令行
2. **Device 选择**：弹窗下拉列表，动态加载插件
3. **RTOS/Module 菜单**：根据 Device 配置动态更新
4. **命令行系统**：Trace32 风格命令，支持拖拽加载
5. **跨资源导航**：Jump Marker、历史栈、详情视图
6. **分阶段实现**：4 个阶段，从基础框架到高级特性

采用 Qt/PySide6 作为主要技术栈，兼顾跨平台性和桌面体验。
