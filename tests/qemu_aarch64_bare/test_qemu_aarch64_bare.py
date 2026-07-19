import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader


class TestQEMUAArch64FirmwareAutoParse(unittest.TestCase):
    """QEMU AArch64 (Cortex-A53) real-run firmware tests.

    Differences from qemu_m4_bare / qemu_r52_bare:
    - CPU is Cortex-A53 (ARMv8-A), 64-bit
    - QEMU machine 'virt', not mps2-an386 / mps3-an536
    - All-RAM layout (code + data both in RAM at 0x40000000)
    - AArch64 boot: Linux-style -kernel loads ELF and jumps to entry
    - Pointers are 8 bytes; DWARF DW_TAG_pointer_type byte_size == 8
    - Validates 64-bit pointer parsing path in core/elf_parser.py
    """

    ELF_PATH = os.path.join(os.path.dirname(__file__), 'firmware', 'output', 'img', 'test_firmware_aarch64.elf')
    DUMP_PATH = os.path.join(os.path.dirname(__file__), 'firmware', 'output', 'img', 'test_dump_aarch64.bin')
    RAM_START = 0x40000000
    RAM_END = 0x40004000  # 16KB dump

    def setUp(self):
        if not os.path.exists(self.ELF_PATH) or not os.path.exists(self.DUMP_PATH):
            self.skipTest("AArch64 firmware ELF/dump files not found")

        self.elf_parser = ELFParser(self.ELF_PATH)
        profile_loader = ProfileLoader()
        profile = profile_loader.load_profile('qemu/aarch64_bare')
        regions = profile_loader.get_memory_regions(profile)
        self.dump_reader = DumpReader(self.DUMP_PATH, regions)

    def test_aarch64_elf_exists(self):
        """AArch64 ELF and dump both exist and are non-empty."""
        self.assertGreater(os.path.getsize(self.ELF_PATH), 1000)
        self.assertGreater(os.path.getsize(self.DUMP_PATH), 1000)

    def test_aarch64_elf_header(self):
        """AArch64 ELF: class 64, machine 'AArch64', entry in RAM, has DWARF."""
        header = self.elf_parser.get_elf_header()
        self.assertEqual(header['class'], 64)
        self.assertEqual(header['machine'], 'AArch64')
        self.assertGreaterEqual(header['entry'], self.RAM_START,
                               f"entry {header['entry']:#x} should be in RAM")
        self.assertLess(header['entry'], self.RAM_END,
                        f"entry {header['entry']:#x} should be in RAM")
        self.assertIsNotNone(self.elf_parser.dwarfinfo)

    def test_aarch64_bss_variables_in_ram(self):
        """All g_* globals have addresses in RAM (0x40000000-0x40004000)."""
        for name in ('g_assert_infos', 'g_test_points', 'g_trace_buffer',
                     'g_trace_write_idx', 'g_system_ticks', 'g_error_count',
                     'g_system_status', 'g_active_assert_idx',
                     'g_string_pool', 'g_string_pool_used'):
            sym = self.elf_parser.get_symbol_by_name(name)
            self.assertIsNotNone(sym, f"{name} should exist")
            self.assertGreaterEqual(sym['address'], self.RAM_START,
                                   f"{name} should be in RAM")
            self.assertLess(sym['address'], self.RAM_END,
                           f"{name} should be in RAM")

    def test_aarch64_scalar_values(self):
        """Scalars after real AArch64 run match simulate_runtime()."""
        self.assertEqual(self.elf_parser.parse_struct_auto('g_system_ticks', self.dump_reader), 5234567)
        self.assertEqual(self.elf_parser.parse_struct_auto('g_error_count', self.dump_reader), 9)
        self.assertEqual(self.elf_parser.parse_struct_auto('g_system_status', self.dump_reader), 0xFF)
        self.assertEqual(self.elf_parser.parse_struct_auto('g_active_assert_idx', self.dump_reader), 2)
        self.assertEqual(self.elf_parser.parse_struct_auto('g_trace_write_idx', self.dump_reader), 20)
        self.assertEqual(self.elf_parser.parse_struct_auto('g_string_pool_used', self.dump_reader), 378)

    def test_aarch64_assert_info_array_expansion(self):
        """g_assert_infos is assert_info_t[4], all 4 slots expanded."""
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

    def test_aarch64_assert_record_details(self):
        """All assert_record_t fields correct in AArch64 dump (with char* deref)."""
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

    def test_aarch64_test_point_array_expansion(self):
        """g_test_points is test_point_t[8], all 8 expanded."""
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

    def test_aarch64_trace_buffer_expansion(self):
        """g_trace_buffer is trace_record_t[32], first 20 valid, last 12 zero."""
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

    def test_aarch64_char_pointer_deref(self):
        """All char* fields in AArch64 dump auto-deref to Python str."""
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

    def test_aarch64_pointer_size_is_8(self):
        """Validate 64-bit pointer fix: assert_record_t.file_name type has byte_size=8."""
        struct_type = self.elf_parser.get_struct_type('assert_record_t')
        self.assertIsNotNone(struct_type, "assert_record_t must be in DWARF")
        self.assertIn('members', struct_type)

        file_name_member = None
        for m in struct_type['members']:
            if m.get('name') == 'file_name':
                file_name_member = m
                break
        self.assertIsNotNone(file_name_member, "file_name member must exist")

        t = file_name_member.get('type', {})
        self.assertEqual(t.get('kind'), 'pointer',
                         f"file_name should be pointer, got {t.get('kind')}")
        self.assertEqual(t.get('byte_size'), 8,
                         f"AArch64 pointer byte_size must be 8, got {t.get('byte_size')}")

        arr = self.elf_parser.parse_struct_auto('g_assert_infos', self.dump_reader)
        r = arr[0]['records'][0]
        self.assertIsInstance(r['file_name'], str)
        self.assertEqual(r['file_name'], 'main.c')

    def test_aarch64_auto_parse_matches_manual_read(self):
        """parse_struct_auto matches manual read_uint64 (64-bit) on AArch64."""
        ticks_manual = self.dump_reader.read_uint32(
            self.elf_parser.get_symbol_by_name('g_system_ticks')['address'])
        ticks_auto = self.elf_parser.parse_struct_auto('g_system_ticks', self.dump_reader)
        self.assertEqual(ticks_manual, ticks_auto)

        arr = self.elf_parser.parse_struct_auto('g_assert_infos', self.dump_reader)
        ai0_addr = self.elf_parser.get_symbol_by_name('g_assert_infos')['address']
        file_name_ptr = self.dump_reader.read_uint64(ai0_addr + 8)
        self.assertNotEqual(file_name_ptr, 0, "file_name pointer should be non-null")
        manual_str = self.dump_reader.read_string(file_name_ptr, 16)
        self.assertEqual(manual_str, arr[0]['records'][0]['file_name'])


if __name__ == '__main__':
    unittest.main()