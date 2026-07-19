import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader


class TestQEMUArmMps3An536FirmwareAutoParse(unittest.TestCase):
    """QEMU Cortex-R52 真实运行固件测试。

    与 qemu_m4_bare 的区别：
    - CPU 是 Cortex-R52 (ARMv7-R)，非 Cortex-M4 (ARMv7-E)
    - QEMU 机器 mps3-an536，非 mps2-an386
    - 全 RAM 布局（代码+数据都在 SRAM），无 Flash/RAM 分离
    - 启动文件用 ARM 模式无向量表，非 M-profile 的向量表启动
    - 验证解析器在 R-profile ARMv7-R 上工作一致

    共享固件源码 ../firmware/_common/test_firmware_bss.c 与 M4 相同，
    所以数据期望值完全一致。
    """

    ELF_PATH = os.path.join(os.path.dirname(__file__), 'firmware', 'output', 'img', 'test_firmware_r52.elf')
    DUMP_PATH = os.path.join(os.path.dirname(__file__), 'firmware', 'output', 'img', 'test_dump_r52.bin')
    RAM_START = 0x20000000
    RAM_END = 0x20004000  # 16KB dump

    def setUp(self):
        if not os.path.exists(self.ELF_PATH) or not os.path.exists(self.DUMP_PATH):
            self.skipTest("R52 firmware ELF/dump files not found")

        self.elf_parser = ELFParser(self.ELF_PATH)
        profile_loader = ProfileLoader()
        profile = profile_loader.load_profile('qemu/arm_mps3_an536_bare')
        regions = profile_loader.get_memory_regions(profile)
        self.dump_reader = DumpReader(self.DUMP_PATH, regions)

    def test_r52_elf_exists(self):
        """R52 版 ELF 和 dump 文件都存在且非空。"""
        self.assertGreater(os.path.getsize(self.ELF_PATH), 1000)
        self.assertGreater(os.path.getsize(self.DUMP_PATH), 1000)

    def test_r52_elf_header(self):
        """R52 版 ELF：ARM 32 位，entry 在 RAM 段（0x20000000 起），有 DWARF。"""
        header = self.elf_parser.get_elf_header()
        self.assertEqual(header['class'], 32)
        self.assertEqual(header['machine'], 'ARM')
        entry_actual = header['entry'] & ~1
        self.assertGreaterEqual(entry_actual, self.RAM_START,
                                f"entry {header['entry']:#x} 应在 RAM 段")
        self.assertLess(entry_actual, self.RAM_END,
                        f"entry {header['entry']:#x} 应在 RAM 段")
        self.assertIsNotNone(self.elf_parser.dwarfinfo)

    def test_r52_bss_variables_in_ram(self):
        """所有 g_* 全局变量地址都在 RAM (0x20000000-0x20004000) 范围内。"""
        for name in ('g_assert_infos', 'g_test_points', 'g_trace_buffer',
                     'g_trace_write_idx', 'g_system_ticks', 'g_error_count',
                     'g_system_status', 'g_active_assert_idx',
                     'g_string_pool', 'g_string_pool_used'):
            sym = self.elf_parser.get_symbol_by_name(name)
            self.assertIsNotNone(sym, f"{name} 应存在")
            self.assertGreaterEqual(sym['address'], self.RAM_START,
                                    f"{name} 应在 RAM 段")
            self.assertLess(sym['address'], self.RAM_END,
                            f"{name} 应在 RAM 段")

    def test_r52_scalar_values(self):
        """R52 真实运行后的标量值与 simulate_runtime() 一致。"""
        self.assertEqual(self.elf_parser.parse_struct_auto('g_system_ticks', self.dump_reader), 5234567)
        self.assertEqual(self.elf_parser.parse_struct_auto('g_error_count', self.dump_reader), 9)
        self.assertEqual(self.elf_parser.parse_struct_auto('g_system_status', self.dump_reader), 0xFF)
        self.assertEqual(self.elf_parser.parse_struct_auto('g_active_assert_idx', self.dump_reader), 2)
        self.assertEqual(self.elf_parser.parse_struct_auto('g_trace_write_idx', self.dump_reader), 20)
        self.assertEqual(self.elf_parser.parse_struct_auto('g_string_pool_used', self.dump_reader), 378)

    def test_r52_assert_info_array_expansion(self):
        """g_assert_infos 是 assert_info_t[4]，R52 dump 中 4 个槽位全展开。"""
        arr = self.elf_parser.parse_struct_auto('g_assert_infos', self.dump_reader)
        self.assertIsNotNone(arr)
        self.assertIsInstance(arr, list)
        self.assertEqual(len(arr), 4)

        for ai in arr:
            self.assertIsInstance(ai, dict)
            self.assertEqual(ai['max_count'], 8)
            self.assertEqual(len(ai['records']), 8)

        self.assertEqual(arr[0]['count'], 3)
        self.assertEqual(arr[1]['count'], 2)
        self.assertEqual(arr[2]['count'], 3)
        self.assertEqual(arr[3]['count'], 1)

    def test_r52_assert_record_details(self):
        """R52 dump 中每条 assert_record_t 的所有字段都正确（含 char* 解引用）。"""
        arr = self.elf_parser.parse_struct_auto('g_assert_infos', self.dump_reader)

        r = arr[0]['records'][0]
        self.assertEqual(r['file_name'], 'main.c')
        self.assertEqual(r['line_number'], 128)
        self.assertEqual(r['function_name'], 'main')
        self.assertEqual(r['assert_condition'], '(ptr != NULL)')
        self.assertEqual(r['timestamp'], 1000100)
        self.assertEqual(r['task_id'], 1)
        self.assertEqual(r['error_code'], 0x00010001)

        r = arr[2]['records'][2]
        self.assertEqual(r['file_name'], 'storage.c')
        self.assertEqual(r['function_name'], 'flash_erase')
        self.assertEqual(r['error_code'], 0x02030003)

        r = arr[3]['records'][0]
        self.assertEqual(r['file_name'], 'audio.c')

        r = arr[3]['records'][1]
        self.assertIsNone(r['file_name'])
        self.assertEqual(r['timestamp'], 0)

    def test_r52_test_point_array_expansion(self):
        """g_test_points 是 test_point_t[8]，R52 dump 中 8 个测点全展开。"""
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

    def test_r52_trace_buffer_expansion(self):
        """g_trace_buffer 是 trace_record_t[32]，前 20 条有数据，后 12 条为 0。"""
        trs = self.elf_parser.parse_struct_auto('g_trace_buffer', self.dump_reader)
        self.assertIsInstance(trs, list)
        self.assertEqual(len(trs), 32)

        for i in range(20):
            tr = trs[i]
            self.assertEqual(tr['timestamp'], 1000000 + i * 500, f"trace[{i}].timestamp")
            self.assertEqual(tr['point_id'], (i % 8) + 1, f"trace[{i}].point_id")

        for i in range(20, 32):
            tr = trs[i]
            self.assertEqual(tr['timestamp'], 0)

    def test_r52_char_pointer_deref(self):
        """R52 dump 中所有 char* 字段都自动解引用为 Python str。"""
        arr = self.elf_parser.parse_struct_auto('g_assert_infos', self.dump_reader)
        tps = self.elf_parser.parse_struct_auto('g_test_points', self.dump_reader)

        for i in range(arr[0]['count']):
            r = arr[0]['records'][i]
            self.assertIsInstance(r['file_name'], str)
            self.assertIsInstance(r['function_name'], str)
            self.assertTrue(r['file_name'].endswith('.c'))

        for tp in tps:
            if tp['id'] != 0:
                self.assertIsInstance(tp['name'], str)
                self.assertGreater(len(tp['name']), 2)

    def test_r52_auto_parse_matches_manual_read(self):
        """parse_struct_auto 与手动 read_uint32 读到的值一致。"""
        ticks_manual = self.dump_reader.read_uint32(
            self.elf_parser.get_symbol_by_name('g_system_ticks')['address'])
        ticks_auto = self.elf_parser.parse_struct_auto('g_system_ticks', self.dump_reader)
        self.assertEqual(ticks_manual, ticks_auto)

        base = self.elf_parser.get_symbol_by_name('g_assert_infos')['address']
        count_manual = self.dump_reader.read_uint32(base)
        arr = self.elf_parser.parse_struct_auto('g_assert_infos', self.dump_reader)
        self.assertEqual(count_manual, arr[0]['count'])


if __name__ == '__main__':
    unittest.main()