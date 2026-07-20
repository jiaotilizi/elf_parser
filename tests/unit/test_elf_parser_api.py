"""ELFParser 公开 API 单元测试。

覆盖 ELFParser 类的所有公开方法：
  - get_elf_header / is_32bit / get_address_size
  - get_symbol_by_name / get_all_symbols / find_symbols_by_pattern / find_function_by_address
  - get_struct_type
  - parse_struct_auto
  - read_memory_from_elf / read_memory_from_dump / parse_struct_from_dump
  - print_build_info

依赖 bss_simulated 场景的 ELF（最小、稳定、符号齐全）。
ELF 不存在时跳过全部用例。
"""
import os
import sys
import unittest
import io
import contextlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader
from core.profile_loader import ProfileLoader


# 使用 bss_simulated 场景的 ELF（最小、稳定）
ELF_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                       'bss_simulated', 'firmware', 'test_firmware_bss.elf')
DUMP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        'bss_simulated', 'firmware', 'test_dump_bss.bin')


@unittest.skipUnless(os.path.exists(ELF_PATH),
                    "bss_simulated ELF not found, run tests/bss_simulated/firmware/build.sh")
class TestELFParserPublicAPI(unittest.TestCase):
    """ELFParser 公开 API 测试。"""

    @classmethod
    def setUpClass(cls):
        cls.parser = ELFParser(ELF_PATH)
        # 加载 dump data 用于 read_memory_from_dump / parse_struct_from_dump
        with open(DUMP_PATH, 'rb') as f:
            cls.dump_data = f.read()
        # 必须通过 ProfileLoader 加载 regions，否则 DumpReader 默认起始地址为 0
        loader = ProfileLoader()
        profile = loader.load_profile('profiles/bss_simulated.yaml')
        regions = loader.get_memory_regions(profile)
        cls.dump_reader = DumpReader(DUMP_PATH, regions)

    # ── 1. ELF 元信息：get_elf_header / is_32bit / get_address_size ──
    def test_get_elf_header(self):
        """get_elf_header 返回 class/machine/entry 等关键字段。"""
        header = self.parser.get_elf_header()
        self.assertIsInstance(header, dict)
        self.assertIn(header['class'], (32, 64))
        self.assertIn('machine', header)
        self.assertIn('entry', header)

    def test_is_32bit(self):
        """is_32bit 与 header['class'] 一致。"""
        header = self.parser.get_elf_header()
        self.assertEqual(self.parser.is_32bit(), header['class'] == 32)

    def test_get_address_size(self):
        """get_address_size 与 is_32bit 一致。"""
        expected = 4 if self.parser.is_32bit() else 8
        self.assertEqual(self.parser.get_address_size(), expected)

    def test_print_build_info(self):
        """print_build_info 不抛异常且打印非空内容。"""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.parser.print_build_info()
        output = buf.getvalue()
        self.assertIn('ELF Build Information', output)
        self.assertIn('DWARF', output)
        self.assertIn('Compiler', output)

    # ── 2. 符号查询：get_symbol_by_name / get_all_symbols / find_symbols_by_pattern ──
    def test_get_symbol_by_name_existing(self):
        """get_symbol_by_name 找到已知符号。"""
        sym = self.parser.get_symbol_by_name('g_system_ticks')
        self.assertIsNotNone(sym)
        self.assertEqual(sym['name'], 'g_system_ticks')
        self.assertIn('address', sym)
        self.assertIn('size', sym)

    def test_get_symbol_by_name_non_existing(self):
        """get_symbol_by_name 对不存在的符号返回 None。"""
        sym = self.parser.get_symbol_by_name('non_existent_symbol_xyz')
        self.assertIsNone(sym)

    def test_get_all_symbols(self):
        """get_all_symbols 返回非空列表。"""
        syms = self.parser.get_all_symbols()
        self.assertIsInstance(syms, list)
        self.assertGreater(len(syms), 0)
        # 每个元素都有 name/address/size 字段
        for s in syms:
            self.assertIn('name', s)
            self.assertIn('address', s)

    def test_find_symbols_by_pattern_prefix(self):
        """find_symbols_by_pattern 用 g_ 前缀能匹配多个符号。"""
        syms = self.parser.find_symbols_by_pattern('g_')
        self.assertIsInstance(syms, list)
        self.assertGreaterEqual(len(syms), 5, "Should find multiple g_ symbols")
        for s in syms:
            self.assertTrue(s['name'].startswith('g_'))

    def test_find_symbols_by_pattern_exact(self):
        """find_symbols_by_pattern 用完整名匹配单个符号。"""
        syms = self.parser.find_symbols_by_pattern('g_system_ticks')
        self.assertEqual(len(syms), 1)
        self.assertEqual(syms[0]['name'], 'g_system_ticks')

    def test_find_symbols_by_pattern_no_match(self):
        """find_symbols_by_pattern 对不存在的模式返回空列表。"""
        syms = self.parser.find_symbols_by_pattern('xyz_not_exist')
        self.assertEqual(syms, [])

    # ── 3. 函数查询：find_function_by_address ──
    def test_find_function_by_address_existing(self):
        """find_function_by_address 用 main 函数起始地址能找到 main。

        依赖 DWARF CU 信息（部分 ELF 链接后可能丢失 CU），无 CU 时跳过。
        """
        if not self.parser._cu_cache:
            self.skipTest("ELF has no DWARF CU cache, find_function_by_address needs CU info")
        # 先拿到 main 符号的地址
        main_sym = self.parser.get_symbol_by_name('main')
        if main_sym is None:
            self.skipTest("main symbol not found")
        # main + 4 应该仍在 main 函数内
        result = self.parser.find_function_by_address(main_sym['address'] + 4)
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'main')

    def test_find_function_by_address_invalid(self):
        """find_function_by_address 对无效地址返回 None。"""
        result = self.parser.find_function_by_address(0xDEADBEEF)
        self.assertIsNone(result)

    # ── 4. 类型查询：get_struct_type ──
    def test_get_struct_type_existing(self):
        """get_struct_type 找到已知结构体。"""
        # assert_info_t 是 bss_simulated 中定义的结构体
        st = self.parser.get_struct_type('assert_info_t')
        self.assertIsNotNone(st)
        self.assertIn(st.get('kind'), ('struct', 'typedef'))
        self.assertIn('members', st)

    def test_get_struct_type_non_existing(self):
        """get_struct_type 对不存在的类型返回 None。"""
        st = self.parser.get_struct_type('non_existent_type_xyz')
        self.assertIsNone(st)

    # ── 5. parse_struct_auto ──
    def test_parse_struct_auto_scalar(self):
        """parse_struct_auto 解析标量变量返回整数。"""
        val = self.parser.parse_struct_auto('g_system_ticks', self.dump_reader)
        self.assertIsInstance(val, int)
        self.assertEqual(val, 5234567)

    def test_parse_struct_auto_array(self):
        """parse_struct_auto 解析结构体数组返回 list。"""
        arr = self.parser.parse_struct_auto('g_assert_infos', self.dump_reader)
        self.assertIsInstance(arr, list)
        self.assertEqual(len(arr), 4)

    def test_parse_struct_auto_non_existing(self):
        """parse_struct_auto 对不存在的变量返回 None。"""
        val = self.parser.parse_struct_auto('non_existent_var', self.dump_reader)
        self.assertIsNone(val)

    # ── 6. read_memory_from_elf / read_memory_from_dump / parse_struct_from_dump ──
    def test_read_memory_from_elf_valid(self):
        """read_memory_from_elf 从 ELF 段读数据。"""
        # 从 .text 段（地址 0）读 16 字节
        data = self.parser.read_memory_from_elf(0, 16)
        if data is not None:
            self.assertEqual(len(data), 16)
        # 0 地址