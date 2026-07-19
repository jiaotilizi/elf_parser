#!/usr/bin/env python3
"""展示脚本基类：把 dump 自动解析恢复的结构体内容渲染到终端。

把 `firmware/bss_simulated/show_bss_parsed.py` 和
`firmware/qemu_m4_bare/show_qemu_parsed.py` 的共同渲染逻辑提取到基类：
  - Section 1: 系统状态（标量变量）
  - Section 2: g_assert_infos[4] assert_info_t 数组
  - Section 3: g_test_points[8] 测试点统计
  - Section 4: g_trace_buffer[32] 环形 trace 缓冲区

子类只需指定：
  - scenario_dir / elf_filename / dump_filename / profile_name
  - banner_title（场景标题）
  - banner_lines（描述行）
  - footer_lines（结尾总结）

用法：
    class MyShow(ShowParsedBase):
        BANNER_TITLE = '我的场景 Crash Dump 自动恢复演示'
        BANNER_LINES = ['  ELF  : ...', '  原理 : ...']
        FOOTER_LINES = ['★ 这是 ...']

    show = MyShow(scenario_dir='/path/to/scenario',
                  elf_filename='fw.elf',
                  dump_filename='dump.bin',
                  profile_name='test/my_scenario')
    show.run()
"""
import os
import sys

# 让脚本能 import 到 core 模块（在 elf_parser/ 下）
_ELF_PARSER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ELF_PARSER_DIR not in sys.path:
    sys.path.insert(0, _ELF_PARSER_DIR)

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader


