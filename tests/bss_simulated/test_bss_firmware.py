import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader


class TestBSSFirmwareAutoParse(unittest.TestCase):
    """BSS 段固件测试：
    全局变量全部在 BSS 段（未初始化），运行时动态赋值，
    trigger_crash_assert() 后 dump RAM，
    验证 parse_struct_auto 能 100% 自动恢复所有结构体细节。
    """

    def setUp(self):
        self.elf_path = os.path.join(os.path.dirname(__file__), 'firmware', 'test_firmware_bss.elf')
        self.dump_path = os.path.join(os.path.dirname(__file__), 'firmware', 'test_dump_bss.bin')
        if not os.path.exists(self.elf_path) or not os.path.exists(self.dump_path):
            self.skipTest("BSS firmware ELF/dump files not found")

        self.elf_parser = ELFParser(self.elf_path)
        profile_loader = ProfileLoader()
        profile = profile_loader.load_profile('test/bss_simulated')
        regions = profile_loader.get_memory_regions(profile)
        self.dump_reader = DumpReader(self.dump_path, regions)

    # ── 1. BSS 段验证 ──────────────────────────────────────────
    def test_all_globals_in_bss_section(self):
        """所有 g_ 开头的变量都在 BSS 段（地址位于 .bss 范围内）。"""
        # 验证关键变量的地址顺序（与 nm 输出一致）
        g_assert = self.elf_parser.get_symbol_by_name('g_assert_infos')
        g_tp = self.elf_parser.get_symbol_by_name('g_test_points')
        g_trace = self.elf_parser.get_symbol_by_name('g_trace_buffer')
        g_sys = self.elf_parser.get_symbol_by_name('g_system_ticks')
        g_pool = self.elf_parser.get_symbol_by_name('g_string_pool')

        self.assertIsNotNone(g_assert)
        self.assertIsNotNone(g_tp)
        self.assertIsNotNone(g_trace)
        self.assertIsNotNone(g_sys)
        self.assertIsNotNone(g_pool)

        # BSS 段变量地址应该是递增的
        self.assertLess(g_assert['address'], g_tp['address'])
        self.assertLess(g_tp['address'], g_trace['address'])
        self.assertLess(g_trace['address'], g_sys['address'])
        self.assertLess(g_sys['address'], g_pool['address'])

        # g_assert_infos 大小: 4 * (8 + 8*36) = 4 * 296 = 1184
        self.assertEqual(g_assert['size'], 1184)

    # ── 2. 标量变量自动恢复 ───────────────────────────────────
    def test_scalar_variables_auto_parsed(self):
        """标量变量通过 parse_struct_auto 自动恢复。"""
        self.assertEqual(self.elf_parser.parse_struct_auto('g_system_ticks', self.dump_reader), 5234567)
        self.assertEqual(self.elf_parser.parse_struct_auto('g_error_count', self.dump_reader), 9)
        self.assertEqual(self.elf_parser.parse_struct_auto('g_system_status', self.dump_reader), 0xFF)
        self.assertEqual(self.elf_parser.parse_struct_auto('g_active_assert_idx', self.dump_reader), 2)
        self.assertEqual(self.elf_parser.parse_struct_auto('g_trace_write_idx', self.dump_reader), 20)

    # ── 3. assert_info_t[4] 数组自动展开 ─────────────────────
    def test_assert_info_array_auto_expansion(self):
        """g_assert_infos 是 assert_info_t[4]，自动展开 4 个元素，每个元素是结构体。"""
        arr = self.elf_parser.parse_struct_auto('g_assert_infos', self.dump_reader)
        self.assertIsNotNone(arr)
        self.assertIsInstance(arr, list)
        self.assertEqual(len(arr), 4)

        # 每个元素都是 assert_info_t 结构
        for ai in arr:
            self.assertIsInstance(ai, dict)
            self.assertIn('count', ai)
            self.assertIn('max_count', ai)
            self.assertIn('records', ai)
            self.assertEqual(ai['max_count'], 8)
            self.assertEqual(len(ai['records']), 8)

        # 各元素的 count 分别为 3, 2, 3, 1（与 simulate_runtime 一致）
        self.assertEqual(arr[0]['count'], 3)
        self.assertEqual(arr[1]['count'], 2)
        self.assertEqual(arr[2]['count'], 3)
        self.assertEqual(arr[3]['count'], 1)

    def test_assert_record_details_auto_parsed(self):
        """每条 assert_record_t 的所有字段（含 char* 自动解引用）都正确。"""
        arr = self.elf_parser.parse_struct_auto('g_assert_infos', self.dump_reader)

        # 第 0 组第 0 条
        r = arr[0]['records'][0]
        self.assertEqual(r['file_name'], 'main.c')
        self.assertEqual(r['line_number'], 128)
        self.assertEqual(r['function_name'], 'main')
        self.assertEqual(r['assert_condition'], '(ptr != NULL)')
        self.assertEqual(r['timestamp'], 1000100)
        self.assertEqual(r['task_id'], 1)
        self.assertEqual(r['error_code'], 0x00010001)
        # reserved[2] 数组
        self.assertEqual(r['reserved'], [0, 0])

        # 第 1 组第 1 条
        r = arr[1]['records'][1]
        self.assertEqual(r['file_name'], 'network.c')
        self.assertEqual(r['line_number'], 620)
        self.assertEqual(r['function_name'], 'net_recv')
        self.assertEqual(r['assert_condition'], '(size > 0)')
        self.assertEqual(r['timestamp'], 2000400)
        self.assertEqual(r['task_id'], 3)
        self.assertEqual(r['error_code'], 0x01020002)

        # 第 2 组第 2 条（active）
        r = arr[2]['records'][2]
        self.assertEqual(r['file_name'], 'storage.c')
        self.assertEqual(r['line_number'], 384)
        self.assertEqual(r['function_name'], 'flash_erase')
        self.assertEqual(r['assert_condition'], '(page < MAX)')
        self.assertEqual(r['timestamp'], 3000300)
        self.assertEqual(r['task_id'], 4)
        self.assertEqual(r['error_code'], 0x02030003)

        # 第 3 组第 0 条
        r = arr[3]['records'][0]
        self.assertEqual(r['file_name'], 'audio.c')
        self.assertEqual(r['line_number'], 512)
        self.assertEqual(r['function_name'], 'audio_mix')
        self.assertEqual(r['assert_condition'], '(ch < MAX_CH)')

        # 空记录应为 null/0
        r = arr[0]['records'][3]
        self.assertIsNone(r['file_name'])
        self.assertEqual(r['line_number'], 0)
        self.assertEqual(r['timestamp'], 0)

    # ── 4. test_point_t[8] 数组自动展开 ─────────────────────
    def test_test_point_array_auto_expansion(self):
        """g_test_points 是 test_point_t[8]，8 个元素全部自动展开。"""
        tps = self.elf_parser.parse_struct_auto('g_test_points', self.dump_reader)
        self.assertIsInstance(tps, list)
        self.assertEqual(len(tps), 8)

        expected = [
            (1, 'TaskIdle',    15000, 1000000, 5000000, 10,    500,   50),
            (2, 'TaskMain',     8500, 1000100, 5000200, 50,   2000,  300),
            (3, 'TaskNet',      3200, 1000200, 5000400, 100,  5000,  800),
            (4, 'TaskStorage',  1200, 1000500, 5000800, 200,  8000, 1500),
            (5, 'ISR_Timer',   25000, 1000000, 4999999,   1,    50,    5),
            (6, 'ISR_UART',    12500, 1000000, 4999000,   5,   100,   20),
            (7, 'TaskAudio',    6000, 2000000, 5000100, 500,  3000, 1200),
            (8, 'TaskDisplay',  4500, 2500000, 4800000, 800,  6000, 2000),
        ]
        for i, (id, name, count, ts_f, ts_l, mn, mx, avg) in enumerate(expected):
            tp = tps[i]
            self.assertEqual(tp['id'], id, f"test_point[{i}].id")
            self.assertEqual(tp['name'], name, f"test_point[{i}].name")
            self.assertEqual(tp['count'], count, f"test_point[{i}].count")
            self.assertEqual(tp['timestamp_first'], ts_f, f"test_point[{i}].timestamp_first")
            self.assertEqual(tp['timestamp_last'], ts_l, f"test_point[{i}].timestamp_last")
            self.assertEqual(tp['min_duration'], mn, f"test_point[{i}].min_duration")
            self.assertEqual(tp['max_duration'], mx, f"test_point[{i}].max_duration")
            self.assertEqual(tp['avg_duration'], avg, f"test_point[{i}].avg_duration")

    # ── 5. trace_record_t[32] 环形缓冲区 ────────────────────
    def test_trace_buffer_auto_expansion(self):
        """g_trace_buffer 是 trace_record_t[32]，环形缓冲区，写指针在 20。"""
        trs = self.elf_parser.parse_struct_auto('g_trace_buffer', self.dump_reader)
        self.assertIsInstance(trs, list)
        self.assertEqual(len(trs), 32)

        # 前 20 条有数据
        for i in range(20):
            tr = trs[i]
            self.assertEqual(tr['timestamp'], 1000000 + i * 500, f"trace[{i}].timestamp")
            self.assertEqual(tr['point_id'], (i % 8) + 1, f"trace[{i}].point_id")
            self.assertEqual(tr['task_id'], i % 6, f"trace[{i}].task_id")
            self.assertEqual(tr['event_type'], i % 2, f"trace[{i}].event_type")
            self.assertEqual(tr['data'], i * 10, f"trace[{i}].data")

        # 从 20 开始应该全 0（未写入）
        for i in range(20, 32):
            tr = trs[i]
            self.assertEqual(tr['timestamp'], 0)
            self.assertEqual(tr['point_id'], 0)
            self.assertEqual(tr['event_type'], 0)

    # ── 6. 字符串池自动解引用 ───────────────────────────────
    def test_char_pointer_auto_deref_strings(self):
        """所有 char* 字段都自动解引用为字符串，而不是显示指针值。"""
        arr = self.elf_parser.parse_struct_auto('g_assert_infos', self.dump_reader)
        tps = self.elf_parser.parse_struct_auto('g_test_points', self.dump_reader)

        # assert 中的字符串
        for i in range(arr[0]['count']):
            r = arr[0]['records'][i]
            self.assertIsInstance(r['file_name'], str)
            self.assertIsInstance(r['function_name'], str)
            self.assertIsInstance(r['assert_condition'], str)
            self.assertTrue(r['file_name'].endswith('.c'))
            self.assertGreater(len(r['function_name']), 0)
            self.assertTrue(r['assert_condition'].startswith('('))

        # test_point 中的 name 字符串
        for tp in tps:
            if tp['id'] != 0:
                self.assertIsInstance(tp['name'], str)
                self.assertGreater(len(tp['name']), 2)

    # ── 7. 交叉验证：与手动读取一致 ─────────────────────────
    def test_auto_parse_matches_manual_read(self):
        """自动解析结果与手动用符号地址读取的值一致。"""
        ticks_manual = self.dump_reader.read_uint32(
            self.elf_parser.get_symbol_by_name('g_system_ticks')['address'])
        ticks_auto = self.elf_parser.parse_struct_auto('g_system_ticks', self.dump_reader)
        self.assertEqual(ticks_manual, ticks_auto)

        # assert_infos[0].count 手动读取
        base = self.elf_parser.get_symbol_by_name('g_assert_infos')['address']
        count_manual = self.dump_reader.read_uint32(base)  # 第一个元素的 count 在偏移 0
        arr = self.elf_parser.parse_struct_auto('g_assert_infos', self.dump_reader)
        self.assertEqual(count_manual, arr[0]['count'])

    # ── 8. ELF 元信息验证（合并自 test_real_elf.py） ────────
    def test_elf_header(self):
        """验证 ARM 32 位 ELF 头信息。"""
        header = self.elf_parser.get_elf_header()
        self.assertEqual(header['class'], 32)
        self.assertEqual(header['machine'], 'ARM')
        # entry 应在 FLASH 范围内（0x08000000 - 0x08080000）， Thumb 标志位可忽略
        entry = header['entry'] & ~1
        self.assertGreaterEqual(entry, 0x08000000,
                               f"entry {header['entry']:#x} should be in FLASH")
        self.assertLess(entry, 0x08080000,
                       f"entry {header['entry']:#x} should be in FLASH")

    def test_code_symbols_in_flash(self):
        """代码符号（函数）位于 Flash 段。"""
        for func_name in ('main', 'firmware_init', 'simulate_runtime', 'trigger_crash_assert'):
            sym = self.elf_parser.get_symbol_by_name(func_name)
            self.assertIsNotNone(sym, f"{func_name} should exist")
            self.assertGreaterEqual(sym['address'], 0x08000000, f"{func_name} should be in FLASH")
            self.assertLess(sym['address'], 0x09000000, f"{func_name} should be in FLASH")


if __name__ == '__main__':
    unittest.main()
