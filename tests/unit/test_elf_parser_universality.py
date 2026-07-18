"""ELFParser 跨架构泛用性合成测试。

不依赖 QEMU 也不依赖外部工具链，通过构造合成 dump + 直接调用
`_read_typed_value` 验证：
  - 32 位指针返回 8 hex 宽的字符串
  - 64 位指针返回 16 hex 宽的字符串（验证 elf_parser.py L443-452 修复）
  - 64 位 char* 自动解引用为字符串
  - 0 值 char* 返回 None（而非 `<ptr 0x0...>`）
  - 异常 byte_size（如 2）走 fallback 路径不崩
  - _address_size 与 byte_size 一致性

这个测试是 Phase 1.1 修复（按指针 byte_size 选 4/8 字节读取）的回归保护：
如果有人误改回硬编码 read_uint32，64 位用例会立即失败。
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.elf_parser import ELFParser
from core.dump_reader import DumpReader


class TestELFParserUniversality(unittest.TestCase):
    """跨架构指针解析的合成测试，无需真实 ELF/DWARF。"""

    def setUp(self):
        # 跳过 __init__ 的 ELF 解析，直接造一个空壳实例
        self.parser = ELFParser.__new__(ELFParser)
        # 默认按 32 位假设（多数现存场景），64 位用例会显式覆盖
        self.parser._address_size = 4

        # 临时目录 + 临时 dump 文件
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_dump_reader(self, data: bytes, ram_base: int = 0x20000000) -> DumpReader:
        """把字节序列写成 dump 文件，返回绑定到 ram_base 的 DumpReader。

        自动填充到 512 字节，避免 read_string(max_length=256) 越界返回 None。
        """
        if len(data) < 512:
            data = data + b'\x00' * (512 - len(data))
        dump_path = os.path.join(self.temp_dir, 'synth_dump.bin')
        with open(dump_path, 'wb') as f:
            f.write(data)
        regions = [{'name': 'ram', 'start_addr': ram_base, 'size': len(data)}]
        return DumpReader(dump_path, regions)

    @staticmethod
    def _hex_part(ptr_str: str) -> str:
        """从 '<ptr 0xdeadbeef>' 提取 hex 部分 'deadbeef'。"""
        # '<ptr 0xXXXX>' → 'XXXX'
        return ptr_str.split('0x')[1].rstrip('>')

    # ── 1. 32 位指针：8 hex 宽 ─────────────────────────────────
    def test_32bit_pointer_returns_8_hex_width(self):
        """4 字节指针返回 `<ptr 0xdeadbeef>`，宽度为 8 hex。"""
        # 0xdeadbeef little-endian
        data = (0xdeadbeef).to_bytes(4, 'little')
        reader = self._make_dump_reader(data)

        type_info = {
            'kind': 'pointer',
            'byte_size': 4,
            'name': None,
            'ref_type': {'kind': 'base', 'name': 'long', 'byte_size': 4},
        }
        result = self.parser._read_typed_value(type_info, 0x20000000, reader)
        self.assertEqual(result, '<ptr 0xdeadbeef>')
        # 8 hex 字符（不含 0x 前缀和 > 后缀）
        self.assertEqual(len(self._hex_part(result)), 8)

    # ── 2. 64 位指针：16 hex 宽（核心修复验证）─────────────────
    def test_64bit_pointer_returns_16_hex_width(self):
        """8 字节指针返回 `<ptr 0x00000000feedface>`，宽度为 16 hex。

        这是 Phase 1.1 修复的关键回归测试：如果硬编码 read_uint32，
        会读到 0xfeedface（截断高 32 位），返回 `<ptr 0xfeedface>`（8 hex 宽），
        测试会立即失败。
        """
        # 0x00000000feedface little-endian = 8 字节
        data = (0x00000000feedface).to_bytes(8, 'little')
        reader = self._make_dump_reader(data)
        self.parser._address_size = 8  # 64 位架构

        type_info = {
            'kind': 'pointer',
            'byte_size': 8,
            'name': None,
            'ref_type': {'kind': 'base', 'name': 'long', 'byte_size': 8},
        }
        result = self.parser._read_typed_value(type_info, 0x20000000, reader)
        self.assertEqual(result, '<ptr 0x00000000feedface>')
        # 16 hex 字符（不含 0x 前缀和 > 后缀）
        self.assertEqual(len(self._hex_part(result)), 16)

    # ── 3. 64 位 char* 自动解引用为字符串 ────────────────────────
    def test_64bit_char_pointer_auto_derefs_string(self):
        """8 字节 char* 指向字符串地址，应自动解引用返回 Python str。"""
        # 8 字节指针指向偏移 8（即 0x20000008），后面跟 'hello\0'
        ptr_val = 0x20000008
        data = ptr_val.to_bytes(8, 'little') + b'hello\x00'
        reader = self._make_dump_reader(data)
        self.parser._address_size = 8

        # char* 类型：pointer → const → char
        type_info = {
            'kind': 'pointer',
            'byte_size': 8,
            'name': 'char*',
            'ref_type': {
                'kind': 'const',
                'name': 'const char',
                'ref_type': {'kind': 'base', 'name': 'char', 'byte_size': 1},
            },
        }
        result = self.parser._read_typed_value(type_info, 0x20000000, reader)
        self.assertIsInstance(result, str)
        self.assertEqual(result, 'hello')

    # ── 4. 0 值 char* 返回 None ────────────────────────────────
    def test_null_char_pointer_returns_none(self):
        """0 值 char* 返回 None，而非 `<ptr 0x0000000000000000>`。"""
        data = b'\x00' * 32
        reader = self._make_dump_reader(data)
        self.parser._address_size = 8

        type_info = {
            'kind': 'pointer',
            'byte_size': 8,
            'name': 'char*',
            'ref_type': {'kind': 'base', 'name': 'char', 'byte_size': 1},
        }
        result = self.parser._read_typed_value(type_info, 0x20000000, reader)
        self.assertIsNone(result)

    # ── 5. 非 char* 的 0 值指针仍返回 hex 字符串 ────────────────
    def test_null_non_char_pointer_returns_hex(self):
        """0 值的 long* 仍应返回 `<ptr 0x00000000>` 而非 None。"""
        data = b'\x00' * 32
        reader = self._make_dump_reader(data)

        type_info = {
            'kind': 'pointer',
            'byte_size': 4,
            'name': None,
            'ref_type': {'kind': 'base', 'name': 'long', 'byte_size': 4},
        }
        result = self.parser._read_typed_value(type_info, 0x20000000, reader)
        self.assertEqual(result, '<ptr 0x00000000>')

    # ── 6. 异常 byte_size 走 fallback 不崩 ────────────────────
    def test_unusual_byte_size_fallback_no_crash(self):
        """byte_size=2 走 fallback 路径，不应抛异常。"""
        data = b'\xab\xcd' + b'\x00' * 30
        reader = self._make_dump_reader(data)

        type_info = {
            'kind': 'pointer',
            'byte_size': 2,
            'name': None,
            'ref_type': {'kind': 'base', 'name': 'short', 'byte_size': 2},
        }
        # 不应抛异常
        result = self.parser._read_typed_value(type_info, 0x20000000, reader)
        # byte_size=2 走 else 分支，hex_width=8（非 8 字节都按 8 hex 宽格式化）
        self.assertEqual(result, '<ptr 0x0000cdab>')

    # ── 7. byte_size 缺失时回退到 _address_size ────────────────
    def test_missing_byte_size_uses_address_size(self):
        """type_info 无 byte_size 字段时，应使用 _address_size。"""
        # 8 字节 dump
        data = (0x12345678).to_bytes(4, 'little') + b'\x00' * 28
        reader = self._make_dump_reader(data)
        # _address_size=4，缺 byte_size 应按 4 字节读
        self.parser._address_size = 4

        type_info = {
            'kind': 'pointer',
            # 故意省略 byte_size
            'name': None,
            'ref_type': {'kind': 'base', 'name': 'long', 'byte_size': 4},
        }
        result = self.parser._read_typed_value(type_info, 0x20000000, reader)
        self.assertEqual(result, '<ptr 0x12345678>')

    # ── 8. DumpReader.read_pointer_by_size 一致性 ─────────────
    def test_dump_reader_pointer_by_size_helper(self):
        """DumpReader.read_pointer_by_size 与 _read_typed_value 行为一致。"""
        data = (0x00000000cafef00d).to_bytes(8, 'little') + b'\x00' * 24
        reader = self._make_dump_reader(data)

        # 8 字节读法
        v8 = reader.read_pointer_by_size(0x20000000, byte_size=8)
        self.assertEqual(v8, 0x00000000cafef00d)

        # 4 字节读法（只读低 32 位）
        v4 = reader.read_pointer_by_size(0x20000000, byte_size=4)
        self.assertEqual(v4, 0xcafef00d)


if __name__ == '__main__':
    unittest.main()