class ShowParsedBase:
    """展示脚本的基类，提供通用的渲染框架。

    子类应设置类属性 BANNER_TITLE / BANNER_LINES / FOOTER_LINES，
    然后通过 run() 调用各 section。如需自定义 section，重载对应方法。
    """

    # 子类覆写：banner 标题（第一行）
    BANNER_TITLE: str = '离线内存分析 — Crash Dump 自动恢复演示'
    # 子类覆写：banner 描述行（标题下方，结束分隔符之前）
    BANNER_LINES: list = []
    # 子类覆写：结尾总结行
    FOOTER_LINES: list = []

    def __init__(
        self,
        scenario_dir: str,
        elf_filename: str,
        dump_filename: str,
        profile_name: str,
    ):
        self.scenario_dir = scenario_dir
        self.elf_path = os.path.join(scenario_dir, elf_filename)
        self.dump_path = os.path.join(scenario_dir, dump_filename)
        self.profile_name = profile_name

        # 延迟初始化（run 时才创建）
        self.elf_parser: ELFParser = None
        self.dump_reader: DumpReader = None

    # ── 初始化 ──────────────────────────────────────────────
    def _init_parsers(self):
        self.elf_parser = ELFParser(self.elf_path)
        loader = ProfileLoader()
        profile = loader.load_profile(self.profile_name)
        regions = loader.get_memory_regions(profile)
        self.dump_reader = DumpReader(self.dump_path, regions)

    # ── 入口 ────────────────────────────────────────────────
    def run(self):
        """主入口：banner → 4 个 section → footer。"""
        if not os.path.exists(self.elf_path):
            print(f"✗ ELF 不存在: {self.elf_path}", file=sys.stderr)
            return 1
        if not os.path.exists(self.dump_path):
            print(f"✗ Dump 不存在: {self.dump_path}", file=sys.stderr)
            return 1

        self._init_parsers()
        self.banner()
        self.show_system_status()
        self.show_assert_infos()
        self.show_test_points()
        self.show_trace_buffer()
        self.footer()
        return 0

    # ── Banner ──────────────────────────────────────────────
    def banner(self):
        print("=" * 78)
        print(f"   {self.BANNER_TITLE}")
        print("=" * 78)
        for line in self.BANNER_LINES:
            print(line)
        print("=" * 78)

    def footer(self):
        print("\n" + "=" * 78)
        for line in self.FOOTER_LINES:
            print(line)
        print("=" * 78)

    # ── Section 1: 系统状态 ────────────────────────────────
    def show_system_status(self):
        print("\n" + "─" * 78)
        print("【1】系统状态（标量变量自动恢复）")
        print("─" * 78)
        ticks = self.elf_parser.parse_struct_auto('g_system_ticks', self.dump_reader)
        err = self.elf_parser.parse_struct_auto('g_error_count', self.dump_reader)
        st = self.elf_parser.parse_struct_auto('g_system_status', self.dump_reader)
        active = self.elf_parser.parse_struct_auto('g_active_assert_idx', self.dump_reader)
        twi = self.elf_parser.parse_struct_auto('g_trace_write_idx', self.dump_reader)
        spu = self.elf_parser.parse_struct_auto('g_string_pool_used', self.dump_reader)
        status_map = {0x01: 'RUNNING', 0x02: 'SUSPENDED', 0xFF: 'CRASHED', 0x00: 'IDLE'}

        print(f"  g_system_ticks     = {ticks}  "
              f"(运行时间: {ticks / 1000000:.3f} s)")
        print(f"  g_error_count      = {err}")
        print(f"  g_system_status    = 0x{st:02x}  ({status_map.get(st, 'UNKNOWN')})")
        print(f"  g_active_assert_idx= {active}")
        print(f"  g_trace_write_idx  = {twi}")
        print(f"  g_string_pool_used = {spu} 字节")

    # ── Section 2: assert_info 数组 ────────────────────────
    def show_assert_infos(self):
        print("\n" + "─" * 78)
        print("【2】g_assert_infos[4] — assert_info_t 数组")
        print("─" * 78)
        arr = self.elf_parser.parse_struct_auto('g_assert_infos', self.dump_reader)
        active = self.elf_parser.parse_struct_auto('g_active_assert_idx', self.dump_reader)
        print(f"  共 {len(arr)} 个 assert_info 槽位")
        for i, ai in enumerate(arr):
            n = ai['count']
            m = ai['max_count']
            marker = " ← active" if i == active else ""
            print(f"\n  [{i}] count={n}/{m}{marker}")
            for j in range(n):
                r = ai['records'][j]
                print(f"      record[{j}]: "
                      f"file={r['file_name']!r:<15} "
                      f"line={r['line_number']:<5} "
                      f"func={r['function_name']!r:<15} "
                      f"ts={r['timestamp']}")
                print(f"                 "
                      f"cond={r['assert_condition']!r}  "
                      f"task={r['task_id']}  "
                      f"err=0x{r['error_code']:08x}")

    # ── Section 3: test_point 数组 ─────────────────────────
    def show_test_points(self):
        print("\n" + "─" * 78)
        print("【3】g_test_points[8] — 测试点统计")
        print("─" * 78)
        tps = self.elf_parser.parse_struct_auto('g_test_points', self.dump_reader)
        print(f"  {'ID':<3} {'名称':<13} {'次数':>8} {'首测时间':>10} {'末测时间':>10} "
              f"{'最短(us)':>9} {'最长(us)':>9} {'平均(us)':>9}")
        print(f"  {'─'*3} {'─'*13} {'─'*8} {'─'*10} {'─'*10} {'─'*9} {'─'*9} {'─'*9}")
        for tp in tps:
            if tp['id'] == 0:
                continue
            print(f"  {tp['id']:<3} {tp['name']!r:<13} {tp['count']:>8} "
                  f"{tp['timestamp_first']:>10} {tp['timestamp_last']:>10} "
                  f"{tp['min_duration']:>9} {tp['max_duration']:>9} {tp['avg_duration']:>9}")

    # ── Section 4: trace buffer ────────────────────────────
    def show_trace_buffer(self):
        print("\n" + "─" * 78)
        twi = self.elf_parser.parse_struct_auto('g_trace_write_idx', self.dump_reader)
        print(f"【4】g_trace_buffer[32] — 环形 trace 缓冲区（写指针={twi}）")
        print("─" * 78)
        trs = self.elf_parser.parse_struct_auto('g_trace_buffer', self.dump_reader)
        ev_map = {0: 'ENTER', 1: 'EXIT', 2: 'ERROR'}
        valid = [t for t in trs if t['timestamp'] != 0]
        print(f"  有效记录: {len(valid)} 条 (总容量 {len(trs)} 条)")
        print(f"  {'序号':<4} {'时间戳':>10} {'测点':>5} {'任务':>5} {'事件':>7} {'数据':>6}")
        print(f"  {'─'*4} {'─'*10} {'─'*5} {'─'*5} {'─'*7} {'─'*6}")
        for i, tr in enumerate(trs):
            if tr['timestamp'] == 0:
                continue
            marker = " ← 写指针位置" if i == twi else ""
            print(f"  [{i:<2}] {tr['timestamp']:>10} {tr['point_id']:>5} "
                  f"{tr['task_id']:>5} {ev_map.get(tr['event_type'], str(tr['event_type'])):>7} "
                  f"{tr['data']:>6}{marker}")


def show_parsed_from_scenario(
    scenario_dir: str,
    profile_name: str,
    elf_filename: str,
    dump_filename: str,
):
    class ShowParsed(ShowParsedBase):
        BANNER_TITLE = f'QEMU {profile_name} — Crash Dump 自动恢复演示'
        BANNER_LINES = [
            f'  ELF  : {elf_filename}',
            f'  Dump : {dump_filename}',
            f'  原理 : 通过 DWARF 自动推导结构体布局，从 raw memory dump 恢复结构化数据',
        ]
        FOOTER_LINES = ['★ 解析完成']

    show = ShowParsed(
        scenario_dir=scenario_dir,
        elf_filename=elf_filename,
        dump_filename=dump_filename,
        profile_name=profile_name,
    )
    return show.run()
